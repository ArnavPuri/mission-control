"""Publishing drafts to X and LinkedIn, against fake APIs."""

import json

import httpx
import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models import ContentStatus, EventLog, MarketingContent
from app.integrations import publishing
from app.orchestrator import review


@pytest.fixture
def x_keys(monkeypatch):
    # The example credentials from X's "Creating a signature" docs
    monkeypatch.setattr(settings, "x_api_key", "xvz1evFS4wEEPTGEFPHBog")
    monkeypatch.setattr(settings, "x_api_secret", "kAcSOqF21Fu85e7zjz7ZN2U4ZRhfV3WpwPAoE3Z7kBw")
    monkeypatch.setattr(settings, "x_access_token", "370773112-GmHxMAgYyLbNEtIKZeRNFsMKPR9EyMZeS9weJAEb")
    monkeypatch.setattr(settings, "x_access_token_secret", "LswwdoUaIvS8ltyTt5jkRh4J50vUPVVHtR2YPi5kE")


@pytest.fixture
def linkedin_keys(monkeypatch):
    monkeypatch.setattr(settings, "linkedin_access_token", "li-token")
    monkeypatch.setattr(settings, "linkedin_author_urn", "urn:li:person:abc123")


@pytest.fixture
def fake_api(monkeypatch):
    """Route publishing's HTTP calls to a handler; records the requests."""
    requests = []
    responses = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return responses.pop(0) if responses else httpx.Response(500)

    monkeypatch.setattr(publishing, "_transport", httpx.MockTransport(handler))
    return requests, responses


def test_oauth1_signature_matches_x_docs_example(x_keys):
    header = publishing.oauth1_header(
        "POST", "https://api.twitter.com/1.1/statuses/update.json",
        {"include_entities": "true", "status": "Hello Ladies + Gentlemen, a signed OAuth request!"},
        nonce="kYjzVBB8Y0ZFabxSWbWovY3uYSQ2pTgmZeNu2VS4cg", timestamp=1318622958,
    )
    assert 'oauth_signature="hCtSmYh%2BiHYCEqBWrE7C7hYmtUk%3D"' in header
    assert header.startswith("OAuth oauth_consumer_key=")


def test_split_thread_keeps_posts_under_the_limit():
    text = "\n\n".join([" ".join(["word"] * 70), "Short paragraph.", "x" * 600])
    posts = publishing.split_thread(text)
    assert all(len(p) <= 280 for p in posts)
    assert "".join(posts).replace(" ", "").replace("\n", "") == text.replace(" ", "").replace("\n", "")
    assert publishing.split_thread("Just one post") == ["Just one post"]


def test_linkedin_text_escapes_reserved_characters_but_keeps_hashtags():
    assert publishing.linkedin_text("Hi @sam (beta) *new* #launch # 1_2 [x]") == \
        "Hi \\@sam \\(beta\\) \\*new\\* #launch \\# 1\\_2 \\[x\\]"


def test_configured_channels(x_keys):
    assert publishing.configured_channels() == {"x": True, "linkedin": False}


@pytest.mark.asyncio
async def test_publish_to_x_posts_a_thread(x_keys, fake_api):
    requests, responses = fake_api
    responses += [
        httpx.Response(201, json={"data": {"id": "100", "text": "a"}}),
        httpx.Response(201, json={"data": {"id": "101", "text": "b"}}),
    ]
    url = await publishing.publish("x", "First paragraph. " * 10 + "\n\n" + "Second paragraph. " * 10)
    assert url == "https://x.com/i/status/100"
    assert [r.url.path for r in requests] == ["/2/tweets", "/2/tweets"]
    assert requests[0].headers["authorization"].startswith("OAuth ")
    second = json.loads(requests[1].content)
    assert second["reply"] == {"in_reply_to_tweet_id": "100"}


@pytest.mark.asyncio
async def test_publish_to_x_explains_failures(x_keys, fake_api):
    _, responses = fake_api
    responses.append(httpx.Response(401, json={"title": "Unauthorized"}))
    with pytest.raises(publishing.PublishError, match="read and write"):
        await publishing.publish("x", "hello")
    responses.append(httpx.Response(403, json={"detail": "You are not allowed to create a Tweet with duplicate content."}))
    with pytest.raises(publishing.PublishError, match="duplicate content"):
        await publishing.publish("x", "hello")


@pytest.mark.asyncio
async def test_publish_to_linkedin(linkedin_keys, fake_api):
    requests, responses = fake_api
    responses.append(httpx.Response(201, headers={"x-restli-id": "urn:li:share:777"}))
    url = await publishing.publish("linkedin", "Shipped v1 (finally) #buildinpublic")
    assert url == "https://www.linkedin.com/feed/update/urn:li:share:777/"
    req = requests[0]
    assert req.url.path == "/rest/posts"
    assert req.headers["authorization"] == "Bearer li-token"
    assert req.headers["linkedin-version"] == settings.linkedin_api_version
    body = json.loads(req.content)
    assert body["author"] == "urn:li:person:abc123"
    assert body["commentary"] == "Shipped v1 \\(finally\\) #buildinpublic"
    assert body["lifecycleState"] == "PUBLISHED"


@pytest.mark.asyncio
async def test_unconfigured_or_unsupported_channels_say_what_to_do():
    with pytest.raises(publishing.PublishError, match="X_API_KEY"):
        await publishing.publish("x", "hello")
    with pytest.raises(publishing.PublishError, match="isn't supported"):
        await publishing.publish("instagram", "hello")


async def _draft(db_session, channel="x") -> MarketingContent:
    async with db_session() as db:
        content = MarketingContent(title="Launch", body="We launched today!", channel=channel)
        db.add(content)
        await db.commit()
        return content


@pytest.mark.asyncio
async def test_telegram_publish_asks_to_confirm_then_publishes(db_session, x_keys, fake_api):
    _, responses = fake_api
    responses.append(httpx.Response(201, json={"data": {"id": "555", "text": "x"}}))
    content = await _draft(db_session)

    _, markup = review.draft_message(content)
    publish_button = markup["inline_keyboard"][1][0]
    assert publish_button["text"] == "🚀 Publish to X"

    async with db_session() as db:
        confirm = await review.handle_callback(db, publish_button["callback_data"])
        assert isinstance(confirm, review.Confirm)
        yes, cancel = confirm.markup["inline_keyboard"][0]

        undo = await review.handle_callback(db, cancel["callback_data"])
        assert isinstance(undo, review.Confirm) and undo.markup == markup

        outcome = await review.handle_callback(db, yes["callback_data"])
        await db.commit()
        assert outcome == "🚀 Published: https://x.com/i/status/555"
        stored = await db.get(MarketingContent, content.id)
        assert stored.status == ContentStatus.POSTED and stored.posted_url.endswith("/555")
        assert (await db.execute(select(EventLog).where(EventLog.event_type == "content.published"))).scalar_one()

        again = await review.handle_callback(db, yes["callback_data"])
        assert again.startswith("Already posted")


@pytest.mark.asyncio
async def test_no_publish_button_without_credentials(db_session):
    content = await _draft(db_session)
    _, markup = review.draft_message(content)
    assert len(markup["inline_keyboard"]) == 1


@pytest.mark.asyncio
async def test_publish_api(client, db_session, linkedin_keys, fake_api):
    _, responses = fake_api
    content = await _draft(db_session, channel="linkedin")
    responses.append(httpx.Response(500, json={"message": "Internal error"}))
    failed = await client.post(f"/api/mkt-content/{content.id}/publish")
    assert failed.status_code == 400 and "LinkedIn returned 500" in failed.json()["detail"]

    responses.append(httpx.Response(201, headers={"x-restli-id": "urn:li:share:9"}))
    ok = await client.post(f"/api/mkt-content/{content.id}/publish")
    assert ok.json() == {"posted_url": "https://www.linkedin.com/feed/update/urn:li:share:9/"}
    assert (await client.get(f"/api/mkt-content/{content.id}")).json()["status"] == "posted"
    assert (await client.get("/health")).json()["publishing"] == {"x": False, "linkedin": True}
