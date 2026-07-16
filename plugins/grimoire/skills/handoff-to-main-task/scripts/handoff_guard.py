#!/usr/bin/env python3
"""Fail-closed helpers for handoff-to-main-task.

The model owns Codex task-tool calls and prose composition. This script only
evaluates supplied JSON snapshots and emits JSON decisions.
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
import json
import sys
import unicodedata
from typing import Any


def normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def normalize_payload(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in value.strip().split("\n"))


def require_string(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def require_scalar(mapping: dict[str, Any], key: str) -> str | int | float:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f"{key} must be a string or number")
    if isinstance(value, str) and not value:
        raise ValueError(f"{key} must not be empty")
    return value


def compare_exact(
    candidate: dict[str, Any],
    field: str,
    expected: str,
    *,
    normalize: bool = False,
) -> tuple[bool, str]:
    actual = candidate.get(field)
    if not isinstance(actual, str):
        return False, f"{field}: missing"
    left = normalize_text(actual) if normalize else actual
    right = normalize_text(expected) if normalize else expected
    if left == right:
        match_kind = "normalized exact" if normalize else "exact"
        return True, f"{field}: {match_kind}"
    return False, f"{field}: mismatch"


def resolve(data: dict[str, Any]) -> dict[str, Any]:
    anchors = data.get("anchors")
    candidates = data.get("candidates")
    if not isinstance(anchors, dict) or not isinstance(candidates, list):
        raise ValueError("resolve requires anchors object and candidates array")

    require_string(anchors, "cwd")
    if not any(isinstance(anchors.get(key), str) and anchors[key] for key in ("title", "preview")):
        raise ValueError("anchors require a normalized-exact title or preview")

    source_id = data.get("sourceThreadId")
    assessments: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []

    for raw in candidates:
        if not isinstance(raw, dict):
            continue
        candidate = raw
        reasons: list[str] = []
        mismatches: list[str] = []

        candidate_id = candidate.get("id")
        if not isinstance(candidate_id, str) or not candidate_id:
            mismatches.append("id: missing")
        elif source_id and candidate_id == source_id:
            mismatches.append("id: source thread is never a target")

        fields = (("cwd", False), ("title", True), ("preview", True), ("hostId", False), ("status", False))
        for field, normalized in fields:
            expected = anchors.get(field)
            if not isinstance(expected, str) or not expected:
                continue
            ok, reason = compare_exact(candidate, field, expected, normalize=normalized)
            (reasons if ok else mismatches).append(reason)

        not_before = anchors.get("updatedAtNotBefore")
        updated_at = candidate.get("updatedAt")
        if isinstance(not_before, (str, int, float)) and not isinstance(not_before, bool):
            if isinstance(updated_at, bool) or not isinstance(updated_at, type(not_before)):
                mismatches.append("updatedAt: missing or type mismatch")
            elif updated_at < not_before:
                mismatches.append("updatedAt: older than lower bound")
            else:
                reasons.append("updatedAt: within lower bound")

        assessment = {
            "id": candidate_id,
            "title": candidate.get("title"),
            "cwd": candidate.get("cwd"),
            "updatedAt": updated_at,
            "matches": reasons,
            "mismatches": mismatches,
        }
        assessments.append(assessment)
        if not mismatches:
            matches.append(candidate)

    state = "unique" if len(matches) == 1 else "ambiguous" if len(matches) > 1 else "none"
    return {
        "state": state,
        "target": matches[0] if state == "unique" else None,
        "matches": matches,
        "candidates": assessments,
    }


def handoff_id(target_id: str, payload: str) -> str:
    material = target_id + normalize_payload(payload)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def prepare(data: dict[str, Any]) -> dict[str, Any]:
    target_id = require_string(data, "targetId")
    updated_at = require_scalar(data, "updatedAt")
    payload = require_string(data, "payload").rstrip()
    if not payload:
        raise ValueError("payload must contain non-whitespace text")
    identifier = handoff_id(target_id, payload)
    marker = f"<!-- grimoire-handoff: {identifier} -->"
    message = f"{payload}\n\n{marker}"
    return {
        "targetId": target_id,
        "updatedAt": updated_at,
        "handoffId": identifier,
        "marker": marker,
        "payload": payload,
        "message": message,
    }


def revalidate(data: dict[str, Any]) -> dict[str, Any]:
    preview = data.get("preview")
    target = data.get("target")
    messages = data.get("recentMessages", "")
    if not isinstance(preview, dict) or not isinstance(target, dict):
        raise ValueError("revalidate requires preview and target objects")
    if isinstance(messages, list):
        messages = "\n".join(item for item in messages if isinstance(item, str))
    if not isinstance(messages, str):
        raise ValueError("recentMessages must be a string or string array")

    target_id = require_string(target, "id")
    current_updated_at = require_scalar(target, "updatedAt")
    preview_target_id = require_string(preview, "targetId")
    preview_updated_at = require_scalar(preview, "updatedAt")
    payload = require_string(preview, "payload")
    expected_id = require_string(preview, "handoffId")
    marker = require_string(preview, "marker")
    message = require_string(preview, "message")

    if target_id != preview_target_id:
        return {"valid": False, "reason": "target-changed"}
    if current_updated_at != preview_updated_at:
        return {"valid": False, "reason": "target-stale"}
    calculated_id = handoff_id(preview_target_id, payload)
    expected_marker = f"<!-- grimoire-handoff: {calculated_id} -->"
    expected_message = f"{payload.rstrip()}\n\n{expected_marker}"
    if calculated_id != expected_id or marker != expected_marker or message != expected_message:
        return {"valid": False, "reason": "payload-changed"}
    if marker in messages:
        return {"valid": False, "reason": "duplicate"}
    return {"valid": True, "reason": "valid"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("resolve", "prepare", "revalidate"))
    parser.add_argument("input", nargs="?", help="JSON file; defaults to stdin")
    args = parser.parse_args()

    try:
        stream = open(args.input, encoding="utf-8") if args.input else sys.stdin
        with stream if args.input else nullcontext(stream):
            data = json.load(stream)
        if not isinstance(data, dict):
            raise ValueError("input must be a JSON object")
        result = {"resolve": resolve, "prepare": prepare, "revalidate": revalidate}[args.action](data)
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        json.dump({"error": str(exc)}, sys.stderr, ensure_ascii=False)
        sys.stderr.write("\n")
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
