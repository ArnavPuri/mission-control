"""
Publishing content drafts to X and LinkedIn.

X: POST /2/tweets with OAuth 1.0a user context (X_API_KEY, X_API_SECRET,
X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET). A draft longer than one post goes
out as a thread.

LinkedIn: POST /rest/posts with a member access token (LINKEDIN_ACCESS_TOKEN,
scope w_member_social) as LINKEDIN_AUTHOR_URN. LinkedIn access tokens expire
after 60 days; a 401 means it's time for a new one.

Other channels (Instagram, YouTube, blog) need media or a site, so drafts for
them are posted by hand and marked as posted.
"""

import base64
import hashlib
import hmac
import logging
import re
import secrets
import time
from urllib.parse import quote

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

X_API = "https://api.x.com/2"
LINKEDIN_API = "https://api.linkedin.com/rest"
X_MAX_CHARS = 280
LINKEDIN_MAX_CHARS = 3000

# Tests swap in an httpx.MockTransport
_transport: httpx.AsyncBaseTransport | None = None


class PublishError(Exception):
    pass


def configured_channels() -> dict[str, bool]:
    return {
        "x": all([settings.x_api_key, settings.x_api_secret, settings.x_access_token, settings.x_access_token_secret]),
        "linkedin": bool(settings.linkedin_access_token and settings.linkedin_author_urn),
    }


def can_publish(channel: str) -> bool:
    return configured_channels().get(channel, False)


def setup_hint(channel: str) -> str:
    if channel == "x":
        return "Set X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN and X_ACCESS_TOKEN_SECRET to publish to X."
    if channel == "linkedin":
        return "Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN to publish to LinkedIn."
    return f"Publishing to {channel} isn't supported. Post it yourself, then mark it as posted."


async def publish(channel: str, text: str) -> str:
    """Publish text to a channel. Returns the post's URL."""
    text = text.strip()
    if not text:
        raise PublishError("The draft is empty")
    if not can_publish(channel):
        raise PublishError(setup_hint(channel))
    if channel == "x":
        return await _publish_x(text)
    return await _publish_linkedin(text)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=20, transport=_transport)


# --- X -----------------------------------------------------------------------

def _pct(value) -> str:
    # RFC 3986 percent-encoding, as OAuth 1.0a requires
    return quote(str(value), safe="-._~")


def oauth1_header(method: str, url: str, params: dict | None = None,
                  nonce: str | None = None, timestamp: int | None = None) -> str:
    """Authorization header for an OAuth 1.0a (HMAC-SHA1) signed request.

    params are query/form parameters; a JSON body is not part of the signature.
    """
    oauth = {
        "oauth_consumer_key": settings.x_api_key,
        "oauth_nonce": nonce or secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(timestamp or int(time.time())),
        "oauth_token": settings.x_access_token,
        "oauth_version": "1.0",
    }
    pairs = sorted((_pct(k), _pct(v)) for k, v in {**(params or {}), **oauth}.items())
    param_string = "&".join(f"{k}={v}" for k, v in pairs)
    base = "&".join([method.upper(), _pct(url), _pct(param_string)])
    key = f"{_pct(settings.x_api_secret)}&{_pct(settings.x_access_token_secret)}"
    signature = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    oauth["oauth_signature"] = signature
    return "OAuth " + ", ".join(f'{_pct(k)}="{_pct(v)}"' for k, v in sorted(oauth.items()))


def split_thread(text: str, limit: int = X_MAX_CHARS) -> list[str]:
    """Split text into posts of at most limit characters: by paragraph, then
    sentence, then word. (X counts links as 23 characters; this counts them as
    written, so it errs on the safe side.)"""
    if len(text) <= limit:
        return [text]

    # (text, starts a new paragraph)
    pieces: list[tuple[str, bool]] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        first = True
        for sentence in re.split(r"(?<=[.!?])\s+", para) if len(para) > limit else [para]:
            while len(sentence) > limit:
                cut = sentence.rfind(" ", 0, limit)
                cut = cut if cut > 0 else limit
                pieces.append((sentence[:cut].strip(), first))
                sentence, first = sentence[cut:].strip(), False
            if sentence:
                pieces.append((sentence, first))
                first = False

    posts: list[str] = []
    for piece, new_paragraph in pieces:
        sep = "\n\n" if new_paragraph else " "
        if posts and len(posts[-1]) + len(sep) + len(piece) <= limit:
            posts[-1] += sep + piece
        else:
            posts.append(piece)
    return posts


def _x_error(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        detail = data.get("detail") or data.get("title") or (data.get("errors") or [{}])[0].get("message")
    except ValueError:
        detail = resp.text[:200]
    if resp.status_code == 401:
        return "X rejected the API keys or access token (check they have read and write access)"
    if resp.status_code == 429:
        return "X rate limit reached; try again later"
    return f"X returned {resp.status_code}: {detail}"


async def _publish_x(text: str) -> str:
    url = f"{X_API}/tweets"
    first_id = previous_id = None
    posts = split_thread(text)
    async with _client() as client:
        for i, post in enumerate(posts):
            body: dict = {"text": post}
            if previous_id:
                body["reply"] = {"in_reply_to_tweet_id": previous_id}
            resp = await client.post(url, json=body, headers={"Authorization": oauth1_header("POST", url)})
            if resp.status_code not in (200, 201):
                error = _x_error(resp)
                if first_id:
                    error += f" (posted {i} of {len(posts)} posts: https://x.com/i/status/{first_id})"
                raise PublishError(error)
            previous_id = resp.json()["data"]["id"]
            first_id = first_id or previous_id
    return f"https://x.com/i/status/{first_id}"


# --- LinkedIn ----------------------------------------------------------------

# Characters LinkedIn's "little" text format reserves; a "#" that starts a
# hashtag stays as is so hashtags still work
_LITTLE_RESERVED = re.compile(r"[\\|{}@\[\]()<>*_~]|#(?!\w)")


def linkedin_text(text: str) -> str:
    return _LITTLE_RESERVED.sub(lambda m: "\\" + m.group(0), text)


async def _publish_linkedin(text: str) -> str:
    if len(text) > LINKEDIN_MAX_CHARS:
        raise PublishError(f"LinkedIn posts are limited to {LINKEDIN_MAX_CHARS} characters (this one has {len(text)})")
    body = {
        "author": settings.linkedin_author_urn,
        "commentary": linkedin_text(text),
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    headers = {
        "Authorization": f"Bearer {settings.linkedin_access_token}",
        "LinkedIn-Version": settings.linkedin_api_version,
        "X-Restli-Protocol-Version": "2.0.0",
    }
    async with _client() as client:
        resp = await client.post(f"{LINKEDIN_API}/posts", json=body, headers=headers)
    if resp.status_code == 401:
        raise PublishError("LinkedIn rejected the access token (they expire after 60 days)")
    if resp.status_code not in (200, 201):
        try:
            detail = resp.json().get("message", "")
        except ValueError:
            detail = resp.text[:200]
        raise PublishError(f"LinkedIn returned {resp.status_code}: {detail}")
    urn = resp.headers.get("x-restli-id") or resp.headers.get("x-linkedin-id")
    if not urn:
        raise PublishError("LinkedIn accepted the post but didn't say where it is")
    return f"https://www.linkedin.com/feed/update/{urn}/"
