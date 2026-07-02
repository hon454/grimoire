#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


URL = "https://chatgpt.com/backend-api/wham/rate-limit-reset-credits"


def parse_time(value):
    if not value:
        return None
    text = str(value)
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z%z")
    except ValueError:
        return str(value)


def summarize(data):
    credits = data.get("credits") or data.get("items") or []
    if not isinstance(credits, list):
        credits = []
    return {
        "available_count": data.get("available_count", len(credits)),
        "credits": [
            {
                "status": credit.get("status"),
                "title": credit.get("title"),
                "granted_at": parse_time(credit.get("granted_at")),
                "expires_at": parse_time(credit.get("expires_at")),
            }
            for credit in credits
            if isinstance(credit, dict)
        ],
    }


def render(summary):
    lines = [f"Available reset credits: {summary['available_count']}"]
    for index, credit in enumerate(summary["credits"], 1):
        lines.extend(
            [
                "",
                f"{index}. Reset credit",
                f"   Status: {credit.get('status') or '(unknown)'}",
                f"   Granted: {credit.get('granted_at') or '(unknown)'}",
                f"   Expires: {credit.get('expires_at') or '(unknown)'}",
            ]
        )
    return "\n".join(lines)


def access_token(auth_path):
    with auth_path.expanduser().open() as f:
        data = json.load(f)
    token = data.get("tokens", {}).get("access_token")
    if not token:
        raise SystemExit(f"missing tokens.access_token in {auth_path}")
    return token


def fetch(token):
    req = Request(
        URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "Codex reset-credit checker",
        },
    )
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def self_test():
    summary = summarize(
        {
            "available_count": 1,
            "credits": [
                {
                    "id": "do-not-print",
                    "status": "available",
                    "title": "Reset",
                    "granted_at": "2026-07-02T00:00:00Z",
                    "expires_at": "2026-07-03T00:00:00+00:00",
                }
            ],
        }
    )
    assert summary["available_count"] == 1
    assert summary["credits"][0]["status"] == "available"
    assert "id" not in summary["credits"][0]
    assert summary["credits"][0]["granted_at"] != "2026-07-02T00:00:00Z"
    assert "do-not-print" not in render(summary)
    assert "Reset\n" not in render(summary)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--auth", default="~/.codex/auth.json")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return

    try:
        data = fetch(access_token(Path(args.auth)))
    except HTTPError as exc:
        if exc.code == 401:
            raise SystemExit(
                "HTTP 401: credentials are expired or the Authorization header was not accepted"
            )
        raise SystemExit(f"HTTP {exc.code}: request failed")
    except (OSError, URLError, json.JSONDecodeError) as exc:
        raise SystemExit(f"request failed: {exc}")

    summary = summarize(data)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(render(summary))


if __name__ == "__main__":
    main()
