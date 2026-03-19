"""
Email Ingestion - IMAP Poller

Polls an IMAP inbox on a configurable interval and creates Tasks, Ideas,
or Notes based on subject line prefixes:
  - "task:" or "t:" -> Task
  - "idea:" or "i:" -> Idea
  - "note:" or "n:" -> Note
  - (no prefix)     -> Task (default)

Tracks processed emails by Message-ID to avoid duplicates.
Logs all activity to EventLog with source="email".
"""

import asyncio
import email
import imaplib
import logging
import re
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parseaddr

from app.config import settings
from app.db.models import Task, Idea, Note, EventLog
from app.db.session import async_session

logger = logging.getLogger(__name__)

SOURCE = "email"

# In-memory set of processed Message-IDs (survives across polls within a single process)
_processed_message_ids: set[str] = set()

# Prefix patterns: order matters — check longer prefixes first
_PREFIX_PATTERNS = [
    (re.compile(r"^task:\s*", re.IGNORECASE), "task"),
    (re.compile(r"^t:\s*", re.IGNORECASE), "task"),
    (re.compile(r"^idea:\s*", re.IGNORECASE), "idea"),
    (re.compile(r"^i:\s*", re.IGNORECASE), "idea"),
    (re.compile(r"^note:\s*", re.IGNORECASE), "note"),
    (re.compile(r"^n:\s*", re.IGNORECASE), "note"),
]


def parse_subject_prefix(subject: str) -> tuple[str, str]:
    """Parse subject line and return (entity_type, cleaned_subject).

    Returns:
        Tuple of (entity_type, subject_without_prefix).
        entity_type is one of: "task", "idea", "note".
    """
    subject = subject.strip()
    for pattern, entity_type in _PREFIX_PATTERNS:
        match = pattern.match(subject)
        if match:
            return entity_type, subject[match.end():].strip()
    # Default to task
    return "task", subject


def _decode_subject(raw_subject: str | None) -> str:
    """Decode a potentially MIME-encoded subject header."""
    if not raw_subject:
        return "(no subject)"
    parts = decode_header(raw_subject)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def _get_body(msg: email.message.Message) -> str:
    """Extract plain-text body from an email message."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        # Fallback: try HTML if no plain text found
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return ""


async def _create_entity(entity_type: str, title: str, body: str, sender: str) -> dict:
    """Create the appropriate entity in the database.

    Returns dict with entity info: {"entity_type", "entity_id", "title"}.
    """
    async with async_session() as db:
        if entity_type == "task":
            obj = Task(text=title, source=SOURCE)
            db.add(obj)
            await db.flush()
            entity_id = str(obj.id)

            event = EventLog(
                event_type="task.created",
                entity_type="task",
                entity_id=obj.id,
                source=SOURCE,
                data={"text": title, "sender": sender},
            )
            db.add(event)

        elif entity_type == "idea":
            obj = Idea(text=title, source=SOURCE)
            db.add(obj)
            await db.flush()
            entity_id = str(obj.id)

            event = EventLog(
                event_type="idea.created",
                entity_type="idea",
                entity_id=obj.id,
                source=SOURCE,
                data={"text": title, "sender": sender},
            )
            db.add(event)

        elif entity_type == "note":
            obj = Note(title=title, content=body, source=SOURCE)
            db.add(obj)
            await db.flush()
            entity_id = str(obj.id)

            event = EventLog(
                event_type="note.created",
                entity_type="note",
                entity_id=obj.id,
                source=SOURCE,
                data={"title": title, "sender": sender},
            )
            db.add(event)

        else:
            raise ValueError(f"Unknown entity type: {entity_type}")

        await db.commit()

    return {"entity_type": entity_type, "entity_id": entity_id, "title": title}


def _fetch_emails() -> list[email.message.Message]:
    """Connect to IMAP and fetch unseen messages. Runs in a thread."""
    host = settings.email_imap_host
    user = settings.email_imap_user
    password = settings.email_imap_password
    folder = settings.email_imap_folder

    messages = []
    try:
        mail = imaplib.IMAP4_SSL(host)
        mail.login(user, password)
        mail.select(folder)

        status, data = mail.search(None, "UNSEEN")
        if status != "OK" or not data[0]:
            mail.logout()
            return messages

        msg_nums = data[0].split()
        for num in msg_nums:
            status, msg_data = mail.fetch(num, "(RFC822)")
            if status == "OK" and msg_data[0] is not None:
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                messages.append(msg)
                # Mark as seen
                mail.store(num, "+FLAGS", "\\Seen")

        mail.logout()
    except Exception as e:
        logger.error(f"IMAP fetch error: {e}", exc_info=True)

    return messages


async def poll_inbox_once():
    """Run a single poll cycle: fetch unseen emails and create entities."""
    loop = asyncio.get_event_loop()
    messages = await loop.run_in_executor(None, _fetch_emails)

    if not messages:
        return

    logger.info(f"Email poller: fetched {len(messages)} unseen message(s)")

    for msg in messages:
        message_id = msg.get("Message-ID", "")
        if message_id in _processed_message_ids:
            logger.debug(f"Skipping already-processed Message-ID: {message_id}")
            continue

        subject = _decode_subject(msg.get("Subject"))
        body = _get_body(msg)
        sender = parseaddr(msg.get("From", ""))[1]

        entity_type, cleaned_subject = parse_subject_prefix(subject)

        try:
            result = await _create_entity(entity_type, cleaned_subject, body, sender)
            _processed_message_ids.add(message_id)
            logger.info(
                f"Email ingested: {result['entity_type']} '{result['title']}' "
                f"(id={result['entity_id']}) from {sender}"
            )
        except Exception as e:
            logger.error(f"Failed to create entity from email '{subject}': {e}", exc_info=True)


async def start_email_poller():
    """Background task: poll IMAP inbox on a configurable interval."""
    if not settings.email_imap_host or not settings.email_imap_user:
        logger.info("Email IMAP poller not configured, skipping")
        return

    interval = settings.email_poll_interval_seconds
    logger.info(
        f"Email poller started: {settings.email_imap_user}@{settings.email_imap_host} "
        f"folder={settings.email_imap_folder} interval={interval}s"
    )

    while True:
        try:
            await poll_inbox_once()
        except Exception as e:
            logger.error(f"Email poller cycle error: {e}", exc_info=True)
        await asyncio.sleep(interval)
