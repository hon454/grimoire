#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import stat
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional


SCHEMA_VERSION = 1
MAX_JSON_BYTES = 10 * 1024 * 1024
TERMINAL_LIFECYCLES = {"completed", "stopped"}
LOCAL_STATUSES = {"not_started", "in_progress", "completed"}
REMOTE_STATUSES = {"pending", "in_progress", "succeeded", "failed", "uncertain"}
DECISION_TYPES = {"fix", "explain", "question", "defer_reject", "duplicate", "outdated"}
PLATFORM_KINDS = {
    "github_reply",
    "github_resolve",
    "github_pr_body_update",
    "github_rereview",
}
REPOSITORY_ACTIONS = {"commit", "push", "merge", "release", "deployment"}
ALLOWED_FILES = {"state.json", "review.html", ".state.json.tmp", ".review.html.tmp"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LOCALE_RE = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")
OBVIOUS_SECRET_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----|"
    r"\b(?:gh[pousr]|sk)-[A-Za-z0-9_-]{20,}|"
    r"\b(?:password|passwd|access[_-]?token|api[_-]?key)\s*[:=]\s*[\"']?[^\s\"']{12,}",
    re.IGNORECASE,
)


class StateError(RuntimeError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_uuid(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise StateError(f"{field} must be a canonical UUID string")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError) as error:
        raise StateError(f"{field} must be a canonical UUID string") from error
    if str(parsed) != value:
        raise StateError(f"{field} must be a canonical UUID string")
    return value


def new_id(existing: Iterable[str]) -> str:
    used = set(existing)
    while True:
        value = str(uuid.uuid4())
        if value not in used:
            return value


def canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise StateError(f"value is not canonical JSON: {error}") from error


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def require_object(value: Any, required: Iterable[str], field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StateError(f"{field} must be an object")
    expected = set(required)
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        details = []
        if missing:
            details.append(f"missing {missing}")
        if unknown:
            details.append(f"unknown {unknown}")
        raise StateError(f"{field} has invalid fields: {', '.join(details)}")
    return value


def require_string(value: Any, field: str, *, allow_empty: bool = True) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        suffix = "non-empty string" if not allow_empty else "string"
        raise StateError(f"{field} must be a {suffix}")
    return value


def require_bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise StateError(f"{field} must be a boolean")
    return value


def require_int(value: Any, field: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise StateError(f"{field} must be an integer >= {minimum}")
    return value


def require_optional_string(value: Any, field: str) -> Optional[str]:
    if value is not None and not isinstance(value, str):
        raise StateError(f"{field} must be a string or null")
    return value


def require_string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        raise StateError(f"{field} must be an array")
    result = []
    for index, entry in enumerate(value):
        result.append(require_string(entry, f"{field}[{index}]", allow_empty=False))
    if len(result) != len(set(result)):
        raise StateError(f"{field} must not contain duplicates")
    return result


def reject_obvious_secrets(value: Any) -> None:
    if isinstance(value, str) and OBVIOUS_SECRET_RE.search(value):
        raise StateError("candidate contains an obvious credential or private key")
    if isinstance(value, list):
        for entry in value:
            reject_obvious_secrets(entry)
    elif isinstance(value, dict):
        for entry in value.values():
            reject_obvious_secrets(entry)


def canonical_host(value: Any) -> str:
    host = require_string(value, "source.host", allow_empty=False)
    normalized = host.rstrip(".").lower()
    if host != normalized or "/" in host or "://" in host or any(char.isspace() for char in host):
        raise StateError("source.host must already be a canonical lowercase host name")
    return host


def canonical_repo_part(value: Any, field: str) -> str:
    part = require_string(value, field, allow_empty=False)
    normalized = part.lower()
    if part != normalized or "/" in part or any(char.isspace() for char in part):
        raise StateError(f"{field} must already be canonical lowercase owner/repository text")
    return part


def validate_platform_action(value: Any, field: str) -> dict[str, Any]:
    action = require_object(value, {"kind", "target", "summary", "reviewer_authored", "payload"}, field)
    kind = require_string(action["kind"], f"{field}.kind", allow_empty=False)
    if kind not in PLATFORM_KINDS:
        raise StateError(f"{field}.kind is unsupported")
    require_string(action["target"], f"{field}.target", allow_empty=False)
    require_string(action["summary"], f"{field}.summary", allow_empty=False)
    require_bool(action["reviewer_authored"], f"{field}.reviewer_authored")
    payload = action["payload"]
    if kind in {"github_reply", "github_pr_body_update"}:
        payload = require_object(payload, {"body"}, f"{field}.payload")
        require_string(payload["body"], f"{field}.payload.body", allow_empty=False)
    elif kind == "github_rereview":
        payload = require_object(payload, {"reviewers"}, f"{field}.payload")
        reviewers = require_string_list(payload["reviewers"], f"{field}.payload.reviewers")
        normalized_reviewers = {reviewer.lower() for reviewer in reviewers}
        if not reviewers:
            raise StateError(f"{field}.payload.reviewers must not be empty")
        if len(reviewers) != len(normalized_reviewers):
            raise StateError(
                f"{field}.payload.reviewers must not contain case-insensitive duplicates"
            )
    else:
        require_object(payload, set(), f"{field}.payload")
    return action


def remote_effect_projection(action: dict[str, Any]) -> dict[str, Any]:
    """Return only the fields that determine the externally visible mutation."""
    payload = action["payload"]
    if action["kind"] == "github_rereview":
        payload = {"reviewers": sorted(reviewer.lower() for reviewer in payload["reviewers"])}
    return {
        "kind": action["kind"],
        "target": action["target"],
        "payload": payload,
    }


def validate_local_change(value: Any, field: str) -> dict[str, Any]:
    change = require_object(value, {"area", "change_kind"}, field)
    require_string(change["area"], f"{field}.area", allow_empty=False)
    require_string(change["change_kind"], f"{field}.change_kind", allow_empty=False)
    return change


def validate_semantic_action(value: Any, field: str) -> dict[str, Any]:
    action = require_object(
        value,
        {"decision_type", "summary", "local_changes", "platform_actions"},
        field,
    )
    decision_type = require_string(action["decision_type"], f"{field}.decision_type")
    if decision_type not in DECISION_TYPES:
        raise StateError(f"{field}.decision_type is unsupported")
    require_string(action["summary"], f"{field}.summary", allow_empty=False)
    if not isinstance(action["local_changes"], list):
        raise StateError(f"{field}.local_changes must be an array")
    for index, change in enumerate(action["local_changes"]):
        validate_local_change(change, f"{field}.local_changes[{index}]")
    if not isinstance(action["platform_actions"], list):
        raise StateError(f"{field}.platform_actions must be an array")
    for index, platform_action in enumerate(action["platform_actions"]):
        validate_platform_action(platform_action, f"{field}.platform_actions[{index}]")
    return action


def validate_action_envelope(value: Any, field: str) -> dict[str, Any]:
    envelope = require_object(
        value,
        {
            "purpose",
            "allowed_areas",
            "allowed_change_kinds",
            "excluded",
            "validations",
            "repository_actions",
            "platform_actions",
        },
        field,
    )
    require_string(envelope["purpose"], f"{field}.purpose", allow_empty=False)
    require_string_list(envelope["allowed_areas"], f"{field}.allowed_areas")
    require_string_list(envelope["allowed_change_kinds"], f"{field}.allowed_change_kinds")
    excluded = require_string_list(envelope["excluded"], f"{field}.excluded")
    require_string_list(envelope["validations"], f"{field}.validations")
    repository_actions = require_string_list(
        envelope["repository_actions"], f"{field}.repository_actions"
    )
    if any(action not in REPOSITORY_ACTIONS for action in repository_actions):
        raise StateError(f"{field}.repository_actions contains an unsupported action")
    for action in REPOSITORY_ACTIONS:
        if action in repository_actions and action in excluded:
            raise StateError(f"{field} cannot both authorize and exclude {action}")
        if action not in repository_actions and action not in excluded:
            raise StateError(f"{field} must explicitly authorize or exclude {action}")
    if not isinstance(envelope["platform_actions"], list):
        raise StateError(f"{field}.platform_actions must be an array")
    seen = set()
    for index, action in enumerate(envelope["platform_actions"]):
        validate_platform_action(action, f"{field}.platform_actions[{index}]")
        action_key = fingerprint(action)
        if action_key in seen:
            raise StateError(f"{field}.platform_actions must not contain duplicates")
        seen.add(action_key)
    return envelope


def validate_evidence_semantic(value: Any, field: str) -> dict[str, Any]:
    semantic = require_object(
        value,
        {"reviewer_ask", "reviewer_intent", "claims", "code", "examples", "assumptions", "gaps"},
        field,
    )
    require_string(semantic["reviewer_ask"], f"{field}.reviewer_ask", allow_empty=False)
    require_string(semantic["reviewer_intent"], f"{field}.reviewer_intent", allow_empty=False)
    require_string_list(semantic["claims"], f"{field}.claims")
    require_string_list(semantic["assumptions"], f"{field}.assumptions")
    require_string_list(semantic["gaps"], f"{field}.gaps")
    if not isinstance(semantic["code"], list):
        raise StateError(f"{field}.code must be an array")
    for index, excerpt_value in enumerate(semantic["code"]):
        excerpt = require_object(
            excerpt_value,
            {"path", "revision", "text"},
            f"{field}.code[{index}]",
        )
        require_string(excerpt["path"], f"{field}.code[{index}].path", allow_empty=False)
        require_string(excerpt["revision"], f"{field}.code[{index}].revision", allow_empty=False)
        require_string(excerpt["text"], f"{field}.code[{index}].text")
    if not isinstance(semantic["examples"], list):
        raise StateError(f"{field}.examples must be an array")
    for index, example_value in enumerate(semantic["examples"]):
        example = require_object(
            example_value,
            {"input", "behavior", "outcome"},
            f"{field}.examples[{index}]",
        )
        for key in ("input", "behavior", "outcome"):
            require_string(example[key], f"{field}.examples[{index}].{key}")
    return semantic


def validate_presentation(value: Any, field: str) -> dict[str, Any]:
    presentation = require_object(
        value,
        {
            "title",
            "translation",
            "interpretation",
            "reviewer_intent",
            "evidence_diff",
            "alternatives",
            "recommendation",
            "question",
            "code_locations",
        },
        field,
    )
    for key in (
        "title",
        "translation",
        "interpretation",
        "reviewer_intent",
        "evidence_diff",
        "recommendation",
        "question",
    ):
        require_string(presentation[key], f"{field}.{key}")
    if not isinstance(presentation["alternatives"], list):
        raise StateError(f"{field}.alternatives must be an array")
    seen = set()
    for index, value in enumerate(presentation["alternatives"]):
        alternative = require_object(
            value,
            {"choice_id", "label", "tradeoff"},
            f"{field}.alternatives[{index}]",
        )
        choice_id = require_string(
            alternative["choice_id"],
            f"{field}.alternatives[{index}].choice_id",
            allow_empty=False,
        )
        require_string(alternative["label"], f"{field}.alternatives[{index}].label")
        require_string(alternative["tradeoff"], f"{field}.alternatives[{index}].tradeoff")
        if choice_id in seen:
            raise StateError(f"{field}.alternatives has duplicate choice_id")
        seen.add(choice_id)
    if not isinstance(presentation["code_locations"], list):
        raise StateError(f"{field}.code_locations must be an array")
    for index, location_value in enumerate(presentation["code_locations"]):
        location = require_object(
            location_value, {"start_line", "end_line"}, f"{field}.code_locations[{index}]"
        )
        start = require_int(location["start_line"], f"{field}.code_locations[{index}].start_line", minimum=1)
        end = require_int(location["end_line"], f"{field}.code_locations[{index}].end_line", minimum=1)
        if end < start:
            raise StateError(f"{field}.code_locations[{index}].end_line must be >= start_line")
    return presentation


def decision_view(
    presentation: dict[str, Any], proposal: dict[str, Any]
) -> dict[str, Any]:
    displays = {
        entry["choice_id"]: entry for entry in presentation["alternatives"]
    }
    return {
        "question": presentation["question"],
        "alternatives": [
            {
                "choice_id": choice_id,
                "label": displays.get(choice_id, {}).get("label")
                or proposal["choices_by_id"][choice_id]["label"]
                or choice_id,
                "tradeoff": displays.get(choice_id, {}).get("tradeoff")
                or proposal["choices_by_id"][choice_id]["tradeoff"],
            }
            for choice_id in proposal["choice_order"]
        ],
        "recommendation": presentation["recommendation"],
    }


def evidence_projection(item: dict[str, Any], semantic: dict[str, Any], version: int, evidence_id: str) -> dict[str, Any]:
    return {
        "domain": "magical-review-response/evidence/v1",
        "item_id": item["id"],
        "source_id": item["source_id"],
        "evidence_id": evidence_id,
        "version": version,
        "semantic": semantic,
    }


def decision_projection(item: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    evidence = item["evidence"]
    current = evidence["versions"][evidence["current_version"] - 1]
    semantic_choices = {
        choice_id: choice["semantic_action"]
        for choice_id, choice in proposal["choices_by_id"].items()
    }
    return {
        "domain": "magical-review-response/decision/v1",
        "item_id": item["id"],
        "source_id": item["source_id"],
        "source_key": item["source_key"],
        "evidence": {
            "id": current["id"],
            "version": current["version"],
            "fingerprint": current["fingerprint"],
        },
        "choices_by_id": semantic_choices,
        "recommended_choice_id": proposal["recommended_choice_id"],
        "action_envelope": proposal["action_envelope"],
    }


def archive_pending(state: dict[str, Any], status_value: str, reason: str, timestamp: str) -> None:
    pending = state["pending_request"]
    if pending is None:
        return
    archived = copy.deepcopy(pending)
    archived.update({"status": status_value, "ended_at": timestamp, "reason": reason})
    state["request_history"].append(archived)
    state["pending_request"] = None


def archive_authorization(item: dict[str, Any], reason: str, timestamp: str) -> None:
    authorization = item["active_authorization"]
    if authorization is None:
        return
    archived = copy.deepcopy(authorization)
    archived.update({"ended_at": timestamp, "reason": reason})
    item["authorization_history"].append(archived)
    item["active_authorization"] = None


def invalidate_item_authority(
    state: dict[str, Any], item: dict[str, Any], reason: str, timestamp: str
) -> None:
    pending = state["pending_request"]
    if pending is not None and pending["item_id"] == item["id"]:
        archive_pending(state, "invalidated", reason, timestamp)
    archive_authorization(item, reason, timestamp)


def mark_item_stale(
    state: dict[str, Any], item: dict[str, Any], reason: str, diff: str, timestamp: str
) -> None:
    evidence = item["evidence"]
    if evidence["current_version"] is not None:
        evidence["current_status"] = "stale"
    evidence["last_diff"] = diff
    evidence["evaluations"].append(
        {
            "id": new_id(entry["id"] for entry in evidence["evaluations"]),
            "from_version": evidence["current_version"],
            "to_version": None,
            "result": "unverified",
            "reason": reason,
            "diff": diff,
            "proposal_id": item["proposal"]["id"] if item["proposal"] else None,
            "proposal_generation": item["proposal"]["generation"] if item["proposal"] else 0,
            "decision_fingerprint": (
                item["proposal"]["decision_fingerprint"] if item["proposal"] else None
            ),
            "created_at": timestamp,
        }
    )
    invalidate_item_authority(state, item, reason, timestamp)


def blank_presentation(title: str) -> dict[str, Any]:
    return {
        "title": title,
        "translation": "",
        "interpretation": "",
        "reviewer_intent": "",
        "evidence_diff": "",
        "alternatives": [],
        "recommendation": "",
        "question": "",
        "code_locations": [],
    }


def new_item(
    source_id: str,
    source_key: str,
    kind: str,
    source_state: str,
    source_data: dict[str, Any],
    title: str,
    timestamp: str,
    existing_ids: Iterable[str],
) -> dict[str, Any]:
    return {
        "id": new_id(existing_ids),
        "source_id": source_id,
        "source_key": source_key,
        "kind": kind,
        "source_state": source_state,
        "source_data": source_data,
        "presentation": blank_presentation(title),
        "evidence": {
            "current_version": None,
            "current_status": "stale",
            "versions": [],
            "evaluations": [],
            "last_diff": "Evidence has not been evaluated.",
        },
        "proposal": None,
        "active_authorization": None,
        "authorization_history": [],
        "decision_history": [],
        "local_progress": {
            "status": "not_started",
            "started_at": None,
            "completed_at": None,
            "area": None,
            "change_kind": None,
            "validation_summary": "",
            "authorization_id": None,
        },
        "local_attempt_history": [],
        "remote_mutations": [],
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def validate_source_data(value: Any, field: str) -> dict[str, Any]:
    source_data = require_object(
        value,
        {"original", "thread_id", "review_id", "comment_ids", "path", "is_outdated"},
        field,
    )
    require_string(source_data["original"], f"{field}.original")
    require_optional_string(source_data["thread_id"], f"{field}.thread_id")
    require_optional_string(source_data["review_id"], f"{field}.review_id")
    require_string_list(source_data["comment_ids"], f"{field}.comment_ids")
    require_optional_string(source_data["path"], f"{field}.path")
    require_bool(source_data["is_outdated"], f"{field}.is_outdated")
    return source_data


def validate_item_source_contract(
    item: dict[str, Any], state: dict[str, Any], field: str
) -> None:
    source = state["source"]
    data = item["source_data"]
    if source["type"] == "pasted_feedback":
        if (
            item["kind"] != "pasted_feedback"
            or item["source_state"] != "copied"
            or item["source_key"] != f"pasted:{item['id']}"
            or data["thread_id"] is not None
            or data["review_id"] is not None
            or data["comment_ids"]
            or data["path"] is not None
            or data["is_outdated"]
        ):
            raise StateError(f"{field} does not match its pasted Source identity")
        return
    if item["kind"] == "pasted_feedback" or item["source_state"] == "copied":
        raise StateError(f"{field} does not match its GitHub Source type")
    snapshot = source["snapshot"]
    if snapshot is None:
        raise StateError(f"{field} requires a collected GitHub snapshot")
    if item["kind"] == "review_body":
        review_id = data["review_id"]
        if (
            not review_id
            or review_id not in snapshot["reviews_by_id"]
            or item["source_key"] != f"review-body:{review_id}"
            or data["thread_id"] is not None
            or data["comment_ids"]
            or data["path"] is not None
            or data["is_outdated"]
        ):
            raise StateError(f"{field} does not match its GitHub review identity")
        actionable = review_id in snapshot["actionable_review_body_ids"]
    else:
        thread_id = data["thread_id"]
        if not thread_id or thread_id not in snapshot["threads_by_id"]:
            raise StateError(f"{field} references an unknown GitHub thread")
        thread = snapshot["threads_by_id"][thread_id]
        if data["review_id"] != thread["review_id"]:
            raise StateError(f"{field} review identity does not match its GitHub thread")
        comment_ids = {comment["id"] for comment in thread["comments"]}
        if any(comment_id not in comment_ids for comment_id in data["comment_ids"]):
            raise StateError(f"{field} references an unknown GitHub comment")
        if item["kind"] == "inline_thread":
            if (
                item["source_key"] != f"thread:{thread_id}"
                or not data["comment_ids"]
            ):
                raise StateError(f"{field} does not match its GitHub thread identity")
            actionable = (
                thread_id in snapshot["current_thread_ids"] and not thread["is_resolved"]
            )
        elif item["kind"] == "thread_sub_item":
            if len(data["comment_ids"]) != 1:
                raise StateError(f"{field} thread sub-item must reference exactly one reply")
            comment_id = data["comment_ids"][0]
            if item["source_key"] != f"reply:{thread_id}:{comment_id}":
                raise StateError(f"{field} does not match its GitHub reply identity")
            actionable = (
                thread_id in snapshot["current_thread_ids"]
                and not thread["is_resolved"]
                and comment_id in snapshot["actionable_reply_ids"]
            )
        else:
            raise StateError(f"{field}.kind does not match a GitHub Source")
    expected_state = "unresolved" if actionable else "resolved_out_of_scope"
    if item["source_state"] != expected_state:
        raise StateError(f"{field}.source_state does not match current Source actionability")


def validate_proposal(value: Any, item: dict[str, Any], field: str) -> Optional[dict[str, Any]]:
    if value is None:
        return None
    proposal = require_object(
        value,
        {"id", "generation", "choices_by_id", "choice_order", "recommended_choice_id", "action_envelope", "decision_fingerprint"},
        field,
    )
    canonical_uuid(proposal["id"], f"{field}.id")
    require_int(proposal["generation"], f"{field}.generation", minimum=1)
    if not isinstance(proposal["choices_by_id"], dict) or not proposal["choices_by_id"]:
        raise StateError(f"{field}.choices_by_id must be a non-empty object")
    for choice_id, choice_value in proposal["choices_by_id"].items():
        require_string(choice_id, f"{field}.choice key", allow_empty=False)
        choice = require_object(
            choice_value,
            {"id", "label", "tradeoff", "semantic_action"},
            f"{field}.choices_by_id[{choice_id}]",
        )
        if choice["id"] != choice_id:
            raise StateError(f"{field}.choices_by_id[{choice_id}].id must match its key")
        require_string(choice["label"], f"{field}.choices_by_id[{choice_id}].label")
        require_string(choice["tradeoff"], f"{field}.choices_by_id[{choice_id}].tradeoff")
        validate_semantic_action(
            choice["semantic_action"], f"{field}.choices_by_id[{choice_id}].semantic_action"
        )
    order = require_string_list(proposal["choice_order"], f"{field}.choice_order")
    if set(order) != set(proposal["choices_by_id"]):
        raise StateError(f"{field}.choice_order must contain every choice exactly once")
    recommended = require_string(
        proposal["recommended_choice_id"], f"{field}.recommended_choice_id", allow_empty=False
    )
    if recommended not in proposal["choices_by_id"]:
        raise StateError(f"{field}.recommended_choice_id is unknown")
    envelope = validate_action_envelope(proposal["action_envelope"], f"{field}.action_envelope")
    for choice_id, choice in proposal["choices_by_id"].items():
        semantic = choice["semantic_action"]
        for change in semantic["local_changes"]:
            if change["area"] not in envelope["allowed_areas"]:
                raise StateError(f"choice {choice_id} local area is outside the action envelope")
            if change["change_kind"] not in envelope["allowed_change_kinds"]:
                raise StateError(f"choice {choice_id} change kind is outside the action envelope")
            if (
                change["change_kind"] in REPOSITORY_ACTIONS
                and change["change_kind"] not in envelope["repository_actions"]
            ):
                raise StateError(
                    f"choice {choice_id} repository action is not explicitly authorized"
                )
        allowed_platform = {fingerprint(action) for action in envelope["platform_actions"]}
        if any(fingerprint(action) not in allowed_platform for action in semantic["platform_actions"]):
            raise StateError(f"choice {choice_id} platform action is outside the action envelope")
    decision_fingerprint = require_string(
        proposal["decision_fingerprint"], f"{field}.decision_fingerprint", allow_empty=False
    )
    if not SHA256_RE.fullmatch(decision_fingerprint):
        raise StateError(f"{field}.decision_fingerprint must be a SHA-256 value")
    if item["evidence"]["current_version"] is None:
        raise StateError(f"{field} requires current Evidence")
    expected = fingerprint(decision_projection(item, proposal))
    if expected != decision_fingerprint:
        raise StateError(f"{field}.decision_fingerprint does not match its semantic projection")
    return proposal


def validate_evidence(value: Any, field: str) -> dict[str, Any]:
    evidence = require_object(
        value,
        {"current_version", "current_status", "versions", "evaluations", "last_diff"},
        field,
    )
    current_version = evidence["current_version"]
    if current_version is not None:
        require_int(current_version, f"{field}.current_version", minimum=1)
    current_status = require_string(evidence["current_status"], f"{field}.current_status")
    if current_status not in {"valid", "stale"}:
        raise StateError(f"{field}.current_status is invalid")
    require_string(evidence["last_diff"], f"{field}.last_diff")
    if not isinstance(evidence["versions"], list):
        raise StateError(f"{field}.versions must be an array")
    valid_versions = 0
    version_ids = set()
    for index, version_value in enumerate(evidence["versions"], start=1):
        version = require_object(
            version_value,
            {
                "id",
                "version",
                "fingerprint",
                "status",
                "semantic",
                "created_at",
                "invalidated_at",
                "invalidation_reason",
            },
            f"{field}.versions[{index - 1}]",
        )
        version_id = canonical_uuid(version["id"], f"{field}.versions[{index - 1}].id")
        if version_id in version_ids:
            raise StateError(f"{field}.Evidence IDs must be unique")
        version_ids.add(version_id)
        if version["version"] != index:
            raise StateError(f"{field}.versions must be monotonically numbered")
        validate_evidence_semantic(version["semantic"], f"{field}.versions[{index - 1}].semantic")
        require_string(version["fingerprint"], f"{field}.versions[{index - 1}].fingerprint")
        if not SHA256_RE.fullmatch(version["fingerprint"]):
            raise StateError(f"{field}.versions[{index - 1}].fingerprint is invalid")
        status_value = require_string(version["status"], f"{field}.versions[{index - 1}].status")
        if status_value == "valid":
            valid_versions += 1
            if version["invalidated_at"] is not None or version["invalidation_reason"] is not None:
                raise StateError(f"{field}.valid Evidence must not have invalidation metadata")
        elif status_value == "invalid":
            require_string(
                version["invalidated_at"],
                f"{field}.versions[{index - 1}].invalidated_at",
                allow_empty=False,
            )
            require_string(
                version["invalidation_reason"],
                f"{field}.versions[{index - 1}].invalidation_reason",
                allow_empty=False,
            )
        else:
            raise StateError(f"{field}.versions[{index - 1}].status is invalid")
        require_string(version["created_at"], f"{field}.versions[{index - 1}].created_at")
    if current_version is None:
        if evidence["versions"] or current_status != "stale":
            raise StateError(f"{field} without a version must be stale and empty")
    else:
        if current_version != len(evidence["versions"]) or valid_versions != 1:
            raise StateError(f"{field} must have exactly one current valid version")
        if evidence["versions"][-1]["status"] != "valid":
            raise StateError(f"{field} current version must be valid")
    if not isinstance(evidence["evaluations"], list):
        raise StateError(f"{field}.evaluations must be an array")
    seen = set()
    current_generation = 0
    current_proposal_id = None
    current_decision_fingerprint = None
    stale_boundary = False
    for index, evaluation_value in enumerate(evidence["evaluations"]):
        evaluation = require_object(
            evaluation_value,
            {
                "id",
                "from_version",
                "to_version",
                "result",
                "reason",
                "diff",
                "proposal_id",
                "proposal_generation",
                "decision_fingerprint",
                "created_at",
            },
            f"{field}.evaluations[{index}]",
        )
        evaluation_id = canonical_uuid(evaluation["id"], f"{field}.evaluations[{index}].id")
        if evaluation_id in seen:
            raise StateError(f"{field}.evaluations IDs must be unique")
        seen.add(evaluation_id)
        for key in ("from_version", "to_version"):
            value = evaluation[key]
            if value is not None:
                require_int(value, f"{field}.evaluations[{index}].{key}", minimum=1)
        if evaluation["result"] not in {"initial", "same", "changed", "unverified"}:
            raise StateError(f"{field}.evaluations[{index}].result is invalid")
        proposal_id = evaluation["proposal_id"]
        if proposal_id is not None:
            proposal_id = canonical_uuid(
                proposal_id, f"{field}.evaluations[{index}].proposal_id"
            )
        proposal_generation = require_int(
            evaluation["proposal_generation"],
            f"{field}.evaluations[{index}].proposal_generation",
            minimum=0,
        )
        decision_fingerprint = evaluation["decision_fingerprint"]
        if decision_fingerprint is not None and not SHA256_RE.fullmatch(
            require_string(
                decision_fingerprint,
                f"{field}.evaluations[{index}].decision_fingerprint",
                allow_empty=False,
            )
        ):
            raise StateError(f"{field}.evaluations[{index}].decision_fingerprint is invalid")
        result = evaluation["result"]
        if result == "unverified":
            if (
                proposal_generation != current_generation
                or proposal_id != current_proposal_id
                or decision_fingerprint != current_decision_fingerprint
            ):
                raise StateError(f"{field}.evaluations[{index}] stale generation is invalid")
            stale_boundary = True
        else:
            if result == "initial" and current_generation != 0:
                raise StateError(f"{field}.evaluations[{index}] initial result is invalid")
            if result in {"same", "changed"} and current_generation == 0:
                raise StateError(f"{field}.evaluations[{index}] requires prior Evidence")
            advances = (
                current_generation == 0
                or stale_boundary
                or decision_fingerprint != current_decision_fingerprint
            )
            expected_generation = current_generation + 1 if advances else current_generation
            if proposal_generation != expected_generation or proposal_id is None:
                raise StateError(f"{field}.evaluations[{index}] proposal generation is invalid")
            if advances == (proposal_id == current_proposal_id):
                raise StateError(f"{field}.evaluations[{index}] proposal ID generation is invalid")
            current_generation = proposal_generation
            current_proposal_id = proposal_id
            current_decision_fingerprint = decision_fingerprint
            stale_boundary = False
        for key in ("reason", "diff", "created_at"):
            require_string(evaluation[key], f"{field}.evaluations[{index}].{key}")
    if current_status == "valid" and (stale_boundary or current_proposal_id is None):
        raise StateError(f"{field} valid Evidence requires a current proposal generation")
    return evidence


def validate_remote_mutation(value: Any, field: str) -> dict[str, Any]:
    journal = require_object(value, {"id", "action", "attempts", "created_at"}, field)
    canonical_uuid(journal["id"], f"{field}.id")
    validate_platform_action(journal["action"], f"{field}.action")
    require_string(journal["created_at"], f"{field}.created_at")
    if not isinstance(journal["attempts"], list) or not journal["attempts"]:
        raise StateError(f"{field}.attempts must be a non-empty array")
    attempts_by_id = {}
    authorization_ids = set()
    for index, attempt_value in enumerate(journal["attempts"]):
        attempt = require_object(
            attempt_value,
            {
                "id",
                "status",
                "created_at",
                "started_at",
                "finished_at",
                "summary",
                "confirmed_not_applied",
                "authorization_id",
                "decision_fingerprint",
                "action_fingerprint",
                "adopted_from_attempt_id",
            },
            f"{field}.attempts[{index}]",
        )
        attempt_id = canonical_uuid(attempt["id"], f"{field}.attempts[{index}].id")
        if attempt_id in attempts_by_id:
            raise StateError(f"{field}.attempt IDs must be unique")
        status_value = require_string(attempt["status"], f"{field}.attempts[{index}].status")
        if status_value not in REMOTE_STATUSES:
            raise StateError(f"{field}.attempts[{index}].status is invalid")
        require_string(
            attempt["created_at"], f"{field}.attempts[{index}].created_at", allow_empty=False
        )
        started_at = require_optional_string(
            attempt["started_at"], f"{field}.attempts[{index}].started_at"
        )
        finished_at = require_optional_string(
            attempt["finished_at"], f"{field}.attempts[{index}].finished_at"
        )
        summary = require_string(attempt["summary"], f"{field}.attempts[{index}].summary")
        confirmed = require_bool(
            attempt["confirmed_not_applied"],
            f"{field}.attempts[{index}].confirmed_not_applied",
        )
        authorization_id = canonical_uuid(
            attempt["authorization_id"], f"{field}.attempts[{index}].authorization_id"
        )
        if authorization_id in authorization_ids:
            raise StateError(f"{field}.attempt authorization IDs must be unique")
        authorization_ids.add(authorization_id)
        for key in ("decision_fingerprint", "action_fingerprint"):
            if not SHA256_RE.fullmatch(
                require_string(attempt[key], f"{field}.attempts[{index}].{key}", allow_empty=False)
            ):
                raise StateError(f"{field}.attempts[{index}].{key} is invalid")
        if attempt["action_fingerprint"] != fingerprint(journal["action"]):
            raise StateError(f"{field}.attempts[{index}] action fingerprint is stale")
        adopted_from = attempt["adopted_from_attempt_id"]
        if adopted_from is not None:
            canonical_uuid(
                adopted_from, f"{field}.attempts[{index}].adopted_from_attempt_id"
            )
            if status_value != "succeeded" or started_at is not None or not finished_at or not summary or confirmed:
                raise StateError(f"{field}.attempts[{index}] adopted success is invalid")
        elif index > 0 and journal["attempts"][index - 1]["status"] != "failed":
            raise StateError(f"{field} can retry only after a failed attempt")
        elif status_value == "pending":
            if started_at is not None or finished_at is not None or summary or confirmed:
                raise StateError(f"{field}.pending attempt has invalid execution metadata")
        elif status_value == "in_progress":
            if not started_at or finished_at is not None or summary or confirmed:
                raise StateError(f"{field}.in_progress attempt has invalid execution metadata")
        elif status_value in {"succeeded", "uncertain"}:
            if not started_at or not finished_at or not summary or confirmed:
                raise StateError(f"{field}.{status_value} attempt has invalid execution metadata")
        elif status_value == "failed" and (
            not finished_at or not summary or not confirmed
        ):
            raise StateError(f"{field}.failed attempt must be confirmed not applied")
        attempts_by_id[attempt_id] = attempt
    return journal


def validate_item(item_value: Any, state: dict[str, Any], field: str) -> dict[str, Any]:
    item = require_object(
        item_value,
        {
            "id",
            "source_id",
            "source_key",
            "kind",
            "source_state",
            "source_data",
            "presentation",
            "evidence",
            "proposal",
            "active_authorization",
            "authorization_history",
            "decision_history",
            "local_progress",
            "local_attempt_history",
            "remote_mutations",
            "created_at",
            "updated_at",
        },
        field,
    )
    item_id = canonical_uuid(item["id"], f"{field}.id")
    if item_id != field.rsplit("[", 1)[-1].rstrip("]"):
        raise StateError(f"{field}.id must match its map key")
    if item["source_id"] != state["source"]["id"]:
        raise StateError(f"{field}.source_id does not match the Session Source")
    require_string(item["source_key"], f"{field}.source_key", allow_empty=False)
    if item["kind"] not in {"inline_thread", "thread_sub_item", "review_body", "pasted_feedback"}:
        raise StateError(f"{field}.kind is invalid")
    if item["source_state"] not in {"unresolved", "resolved_out_of_scope", "copied"}:
        raise StateError(f"{field}.source_state is invalid")
    validate_source_data(item["source_data"], f"{field}.source_data")
    validate_item_source_contract(item, state, field)
    validate_presentation(item["presentation"], f"{field}.presentation")
    evidence = validate_evidence(item["evidence"], f"{field}.evidence")
    for index, version in enumerate(evidence["versions"]):
        expected = fingerprint(
            evidence_projection(item, version["semantic"], version["version"], version["id"])
        )
        if expected != version["fingerprint"]:
            raise StateError(f"{field}.evidence.versions[{index}].fingerprint is invalid")
    proposal = validate_proposal(item["proposal"], item, f"{field}.proposal")
    latest_evaluation = evidence["evaluations"][-1] if evidence["evaluations"] else None
    if proposal is None:
        if latest_evaluation is not None and latest_evaluation["proposal_id"] is not None:
            raise StateError(f"{field}.proposal is missing for its Evidence generation")
    elif latest_evaluation is None or (
        latest_evaluation["proposal_id"] != proposal["id"]
        or latest_evaluation["proposal_generation"] != proposal["generation"]
        or latest_evaluation["decision_fingerprint"] != proposal["decision_fingerprint"]
    ):
        raise StateError(f"{field}.proposal does not match its Evidence generation")
    authorization = item["active_authorization"]
    authorization_ids = set()
    authorizations = []
    if authorization is not None:
        authorization = require_object(
            authorization,
            {
                "id",
                "request_id",
                "decision_id",
                "item_id",
                "proposal_generation",
                "decision_fingerprint",
                "choice_id",
                "action_envelope",
                "created_at",
            },
            f"{field}.active_authorization",
        )
        for key in ("id", "request_id", "decision_id"):
            canonical_uuid(authorization[key], f"{field}.active_authorization.{key}")
        require_int(
            authorization["proposal_generation"],
            f"{field}.active_authorization.proposal_generation",
            minimum=1,
        )
        authorization_ids.add(authorization["id"])
        authorizations.append(authorization)
        if authorization["item_id"] != item_id:
            raise StateError(f"{field}.active_authorization.item_id is invalid")
        if proposal is None or authorization["decision_fingerprint"] != proposal["decision_fingerprint"]:
            raise StateError(f"{field}.active_authorization is stale")
        if authorization["choice_id"] not in proposal["choices_by_id"]:
            raise StateError(f"{field}.active_authorization.choice_id is invalid")
        if authorization["action_envelope"] != proposal["action_envelope"]:
            raise StateError(f"{field}.active_authorization.action_envelope is stale")
        validate_action_envelope(
            authorization["action_envelope"], f"{field}.active_authorization.action_envelope"
        )
        require_string(
            authorization["created_at"],
            f"{field}.active_authorization.created_at",
            allow_empty=False,
        )
        if evidence["current_status"] != "valid":
            raise StateError(f"{field}.active_authorization requires valid Evidence")
        if (
            state["lifecycle"] != "active"
            or state["source"]["status"] != "ready"
            or item["source_state"] == "resolved_out_of_scope"
        ):
            raise StateError(f"{field}.active_authorization is not executable")
    if not isinstance(item["authorization_history"], list):
        raise StateError(f"{field}.authorization_history must be an array")
    for index, archived_value in enumerate(item["authorization_history"]):
        archived = require_object(
            archived_value,
            {
                "id",
                "request_id",
                "decision_id",
                "item_id",
                "proposal_generation",
                "decision_fingerprint",
                "choice_id",
                "action_envelope",
                "created_at",
                "ended_at",
                "reason",
            },
            f"{field}.authorization_history[{index}]",
        )
        for key in ("id", "request_id", "decision_id"):
            canonical_uuid(archived[key], f"{field}.authorization_history[{index}].{key}")
        require_int(
            archived["proposal_generation"],
            f"{field}.authorization_history[{index}].proposal_generation",
            minimum=1,
        )
        if archived["id"] in authorization_ids:
            raise StateError(f"{field}.authorization IDs must be unique")
        authorization_ids.add(archived["id"])
        authorizations.append(archived)
        if archived["item_id"] != item_id:
            raise StateError(f"{field}.authorization_history[{index}].item_id is invalid")
        if not SHA256_RE.fullmatch(
            require_string(
                archived["decision_fingerprint"],
                f"{field}.authorization_history[{index}].decision_fingerprint",
            )
        ):
            raise StateError(f"{field}.authorization_history[{index}] fingerprint is invalid")
        require_string(
            archived["choice_id"],
            f"{field}.authorization_history[{index}].choice_id",
            allow_empty=False,
        )
        for key in ("created_at", "ended_at", "reason"):
            require_string(
                archived[key],
                f"{field}.authorization_history[{index}].{key}",
                allow_empty=False,
            )
        validate_action_envelope(
            archived["action_envelope"], f"{field}.authorization_history[{index}].action_envelope"
        )
    if not isinstance(item["decision_history"], list):
        raise StateError(f"{field}.decision_history must be an array")
    decisions_by_id = {}
    proposal_generations = {
        (
            evaluation["proposal_id"],
            evaluation["proposal_generation"],
            evaluation["decision_fingerprint"],
        )
        for evaluation in evidence["evaluations"]
        if evaluation["proposal_id"] is not None
    }
    for index, decision_value in enumerate(item["decision_history"]):
        decision = require_object(
            decision_value,
            {
                "id",
                "request_id",
                "item_id",
                "proposal_id",
                "proposal_generation",
                "decision_fingerprint",
                "choice_id",
                "authorization_id",
                "recorded_at",
            },
            f"{field}.decision_history[{index}]",
        )
        for key in ("id", "request_id", "authorization_id", "proposal_id"):
            canonical_uuid(decision[key], f"{field}.decision_history[{index}].{key}")
        require_int(
            decision["proposal_generation"],
            f"{field}.decision_history[{index}].proposal_generation",
            minimum=1,
        )
        if decision["id"] in decisions_by_id:
            raise StateError(f"{field}.decision IDs must be unique")
        decisions_by_id[decision["id"]] = decision
        if decision["item_id"] != item_id:
            raise StateError(f"{field}.decision_history[{index}].item_id is invalid")
        if (
            decision["proposal_id"],
            decision["proposal_generation"],
            decision["decision_fingerprint"],
        ) not in proposal_generations:
            raise StateError(
                f"{field}.decision_history[{index}] references an unknown proposal generation"
            )
        if not SHA256_RE.fullmatch(
            require_string(
                decision["decision_fingerprint"],
                f"{field}.decision_history[{index}].decision_fingerprint",
            )
        ):
            raise StateError(f"{field}.decision_history[{index}] fingerprint is invalid")
        require_string(
            decision["choice_id"],
            f"{field}.decision_history[{index}].choice_id",
            allow_empty=False,
        )
        require_string(
            decision["recorded_at"],
            f"{field}.decision_history[{index}].recorded_at",
            allow_empty=False,
        )
    for authorization_entry in authorizations:
        decision = decisions_by_id.get(authorization_entry["decision_id"])
        if decision is None:
            raise StateError(f"{field}.authorization references an unknown decision")
        if (
            decision["authorization_id"] != authorization_entry["id"]
            or decision["request_id"] != authorization_entry["request_id"]
            or decision["decision_fingerprint"]
            != authorization_entry["decision_fingerprint"]
            or decision["choice_id"] != authorization_entry["choice_id"]
            or decision["proposal_generation"]
            != authorization_entry["proposal_generation"]
        ):
            raise StateError(f"{field}.authorization does not match its decision")
    if authorization is not None and (
        decisions_by_id[authorization["decision_id"]]["proposal_id"] != proposal["id"]
        or authorization["proposal_generation"] != proposal["generation"]
    ):
        raise StateError(f"{field}.active authorization belongs to an older proposal")
    if len(item["presentation"]["code_locations"]) != (
        len(evidence["versions"][evidence["current_version"] - 1]["semantic"]["code"])
        if evidence["current_version"] is not None
        else 0
    ):
        raise StateError(f"{field}.presentation.code_locations must match current Evidence code")
    progress = require_object(
        item["local_progress"],
        {"status", "started_at", "completed_at", "area", "change_kind", "validation_summary", "authorization_id"},
        f"{field}.local_progress",
    )
    if progress["status"] not in LOCAL_STATUSES:
        raise StateError(f"{field}.local_progress.status is invalid")
    for key in ("started_at", "completed_at", "area", "change_kind", "authorization_id"):
        require_optional_string(progress[key], f"{field}.local_progress.{key}")
    require_string(progress["validation_summary"], f"{field}.local_progress.validation_summary")
    if progress["status"] == "not_started" and any(
        progress[key] is not None for key in ("started_at", "completed_at", "area", "change_kind", "authorization_id")
    ):
        raise StateError(f"{field}.not_started local progress has execution metadata")
    if progress["status"] == "in_progress" and (
        not progress["started_at"]
        or progress["completed_at"] is not None
        or not progress["area"]
        or not progress["change_kind"]
        or not progress["authorization_id"]
        or progress["validation_summary"]
    ):
        raise StateError(f"{field}.in_progress local progress is invalid")
    if progress["status"] == "completed" and (
        not progress["started_at"]
        or not progress["completed_at"]
        or not progress["area"]
        or not progress["change_kind"]
        or not progress["authorization_id"]
        or not progress["validation_summary"]
    ):
        raise StateError(f"{field}.completed local progress is invalid")
    if progress["authorization_id"] is not None:
        canonical_uuid(progress["authorization_id"], f"{field}.local_progress.authorization_id")
        progress_authorization = next(
            (entry for entry in authorizations if entry["id"] == progress["authorization_id"]),
            None,
        )
        if progress_authorization is None:
            raise StateError(f"{field}.local_progress references unknown authorization")
        if (
            progress["area"] not in progress_authorization["action_envelope"]["allowed_areas"]
            or progress["change_kind"]
            not in progress_authorization["action_envelope"]["allowed_change_kinds"]
        ):
            raise StateError(f"{field}.local_progress is outside its authorization")
    if not isinstance(item["local_attempt_history"], list):
        raise StateError(f"{field}.local_attempt_history must be an array")
    for index, attempt_value in enumerate(item["local_attempt_history"]):
        attempt = require_object(
            attempt_value,
            {"status", "started_at", "completed_at", "area", "change_kind", "validation_summary", "authorization_id", "reason", "ended_at"},
            f"{field}.local_attempt_history[{index}]",
        )
        if attempt["status"] not in {"completed", "superseded"}:
            raise StateError(f"{field}.local_attempt_history[{index}].status is invalid")
        for key in ("started_at", "area", "change_kind", "authorization_id", "reason", "ended_at"):
            require_string(attempt[key], f"{field}.local_attempt_history[{index}].{key}", allow_empty=False)
        canonical_uuid(attempt["authorization_id"], f"{field}.local_attempt_history[{index}].authorization_id")
        attempt_authorization = next(
            (entry for entry in authorizations if entry["id"] == attempt["authorization_id"]),
            None,
        )
        if attempt_authorization is None:
            raise StateError(f"{field}.local_attempt_history[{index}] references unknown authorization")
        if (
            attempt["area"] not in attempt_authorization["action_envelope"]["allowed_areas"]
            or attempt["change_kind"]
            not in attempt_authorization["action_envelope"]["allowed_change_kinds"]
        ):
            raise StateError(f"{field}.local_attempt_history[{index}] is outside its authorization")
        require_optional_string(attempt["completed_at"], f"{field}.local_attempt_history[{index}].completed_at")
        require_string(attempt["validation_summary"], f"{field}.local_attempt_history[{index}].validation_summary")
        if attempt["status"] == "completed" and (not attempt["completed_at"] or not attempt["validation_summary"]):
            raise StateError(f"{field}.local_attempt_history[{index}] completed attempt is invalid")
    if not isinstance(item["remote_mutations"], list):
        raise StateError(f"{field}.remote_mutations must be an array")
    authorizations_by_id = {entry["id"]: entry for entry in authorizations}
    journal_ids = set()
    attempt_ids = set()
    action_keys = set()
    effect_actual_journals: dict[str, str] = {}
    attempt_entries: dict[str, tuple[int, dict[str, Any], dict[str, Any]]] = {}
    attempt_order = 0
    for index, journal in enumerate(item["remote_mutations"]):
        validate_remote_mutation(journal, f"{field}.remote_mutations[{index}]")
        if journal["id"] in journal_ids:
            raise StateError(f"{field}.remote journal IDs must be unique")
        journal_ids.add(journal["id"])
        action_key = fingerprint(journal["action"])
        if action_key in action_keys:
            raise StateError(f"{field} must keep one journal per remote action")
        action_keys.add(action_key)
        effect_key = fingerprint(remote_effect_projection(journal["action"]))
        if any(attempt["adopted_from_attempt_id"] is None for attempt in journal["attempts"]):
            actual_journal_id = effect_actual_journals.get(effect_key)
            if actual_journal_id is not None and actual_journal_id != journal["id"]:
                raise StateError(f"{field} must keep one actual journal per remote effect")
            effect_actual_journals[effect_key] = journal["id"]
        for attempt in journal["attempts"]:
            if attempt["id"] in attempt_ids:
                raise StateError(f"{field}.remote attempt IDs must be unique")
            attempt_ids.add(attempt["id"])
            attempt_entries[attempt["id"]] = (attempt_order, journal, attempt)
            attempt_order += 1
            attempt_authorization = authorizations_by_id.get(attempt["authorization_id"])
            if attempt_authorization is None:
                raise StateError(f"{field}.remote attempt references unknown authorization")
            if (
                attempt["decision_fingerprint"]
                != attempt_authorization["decision_fingerprint"]
                or journal["action"]
                not in attempt_authorization["action_envelope"]["platform_actions"]
            ):
                raise StateError(f"{field}.remote attempt is outside its authorization")
    for _, journal, attempt in attempt_entries.values():
        source_attempt_id = attempt["adopted_from_attempt_id"]
        if source_attempt_id is None:
            continue
        source_entry = attempt_entries.get(source_attempt_id)
        if source_entry is None:
            raise StateError(f"{field}.remote adoption source is unknown")
        source_order, source_journal, source_attempt = source_entry
        current_order = attempt_entries[attempt["id"]][0]
        if (
            source_order >= current_order
            or source_attempt["status"] != "succeeded"
            or source_attempt["adopted_from_attempt_id"] is not None
            or remote_effect_projection(source_journal["action"])
            != remote_effect_projection(journal["action"])
        ):
            raise StateError(f"{field}.remote adoption source is invalid")
    require_string(item["created_at"], f"{field}.created_at")
    require_string(item["updated_at"], f"{field}.updated_at")
    return item


def validate_pagination(value: Any, field: str, thread_ids: Optional[set[str]] = None) -> bool:
    pagination = require_object(value, {"reviews", "threads", "comments"}, field)
    complete = True
    for key in ("reviews", "threads"):
        part = require_object(pagination[key], {"complete", "pages"}, f"{field}.{key}")
        part_complete = require_bool(part["complete"], f"{field}.{key}.complete")
        pages = require_int(part["pages"], f"{field}.{key}.pages", minimum=0)
        if part_complete and pages < 1:
            raise StateError(f"{field}.{key}.complete requires at least one fetched page")
        complete = part_complete and complete
    comments = require_object(
        pagination["comments"], {"complete", "pages_by_thread"}, f"{field}.comments"
    )
    complete = require_bool(comments["complete"], f"{field}.comments.complete") and complete
    if not isinstance(comments["pages_by_thread"], dict):
        raise StateError(f"{field}.comments.pages_by_thread must be an object")
    for thread_id, pages in comments["pages_by_thread"].items():
        require_string(thread_id, f"{field}.comments.pages_by_thread key", allow_empty=False)
        require_int(pages, f"{field}.comments.pages_by_thread[{thread_id}]", minimum=1)
    if thread_ids is not None and set(comments["pages_by_thread"]) != thread_ids:
        raise StateError(f"{field}.comments.pages_by_thread must cover every collected thread")
    return complete


def validate_github_identity(value: Any, field: str) -> dict[str, Any]:
    identity = require_object(value, {"host", "owner", "repo", "pr_number"}, field)
    canonical_host(identity["host"])
    canonical_repo_part(identity["owner"], f"{field}.owner")
    canonical_repo_part(identity["repo"], f"{field}.repo")
    require_int(identity["pr_number"], f"{field}.pr_number", minimum=1)
    return identity


def validate_github_snapshot(value: Any, field: str) -> dict[str, Any]:
    snapshot = require_object(
        value,
        {
            "head_ref_oid",
            "base_ref_oid",
            "reviews_by_id",
            "threads_by_id",
            "current_thread_ids",
            "actionable_reply_ids",
            "actionable_review_body_ids",
        },
        field,
    )
    require_string(snapshot["head_ref_oid"], f"{field}.head_ref_oid", allow_empty=False)
    require_optional_string(snapshot["base_ref_oid"], f"{field}.base_ref_oid")
    if not isinstance(snapshot["reviews_by_id"], dict):
        raise StateError(f"{field}.reviews_by_id must be an object")
    for review_id, review_value in snapshot["reviews_by_id"].items():
        review = require_object(review_value, {"id", "body", "author", "state"}, f"{field}.reviews_by_id[{review_id}]")
        if review["id"] != review_id:
            raise StateError(f"{field}.reviews_by_id key must match review.id")
        for key in ("id", "body", "author", "state"):
            require_string(review[key], f"{field}.reviews_by_id[{review_id}].{key}")
    if not isinstance(snapshot["threads_by_id"], dict):
        raise StateError(f"{field}.threads_by_id must be an object")
    all_comments = set()
    for thread_id, thread_value in snapshot["threads_by_id"].items():
        thread = require_object(
            thread_value,
            {"id", "is_resolved", "is_outdated", "review_id", "comments"},
            f"{field}.threads_by_id[{thread_id}]",
        )
        if thread["id"] != thread_id:
            raise StateError(f"{field}.threads_by_id key must match thread.id")
        require_bool(thread["is_resolved"], f"{field}.threads_by_id[{thread_id}].is_resolved")
        require_bool(thread["is_outdated"], f"{field}.threads_by_id[{thread_id}].is_outdated")
        review_id = require_string(
            thread["review_id"], f"{field}.threads_by_id[{thread_id}].review_id", allow_empty=False
        )
        if review_id not in snapshot["reviews_by_id"]:
            raise StateError(f"{field}.threads_by_id[{thread_id}].review_id is missing")
        if not isinstance(thread["comments"], list) or not thread["comments"]:
            raise StateError(f"{field}.threads_by_id[{thread_id}].comments must be non-empty")
        for index, comment_value in enumerate(thread["comments"]):
            comment = require_object(
                comment_value,
                {
                    "id",
                    "body",
                    "author",
                    "path",
                    "line",
                    "start_line",
                    "original_line",
                    "created_at",
                },
                f"{field}.threads_by_id[{thread_id}].comments[{index}]",
            )
            comment_id = require_string(
                comment["id"],
                f"{field}.threads_by_id[{thread_id}].comments[{index}].id",
                allow_empty=False,
            )
            if comment_id in all_comments:
                raise StateError(f"{field} comment IDs must be globally unique")
            all_comments.add(comment_id)
            for key in ("body", "author", "path", "created_at"):
                require_string(comment[key], f"{field}.threads_by_id[{thread_id}].comments[{index}].{key}")
            for key in ("line", "start_line", "original_line"):
                line = comment[key]
                if line is not None:
                    require_int(line, f"{field}.threads_by_id[{thread_id}].comments[{index}].{key}", minimum=1)
    current_thread_ids = require_string_list(snapshot["current_thread_ids"], f"{field}.current_thread_ids")
    if any(thread_id not in snapshot["threads_by_id"] for thread_id in current_thread_ids):
        raise StateError(f"{field}.current_thread_ids contains an unknown thread")
    reply_ids = require_string_list(snapshot["actionable_reply_ids"], f"{field}.actionable_reply_ids")
    if any(reply_id not in all_comments for reply_id in reply_ids):
        raise StateError(f"{field}.actionable_reply_ids contains an unknown comment")
    review_ids = require_string_list(
        snapshot["actionable_review_body_ids"], f"{field}.actionable_review_body_ids"
    )
    if any(review_id not in snapshot["reviews_by_id"] for review_id in review_ids):
        raise StateError(f"{field}.actionable_review_body_ids contains an unknown review")
    current_ids = set(current_thread_ids)
    actionable_replies = set(reply_ids)
    unresolved_review_ids = set()
    for thread_id in current_ids:
        thread = snapshot["threads_by_id"][thread_id]
        if thread["is_resolved"]:
            continue
        unresolved_review_ids.add(thread["review_id"])
        reply_comment_ids = {comment["id"] for comment in thread["comments"][1:]}
        actionable_replies.difference_update(reply_comment_ids)
    if actionable_replies:
        raise StateError(f"{field}.actionable_reply_ids must be replies in unresolved current threads")
    if any(review_id not in unresolved_review_ids for review_id in review_ids):
        raise StateError(
            f"{field}.actionable_review_body_ids require an unresolved current thread"
        )
    return snapshot


def validate_source(value: Any, field: str) -> dict[str, Any]:
    source = require_object(
        value,
        {
            "id",
            "type",
            "identity",
            "status",
            "stale_reason",
            "snapshot",
            "collection",
            "created_at",
            "updated_at",
        },
        field,
    )
    canonical_uuid(source["id"], f"{field}.id")
    if source["type"] not in {"github_pr", "pasted_feedback"}:
        raise StateError(f"{field}.type is invalid")
    if source["status"] not in {"ready", "stale"}:
        raise StateError(f"{field}.status is invalid")
    stale_reason = require_string(source["stale_reason"], f"{field}.stale_reason")
    collection = require_object(
        source["collection"],
        {"status", "pagination", "errors", "collected_at"},
        f"{field}.collection",
    )
    if collection["status"] not in {"not_applicable", "never", "complete", "incomplete"}:
        raise StateError(f"{field}.collection.status is invalid")
    if not isinstance(collection["errors"], list):
        raise StateError(f"{field}.collection.errors must be an array")
    for index, error in enumerate(collection["errors"]):
        require_string(error, f"{field}.collection.errors[{index}]")
    collected_at = require_optional_string(
        collection["collected_at"], f"{field}.collection.collected_at"
    )
    if source["type"] == "github_pr":
        validate_github_identity(source["identity"], f"{field}.identity")
        if collection["status"] == "not_applicable":
            raise StateError(f"{field}.GitHub Source cannot use not_applicable collection")
        pagination_complete = False
        if collection["pagination"] is not None:
            pagination_complete = validate_pagination(
                collection["pagination"], f"{field}.collection.pagination"
            )
        if source["snapshot"] is not None:
            validate_github_snapshot(source["snapshot"], f"{field}.snapshot")
        if collection["status"] == "never":
            if (
                source["status"] != "stale"
                or not stale_reason
                or source["snapshot"] is not None
                or collection["pagination"] is not None
                or collection["errors"]
                or collected_at is not None
            ):
                raise StateError(f"{field}.uncollected GitHub Source is inconsistent")
        elif collection["status"] == "incomplete":
            if (
                source["status"] != "stale"
                or not stale_reason
                or collection["pagination"] is None
                or collected_at is None
                or (pagination_complete and not collection["errors"])
            ):
                raise StateError(f"{field}.incomplete GitHub Source is inconsistent")
        elif (
            source["status"] != "ready"
            or stale_reason
            or source["snapshot"] is None
            or collection["pagination"] is None
            or not pagination_complete
            or collection["errors"]
            or collected_at is None
        ):
            raise StateError(f"{field}.complete GitHub Source is inconsistent")
        if collection["status"] == "complete":
            validate_pagination(
                collection["pagination"],
                f"{field}.collection.pagination",
                set(source["snapshot"]["current_thread_ids"]),
            )
    else:
        identity = require_object(source["identity"], {"batch_id"}, f"{field}.identity")
        if identity["batch_id"] != source["id"]:
            raise StateError(f"{field}.identity.batch_id must match source.id")
        snapshot = require_object(source["snapshot"], {"batch_text", "item_source_keys"}, f"{field}.snapshot")
        require_string(snapshot["batch_text"], f"{field}.snapshot.batch_text")
        require_string_list(snapshot["item_source_keys"], f"{field}.snapshot.item_source_keys")
        if (
            source["status"] != "ready"
            or stale_reason
            or collection["status"] != "not_applicable"
            or collection["pagination"] is not None
            or collection["errors"]
            or collected_at is None
        ):
            raise StateError(f"{field}.pasted Source collection is inconsistent")
    require_string(source["created_at"], f"{field}.created_at")
    require_string(source["updated_at"], f"{field}.updated_at")
    return source


def validate_state(state_value: Any, expected_thread_id: Optional[str] = None) -> dict[str, Any]:
    state = require_object(
        state_value,
        {
            "schema_version",
            "owner",
            "revision",
            "lifecycle",
            "created_at",
            "updated_at",
            "output_locale",
            "source",
            "items",
            "item_order",
            "pending_request",
            "request_history",
        },
        "state",
    )
    if state["schema_version"] != SCHEMA_VERSION:
        raise StateError(f"unsupported schema_version: {state['schema_version']!r}")
    owner = require_object(state["owner"], {"thread_id"}, "state.owner")
    thread_id = canonical_uuid(owner["thread_id"], "state.owner.thread_id")
    if expected_thread_id is not None and thread_id != expected_thread_id:
        raise StateError("state owner.thread_id does not match --thread-id")
    require_int(state["revision"], "state.revision", minimum=1)
    if state["lifecycle"] not in {"active", "completed", "stopped"}:
        raise StateError("state.lifecycle is invalid")
    require_string(state["created_at"], "state.created_at")
    require_string(state["updated_at"], "state.updated_at")
    output_locale = require_string(state["output_locale"], "state.output_locale", allow_empty=False)
    if not LOCALE_RE.fullmatch(output_locale):
        raise StateError("state.output_locale is invalid")
    validate_source(state["source"], "state.source")
    if not isinstance(state["items"], dict):
        raise StateError("state.items must be an object")
    order = require_string_list(state["item_order"], "state.item_order")
    if set(order) != set(state["items"]):
        raise StateError("state.item_order must contain every Item exactly once")
    source_keys = set()
    for item_id, item_value in state["items"].items():
        canonical_uuid(item_id, "state.items key")
        item = validate_item(item_value, state, f"state.items[{item_id}]")
        if item["source_key"] in source_keys:
            raise StateError("state Item source_key values must be unique")
        source_keys.add(item["source_key"])
    if state["source"]["type"] == "pasted_feedback":
        if set(state["source"]["snapshot"]["item_source_keys"]) != source_keys:
            raise StateError("pasted Source item keys do not match Session Items")
    pending = state["pending_request"]
    if pending is not None:
        pending = require_object(
            pending,
            {
                "request_id",
                "item_id",
                "proposal_id",
                "proposal_generation",
                "decision_fingerprint",
                "choice_ids",
                "question",
                "created_at",
            },
            "state.pending_request",
        )
        canonical_uuid(pending["request_id"], "state.pending_request.request_id")
        canonical_uuid(pending["proposal_id"], "state.pending_request.proposal_id")
        require_int(
            pending["proposal_generation"],
            "state.pending_request.proposal_generation",
            minimum=1,
        )
        item_id = canonical_uuid(pending["item_id"], "state.pending_request.item_id")
        if item_id not in state["items"]:
            raise StateError("state.pending_request.item_id is unknown")
        item = state["items"][item_id]
        proposal = item["proposal"]
        if proposal is None or (
            pending["proposal_id"] != proposal["id"]
            or pending["proposal_generation"] != proposal["generation"]
            or pending["decision_fingerprint"] != proposal["decision_fingerprint"]
        ):
            raise StateError("state.pending_request is stale")
        choices = require_string_list(pending["choice_ids"], "state.pending_request.choice_ids")
        if set(choices) != set(proposal["choices_by_id"]):
            raise StateError("state.pending_request.choice_ids are stale")
        require_string(pending["question"], "state.pending_request.question", allow_empty=False)
        require_string(pending["created_at"], "state.pending_request.created_at", allow_empty=False)
        if item["evidence"]["current_status"] != "valid":
            raise StateError("state.pending_request requires valid Evidence")
        if (
            state["lifecycle"] != "active"
            or state["source"]["status"] != "ready"
            or item["source_state"] == "resolved_out_of_scope"
        ):
            raise StateError("state.pending_request is not eligible for a decision")
    if not isinstance(state["request_history"], list):
        raise StateError("state.request_history must be an array")
    seen_request_ids = set()
    if pending is not None:
        seen_request_ids.add(pending["request_id"])
    archived_requests = {}
    for index, archived_value in enumerate(state["request_history"]):
        archived = require_object(
            archived_value,
            {
                "request_id",
                "item_id",
                "proposal_id",
                "proposal_generation",
                "decision_fingerprint",
                "choice_ids",
                "question",
                "created_at",
                "status",
                "ended_at",
                "reason",
            },
            f"state.request_history[{index}]",
        )
        request_id = canonical_uuid(archived["request_id"], f"state.request_history[{index}].request_id")
        canonical_uuid(
            archived["proposal_id"], f"state.request_history[{index}].proposal_id"
        )
        require_int(
            archived["proposal_generation"],
            f"state.request_history[{index}].proposal_generation",
            minimum=1,
        )
        if request_id in seen_request_ids:
            raise StateError("state request IDs must never be reused")
        seen_request_ids.add(request_id)
        archived_requests[request_id] = archived
        item_id = canonical_uuid(
            archived["item_id"], f"state.request_history[{index}].item_id"
        )
        if item_id not in state["items"]:
            raise StateError(f"state.request_history[{index}].item_id is unknown")
        if not SHA256_RE.fullmatch(
            require_string(
                archived["decision_fingerprint"],
                f"state.request_history[{index}].decision_fingerprint",
            )
        ):
            raise StateError(f"state.request_history[{index}] fingerprint is invalid")
        require_string_list(
            archived["choice_ids"], f"state.request_history[{index}].choice_ids"
        )
        for key in ("question", "created_at", "ended_at", "reason"):
            require_string(
                archived[key],
                f"state.request_history[{index}].{key}",
                allow_empty=False,
            )
        if archived["status"] not in {"consumed", "invalidated"}:
            raise StateError(f"state.request_history[{index}].status is invalid")
    for item in state["items"].values():
        for decision in item["decision_history"]:
            request = archived_requests.get(decision["request_id"])
            if request is None or request["status"] != "consumed":
                raise StateError("state decision must reference a consumed request")
            if (
                request["item_id"] != item["id"]
                or request["proposal_id"] != decision["proposal_id"]
                or request["proposal_generation"] != decision["proposal_generation"]
                or request["decision_fingerprint"] != decision["decision_fingerprint"]
                or decision["choice_id"] not in request["choice_ids"]
            ):
                raise StateError("state decision does not match its consumed request")
    if state["lifecycle"] != "active" and pending is not None:
        raise StateError("terminal state cannot have a pending request")
    if state["lifecycle"] != "active":
        for item in state["items"].values():
            if item["active_authorization"] is not None:
                raise StateError("terminal state cannot have active authorization")
    encoded = canonical_json(state)
    if len(encoded) > MAX_JSON_BYTES:
        raise StateError("result state exceeds the 10 MiB limit")
    return state


def require_active_state(state: dict[str, Any]) -> None:
    if state["lifecycle"] != "active":
        raise StateError("operation requires an active Review Session")


def item_by_id(state: dict[str, Any], item_id: Any) -> dict[str, Any]:
    item_key = canonical_uuid(item_id, "candidate.item_id")
    try:
        return state["items"][item_key]
    except KeyError as error:
        raise StateError("candidate.item_id is unknown") from error


def active_authorization(state: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    require_active_state(state)
    if state["source"]["status"] != "ready":
        raise StateError("Source is stale; execution is blocked")
    if item["evidence"]["current_status"] != "valid":
        raise StateError("Evidence is stale; execution is blocked")
    authorization = item["active_authorization"]
    proposal = item["proposal"]
    if authorization is None or proposal is None:
        raise StateError("Item has no active authorization")
    if authorization["decision_fingerprint"] != proposal["decision_fingerprint"]:
        raise StateError("active authorization does not match the current decision fingerprint")
    return authorization


def op_update_item_analysis(
    state: dict[str, Any], candidate: dict[str, Any], timestamp: str
) -> None:
    require_object(
        candidate,
        {
            "op",
            "expected_revision",
            "item_id",
            "evidence",
            "reason",
            "diff",
            "presentation",
            "choices",
            "recommended_choice_id",
            "action_envelope",
        },
        "candidate",
    )
    require_active_state(state)
    if state["source"]["status"] != "ready":
        raise StateError("Source is stale; new valid Evidence is blocked")
    item = item_by_id(state, candidate["item_id"])
    semantic = validate_evidence_semantic(candidate["evidence"], "candidate.evidence")
    reason = require_string(candidate["reason"], "candidate.reason", allow_empty=False)
    diff = require_string(candidate["diff"], "candidate.diff")
    presentation = copy.deepcopy(validate_presentation(candidate["presentation"], "candidate.presentation"))
    if len(presentation["code_locations"]) != len(semantic["code"]):
        raise StateError("candidate.presentation.code_locations must match candidate.evidence.code")
    if not isinstance(candidate["choices"], list) or not candidate["choices"]:
        raise StateError("candidate.choices must be a non-empty array")
    choices_by_id = {}
    choice_order = []
    for index, choice_value in enumerate(candidate["choices"]):
        choice = require_object(
            choice_value,
            {"id", "label", "tradeoff", "semantic_action"},
            f"candidate.choices[{index}]",
        )
        choice_id = require_string(choice["id"], f"candidate.choices[{index}].id", allow_empty=False)
        if choice_id in choices_by_id:
            raise StateError("candidate.choices IDs must be unique")
        validate_semantic_action(choice["semantic_action"], f"candidate.choices[{index}].semantic_action")
        choices_by_id[choice_id] = copy.deepcopy(choice)
        choice_order.append(choice_id)
    recommended = require_string(
        candidate["recommended_choice_id"], "candidate.recommended_choice_id", allow_empty=False
    )
    if recommended not in choices_by_id:
        raise StateError("candidate.recommended_choice_id is unknown")
    envelope = copy.deepcopy(validate_action_envelope(candidate["action_envelope"], "candidate.action_envelope"))
    evidence = item["evidence"]
    evidence_was_stale = evidence["current_status"] != "valid"
    old_version = evidence["current_version"]
    semantic_fingerprint = fingerprint(semantic)
    old_semantic_fingerprint = None
    if old_version is not None:
        old_semantic_fingerprint = fingerprint(evidence["versions"][old_version - 1]["semantic"])
    if old_version is None:
        version_number = 1
        evidence_id = new_id(version["id"] for version in evidence["versions"])
        version = {
            "id": evidence_id,
            "version": version_number,
            "fingerprint": fingerprint(evidence_projection(item, semantic, version_number, evidence_id)),
            "status": "valid",
            "semantic": copy.deepcopy(semantic),
            "created_at": timestamp,
            "invalidated_at": None,
            "invalidation_reason": None,
        }
        evidence["versions"].append(version)
        result = "initial"
    elif semantic_fingerprint == old_semantic_fingerprint:
        version_number = old_version
        result = "same"
    else:
        previous = evidence["versions"][old_version - 1]
        if previous["status"] != "valid":
            raise StateError("current Evidence version is not valid")
        previous["status"] = "invalid"
        previous["invalidated_at"] = timestamp
        previous["invalidation_reason"] = reason
        version_number = old_version + 1
        evidence_id = new_id(version["id"] for version in evidence["versions"])
        evidence["versions"].append(
            {
                "id": evidence_id,
                "version": version_number,
                "fingerprint": fingerprint(evidence_projection(item, semantic, version_number, evidence_id)),
                "status": "valid",
                "semantic": copy.deepcopy(semantic),
                "created_at": timestamp,
                "invalidated_at": None,
                "invalidation_reason": None,
            }
        )
        result = "changed"
    evidence["current_version"] = version_number
    evidence["current_status"] = "valid"
    evidence["last_diff"] = diff
    proposal = {
        "id": "00000000-0000-0000-0000-000000000000",
        "generation": 0,
        "choices_by_id": choices_by_id,
        "choice_order": choice_order,
        "recommended_choice_id": recommended,
        "action_envelope": envelope,
        "decision_fingerprint": "0" * 64,
    }
    proposal["decision_fingerprint"] = fingerprint(decision_projection(item, proposal))
    old_proposal = item["proposal"]
    old_fingerprint = old_proposal["decision_fingerprint"] if old_proposal else None
    old_generation = old_proposal["generation"] if old_proposal else 0
    proposal["generation"] = (
        old_generation + 1
        if old_proposal is None
        or evidence_was_stale
        or old_fingerprint != proposal["decision_fingerprint"]
        else old_generation
    )
    proposal["id"] = (
        old_proposal["id"]
        if proposal["generation"] == old_generation
        else new_id(
            ([old_proposal["id"]] if old_proposal else [])
            + [decision["proposal_id"] for decision in item["decision_history"]]
        )
    )
    evidence["evaluations"].append(
        {
            "id": new_id(entry["id"] for entry in evidence["evaluations"]),
            "from_version": old_version,
            "to_version": version_number,
            "result": result,
            "reason": reason,
            "diff": diff,
            "proposal_id": proposal["id"],
            "proposal_generation": proposal["generation"],
            "decision_fingerprint": proposal["decision_fingerprint"],
            "created_at": timestamp,
        }
    )
    if old_fingerprint != proposal["decision_fingerprint"]:
        invalidate_item_authority(state, item, "decision fingerprint changed", timestamp)
    elif (
        state["pending_request"] is not None
        and state["pending_request"]["item_id"] == item["id"]
        and decision_view(item["presentation"], old_proposal)
        != decision_view(presentation, proposal)
    ):
        archive_pending(state, "invalidated", "decision-facing presentation changed", timestamp)
    item["proposal"] = proposal
    item["presentation"] = presentation
    item["presentation"]["evidence_diff"] = diff
    item["updated_at"] = timestamp


def op_mark_evidence_stale(state: dict[str, Any], candidate: dict[str, Any], timestamp: str) -> None:
    require_object(
        candidate,
        {"op", "expected_revision", "item_id", "reason", "diff"},
        "candidate",
    )
    item = item_by_id(state, candidate["item_id"])
    reason = require_string(candidate["reason"], "candidate.reason", allow_empty=False)
    diff = require_string(candidate["diff"], "candidate.diff")
    mark_item_stale(state, item, reason, diff, timestamp)
    item["updated_at"] = timestamp


def op_request_decision(state: dict[str, Any], candidate: dict[str, Any], timestamp: str) -> None:
    require_object(candidate, {"op", "expected_revision", "item_id", "question"}, "candidate")
    require_active_state(state)
    if state["pending_request"] is not None:
        raise StateError("only one pending decision request is allowed")
    item = item_by_id(state, candidate["item_id"])
    if item["source_state"] == "resolved_out_of_scope":
        raise StateError("resolved_out_of_scope Item is not eligible for a new decision")
    if item["evidence"]["current_status"] != "valid" or state["source"]["status"] != "ready":
        raise StateError("valid Source and Evidence are required before requesting a decision")
    if item["proposal"] is None:
        raise StateError("Item has no decision proposal")
    if item["active_authorization"] is not None:
        raise StateError("Item already has active authorization")
    question = require_string(candidate["question"], "candidate.question", allow_empty=False)
    used_ids = [entry["request_id"] for entry in state["request_history"]]
    request_id = new_id(used_ids)
    state["pending_request"] = {
        "request_id": request_id,
        "item_id": item["id"],
        "proposal_id": item["proposal"]["id"],
        "proposal_generation": item["proposal"]["generation"],
        "decision_fingerprint": item["proposal"]["decision_fingerprint"],
        "choice_ids": list(item["proposal"]["choice_order"]),
        "question": question,
        "created_at": timestamp,
    }
    item["presentation"]["question"] = question
    item["updated_at"] = timestamp


def op_record_decision(state: dict[str, Any], candidate: dict[str, Any], timestamp: str) -> None:
    require_object(
        candidate,
        {"op", "expected_revision", "item_id", "request_id", "choice_id"},
        "candidate",
    )
    require_active_state(state)
    item = item_by_id(state, candidate["item_id"])
    pending = state["pending_request"]
    request_id = canonical_uuid(candidate["request_id"], "candidate.request_id")
    choice_id = require_string(candidate["choice_id"], "candidate.choice_id", allow_empty=False)
    if pending is None:
        raise StateError("there is no pending decision request")
    if pending["request_id"] != request_id or pending["item_id"] != item["id"]:
        raise StateError("only the current pending request can be decided")
    proposal = item["proposal"]
    if proposal is None or (
        pending["proposal_id"] != proposal["id"]
        or pending["proposal_generation"] != proposal["generation"]
        or pending["decision_fingerprint"] != proposal["decision_fingerprint"]
    ):
        raise StateError("pending request no longer matches the Item")
    if choice_id not in pending["choice_ids"]:
        raise StateError("candidate.choice_id is not offered by the pending request")
    decision_id = new_id(decision["id"] for decision in item["decision_history"])
    authorization_ids = [entry["id"] for entry in item["authorization_history"]]
    authorization_id = new_id(authorization_ids)
    decision = {
        "id": decision_id,
        "request_id": request_id,
        "item_id": item["id"],
        "proposal_id": proposal["id"],
        "proposal_generation": proposal["generation"],
        "decision_fingerprint": proposal["decision_fingerprint"],
        "choice_id": choice_id,
        "authorization_id": authorization_id,
        "recorded_at": timestamp,
    }
    item["decision_history"].append(decision)
    item["active_authorization"] = {
        "id": authorization_id,
        "request_id": request_id,
        "decision_id": decision_id,
        "item_id": item["id"],
        "proposal_generation": proposal["generation"],
        "decision_fingerprint": proposal["decision_fingerprint"],
        "choice_id": choice_id,
        "action_envelope": copy.deepcopy(proposal["action_envelope"]),
        "created_at": timestamp,
    }
    archive_pending(state, "consumed", "decision recorded", timestamp)
    item["updated_at"] = timestamp


def op_start_local_work(state: dict[str, Any], candidate: dict[str, Any], timestamp: str) -> None:
    require_object(
        candidate,
        {"op", "expected_revision", "item_id", "area", "change_kind"},
        "candidate",
    )
    item = item_by_id(state, candidate["item_id"])
    authorization = active_authorization(state, item)
    progress = item["local_progress"]
    if progress["status"] != "not_started":
        raise StateError("local work can start only from not_started")
    area = require_string(candidate["area"], "candidate.area", allow_empty=False)
    change_kind = require_string(candidate["change_kind"], "candidate.change_kind", allow_empty=False)
    envelope = authorization["action_envelope"]
    if area not in envelope["allowed_areas"] or change_kind not in envelope["allowed_change_kinds"]:
        raise StateError("local work is outside the active Action Envelope")
    chosen = item["proposal"]["choices_by_id"][authorization["choice_id"]]["semantic_action"]
    if {"area": area, "change_kind": change_kind} not in chosen["local_changes"]:
        raise StateError("local work is outside the chosen semantic action")
    progress.update(
        {
            "status": "in_progress",
            "started_at": timestamp,
            "area": area,
            "change_kind": change_kind,
            "authorization_id": authorization["id"],
        }
    )
    item["updated_at"] = timestamp


def op_reconcile_local_work(
    state: dict[str, Any], candidate: dict[str, Any], timestamp: str
) -> None:
    require_object(
        candidate,
        {"op", "expected_revision", "item_id", "outcome", "reason", "validation_summary"},
        "candidate",
    )
    item = item_by_id(state, candidate["item_id"])
    progress = item["local_progress"]
    if progress["status"] not in {"in_progress", "completed"}:
        raise StateError("local reconciliation requires recorded local work")
    outcome = require_string(candidate["outcome"], "candidate.outcome")
    if outcome not in {"completed", "superseded"}:
        raise StateError("candidate.outcome must be completed or superseded")
    reason = require_string(candidate["reason"], "candidate.reason", allow_empty=False)
    summary = require_string(candidate["validation_summary"], "candidate.validation_summary")
    if outcome == "completed" and not (summary or progress["validation_summary"]):
        raise StateError("completed reconciliation requires a validation summary")
    if progress["status"] == "completed" and outcome != "completed":
        raise StateError("completed local work can only be reconciled as completed")
    archived = copy.deepcopy(progress)
    archived.update(
        {
            "status": outcome,
            "reason": reason,
            "ended_at": timestamp,
            "completed_at": progress["completed_at"] or (timestamp if outcome == "completed" else None),
            "validation_summary": progress["validation_summary"] or summary,
        }
    )
    item["local_attempt_history"].append(archived)
    item["local_progress"] = {
        "status": "not_started",
        "started_at": None,
        "completed_at": None,
        "area": None,
        "change_kind": None,
        "validation_summary": "",
        "authorization_id": None,
    }
    item["updated_at"] = timestamp


def op_complete_local_work(state: dict[str, Any], candidate: dict[str, Any], timestamp: str) -> None:
    require_object(
        candidate,
        {"op", "expected_revision", "item_id", "validation_summary"},
        "candidate",
    )
    item = item_by_id(state, candidate["item_id"])
    authorization = active_authorization(state, item)
    progress = item["local_progress"]
    if progress["status"] != "in_progress":
        raise StateError("local work can complete only from in_progress")
    chosen = item["proposal"]["choices_by_id"][authorization["choice_id"]]["semantic_action"]
    recorded_change = {"area": progress["area"], "change_kind": progress["change_kind"]}
    if (
        recorded_change not in chosen["local_changes"]
        or progress["area"] not in authorization["action_envelope"]["allowed_areas"]
        or progress["change_kind"]
        not in authorization["action_envelope"]["allowed_change_kinds"]
    ):
        raise StateError("in_progress local work is outside the current authorization")
    summary = require_string(
        candidate["validation_summary"], "candidate.validation_summary", allow_empty=False
    )
    progress.update(
        {"status": "completed", "completed_at": timestamp, "validation_summary": summary}
    )
    item["updated_at"] = timestamp


def op_prepare_remote_mutation(
    state: dict[str, Any], candidate: dict[str, Any], timestamp: str
) -> None:
    require_object(
        candidate,
        {"op", "expected_revision", "item_id", "action"},
        "candidate",
    )
    item = item_by_id(state, candidate["item_id"])
    authorization = active_authorization(state, item)
    action = copy.deepcopy(validate_platform_action(candidate["action"], "candidate.action"))
    require_authorized_platform_action(item, authorization, action)
    for journal in item["remote_mutations"]:
        if journal["action"] == action:
            raise StateError(
                "this remote mutation already has a journal; use its retry or adoption transition"
            )
        if remote_effect_projection(journal["action"]) == remote_effect_projection(action):
            raise StateError(
                "this remote effect already has a journal; reuse the exact action or verify and adopt a prior success"
            )
    journal_id = new_id(journal["id"] for journal in item["remote_mutations"])
    attempt_id = new_id(
        attempt["id"]
        for journal in item["remote_mutations"]
        for attempt in journal["attempts"]
    )
    item["remote_mutations"].append(
        {
            "id": journal_id,
            "action": action,
            "attempts": [
                {
                    "id": attempt_id,
                    "authorization_id": authorization["id"],
                    "decision_fingerprint": authorization["decision_fingerprint"],
                    "action_fingerprint": fingerprint(action),
                    "adopted_from_attempt_id": None,
                    "status": "pending",
                    "created_at": timestamp,
                    "started_at": None,
                    "finished_at": None,
                    "summary": "",
                    "confirmed_not_applied": False,
                }
            ],
            "created_at": timestamp,
        }
    )
    item["updated_at"] = timestamp


def journal_and_attempt(
    item: dict[str, Any], journal_id: Any, attempt_id: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    journal_key = canonical_uuid(journal_id, "candidate.journal_id")
    attempt_key = canonical_uuid(attempt_id, "candidate.attempt_id")
    for journal in item["remote_mutations"]:
        if journal["id"] == journal_key:
            for attempt in journal["attempts"]:
                if attempt["id"] == attempt_key:
                    return journal, attempt
            raise StateError("candidate.attempt_id is unknown for this journal")
    raise StateError("candidate.journal_id is unknown")


def require_authorized_platform_action(
    item: dict[str, Any], authorization: dict[str, Any], action: dict[str, Any]
) -> None:
    chosen = item["proposal"]["choices_by_id"][authorization["choice_id"]]["semantic_action"]
    if (
        action not in authorization["action_envelope"]["platform_actions"]
        or action not in chosen["platform_actions"]
    ):
        raise StateError("remote mutation is outside the active authorization")


def remote_attempt_matches_authorization(
    authorization: Optional[dict[str, Any]], journal: dict[str, Any], attempt: dict[str, Any]
) -> bool:
    return (
        authorization is not None
        and attempt["authorization_id"] == authorization["id"]
        and attempt["decision_fingerprint"] == authorization["decision_fingerprint"]
        and attempt["action_fingerprint"] == fingerprint(journal["action"])
    )


def op_start_remote_mutation(
    state: dict[str, Any], candidate: dict[str, Any], timestamp: str
) -> None:
    require_object(
        candidate,
        {"op", "expected_revision", "item_id", "journal_id", "attempt_id"},
        "candidate",
    )
    item = item_by_id(state, candidate["item_id"])
    authorization = active_authorization(state, item)
    journal, attempt = journal_and_attempt(
        item, candidate["journal_id"], candidate["attempt_id"]
    )
    require_authorized_platform_action(item, authorization, journal["action"])
    if not remote_attempt_matches_authorization(authorization, journal, attempt):
        raise StateError("remote attempt does not belong to the active authorization")
    if attempt["status"] != "pending":
        raise StateError("remote attempt can start only from pending")
    attempt["status"] = "in_progress"
    attempt["started_at"] = timestamp
    item["updated_at"] = timestamp


def op_finish_remote_mutation(
    state: dict[str, Any], candidate: dict[str, Any], timestamp: str
) -> None:
    require_object(
        candidate,
        {
            "op",
            "expected_revision",
            "item_id",
            "journal_id",
            "attempt_id",
            "outcome",
            "summary",
            "confirmed_not_applied",
        },
        "candidate",
    )
    item = item_by_id(state, candidate["item_id"])
    journal, attempt = journal_and_attempt(item, candidate["journal_id"], candidate["attempt_id"])
    if attempt["status"] != "in_progress":
        raise StateError("remote attempt can finish only from in_progress")
    outcome = require_string(candidate["outcome"], "candidate.outcome")
    if outcome not in {"succeeded", "failed", "uncertain"}:
        raise StateError("candidate.outcome must be succeeded, failed, or uncertain")
    confirmed = require_bool(candidate["confirmed_not_applied"], "candidate.confirmed_not_applied")
    if outcome == "failed" and not confirmed:
        raise StateError("failed is allowed only when non-application is confirmed")
    if outcome != "failed" and confirmed:
        raise StateError("confirmed_not_applied is valid only for failed")
    summary = require_string(candidate["summary"], "candidate.summary", allow_empty=False)
    attempt.update(
        {
            "status": outcome,
            "finished_at": timestamp,
            "summary": summary,
            "confirmed_not_applied": confirmed,
        }
    )
    matches_current = remote_attempt_matches_authorization(
        item["active_authorization"], journal, attempt
    )
    if not matches_current and outcome in {"succeeded", "uncertain"}:
        mark_item_stale(
            state,
            item,
            "late remote result belongs to a superseded authorization",
            summary,
            timestamp,
        )
    elif matches_current and outcome in {"failed", "uncertain"}:
        mark_item_stale(
            state,
            item,
            f"remote mutation {outcome}",
            summary,
            timestamp,
        )
    item["updated_at"] = timestamp


def op_cancel_pending_remote_mutation(
    state: dict[str, Any], candidate: dict[str, Any], timestamp: str
) -> None:
    require_object(
        candidate,
        {"op", "expected_revision", "item_id", "journal_id", "attempt_id", "reason"},
        "candidate",
    )
    item = item_by_id(state, candidate["item_id"])
    journal, attempt = journal_and_attempt(
        item, candidate["journal_id"], candidate["attempt_id"]
    )
    if attempt["status"] != "pending":
        raise StateError("only a pending remote attempt can be cancelled before its call")
    reason = require_string(candidate["reason"], "candidate.reason", allow_empty=False)
    attempt.update(
        {
            "status": "failed",
            "finished_at": timestamp,
            "summary": reason,
            "confirmed_not_applied": True,
        }
    )
    if remote_attempt_matches_authorization(item["active_authorization"], journal, attempt):
        mark_item_stale(
            state,
            item,
            "pending remote mutation was cancelled before its call",
            reason,
            timestamp,
        )
    item["updated_at"] = timestamp


def op_mark_remote_uncertain(
    state: dict[str, Any], candidate: dict[str, Any], timestamp: str
) -> None:
    require_object(
        candidate,
        {"op", "expected_revision", "item_id", "journal_id", "attempt_id", "reason"},
        "candidate",
    )
    item = item_by_id(state, candidate["item_id"])
    _journal, attempt = journal_and_attempt(item, candidate["journal_id"], candidate["attempt_id"])
    if attempt["status"] != "in_progress":
        raise StateError("only an in_progress remote attempt can become uncertain")
    reason = require_string(candidate["reason"], "candidate.reason", allow_empty=False)
    attempt.update({"status": "uncertain", "finished_at": timestamp, "summary": reason})
    mark_item_stale(state, item, "resume found an in_progress remote mutation", reason, timestamp)
    item["updated_at"] = timestamp


def op_reconcile_remote_mutation(
    state: dict[str, Any], candidate: dict[str, Any], timestamp: str
) -> None:
    require_object(
        candidate,
        {
            "op",
            "expected_revision",
            "item_id",
            "journal_id",
            "attempt_id",
            "outcome",
            "summary",
            "confirmed_not_applied",
        },
        "candidate",
    )
    item = item_by_id(state, candidate["item_id"])
    journal, attempt = journal_and_attempt(item, candidate["journal_id"], candidate["attempt_id"])
    if attempt["status"] != "uncertain":
        raise StateError("only an uncertain remote attempt can be reconciled")
    outcome = require_string(candidate["outcome"], "candidate.outcome")
    if outcome not in {"succeeded", "failed"}:
        raise StateError("reconciliation outcome must be succeeded or failed")
    confirmed = require_bool(candidate["confirmed_not_applied"], "candidate.confirmed_not_applied")
    if outcome == "failed" and not confirmed:
        raise StateError("failed reconciliation requires confirmed non-application")
    if outcome == "succeeded" and confirmed:
        raise StateError("succeeded reconciliation cannot be confirmed not applied")
    attempt.update(
        {
            "status": outcome,
            "finished_at": timestamp,
            "summary": require_string(candidate["summary"], "candidate.summary", allow_empty=False),
            "confirmed_not_applied": confirmed,
        }
    )
    if outcome == "succeeded" and not remote_attempt_matches_authorization(
        item["active_authorization"], journal, attempt
    ):
        mark_item_stale(
            state,
            item,
            "late remote reconciliation belongs to a superseded authorization",
            attempt["summary"],
            timestamp,
        )
    item["updated_at"] = timestamp


def op_retry_remote_mutation(
    state: dict[str, Any], candidate: dict[str, Any], timestamp: str
) -> None:
    require_object(
        candidate,
        {"op", "expected_revision", "item_id", "journal_id"},
        "candidate",
    )
    item = item_by_id(state, candidate["item_id"])
    authorization = active_authorization(state, item)
    journal_key = canonical_uuid(candidate["journal_id"], "candidate.journal_id")
    journal = next(
        (entry for entry in item["remote_mutations"] if entry["id"] == journal_key), None
    )
    if journal is None:
        raise StateError("candidate.journal_id is unknown")
    require_authorized_platform_action(item, authorization, journal["action"])
    if journal["attempts"][-1]["status"] != "failed":
        raise StateError("retry requires a reconciled failed attempt")
    if any(
        attempt["authorization_id"] == authorization["id"]
        for attempt in journal["attempts"]
    ):
        raise StateError("active authorization already has an attempt for this action")
    attempt_ids = [attempt["id"] for entry in item["remote_mutations"] for attempt in entry["attempts"]]
    journal["attempts"].append(
        {
            "id": new_id(attempt_ids),
            "authorization_id": authorization["id"],
            "decision_fingerprint": authorization["decision_fingerprint"],
            "action_fingerprint": fingerprint(journal["action"]),
            "adopted_from_attempt_id": None,
            "status": "pending",
            "created_at": timestamp,
            "started_at": None,
            "finished_at": None,
            "summary": "",
            "confirmed_not_applied": False,
        }
    )
    item["updated_at"] = timestamp


def op_adopt_remote_mutation(
    state: dict[str, Any], candidate: dict[str, Any], timestamp: str
) -> None:
    require_object(
        candidate,
        {
            "op",
            "expected_revision",
            "item_id",
            "action",
            "source_journal_id",
            "source_attempt_id",
            "verification_summary",
        },
        "candidate",
    )
    item = item_by_id(state, candidate["item_id"])
    authorization = active_authorization(state, item)
    action = copy.deepcopy(validate_platform_action(candidate["action"], "candidate.action"))
    require_authorized_platform_action(item, authorization, action)
    source_journal, source_attempt = journal_and_attempt(
        item, candidate["source_journal_id"], candidate["source_attempt_id"]
    )
    if (
        source_attempt["status"] != "succeeded"
        or source_attempt["adopted_from_attempt_id"] is not None
    ):
        raise StateError("adoption requires an actual previously succeeded remote attempt")
    if remote_effect_projection(source_journal["action"]) != remote_effect_projection(action):
        raise StateError("adoption source does not match the approved remote effect")
    journal = next(
        (entry for entry in item["remote_mutations"] if entry["action"] == action), None
    )
    if journal is None:
        journal = {
            "id": new_id(entry["id"] for entry in item["remote_mutations"]),
            "action": action,
            "attempts": [],
            "created_at": timestamp,
        }
        item["remote_mutations"].append(journal)
    if any(
        attempt["authorization_id"] == authorization["id"]
        for attempt in journal["attempts"]
    ):
        raise StateError("active authorization already has an attempt for this action")
    summary = require_string(
        candidate["verification_summary"],
        "candidate.verification_summary",
        allow_empty=False,
    )
    attempt_ids = [
        attempt["id"]
        for entry in item["remote_mutations"]
        for attempt in entry["attempts"]
    ]
    journal["attempts"].append(
        {
            "id": new_id(attempt_ids),
            "authorization_id": authorization["id"],
            "decision_fingerprint": authorization["decision_fingerprint"],
            "action_fingerprint": fingerprint(journal["action"]),
            "adopted_from_attempt_id": source_attempt["id"],
            "status": "succeeded",
            "created_at": timestamp,
            "started_at": None,
            "finished_at": timestamp,
            "summary": summary,
            "confirmed_not_applied": False,
        }
    )
    item["updated_at"] = timestamp


def op_close_authorization(
    state: dict[str, Any], candidate: dict[str, Any], timestamp: str
) -> None:
    require_object(
        candidate,
        {"op", "expected_revision", "item_id", "reason"},
        "candidate",
    )
    item = item_by_id(state, candidate["item_id"])
    authorization = active_authorization(state, item)
    if item["local_progress"]["status"] == "in_progress":
        raise StateError("cannot close authorization while local work is in progress")
    if (
        item["local_progress"]["status"] != "not_started"
        and item["local_progress"]["authorization_id"] != authorization["id"]
    ):
        raise StateError("reconcile local work from the previous authorization before closing")
    chosen = item["proposal"]["choices_by_id"][authorization["choice_id"]]["semantic_action"]
    local_attempts = item["local_attempt_history"] + [item["local_progress"]]
    for local_change in chosen["local_changes"]:
        if not any(
            attempt["authorization_id"] == authorization["id"]
            and attempt["status"] == "completed"
            and attempt["area"] == local_change["area"]
            and attempt["change_kind"] == local_change["change_kind"]
            for attempt in local_attempts
        ):
            raise StateError("cannot close authorization before every approved local change completes")
    for action in chosen["platform_actions"]:
        journal = next(
            (entry for entry in item["remote_mutations"] if entry["action"] == action), None
        )
        if journal is None:
            raise StateError("cannot close authorization before every approved platform action runs")
        attempt = journal["attempts"][-1]
        if not remote_attempt_matches_authorization(authorization, journal, attempt):
            raise StateError("approved platform action has no attempt for the active authorization")
        if attempt["status"] not in {"succeeded", "failed"}:
            raise StateError("cannot close authorization while an approved platform action is unfinished")
    reason = require_string(candidate["reason"], "candidate.reason", allow_empty=False)
    archive_authorization(item, reason, timestamp)
    item["updated_at"] = timestamp


def op_set_session_lifecycle(
    state: dict[str, Any], candidate: dict[str, Any], timestamp: str
) -> None:
    require_object(
        candidate,
        {"op", "expected_revision", "lifecycle", "reason"},
        "candidate",
    )
    require_active_state(state)
    lifecycle = require_string(candidate["lifecycle"], "candidate.lifecycle")
    if lifecycle not in TERMINAL_LIFECYCLES:
        raise StateError("candidate.lifecycle must be completed or stopped")
    reason = require_string(candidate["reason"], "candidate.reason", allow_empty=False)
    if lifecycle == "completed":
        if state["source"]["status"] != "ready":
            raise StateError("cannot complete a Session while the Source is stale")
        if state["pending_request"] is not None:
            raise StateError("cannot complete a Session with a pending decision request")
        if any(item["active_authorization"] is not None for item in state["items"].values()):
            raise StateError("cannot complete a Session with active authorization")
        for item in state["items"].values():
            if item["source_state"] == "resolved_out_of_scope":
                continue
            proposal = item["proposal"]
            if item["evidence"]["current_status"] != "valid" or proposal is None:
                raise StateError("cannot complete a Session with undecided or stale Items")
            if not item["decision_history"] or (
                item["decision_history"][-1]["proposal_id"] != proposal["id"]
                or item["decision_history"][-1]["proposal_generation"]
                != proposal["generation"]
                or item["decision_history"][-1]["decision_fingerprint"]
                != proposal["decision_fingerprint"]
            ):
                raise StateError("cannot complete a Session before every current Item is decided")
        if any(item["local_progress"]["status"] == "in_progress" for item in state["items"].values()):
            raise StateError("cannot complete a Session with in_progress local work")
        if any(
            attempt["status"] in {"pending", "in_progress", "uncertain"}
            for item in state["items"].values()
            for journal in item["remote_mutations"]
            for attempt in journal["attempts"]
        ):
            raise StateError("cannot complete a Session with unfinished remote mutation")
    else:
        if state["pending_request"] is not None:
            archive_pending(state, "invalidated", reason, timestamp)
        for item in state["items"].values():
            archive_authorization(item, reason, timestamp)
    state["lifecycle"] = lifecycle


def normalize_review(review_value: Any, field: str) -> dict[str, Any]:
    review = require_object(review_value, {"id", "body", "author", "state"}, field)
    for key in ("id", "body", "author", "state"):
        require_string(review[key], f"{field}.{key}", allow_empty=(key == "body"))
    return copy.deepcopy(review)


def normalize_thread(thread_value: Any, field: str) -> dict[str, Any]:
    thread = require_object(
        thread_value,
        {"id", "is_resolved", "is_outdated", "review_id", "comments"},
        field,
    )
    for key in ("id", "review_id"):
        require_string(thread[key], f"{field}.{key}", allow_empty=False)
    require_bool(thread["is_resolved"], f"{field}.is_resolved")
    require_bool(thread["is_outdated"], f"{field}.is_outdated")
    if not isinstance(thread["comments"], list) or not thread["comments"]:
        raise StateError(f"{field}.comments must be a non-empty array")
    comments = []
    for index, comment_value in enumerate(thread["comments"]):
        comment = require_object(
            comment_value,
            {"id", "body", "author", "path", "line", "start_line", "original_line", "created_at"},
            f"{field}.comments[{index}]",
        )
        for key in ("id", "author", "path", "created_at"):
            require_string(comment[key], f"{field}.comments[{index}].{key}", allow_empty=False)
        require_string(comment["body"], f"{field}.comments[{index}].body")
        for key in ("line", "start_line", "original_line"):
            if comment[key] is not None:
                require_int(comment[key], f"{field}.comments[{index}].{key}", minimum=1)
        comments.append(copy.deepcopy(comment))
    normalized = copy.deepcopy(thread)
    normalized["comments"] = comments
    return normalized


def github_source_data(thread: dict[str, Any], comment_ids: Optional[list[str]] = None) -> dict[str, Any]:
    selected = thread["comments"]
    if comment_ids is not None:
        selected = [comment for comment in selected if comment["id"] in comment_ids]
    return {
        "original": "\n\n".join(comment["body"] for comment in selected),
        "thread_id": thread["id"],
        "review_id": thread["review_id"],
        "comment_ids": [comment["id"] for comment in selected],
        "path": thread["comments"][0]["path"],
        "is_outdated": thread["is_outdated"],
    }


def op_update_github_source(
    state: dict[str, Any], candidate: dict[str, Any], timestamp: str
) -> None:
    require_object(candidate, {"op", "expected_revision", "collection"}, "candidate")
    require_active_state(state)
    source = state["source"]
    if source["type"] != "github_pr":
        raise StateError("update_github_source requires a GitHub Source")
    collection = require_object(
        candidate["collection"],
        {"identity", "pagination", "errors", "snapshot"},
        "candidate.collection",
    )
    identity = validate_github_identity(collection["identity"], "candidate.collection.identity")
    if identity != source["identity"]:
        raise StateError(
            "different PR identity requires remote reconciliation, terminal Session, approved purge, and new initialization"
        )
    errors = require_string_list(collection["errors"], "candidate.collection.errors")
    snapshot_input = collection["snapshot"]
    thread_ids = None
    if snapshot_input is not None:
        raw_snapshot = require_object(
            snapshot_input,
            {
                "head_ref_oid",
                "base_ref_oid",
                "reviews",
                "threads",
                "actionable_reply_ids",
                "actionable_review_body_ids",
            },
            "candidate.collection.snapshot",
        )
        if not isinstance(raw_snapshot["threads"], list):
            raise StateError("candidate.collection.snapshot.threads must be an array")
        thread_ids = {
            require_string(thread.get("id") if isinstance(thread, dict) else None, "thread.id", allow_empty=False)
            for thread in raw_snapshot["threads"]
        }
    pagination_complete = validate_pagination(
        collection["pagination"], "candidate.collection.pagination", thread_ids
    )
    if (not pagination_complete or errors) and snapshot_input is not None:
        raise StateError("incomplete GitHub collection must use snapshot: null")
    complete = pagination_complete and not errors and snapshot_input is not None
    if not complete:
        source["status"] = "stale"
        source["stale_reason"] = "; ".join(errors) or "GitHub pagination was incomplete"
        source["collection"] = {
            "status": "incomplete",
            "pagination": copy.deepcopy(collection["pagination"]),
            "errors": errors,
            "collected_at": timestamp,
        }
        for item in state["items"].values():
            mark_item_stale(
                state,
                item,
                "GitHub Source collection was incomplete",
                source["stale_reason"],
                timestamp,
            )
        source["updated_at"] = timestamp
        return
    raw_snapshot = snapshot_input
    head_ref_oid = require_string(
        raw_snapshot["head_ref_oid"], "candidate.collection.snapshot.head_ref_oid", allow_empty=False
    )
    base_ref_oid = require_optional_string(
        raw_snapshot["base_ref_oid"], "candidate.collection.snapshot.base_ref_oid"
    )
    if not isinstance(raw_snapshot["reviews"], list):
        raise StateError("candidate.collection.snapshot.reviews must be an array")
    reviews = {}
    for index, review_value in enumerate(raw_snapshot["reviews"]):
        review = normalize_review(review_value, f"candidate.collection.snapshot.reviews[{index}]")
        if review["id"] in reviews:
            raise StateError("GitHub review IDs must be unique")
        reviews[review["id"]] = review
    threads = {}
    all_comment_ids = set()
    for index, thread_value in enumerate(raw_snapshot["threads"]):
        thread = normalize_thread(thread_value, f"candidate.collection.snapshot.threads[{index}]")
        if thread["id"] in threads:
            raise StateError("GitHub thread IDs must be unique")
        if thread["review_id"] not in reviews:
            raise StateError("every GitHub thread must reference a collected review")
        for comment in thread["comments"]:
            if comment["id"] in all_comment_ids:
                raise StateError("GitHub comment IDs must be globally unique")
            all_comment_ids.add(comment["id"])
        threads[thread["id"]] = thread
    actionable_reply_ids = require_string_list(
        raw_snapshot["actionable_reply_ids"],
        "candidate.collection.snapshot.actionable_reply_ids",
    )
    if any(reply_id not in all_comment_ids for reply_id in actionable_reply_ids):
        raise StateError("actionable_reply_ids contains an unknown comment")
    root_comment_ids = {thread["comments"][0]["id"] for thread in threads.values()}
    if any(reply_id in root_comment_ids for reply_id in actionable_reply_ids):
        raise StateError("only replies can become thread sub-items")
    unresolved_reply_ids = {
        comment["id"]
        for thread in threads.values()
        if not thread["is_resolved"]
        for comment in thread["comments"][1:]
    }
    if any(reply_id not in unresolved_reply_ids for reply_id in actionable_reply_ids):
        raise StateError("reply sub-items require an unresolved inline thread")
    actionable_review_body_ids = require_string_list(
        raw_snapshot["actionable_review_body_ids"],
        "candidate.collection.snapshot.actionable_review_body_ids",
    )
    unresolved_review_ids = {
        thread["review_id"] for thread in threads.values() if not thread["is_resolved"]
    }
    if any(review_id not in unresolved_review_ids for review_id in actionable_review_body_ids):
        raise StateError("review body Items require a review with an unresolved inline thread")
    previous = source["snapshot"]
    merged_reviews = copy.deepcopy(previous["reviews_by_id"]) if previous else {}
    merged_threads = copy.deepcopy(previous["threads_by_id"]) if previous else {}
    relevant_review_ids = {thread["review_id"] for thread in threads.values()}
    relevant_review_ids.update(
        item["source_data"]["review_id"]
        for item in state["items"].values()
        if item["source_data"]["review_id"] is not None
    )
    for review_id in relevant_review_ids:
        if review_id in reviews:
            merged_reviews[review_id] = reviews[review_id]
    merged_threads.update(threads)
    snapshot = {
        "head_ref_oid": head_ref_oid,
        "base_ref_oid": base_ref_oid,
        "reviews_by_id": merged_reviews,
        "threads_by_id": merged_threads,
        "current_thread_ids": list(threads),
        "actionable_reply_ids": actionable_reply_ids,
        "actionable_review_body_ids": actionable_review_body_ids,
    }
    validate_github_snapshot(snapshot, "normalized GitHub snapshot")
    source_changed = previous != snapshot
    source["snapshot"] = snapshot
    source["status"] = "ready"
    source["stale_reason"] = ""
    source["collection"] = {
        "status": "complete",
        "pagination": copy.deepcopy(collection["pagination"]),
        "errors": [],
        "collected_at": timestamp,
    }
    items_by_source_key = {item["source_key"]: item for item in state["items"].values()}
    active_source_keys = set()
    for thread in threads.values():
        thread_key = f"thread:{thread['id']}"
        if not thread["is_resolved"]:
            active_source_keys.add(thread_key)
            item = items_by_source_key.get(thread_key)
            if item is None:
                item = new_item(
                    source["id"],
                    thread_key,
                    "inline_thread",
                    "unresolved",
                    github_source_data(thread),
                    f"Review thread in {thread['comments'][0]['path']}",
                    timestamp,
                    state["items"],
                )
                state["items"][item["id"]] = item
                state["item_order"].append(item["id"])
                items_by_source_key[thread_key] = item
            else:
                item["source_state"] = "unresolved"
                item["source_data"] = github_source_data(thread)
                item["updated_at"] = timestamp
        elif thread_key in items_by_source_key:
            items_by_source_key[thread_key]["source_state"] = "resolved_out_of_scope"
            items_by_source_key[thread_key]["source_data"] = github_source_data(thread)
            items_by_source_key[thread_key]["updated_at"] = timestamp
        for comment in thread["comments"][1:]:
            reply_key = f"reply:{thread['id']}:{comment['id']}"
            if not thread["is_resolved"] and comment["id"] in actionable_reply_ids:
                active_source_keys.add(reply_key)
                item = items_by_source_key.get(reply_key)
                if item is None:
                    item = new_item(
                        source["id"],
                        reply_key,
                        "thread_sub_item",
                        "unresolved",
                        github_source_data(thread, [comment["id"]]),
                        f"Independent reply in {thread['comments'][0]['path']}",
                        timestamp,
                        state["items"],
                    )
                    state["items"][item["id"]] = item
                    state["item_order"].append(item["id"])
                    items_by_source_key[reply_key] = item
                else:
                    item["source_state"] = "unresolved"
                    item["source_data"] = github_source_data(thread, [comment["id"]])
                    item["updated_at"] = timestamp
    for review_id in actionable_review_body_ids:
        review_key = f"review-body:{review_id}"
        active_source_keys.add(review_key)
        review = reviews[review_id]
        item = items_by_source_key.get(review_key)
        data = {
            "original": review["body"],
            "thread_id": None,
            "review_id": review_id,
            "comment_ids": [],
            "path": None,
            "is_outdated": False,
        }
        if item is None:
            item = new_item(
                source["id"],
                review_key,
                "review_body",
                "unresolved",
                data,
                f"Actionable review body by {review['author']}",
                timestamp,
                state["items"],
            )
            state["items"][item["id"]] = item
            state["item_order"].append(item["id"])
            items_by_source_key[review_key] = item
        else:
            item["source_state"] = "unresolved"
            item["source_data"] = data
            item["updated_at"] = timestamp
    for item in state["items"].values():
        if item["source_key"] not in active_source_keys:
            item["source_state"] = "resolved_out_of_scope"
            item["updated_at"] = timestamp
    if source_changed:
        for item in state["items"].values():
            mark_item_stale(
                state,
                item,
                "GitHub Source snapshot changed",
                "Review threads, replies, review bodies, or ref OIDs changed.",
                timestamp,
            )
    source["updated_at"] = timestamp


def apply_operation(state: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise StateError("candidate must be an object")
    if set(candidate).issuperset({"op", "expected_revision"}) is False:
        raise StateError("candidate requires op and expected_revision")
    op = require_string(candidate["op"], "candidate.op", allow_empty=False)
    expected_revision = require_int(candidate["expected_revision"], "candidate.expected_revision")
    if expected_revision != state["revision"]:
        raise StateError(
            f"stale expected_revision: expected {state['revision']}, received {expected_revision}"
        )
    next_state = copy.deepcopy(state)
    timestamp = now_utc()
    if op == "update_github_source":
        op_update_github_source(next_state, candidate, timestamp)
    elif op == "update_item_analysis":
        op_update_item_analysis(next_state, candidate, timestamp)
    elif op == "mark_evidence_stale":
        op_mark_evidence_stale(next_state, candidate, timestamp)
    elif op == "request_decision":
        op_request_decision(next_state, candidate, timestamp)
    elif op == "record_decision":
        op_record_decision(next_state, candidate, timestamp)
    elif op == "start_local_work":
        op_start_local_work(next_state, candidate, timestamp)
    elif op == "complete_local_work":
        op_complete_local_work(next_state, candidate, timestamp)
    elif op == "reconcile_local_work":
        op_reconcile_local_work(next_state, candidate, timestamp)
    elif op == "prepare_remote_mutation":
        op_prepare_remote_mutation(next_state, candidate, timestamp)
    elif op == "start_remote_mutation":
        op_start_remote_mutation(next_state, candidate, timestamp)
    elif op == "finish_remote_mutation":
        op_finish_remote_mutation(next_state, candidate, timestamp)
    elif op == "cancel_pending_remote_mutation":
        op_cancel_pending_remote_mutation(next_state, candidate, timestamp)
    elif op == "mark_remote_uncertain":
        op_mark_remote_uncertain(next_state, candidate, timestamp)
    elif op == "reconcile_remote_mutation":
        op_reconcile_remote_mutation(next_state, candidate, timestamp)
    elif op == "retry_remote_mutation":
        op_retry_remote_mutation(next_state, candidate, timestamp)
    elif op == "adopt_remote_mutation":
        op_adopt_remote_mutation(next_state, candidate, timestamp)
    elif op == "close_authorization":
        op_close_authorization(next_state, candidate, timestamp)
    elif op == "set_session_lifecycle":
        op_set_session_lifecycle(next_state, candidate, timestamp)
    else:
        raise StateError(f"unknown operation: {op}")
    next_state["revision"] += 1
    next_state["updated_at"] = timestamp
    return validate_state(next_state, state["owner"]["thread_id"])


def initialize_state(thread_id: str, candidate: dict[str, Any]) -> dict[str, Any]:
    require_object(candidate, {"op", "expected_revision", "source", "output_locale"}, "candidate")
    if candidate["op"] != "initialize_session":
        raise StateError("state does not exist; initialize_session is required")
    if require_int(candidate["expected_revision"], "candidate.expected_revision") != 0:
        raise StateError("initialize_session requires expected_revision 0")
    source_input = candidate["source"]
    if not isinstance(source_input, dict) or "type" not in source_input:
        raise StateError("candidate.source must be a typed object")
    source_type = source_input["type"]
    timestamp = now_utc()
    output_locale = require_string(candidate["output_locale"], "candidate.output_locale", allow_empty=False)
    if not LOCALE_RE.fullmatch(output_locale):
        raise StateError("candidate.output_locale is invalid")
    source_id = new_id([])
    items = {}
    item_order = []
    if source_type == "github_pr":
        require_object(source_input, {"type", "host", "owner", "repo", "pr_number"}, "candidate.source")
        identity = {
            "host": canonical_host(source_input["host"]),
            "owner": canonical_repo_part(source_input["owner"], "candidate.source.owner"),
            "repo": canonical_repo_part(source_input["repo"], "candidate.source.repo"),
            "pr_number": require_int(source_input["pr_number"], "candidate.source.pr_number", minimum=1),
        }
        source = {
            "id": source_id,
            "type": "github_pr",
            "identity": identity,
            "status": "stale",
            "stale_reason": "GitHub Source has not been collected",
            "snapshot": None,
            "collection": {
                "status": "never",
                "pagination": None,
                "errors": [],
                "collected_at": None,
            },
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    elif source_type == "pasted_feedback":
        require_object(source_input, {"type", "batch_text", "items"}, "candidate.source")
        batch_text = require_string(source_input["batch_text"], "candidate.source.batch_text")
        if not isinstance(source_input["items"], list) or not source_input["items"]:
            raise StateError("candidate.source.items must be a non-empty array")
        item_source_keys = []
        for index, item_value in enumerate(source_input["items"]):
            item_input = require_object(item_value, {"original"}, f"candidate.source.items[{index}]")
            original = require_string(
                item_input["original"], f"candidate.source.items[{index}].original", allow_empty=False
            )
            item = new_item(
                source_id,
                "pending",
                "pasted_feedback",
                "copied",
                {
                    "original": original,
                    "thread_id": None,
                    "review_id": None,
                    "comment_ids": [],
                    "path": None,
                    "is_outdated": False,
                },
                f"Pasted review item {index + 1}",
                timestamp,
                items,
            )
            item_id = item["id"]
            source_key = f"pasted:{item_id}"
            item["source_key"] = source_key
            items[item_id] = item
            item_order.append(item_id)
            item_source_keys.append(source_key)
        source = {
            "id": source_id,
            "type": "pasted_feedback",
            "identity": {"batch_id": source_id},
            "status": "ready",
            "stale_reason": "",
            "snapshot": {"batch_text": batch_text, "item_source_keys": item_source_keys},
            "collection": {
                "status": "not_applicable",
                "pagination": None,
                "errors": [],
                "collected_at": timestamp,
            },
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    else:
        raise StateError("candidate.source.type must be github_pr or pasted_feedback")
    state = {
        "schema_version": SCHEMA_VERSION,
        "owner": {"thread_id": thread_id},
        "revision": 1,
        "lifecycle": "active",
        "created_at": timestamp,
        "updated_at": timestamp,
        "output_locale": output_locale,
        "source": source,
        "items": items,
        "item_order": item_order,
        "pending_request": None,
        "request_history": [],
    }
    return validate_state(state, thread_id)


def duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise StateError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def decode_json_bytes(data: bytes, field: str) -> Any:
    if len(data) > MAX_JSON_BYTES:
        raise StateError(f"{field} exceeds the 10 MiB limit")
    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=duplicate_rejecting_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                StateError(f"invalid JSON constant: {value}")
            ),
        )
    except UnicodeDecodeError as error:
        raise StateError(f"{field} must be UTF-8 JSON") from error
    except json.JSONDecodeError as error:
        raise StateError(f"{field} is invalid JSON: {error}") from error


def current_uid() -> int:
    if not hasattr(os, "getuid"):
        raise StateError("review state storage requires POSIX ownership semantics")
    return os.getuid()


def require_owned_directory(path: Path, field: str) -> None:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        raise StateError(f"{field} must not be a symlink")
    if not stat.S_ISDIR(info.st_mode):
        raise StateError(f"{field} must be a directory")
    if info.st_uid != current_uid():
        raise StateError(f"{field} must be owned by the current user")
    if stat.S_IMODE(info.st_mode) != 0o700:
        raise StateError(f"{field} must have mode 0700")


def require_owned_regular_file(
    path: Path, field: str, expected_mode: Optional[int] = None
) -> None:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        raise StateError(f"{field} must not be a symlink")
    if not stat.S_ISREG(info.st_mode):
        raise StateError(f"{field} must be a regular file")
    if info.st_uid != current_uid():
        raise StateError(f"{field} must be owned by the current user")
    if expected_mode is not None and stat.S_IMODE(info.st_mode) != expected_mode:
        raise StateError(f"{field} must have mode {expected_mode:04o}")


def ensure_directory(path: Path, field: str, create: bool) -> None:
    try:
        require_owned_directory(path, field)
    except FileNotFoundError:
        if not create:
            raise StateError(f"{field} does not exist")
        path.mkdir(mode=0o700)
        os.chmod(path, 0o700)
        require_owned_directory(path, field)


def session_directory(home_arg: str, thread_id: str, create: bool) -> tuple[Path, Path]:
    canonical_uuid(thread_id, "--thread-id")
    home_input = Path(home_arg).expanduser()
    if not home_input.exists() and create:
        home_input.mkdir(mode=0o700, parents=True)
    try:
        home = home_input.resolve(strict=True)
    except FileNotFoundError as error:
        raise StateError("GRIMOIRE_HOME does not exist") from error
    ensure_directory(home, "GRIMOIRE_HOME", create=False)
    managed = home / "review-response"
    threads = managed / "threads"
    thread_dir = threads / thread_id
    ensure_directory(managed, "review-response directory", create)
    ensure_directory(threads, "threads directory", create)
    ensure_directory(thread_dir, "Thread directory", create)
    try:
        thread_dir.relative_to(home)
    except ValueError as error:
        raise StateError("Thread directory escapes GRIMOIRE_HOME") from error
    return home, thread_dir


def read_owned_file(path: Path, field: str) -> bytes:
    require_owned_regular_file(path, field, 0o600)
    with path.open("rb") as handle:
        data = handle.read(MAX_JSON_BYTES + 1)
    if len(data) > MAX_JSON_BYTES:
        raise StateError(f"{field} exceeds the 10 MiB limit")
    return data


def load_state(thread_dir: Path, thread_id: str) -> dict[str, Any]:
    data = read_owned_file(thread_dir / "state.json", "state.json")
    return validate_state(decode_json_bytes(data, "state.json"), thread_id)


def write_fixed_temp(path: Path, data: bytes) -> None:
    if path.exists() or path.is_symlink():
        require_owned_regular_file(path, path.name, 0o600)
        path.unlink()
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
    finally:
        os.close(descriptor)


def render_bytes(state: dict[str, Any], template_path: Path) -> bytes:
    require_owned_regular_file(template_path, "review HTML template")
    script_dir = Path(__file__).resolve().parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    from render_review import render_state  # pylint: disable=import-outside-toplevel

    template = template_path.read_text(encoding="utf-8")
    return render_state(state, template).encode("utf-8")


def publish_state(
    thread_dir: Path,
    state: dict[str, Any],
    template_path: Path,
    after_state_replace: Optional[Callable[[], None]] = None,
) -> None:
    state_bytes = canonical_json(state) + b"\n"
    if len(state_bytes) > MAX_JSON_BYTES:
        raise StateError("result state exceeds the 10 MiB limit")
    html_bytes = render_bytes(state, template_path)
    state_tmp = thread_dir / ".state.json.tmp"
    html_tmp = thread_dir / ".review.html.tmp"
    state_path = thread_dir / "state.json"
    html_path = thread_dir / "review.html"
    for path, field in ((state_path, "state.json"), (html_path, "review.html")):
        if path.exists() or path.is_symlink():
            require_owned_regular_file(path, field, 0o600)
    write_fixed_temp(state_tmp, state_bytes)
    try:
        write_fixed_temp(html_tmp, html_bytes)
    except Exception:
        unlink_file(state_tmp)
        raise
    os.replace(state_tmp, state_path)
    if after_state_replace is not None:
        after_state_replace()
    os.replace(html_tmp, html_path)


def apply_candidate(
    home: str,
    thread_id: str,
    candidate: dict[str, Any],
    template_path: Path,
    after_state_replace: Optional[Callable[[], None]] = None,
) -> dict[str, Any]:
    canonical_uuid(thread_id, "--thread-id")
    reject_obvious_secrets(candidate)
    op = candidate.get("op") if isinstance(candidate, dict) else None
    create = op == "initialize_session"
    _home, thread_dir = session_directory(home, thread_id, create=create)
    state_path = thread_dir / "state.json"
    if create:
        if state_path.exists() or state_path.is_symlink():
            raise StateError("Review Session already exists for this Thread; resume it")
        html_path = thread_dir / "review.html"
        if html_path.exists() or html_path.is_symlink():
            raise StateError("review.html exists without state.json; preserve it and repair manually")
        with os.scandir(thread_dir) as entries:
            unexpected = [entry.name for entry in entries if entry.name not in ALLOWED_FILES]
        if unexpected:
            raise StateError(f"Thread directory contains unexpected files: {sorted(unexpected)}")
        next_state = initialize_state(thread_id, candidate)
    else:
        current = load_state(thread_dir, thread_id)
        next_state = apply_operation(current, candidate)
    publish_state(thread_dir, next_state, template_path, after_state_replace)
    return next_state


def recover_html(home: str, thread_id: str, template_path: Path) -> dict[str, Any]:
    _home, thread_dir = session_directory(home, thread_id, create=False)
    state = load_state(thread_dir, thread_id)
    state_tmp = thread_dir / ".state.json.tmp"
    if state_tmp.exists() or state_tmp.is_symlink():
        require_owned_regular_file(state_tmp, ".state.json.tmp", 0o600)
        unlink_file(state_tmp)
    html = render_bytes(state, template_path)
    html_tmp = thread_dir / ".review.html.tmp"
    html_path = thread_dir / "review.html"
    if html_path.exists() or html_path.is_symlink():
        require_owned_regular_file(html_path, "review.html", 0o600)
    write_fixed_temp(html_tmp, html)
    os.replace(html_tmp, html_path)
    return state


def unfinished_remote_mutations(state: dict[str, Any]) -> list[str]:
    return [
        attempt["id"]
        for item in state["items"].values()
        for journal in item["remote_mutations"]
        for attempt in journal["attempts"][-1:]
        if attempt["status"] in {"in_progress", "uncertain"}
    ]


def unlink_file(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def inspect_purge_directory(thread_dir: Path) -> list[str]:
    names = []
    with os.scandir(thread_dir) as entries:
        for entry in entries:
            if entry.name not in ALLOWED_FILES:
                raise StateError(f"Thread directory contains unexpected file: {entry.name}")
            path = thread_dir / entry.name
            require_owned_regular_file(path, entry.name, 0o600)
            names.append(entry.name)
    return names


def purge_session(home: str, thread_id: str, expected_revision: int) -> None:
    canonical_uuid(thread_id, "--thread-id")
    require_int(expected_revision, "--expected-revision")
    _home, thread_dir = session_directory(home, thread_id, create=False)
    names = inspect_purge_directory(thread_dir)
    if "state.json" not in names:
        if names:
            raise StateError("state.json is missing while Review Session artifacts remain")
        thread_dir.rmdir()
        return
    state = load_state(thread_dir, thread_id)
    if state["revision"] != expected_revision:
        raise StateError(
            f"stale expected_revision: expected {state['revision']}, received {expected_revision}"
        )
    if state["lifecycle"] not in TERMINAL_LIFECYCLES:
        raise StateError("purge requires a terminal Review Session")
    unfinished = unfinished_remote_mutations(state)
    if unfinished:
        raise StateError("purge requires remote reconciliation for in_progress or uncertain attempts")
    for name in ("review.html", ".review.html.tmp", ".state.json.tmp"):
        if name in names:
            unlink_file(thread_dir / name)
    inspect_purge_directory(thread_dir)
    state = load_state(thread_dir, thread_id)
    if state["revision"] != expected_revision or state["lifecycle"] not in TERMINAL_LIFECYCLES:
        raise StateError("state changed during purge")
    if unfinished_remote_mutations(state):
        raise StateError("remote mutation became unsafe during purge")
    unlink_file(thread_dir / "state.json")
    thread_dir.rmdir()


def default_home() -> str:
    return os.environ.get("GRIMOIRE_HOME", str(Path.home() / ".grimoire"))


def default_template() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "review.html.tmpl"


def read_candidate(path_value: str) -> dict[str, Any]:
    if path_value == "-":
        data = sys.stdin.buffer.read(MAX_JSON_BYTES + 1)
    else:
        path = Path(path_value)
        with path.open("rb") as handle:
            data = handle.read(MAX_JSON_BYTES + 1)
    candidate = decode_json_bytes(data, "candidate")
    if not isinstance(candidate, dict):
        raise StateError("candidate must be a JSON object")
    return candidate


def result_summary(state: dict[str, Any]) -> dict[str, Any]:
    pending = state["pending_request"]
    return {
        "thread_id": state["owner"]["thread_id"],
        "revision": state["revision"],
        "lifecycle": state["lifecycle"],
        "source_status": state["source"]["status"],
        "pending_item_id": pending["item_id"] if pending else None,
        "pending_request_id": pending["request_id"] if pending else None,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Single-writer authority for Thread-owned review state.")
    parser.add_argument("--grimoire-home", default=default_home())
    subparsers = parser.add_subparsers(dest="command", required=True)

    apply_parser = subparsers.add_parser("apply", help="Apply one strict typed operation candidate.")
    apply_parser.add_argument("--thread-id", required=True)
    apply_parser.add_argument("--candidate", required=True, help="JSON path, or - for stdin.")

    recover_parser = subparsers.add_parser("recover-html", help="Rebuild HTML from committed state.")
    recover_parser.add_argument("--thread-id", required=True)

    show_parser = subparsers.add_parser("show", help="Validate state and print a non-sensitive summary.")
    show_parser.add_argument("--thread-id", required=True)

    purge_parser = subparsers.add_parser("purge", help="Purge a terminal Review Session state-last.")
    purge_parser.add_argument("--thread-id", required=True)
    purge_parser.add_argument("--expected-revision", required=True, type=int)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        if args.command == "apply":
            state = apply_candidate(
                args.grimoire_home,
                args.thread_id,
                read_candidate(args.candidate),
                default_template(),
            )
            print(json.dumps(result_summary(state), ensure_ascii=False, sort_keys=True))
        elif args.command == "recover-html":
            state = recover_html(args.grimoire_home, args.thread_id, default_template())
            print(json.dumps(result_summary(state), ensure_ascii=False, sort_keys=True))
        elif args.command == "show":
            _home, thread_dir = session_directory(args.grimoire_home, args.thread_id, create=False)
            state = load_state(thread_dir, args.thread_id)
            print(json.dumps(result_summary(state), ensure_ascii=False, sort_keys=True))
        elif args.command == "purge":
            purge_session(args.grimoire_home, args.thread_id, args.expected_revision)
            print(json.dumps({"purged": True, "thread_id": args.thread_id}, sort_keys=True))
        else:
            raise StateError(f"unknown command: {args.command}")
        return 0
    except (OSError, StateError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
