"""Unit tests for the QA mail reader Lambda handler (no AWS calls)."""

import io
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parents[2]
        / "infiquetra_aws_infra"
        / "lambda_src"
        / "qa_mail_reader"
    ),
)
import handler

RAW = (
    b"Received: from mail.example.com by inbound-smtp for probe@qa.infiquetra.com;\r\n"
    b"From: Camp <noreply@example.com>\r\n"
    b"To: director+run1@qa.infiquetra.com\r\n"
    b"Subject: You're invited\r\n"
    b"MIME-Version: 1.0\r\n"
    b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
    b"Accept: https://nonprod.campps.infiquetra.com/invite?t=abc&x=1.\r\n"
)


class FakeS3:
    class exceptions:  # noqa: N801
        class NoSuchKey(Exception):  # noqa: N818 - mirrors boto3
            pass

    def __init__(self, objects: dict[str, tuple[bytes, datetime]]) -> None:
        self.objects = objects
        self.tags: dict[str, list[dict[str, str]]] = {}
        self.requested: list[str] = []

    def get_paginator(self, _name: str) -> Any:
        fake = self

        class Paginator:
            def paginate(self, Bucket: str, Prefix: str) -> Any:  # noqa: N803
                yield {
                    "Contents": [
                        {"Key": k, "LastModified": m}
                        for k, (_, m) in fake.objects.items()
                        if k.startswith(Prefix)
                    ]
                }

        return Paginator()

    def get_object(self, Bucket: str, Key: str, Range: str = "") -> Any:  # noqa: N803
        self.requested.append(Key)
        if Key not in self.objects:
            raise self.exceptions.NoSuchKey()
        body, modified = self.objects[Key]
        return {"Body": io.BytesIO(body), "LastModified": modified}

    def get_object_tagging(self, Bucket: str, Key: str) -> Any:  # noqa: N803
        return {"TagSet": self.tags.get(Key, [])}

    def put_object_tagging(self, Bucket: str, Key: str, Tagging: Any) -> None:  # noqa: N803
        self.tags[Key] = Tagging["TagSet"]


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeS3:
    now = datetime.now(UTC)
    s3 = FakeS3(
        {
            "inbound/new1": (RAW, now - timedelta(minutes=5)),
            "inbound/old1": (RAW, now - timedelta(hours=30)),
            "other/secret": (RAW, now),
        }
    )
    monkeypatch.setattr(handler, "_s3", s3)
    return s3


def call(**params: str) -> tuple[int, Any]:
    out = handler.handler({"queryStringParameters": params}, None)
    return out["statusCode"], json.loads(out["body"])


@pytest.mark.parametrize("bad", ["../other/secret", "a/b", "", "x" * 200, "%2e%2e"])
def test_get_rejects_ids_that_could_leave_inbound(fake: FakeS3, bad: str) -> None:
    status, _ = call(action="get", id=bad)
    assert status == 400
    assert all(k.startswith("inbound/") for k in fake.requested)


def test_list_filters_by_recipient_and_window(fake: FakeS3) -> None:
    status, body = call(action="list", to="Director+run1@qa.infiquetra.com", hours="2")
    assert status == 200
    assert [m["id"] for m in body["messages"]] == ["new1"]
    assert all(k.startswith("inbound/") for k in fake.requested)

    _, body = call(action="list", to="probe@qa.infiquetra.com", hours="48")
    assert [m["id"] for m in body["messages"]] == ["new1", "old1"]

    _, body = call(action="list", to="nobody@qa.infiquetra.com", hours="48")
    assert body["messages"] == []


def test_get_parses_body_links_and_marks_read(fake: FakeS3) -> None:
    status, body = call(action="get", id="new1", mark_read="1")
    assert status == 200
    assert body["subject"] == "You're invited"
    assert body["links"] == ["https://nonprod.campps.infiquetra.com/invite?t=abc&x=1"]
    assert body["read"] is True
    assert fake.tags["inbound/new1"] == [{"Key": "qa-read", "Value": "true"}]


def test_get_missing_is_404(fake: FakeS3) -> None:
    status, _ = call(action="get", id="nope")
    assert status == 404
