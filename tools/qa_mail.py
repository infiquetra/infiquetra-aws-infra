#!/usr/bin/env python3
"""team-hermod client for the QA mail lookup (SigV4, campps-qa-nonprod profile).

  qa_mail.py list director+run1@qa.infiquetra.com --hours 2
  qa_mail.py get <message-id> [--mark-read]

The function URL comes from --url or $QA_MAIL_URL (CamppsQaMailStack output
QaMailReaderUrl).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest


def call(url: str, params: dict[str, str], profile: str, region: str) -> object:
    full = f"{url.rstrip('/')}/?{urllib.parse.urlencode(params)}"
    if not full.startswith("https://"):
        raise SystemExit("URL must be https")
    creds = boto3.Session(profile_name=profile).get_credentials()
    if creds is None:
        raise SystemExit(f"no credentials for profile {profile}; run aws sso login")
    request = AWSRequest(method="GET", url=full)
    SigV4Auth(creds.get_frozen_credentials(), "lambda", region).add_auth(request)
    req = urllib.request.Request(  # noqa: S310 - https enforced above
        full, headers=dict(request.headers), method="GET"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310  # nosec B310 - https only
        return json.loads(resp.read())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default=os.environ.get("QA_MAIL_URL"))
    parser.add_argument("--profile", default="campps-qa-nonprod")
    parser.add_argument("--region", default="us-east-1")
    sub = parser.add_subparsers(dest="cmd", required=True)
    lst = sub.add_parser("list")
    lst.add_argument("to")
    lst.add_argument("--hours", type=int, default=24)
    get = sub.add_parser("get")
    get.add_argument("id")
    get.add_argument("--mark-read", action="store_true")
    args = parser.parse_args()
    if not args.url:
        parser.error("set --url or QA_MAIL_URL")

    if args.cmd == "list":
        params = {"action": "list", "to": args.to, "hours": str(args.hours)}
    else:
        params = {"action": "get", "id": args.id}
        if args.mark_read:
            params["mark_read"] = "1"
    json.dump(call(args.url, params, args.profile, args.region), sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
