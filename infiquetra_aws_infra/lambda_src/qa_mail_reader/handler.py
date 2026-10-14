"""Read-only QA mail lookup behind an AWS_IAM Lambda function URL.

Routes (GET, query string):
  ?action=list&to=<addr>&hours=<N>     newest first, recipient match
  ?action=get&id=<message-id>[&mark_read=1]
Only objects under ``inbound/`` in the QA mail bucket are ever read.
"""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timedelta
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses
from typing import Any

import boto3

BUCKET = os.environ.get("QA_MAIL_BUCKET", "")
PREFIX = "inbound/"
MAX_HOURS = 168
MAX_LIST = 50
HEADER_BYTES = 32768
ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")
ADDR_RE = re.compile(r"^[^@\s]+@[A-Za-z0-9.\-]+$")
RECEIVED_FOR_RE = re.compile(r"\bfor\s+<?([^\s<>;]+@[^\s<>;]+)>?", re.IGNORECASE)
LINK_RE = re.compile(r"https?://[^\s\"'<>)\]]+")

_s3: Any = None


def _client() -> Any:
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3")
    return _s3


def _resp(status: int, body: Any) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def key_for(message_id: str) -> str:
    """Map a message ID to its key; refuse anything that could escape inbound/."""
    if not ID_RE.match(message_id):
        raise ValueError("invalid id")
    return f"{PREFIX}{message_id}"


def recipients(msg: EmailMessage) -> set[str]:
    found: set[str] = set()
    for header in ("To", "Cc", "Delivered-To", "X-Original-To"):
        for _, addr in getaddresses(msg.get_all(header, [])):
            if addr:
                found.add(addr.lower())
    for received in msg.get_all("Received", []):
        for addr in RECEIVED_FOR_RE.findall(str(received)):
            found.add(addr.lower())
    return found


def parse_headers(raw: bytes) -> EmailMessage:
    msg = BytesParser(policy=policy.default).parsebytes(raw, headersonly=True)
    assert isinstance(msg, EmailMessage)  # nosec B101 - policy.default type
    return msg


def summarize(message_id: str, msg: EmailMessage, modified: Any) -> dict[str, Any]:
    return {
        "id": message_id,
        "received": modified,
        "from": str(msg.get("From", "")),
        "to": sorted(recipients(msg)),
        "subject": str(msg.get("Subject", "")),
        "date": str(msg.get("Date", "")),
    }


def list_messages(to: str, hours: int) -> list[dict[str, Any]]:
    since = datetime.now(UTC) - timedelta(hours=hours)
    s3 = _client()
    candidates = []
    for page in s3.get_paginator("list_objects_v2").paginate(
        Bucket=BUCKET, Prefix=PREFIX
    ):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            message_id = key[len(PREFIX) :]
            if obj["LastModified"] >= since and ID_RE.match(message_id):
                candidates.append(obj)
    candidates.sort(key=lambda o: o["LastModified"], reverse=True)

    results = []
    for obj in candidates:
        head = s3.get_object(
            Bucket=BUCKET, Key=obj["Key"], Range=f"bytes=0-{HEADER_BYTES - 1}"
        )["Body"].read()
        msg = parse_headers(head)
        if to in recipients(msg):
            results.append(
                summarize(obj["Key"][len(PREFIX) :], msg, obj["LastModified"])
            )
            if len(results) >= MAX_LIST:
                break
    return results


def extract_links(*bodies: str | None) -> list[str]:
    links: list[str] = []
    for body in bodies:
        for link in LINK_RE.findall(body or ""):
            link = link.replace("&amp;", "&").rstrip(".,;")
            if link not in links:
                links.append(link)
    return links


def get_message(message_id: str, mark_read: bool) -> dict[str, Any]:
    key = key_for(message_id)
    s3 = _client()
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    msg = BytesParser(policy=policy.default).parsebytes(obj["Body"].read())
    assert isinstance(msg, EmailMessage)  # nosec B101 - policy.default type
    text_part = msg.get_body(preferencelist=("plain",))
    html_part = msg.get_body(preferencelist=("html",))
    text = text_part.get_content() if text_part is not None else None
    html = html_part.get_content() if html_part is not None else None

    tags = s3.get_object_tagging(Bucket=BUCKET, Key=key).get("TagSet", [])
    was_read = any(t["Key"] == "qa-read" for t in tags)
    if mark_read and not was_read:
        s3.put_object_tagging(
            Bucket=BUCKET,
            Key=key,
            Tagging={"TagSet": [*tags, {"Key": "qa-read", "Value": "true"}]},
        )

    result = summarize(message_id, msg, obj.get("LastModified"))
    result.update(
        {
            "headers": {k: str(v) for k, v in msg.items()},
            "text": text,
            "html": html,
            "links": extract_links(text, html),
            "read": was_read or mark_read,
        }
    )
    return result


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    params = event.get("queryStringParameters") or {}
    action = params.get("action", "list")
    try:
        if action == "list":
            to = (params.get("to") or "").strip().lower()
            if not ADDR_RE.match(to):
                return _resp(400, {"error": "to must be an email address"})
            hours = min(max(int(params.get("hours", "24")), 1), MAX_HOURS)
            return _resp(200, {"messages": list_messages(to, hours)})
        if action == "get":
            mark_read = params.get("mark_read", "") in ("1", "true", "yes")
            return _resp(200, get_message(params.get("id", ""), mark_read))
    except ValueError as exc:
        return _resp(400, {"error": str(exc)})
    except _client().exceptions.NoSuchKey:
        return _resp(404, {"error": "not found"})
    return _resp(400, {"error": "action must be list or get"})
