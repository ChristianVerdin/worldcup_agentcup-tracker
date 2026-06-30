"""AgentMail integration.

Two jobs:
  1. request_standing() — send "STANDING" from your inbox to the contest address
     and poll the inbox for the contest's reply. This is the *official* channel
     (the welcome email says: "Reply STANDING any time to see your rank") and it
     doubles as the AgentMail showcase.
  2. send_digest() — email a formatted update to your Gmail from your inbox.

SDK surface (verified against agentmail==0.5.x):
  client.inboxes.messages.send(inbox_id, *, to, subject, text, html=...)
      -> SendMessageResponse(message_id, thread_id)
  client.inboxes.messages.list(inbox_id, *, from_, after, limit, ascending)
      -> ListMessagesResponse(count, messages=[Message, ...])
  client.inboxes.messages.get(inbox_id, message_id) -> Message(text, preview, ...)
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime, timezone

from agentmail import AgentMail


def parse_standing_reply(text: str) -> dict:
    """Extract the authoritative numbers from the contest's STANDING reply.

    The reply reads like:
      "You're rank 1 of 57 with 2 points (ceiling 59). Your predicted champion
       is still alive. ..."
    Anything not found stays None so callers can fall back to other sources.
    """
    out = {"rank": None, "field_size": None, "points": None, "ceiling": None, "champion_alive": None}
    if not text:
        return out
    t = " ".join(text.split())
    m = re.search(r"rank\s+(\d+)\s+of\s+(\d+)", t, re.I)
    if m:
        out["rank"], out["field_size"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"with\s+(\d+)\s+point", t, re.I)
    if m:
        out["points"] = int(m.group(1))
    m = re.search(r"ceiling\s+(\d+)", t, re.I)
    if m:
        out["ceiling"] = int(m.group(1))
    if re.search(r"champion\s+is\s+(?:still\s+)?alive", t, re.I):
        out["champion_alive"] = True
    elif re.search(r"champion[^.]*(?:no longer|eliminated|is out)", t, re.I):
        out["champion_alive"] = False
    return out


def _client() -> AgentMail:
    key = os.environ.get("AGENTMAIL_API_KEY")
    if not key:
        raise RuntimeError(
            "AGENTMAIL_API_KEY is not set. Add it as a GitHub Actions secret "
            "(Settings -> Secrets and variables -> Actions), or export it locally."
        )
    return AgentMail(api_key=key)


def request_standing(
    inbox: str,
    contest_address: str = "worldcup@agentmail.to",
    wait_seconds: int = 120,
    poll_seconds: int = 10,
) -> str | None:
    """Send STANDING and return the contest's reply text, or None if it didn't arrive in time."""
    client = _client()
    sent_at = datetime.now(timezone.utc)

    client.inboxes.messages.send(
        inbox_id=inbox,
        to=contest_address,
        subject="STANDING",
        text="STANDING",
    )

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        time.sleep(poll_seconds)
        try:
            resp = client.inboxes.messages.list(
                inbox_id=inbox,
                from_=[contest_address],
                after=sent_at,
                limit=5,
                ascending=False,
            )
        except Exception as exc:  # transient API error — keep polling
            print(f"  [agentmail] list error (will retry): {exc}")
            continue

        messages = getattr(resp, "messages", None) or []
        if messages:
            newest = messages[0]
            try:
                full = client.inboxes.messages.get(
                    inbox_id=inbox, message_id=newest.message_id
                )
                body = (full.text or full.preview or "").strip()
            except Exception:
                body = (getattr(newest, "text", None) or getattr(newest, "preview", None) or "").strip()
            return body or None

    return None


def send_digest(inbox: str, to: str, subject: str, text: str, html: str | None = None):
    """Send the twice-daily update email from your AgentMail inbox to `to`."""
    client = _client()
    return client.inboxes.messages.send(
        inbox_id=inbox, to=to, subject=subject, text=text, html=html
    )
