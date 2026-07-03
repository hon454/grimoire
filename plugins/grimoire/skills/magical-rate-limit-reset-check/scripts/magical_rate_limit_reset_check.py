#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


URL = "https://chatgpt.com/backend-api/wham/rate-limit-reset-credits"


def parse_time(value):
    dt = parse_datetime(value)
    if dt:
        return dt.strftime("%Y-%m-%d %H:%M %Z")
    if value:
        return str(value)
    return None


def parse_datetime(value):
    if not value:
        return None
    text = str(value)
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone()
    except ValueError:
        return None


def format_time_left(value, now=None):
    expires_at = parse_datetime(value)
    if not expires_at:
        return None
    if now is None:
        now = datetime.now(expires_at.tzinfo)
    else:
        now = now.astimezone(expires_at.tzinfo)
    seconds = int((expires_at - now).total_seconds())
    if seconds <= 0:
        return "expired"
    if seconds < 60:
        return "<1m"

    total_minutes = seconds // 60
    days, total_minutes = divmod(total_minutes, 24 * 60)
    hours, minutes = divmod(total_minutes, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    return " ".join(parts)


def summarize_credit(credit, now=None):
    expires_at = credit.get("expires_at")
    return {
        "status": credit.get("status"),
        "title": credit.get("title"),
        "granted_at": parse_time(credit.get("granted_at")),
        "expires_at": parse_time(expires_at),
        "time_left": format_time_left(expires_at, now),
    }


def summarize(data, now=None):
    credits = data.get("credits") or data.get("items") or []
    if not isinstance(credits, list):
        credits = []
    return {
        "available_count": data.get("available_count", len(credits)),
        "credits": [
            summarize_credit(credit, now)
            for credit in credits
            if isinstance(credit, dict)
        ],
    }


def render(summary):
    lines = [f"Reset credits available: {summary['available_count']}"]
    for index, credit in enumerate(summary["credits"], 1):
        lines.extend(
            [
                "",
                f"{index}. Status: {credit.get('status') or '(unknown)'}",
                f"   Granted: {credit.get('granted_at') or '(unknown)'}",
                f"   Expires: {credit.get('expires_at') or '(unknown)'}",
                f"   Time left: {credit.get('time_left') or '(unknown)'}",
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
    now = datetime.fromisoformat("2026-07-02T00:00:00+00:00")
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
        },
        now=now,
    )
    assert summary["available_count"] == 1
    assert summary["credits"][0]["status"] == "available"
    assert summary["credits"][0]["time_left"] == "1d"
    assert "id" not in summary["credits"][0]
    assert summary["credits"][0]["granted_at"] != "2026-07-02T00:00:00Z"
    assert "do-not-print" not in render(summary)
    assert "1. Reset credit" not in render(summary)
    assert "Time left: 1d" in render(summary)
    assert format_time_left("2026-07-02T01:02:30Z", now) == "1h 2m"
    assert format_time_left("2026-07-02T00:00:30Z", now) == "<1m"
    assert format_time_left("2026-07-01T23:59:00Z", now) == "expired"


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
