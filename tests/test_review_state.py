from __future__ import annotations

import copy
import ast
import io
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "grimoire" / "skills" / "magical-review-response"
SCRIPTS = SKILL / "scripts"
TEMPLATE = SKILL / "assets" / "review.html.tmpl"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import render_review  # noqa: E402
import review_state  # noqa: E402


THREAD_A = "12345678-1234-5678-1234-567812345678"
THREAD_B = "22345678-1234-5678-1234-567812345678"


def pasted_source(original: str = "Please validate this edge case.") -> dict:
    return {
        "type": "pasted_feedback",
        "batch_text": original,
        "items": [{"original": original}],
    }


def github_source(number: int = 38) -> dict:
    return {
        "type": "github_pr",
        "host": "github.com",
        "owner": "hon454",
        "repo": "grimoire",
        "pr_number": number,
    }


def semantic(suffix: str = "A", malicious: bool = False) -> dict:
    injection = "</style><script>alert('x')</script>javascript:boom" if malicious else ""
    return {
        "reviewer_ask": f"Validate behavior {suffix}. {injection}",
        "reviewer_intent": f"Avoid regression {suffix}.",
        "claims": [f"Claim {suffix}"],
        "code": [
            {
                "path": f"src/<unsafe-{suffix}>.py",
                "revision": f"head-{suffix}",
                "text": f"value = '<script>{suffix}</script>'",
            }
        ],
        "examples": [
            {"input": f"input {suffix}", "behavior": f"behavior {suffix}", "outcome": f"outcome {suffix}"}
        ],
        "assumptions": [f"Assumption {suffix}"],
        "gaps": [],
    }


def platform_action(target: str = "THREAD_NODE") -> dict:
    return {
        "kind": "github_reply",
        "target": target,
        "summary": "Post the approved reply.",
        "reviewer_authored": True,
        "payload": {"body": "Approved reply body."},
    }


def envelope(with_remote: bool = False) -> dict:
    return {
        "purpose": "Address the selected review item.",
        "allowed_areas": ["src/module.py"],
        "allowed_change_kinds": ["code"],
        "excluded": ["unrelated files", "commit", "push", "merge", "release", "deployment"],
        "validations": ["python3 -m unittest"],
        "repository_actions": [],
        "platform_actions": [platform_action()] if with_remote else [],
    }


def analysis_candidate(
    state: dict,
    item_id: str,
    *,
    evidence_suffix: str = "A",
    action_suffix: str = "A",
    malicious: bool = False,
    with_remote: bool = False,
) -> dict:
    remote = [platform_action()] if with_remote else []
    return {
        "op": "update_item_analysis",
        "expected_revision": state["revision"],
        "item_id": item_id,
        "evidence": semantic(evidence_suffix, malicious=malicious),
        "reason": f"Evaluated {evidence_suffix}",
        "diff": f"Evidence diff {evidence_suffix}",
        "presentation": {
            "title": f"Unsafe <title> {evidence_suffix}" if malicious else f"Review item {evidence_suffix}",
            "translation": "<img src=x onerror=alert(1)>" if malicious else f"Translation {evidence_suffix}",
            "interpretation": f"Interpretation {evidence_suffix}",
            "reviewer_intent": f"Intent {evidence_suffix}",
            "evidence_diff": "ignored; authority replaces this",
            "alternatives": [
                {"choice_id": "approve", "label": "Approve", "tradeoff": "Makes the scoped change."},
                {"choice_id": "decline", "label": "Decline", "tradeoff": "Leaves code unchanged."},
            ],
            "recommendation": "Choose approve.",
            "question": "Choose approve or decline?",
            "code_locations": [{"start_line": 3, "end_line": 4}],
        },
        "choices": [
            {
                "id": "approve",
                "label": "Approve",
                "tradeoff": "Makes the scoped change.",
                "semantic_action": {
                    "decision_type": "fix",
                    "summary": f"Apply semantic action {action_suffix}.",
                    "local_changes": [{"area": "src/module.py", "change_kind": "code"}],
                    "platform_actions": remote,
                },
            },
            {
                "id": "decline",
                "label": "Decline",
                "tradeoff": "Leaves code unchanged.",
                "semantic_action": {
                    "decision_type": "defer_reject",
                    "summary": f"Do not apply semantic action {action_suffix}.",
                    "local_changes": [],
                    "platform_actions": [],
                },
            },
        ],
        "recommended_choice_id": "approve",
        "action_envelope": envelope(with_remote=with_remote),
    }


def remote_only_candidate(
    state: dict, item_id: str, action: dict, *, action_suffix: str
) -> dict:
    candidate = analysis_candidate(
        state, item_id, action_suffix=action_suffix, with_remote=True
    )
    candidate["choices"][0]["semantic_action"]["local_changes"] = []
    candidate["choices"][0]["semantic_action"]["platform_actions"] = [
        copy.deepcopy(action)
    ]
    candidate["action_envelope"]["platform_actions"] = [copy.deepcopy(action)]
    return candidate


def github_snapshot(
    *,
    head: str = "a" * 40,
    resolved: bool = False,
    outdated: bool = True,
    with_reply: bool = False,
) -> dict:
    comments = [
        {
            "id": "COMMENT_ROOT",
            "body": "Please guard this branch.",
            "author": "reviewer",
            "path": "src/module.py",
            "line": 10,
            "start_line": None,
            "original_line": 8,
            "created_at": "2026-07-16T00:00:00Z",
        }
    ]
    if with_reply:
        comments.append(
            {
                "id": "COMMENT_REPLY",
                "body": "Also cover the retry path.",
                "author": "reviewer",
                "path": "src/module.py",
                "line": 12,
                "start_line": None,
                "original_line": 10,
                "created_at": "2026-07-16T00:01:00Z",
            }
        )
    return {
        "head_ref_oid": head,
        "base_ref_oid": "b" * 40,
        "reviews": [
            {"id": "REVIEW_NODE", "body": "Overall review context.", "author": "reviewer", "state": "CHANGES_REQUESTED"}
        ],
        "threads": [
            {
                "id": "THREAD_NODE",
                "is_resolved": resolved,
                "is_outdated": outdated,
                "review_id": "REVIEW_NODE",
                "comments": comments,
            }
        ],
        "actionable_reply_ids": ["COMMENT_REPLY"] if with_reply else [],
        "actionable_review_body_ids": ["REVIEW_NODE"] if not resolved else [],
    }


def pagination(
    *, reviews: bool = True, threads: bool = True, comments: bool = True
) -> dict:
    return {
        "reviews": {"complete": reviews, "pages": 2},
        "threads": {"complete": threads, "pages": 3},
        "comments": {"complete": comments, "pages_by_thread": {"THREAD_NODE": 2}},
    }


def github_collection(
    snapshot: dict | None,
    *,
    identity_number: int = 38,
    pages: dict | None = None,
    errors: list[str] | None = None,
) -> dict:
    return {
        "identity": {
            "host": "github.com",
            "owner": "hon454",
            "repo": "grimoire",
            "pr_number": identity_number,
        },
        "pagination": pages or pagination(),
        "errors": errors or [],
        "snapshot": snapshot,
    }


class ReviewStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name) / "grimoire"

    def apply(self, thread_id: str, candidate: dict, template: Path = TEMPLATE, after=None) -> dict:
        return review_state.apply_candidate(
            str(self.home), thread_id, candidate, template, after_state_replace=after
        )

    def initialize(self, source: dict | None = None, thread_id: str = THREAD_A) -> dict:
        return self.apply(
            thread_id,
            {
                "op": "initialize_session",
                "expected_revision": 0,
                "source": source or pasted_source(),
                "output_locale": "ko-KR",
            },
        )

    def state_path(self, thread_id: str = THREAD_A) -> Path:
        return self.home / "review-response" / "threads" / thread_id / "state.json"

    def html_path(self, thread_id: str = THREAD_A) -> Path:
        return self.state_path(thread_id).with_name("review.html")

    def request_and_approve(self, state: dict, item_id: str) -> dict:
        state = self.apply(
            state["owner"]["thread_id"],
            {
                "op": "request_decision",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "question": "Approve the exact Action Envelope?",
            },
        )
        pending = copy.deepcopy(state["pending_request"])
        return self.apply(
            state["owner"]["thread_id"],
            {
                "op": "record_decision",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "request_id": pending["request_id"],
                "choice_id": "approve",
            },
        )

    def analyzed_and_approved(self, *, with_remote: bool = False) -> tuple[dict, str]:
        state = self.initialize()
        item_id = state["item_order"][0]
        state = self.apply(THREAD_A, analysis_candidate(state, item_id, with_remote=with_remote))
        return self.request_and_approve(state, item_id), item_id

    def collect_github(self, state: dict, snapshot: dict | None, **kwargs) -> dict:
        return self.apply(
            state["owner"]["thread_id"],
            {
                "op": "update_github_source",
                "expected_revision": state["revision"],
                "collection": github_collection(snapshot, **kwargs),
            },
        )

    def stop(self, state: dict) -> dict:
        return self.apply(
            state["owner"]["thread_id"],
            {
                "op": "set_session_lifecycle",
                "expected_revision": state["revision"],
                "lifecycle": "stopped",
                "reason": "User approved stopping this Session.",
            },
        )

    def test_canonical_thread_uuid_is_required_and_nil_is_allowed(self) -> None:
        for bad in (
            "",
            "  ",
            "{12345678-1234-5678-1234-567812345678}",
            "ABCDEFAB-1234-5678-1234-567812345678",
            THREAD_A.replace("-", ""),
        ):
            with self.subTest(thread_id=bad):
                with self.assertRaises(review_state.StateError):
                    self.initialize(thread_id=bad)
        nil = "00000000-0000-0000-0000-000000000000"
        state = self.initialize(thread_id=nil)
        self.assertEqual(nil, state["owner"]["thread_id"])
        self.assertTrue(self.state_path(nil).exists())

    def test_same_thread_resumes_same_session_and_reinit_is_rejected(self) -> None:
        state = self.initialize()
        recovered = review_state.recover_html(str(self.home), THREAD_A, TEMPLATE)
        self.assertEqual(state, recovered)
        self.assertEqual(1, recovered["revision"])
        with self.assertRaisesRegex(review_state.StateError, "already exists"):
            self.initialize()

    def test_pasted_batch_and_authority_ids_are_immutable_and_unique(self) -> None:
        state_a = self.initialize()
        state_b = self.initialize(thread_id=THREAD_B)
        self.assertNotEqual(state_a["source"]["id"], state_b["source"]["id"])
        self.assertNotEqual(state_a["item_order"][0], state_b["item_order"][0])
        self.assertEqual("Please validate this edge case.", state_a["source"]["snapshot"]["batch_text"])
        with self.assertRaisesRegex(review_state.StateError, "unknown operation"):
            self.apply(
                THREAD_A,
                {"op": "replace_pasted_batch", "expected_revision": 1, "batch_text": "changed"},
            )

    def test_identical_items_in_one_pasted_batch_are_not_deduplicated(self) -> None:
        source = {
            "type": "pasted_feedback",
            "batch_text": "same\n\nsame",
            "items": [{"original": "same"}, {"original": "same"}],
        }
        state = self.initialize(source)
        self.assertEqual(2, len(state["item_order"]))
        self.assertNotEqual(state["item_order"][0], state["item_order"][1])

    def test_candidate_schema_expected_revision_and_operation_are_strict(self) -> None:
        state = self.initialize()
        item_id = state["item_order"][0]
        candidate = analysis_candidate(state, item_id)
        candidate["unknown"] = True
        with self.assertRaisesRegex(review_state.StateError, "unknown"):
            self.apply(THREAD_A, candidate)
        candidate = analysis_candidate(state, item_id)
        candidate["expected_revision"] = True
        with self.assertRaisesRegex(review_state.StateError, "integer"):
            self.apply(THREAD_A, candidate)
        candidate = analysis_candidate(state, item_id)
        candidate["expected_revision"] = 0
        with self.assertRaisesRegex(review_state.StateError, "stale expected_revision"):
            self.apply(THREAD_A, candidate)
        with self.assertRaisesRegex(review_state.StateError, "unknown operation"):
            self.apply(THREAD_A, {"op": "migrate", "expected_revision": 1})
        persisted = json.loads(self.state_path().read_text())
        self.assertEqual(1, persisted["revision"])

    def test_action_envelope_must_explicitly_authorize_or_exclude_sensitive_repository_actions(self) -> None:
        state = self.initialize()
        item_id = state["item_order"][0]
        candidate = analysis_candidate(state, item_id)
        candidate["action_envelope"]["excluded"].remove("push")
        with self.assertRaisesRegex(review_state.StateError, "authorize or exclude push"):
            self.apply(THREAD_A, candidate)
        candidate = analysis_candidate(state, item_id)
        candidate["action_envelope"]["repository_actions"] = ["push"]
        with self.assertRaisesRegex(review_state.StateError, "both authorize and exclude push"):
            self.apply(THREAD_A, candidate)

    def test_json_limit_duplicate_keys_and_nonfinite_values_fail_closed(self) -> None:
        with self.assertRaisesRegex(review_state.StateError, "10 MiB"):
            review_state.decode_json_bytes(b" " * (review_state.MAX_JSON_BYTES + 1), "candidate")
        with self.assertRaisesRegex(review_state.StateError, "duplicate"):
            review_state.decode_json_bytes(b'{"op":"x","op":"y"}', "candidate")
        with self.assertRaisesRegex(review_state.StateError, "constant"):
            review_state.decode_json_bytes(b'{"value":NaN}', "candidate")

    def test_obvious_credentials_are_rejected_before_session_creation(self) -> None:
        source = pasted_source('password="correct-horse-battery-staple"')
        with self.assertRaisesRegex(review_state.StateError, "credential"):
            self.initialize(source)
        self.assertFalse(self.state_path().parent.exists())

    def test_pending_request_is_invalidated_by_decision_facing_presentation_changes(self) -> None:
        state = self.initialize()
        item_id = state["item_order"][0]
        state = self.apply(THREAD_A, analysis_candidate(state, item_id))
        state = self.apply(
            THREAD_A,
            {
                "op": "request_decision",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "question": "Which exact option should run?",
            },
        )
        candidate = analysis_candidate(state, item_id)
        candidate["presentation"]["question"] = state["pending_request"]["question"]
        candidate["presentation"]["alternatives"][0]["label"] = "Approve exactly"
        state = self.apply(THREAD_A, candidate)
        self.assertIsNone(state["pending_request"])
        self.assertEqual("invalidated", state["request_history"][-1]["status"])

        state = self.initialize(thread_id=THREAD_B)
        item_id = state["item_order"][0]
        candidate = analysis_candidate(state, item_id)
        candidate["presentation"]["alternatives"] = []
        state = self.apply(THREAD_B, candidate)
        state = self.apply(
            THREAD_B,
            {"op": "request_decision", "expected_revision": state["revision"], "item_id": item_id, "question": "Choose a fallback label?"},
        )
        candidate = analysis_candidate(state, item_id)
        candidate["presentation"]["alternatives"] = []
        candidate["presentation"]["question"] = state["pending_request"]["question"]
        candidate["choices"][0]["label"] = "Changed fallback label"
        state = self.apply(THREAD_B, candidate)
        self.assertIsNone(state["pending_request"])

    def test_code_locations_are_presentation_only_and_payload_is_semantic(self) -> None:
        state = self.initialize()
        item_id = state["item_order"][0]
        state = self.apply(THREAD_A, analysis_candidate(state, item_id, with_remote=True))
        first = state["items"][item_id]["proposal"]["decision_fingerprint"]
        current_code = state["items"][item_id]["evidence"]["versions"][0]["semantic"]["code"][0]
        self.assertNotIn("start_line", current_code)
        candidate = analysis_candidate(state, item_id, with_remote=True)
        candidate["presentation"]["code_locations"] = [{"start_line": 30, "end_line": 31}]
        state = self.apply(THREAD_A, candidate)
        self.assertEqual(first, state["items"][item_id]["proposal"]["decision_fingerprint"])
        candidate = analysis_candidate(state, item_id, with_remote=True)
        candidate["choices"][0]["semantic_action"]["platform_actions"][0]["payload"]["body"] = "Different exact body."
        candidate["action_envelope"]["platform_actions"][0]["payload"]["body"] = "Different exact body."
        state = self.apply(THREAD_A, candidate)
        self.assertNotEqual(first, state["items"][item_id]["proposal"]["decision_fingerprint"])
        malicious = "</pre><script>alert('payload')</script>"
        candidate = analysis_candidate(state, item_id, with_remote=True)
        candidate["choices"][0]["semantic_action"]["platform_actions"][0]["payload"]["body"] = malicious
        candidate["action_envelope"]["platform_actions"][0]["payload"]["body"] = malicious
        state = self.apply(THREAD_A, candidate)
        rendered = render_review.render_state(state, TEMPLATE.read_text())
        self.assertIn("Exact payload", rendered)
        self.assertIn("&lt;script&gt;alert", rendered)
        self.assertNotIn(malicious, rendered)

    def test_local_work_requires_explicit_reconciliation_after_redecision(self) -> None:
        state, item_id = self.analyzed_and_approved()
        old_authorization = state["items"][item_id]["active_authorization"]["id"]
        state = self.apply(
            THREAD_A,
            {
                "op": "start_local_work",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "area": "src/module.py",
                "change_kind": "code",
            },
        )
        state = self.apply(
            THREAD_A,
            analysis_candidate(state, item_id, action_suffix="replacement"),
        )
        state = self.request_and_approve(state, item_id)
        with self.assertRaisesRegex(review_state.StateError, "not_started"):
            self.apply(
                THREAD_A,
                {
                    "op": "start_local_work",
                    "expected_revision": state["revision"],
                    "item_id": item_id,
                    "area": "src/module.py",
                    "change_kind": "code",
                },
            )
        state = self.apply(
            THREAD_A,
            {
                "op": "reconcile_local_work",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "outcome": "superseded",
                "reason": "The previous authorization was replaced.",
                "validation_summary": "",
            },
        )
        history = state["items"][item_id]["local_attempt_history"]
        self.assertEqual(old_authorization, history[-1]["authorization_id"])
        self.assertEqual("superseded", history[-1]["status"])
        self.assertEqual("not_started", state["items"][item_id]["local_progress"]["status"])

    def test_late_remote_results_are_bound_to_their_authorization(self) -> None:
        def prepared_old_attempt(thread_id: str) -> tuple[dict, str, dict, str]:
            state = self.initialize(thread_id=thread_id)
            item_id = state["item_order"][0]
            state = self.apply(thread_id, analysis_candidate(state, item_id, with_remote=True))
            state = self.request_and_approve(state, item_id)
            old_auth = state["items"][item_id]["active_authorization"]["id"]
            state = self.apply(
                thread_id,
                {
                    "op": "prepare_remote_mutation",
                    "expected_revision": state["revision"],
                    "item_id": item_id,
                    "action": platform_action(),
                },
            )
            journal = state["items"][item_id]["remote_mutations"][0]
            attempt = journal["attempts"][0]
            self.assertEqual(old_auth, attempt["authorization_id"])
            self.assertEqual(review_state.fingerprint(journal["action"]), attempt["action_fingerprint"])
            state = self.apply(
                thread_id,
                {
                    "op": "start_remote_mutation",
                    "expected_revision": state["revision"],
                    "item_id": item_id,
                    "journal_id": journal["id"],
                    "attempt_id": attempt["id"],
                },
            )
            state = self.apply(
                thread_id,
                analysis_candidate(state, item_id, action_suffix="new authorization", with_remote=True),
            )
            state = self.request_and_approve(state, item_id)
            return state, item_id, journal, state["items"][item_id]["active_authorization"]["id"]

        failed_state, item_id, journal, current_auth = prepared_old_attempt(THREAD_A)
        failed_state = self.apply(
            THREAD_A,
            {
                "op": "finish_remote_mutation",
                "expected_revision": failed_state["revision"],
                "item_id": item_id,
                "journal_id": journal["id"],
                "attempt_id": journal["attempts"][0]["id"],
                "outcome": "failed",
                "summary": "Confirmed the old call was not applied.",
                "confirmed_not_applied": True,
            },
        )
        self.assertEqual(current_auth, failed_state["items"][item_id]["active_authorization"]["id"])
        self.assertEqual("valid", failed_state["items"][item_id]["evidence"]["current_status"])

        success_state, item_id, journal, _current_auth = prepared_old_attempt(THREAD_B)
        success_state = self.apply(
            THREAD_B,
            {
                "op": "finish_remote_mutation",
                "expected_revision": success_state["revision"],
                "item_id": item_id,
                "journal_id": journal["id"],
                "attempt_id": journal["attempts"][0]["id"],
                "outcome": "succeeded",
                "summary": "The old call applied after authorization changed.",
                "confirmed_not_applied": False,
            },
        )
        self.assertIsNone(success_state["items"][item_id]["active_authorization"])
        self.assertEqual("stale", success_state["items"][item_id]["evidence"]["current_status"])

    def test_late_remote_reconciliation_obeys_superseded_result_rules(self) -> None:
        def uncertain_then_reapproved(thread_id: str) -> tuple[dict, str, dict, dict]:
            state = self.initialize(thread_id=thread_id)
            item_id = state["item_order"][0]
            state = self.apply(thread_id, analysis_candidate(state, item_id, with_remote=True))
            state = self.request_and_approve(state, item_id)
            state = self.apply(
                thread_id,
                {"op": "prepare_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "action": platform_action()},
            )
            journal = state["items"][item_id]["remote_mutations"][0]
            attempt = journal["attempts"][0]
            state = self.apply(
                thread_id,
                {"op": "start_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "journal_id": journal["id"], "attempt_id": attempt["id"]},
            )
            state = self.apply(
                thread_id,
                {"op": "mark_remote_uncertain", "expected_revision": state["revision"], "item_id": item_id, "journal_id": journal["id"], "attempt_id": attempt["id"], "reason": "Unknown call boundary."},
            )
            state = self.apply(
                thread_id,
                analysis_candidate(state, item_id, action_suffix="replacement", with_remote=True),
            )
            state = self.request_and_approve(state, item_id)
            return state, item_id, journal, attempt

        state, item_id, journal, attempt = uncertain_then_reapproved(THREAD_A)
        state = self.apply(
            THREAD_A,
            {"op": "reconcile_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "journal_id": journal["id"], "attempt_id": attempt["id"], "outcome": "succeeded", "summary": "Old call was applied.", "confirmed_not_applied": False},
        )
        self.assertIsNone(state["items"][item_id]["active_authorization"])
        self.assertEqual("stale", state["items"][item_id]["evidence"]["current_status"])

        state, item_id, journal, attempt = uncertain_then_reapproved(THREAD_B)
        current = state["items"][item_id]["active_authorization"]["id"]
        state = self.apply(
            THREAD_B,
            {"op": "reconcile_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "journal_id": journal["id"], "attempt_id": attempt["id"], "outcome": "failed", "summary": "Old call was not applied.", "confirmed_not_applied": True},
        )
        self.assertEqual(current, state["items"][item_id]["active_authorization"]["id"])
        self.assertEqual("valid", state["items"][item_id]["evidence"]["current_status"])

    def test_verified_prior_success_can_be_adopted_by_new_authorization(self) -> None:
        state = self.initialize()
        item_id = state["item_order"][0]
        state = self.apply(
            THREAD_A,
            remote_only_candidate(
                state, item_id, platform_action(), action_suffix="first"
            ),
        )
        state = self.request_and_approve(state, item_id)
        state = self.apply(
            THREAD_A,
            {"op": "prepare_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "action": platform_action()},
        )
        journal = state["items"][item_id]["remote_mutations"][0]
        source_attempt = journal["attempts"][0]
        state = self.apply(
            THREAD_A,
            {"op": "start_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "journal_id": journal["id"], "attempt_id": source_attempt["id"]},
        )
        state = self.apply(
            THREAD_A,
            {"op": "finish_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "journal_id": journal["id"], "attempt_id": source_attempt["id"], "outcome": "succeeded", "summary": "Reply exists remotely.", "confirmed_not_applied": False},
        )
        state = self.apply(
            THREAD_A,
            {"op": "close_authorization", "expected_revision": state["revision"], "item_id": item_id, "reason": "First remote action completed."},
        )
        changed_action = platform_action()
        changed_action["summary"] = "Post the same approved reply after verification."
        state = self.apply(
            THREAD_A,
            remote_only_candidate(
                state,
                item_id,
                changed_action,
                action_suffix="second",
            ),
        )
        state = self.request_and_approve(state, item_id)
        with self.assertRaisesRegex(review_state.StateError, "remote effect already has a journal"):
            self.apply(
                THREAD_A,
                {"op": "prepare_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "action": changed_action},
            )
        with self.assertRaisesRegex(review_state.StateError, "outside the active authorization"):
            self.apply(
                THREAD_A,
                {"op": "retry_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "journal_id": journal["id"]},
            )
        current_authorization = state["items"][item_id]["active_authorization"]["id"]
        state = self.apply(
            THREAD_A,
            {"op": "adopt_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "action": changed_action, "source_journal_id": journal["id"], "source_attempt_id": source_attempt["id"], "verification_summary": "Verified the exact reply is still present remotely."},
        )
        self.assertEqual(2, len(state["items"][item_id]["remote_mutations"]))
        adopted_journal = state["items"][item_id]["remote_mutations"][1]
        self.assertEqual(changed_action, adopted_journal["action"])
        adopted = adopted_journal["attempts"][-1]
        self.assertEqual("succeeded", adopted["status"])
        self.assertIsNone(adopted["started_at"])
        self.assertEqual(source_attempt["id"], adopted["adopted_from_attempt_id"])
        self.assertEqual(current_authorization, adopted["authorization_id"])
        state = self.apply(
            THREAD_A,
            {"op": "close_authorization", "expected_revision": state["revision"], "item_id": item_id, "reason": "Verified prior success was adopted."},
        )
        self.assertIsNone(state["items"][item_id]["active_authorization"])

    def test_rereview_reviewer_order_is_one_remote_effect(self) -> None:
        first_action = {
            "kind": "github_rereview",
            "target": "PR_NODE",
            "summary": "Request another review.",
            "reviewer_authored": True,
            "payload": {"reviewers": ["Alice", "bob"]},
        }
        reversed_action = copy.deepcopy(first_action)
        reversed_action["payload"]["reviewers"].reverse()
        reversed_action["payload"]["reviewers"][1] = "alice"
        empty_action = copy.deepcopy(first_action)
        empty_action["payload"]["reviewers"] = []
        with self.assertRaisesRegex(review_state.StateError, "must not be empty"):
            review_state.validate_platform_action(empty_action, "action")
        duplicate_action = copy.deepcopy(first_action)
        duplicate_action["payload"]["reviewers"] = ["Alice", "alice"]
        with self.assertRaisesRegex(review_state.StateError, "case-insensitive duplicates"):
            review_state.validate_platform_action(duplicate_action, "action")
        state = self.initialize()
        item_id = state["item_order"][0]
        state = self.apply(
            THREAD_A,
            remote_only_candidate(
                state, item_id, first_action, action_suffix="first rereview"
            ),
        )
        state = self.request_and_approve(state, item_id)
        state = self.apply(
            THREAD_A,
            {
                "op": "prepare_remote_mutation",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "action": first_action,
            },
        )
        journal = state["items"][item_id]["remote_mutations"][0]
        attempt = journal["attempts"][0]
        state = self.apply(
            THREAD_A,
            {"op": "start_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "journal_id": journal["id"], "attempt_id": attempt["id"]},
        )
        state = self.apply(
            THREAD_A,
            {"op": "finish_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "journal_id": journal["id"], "attempt_id": attempt["id"], "outcome": "succeeded", "summary": "Review requests exist.", "confirmed_not_applied": False},
        )
        state = self.apply(
            THREAD_A,
            {"op": "close_authorization", "expected_revision": state["revision"], "item_id": item_id, "reason": "First request completed."},
        )
        state = self.apply(
            THREAD_A,
            remote_only_candidate(
                state, item_id, reversed_action, action_suffix="second rereview"
            ),
        )
        state = self.request_and_approve(state, item_id)
        with self.assertRaisesRegex(review_state.StateError, "remote effect already has a journal"):
            self.apply(
                THREAD_A,
                {"op": "prepare_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "action": reversed_action},
            )
        state = self.apply(
            THREAD_A,
            {"op": "adopt_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "action": reversed_action, "source_journal_id": journal["id"], "source_attempt_id": attempt["id"], "verification_summary": "Verified both review requests remain active."},
        )
        self.assertEqual(2, len(state["items"][item_id]["remote_mutations"]))

    def test_remote_journal_rejects_reused_authorization_id(self) -> None:
        state, item_id = self.analyzed_and_approved(with_remote=True)
        state = self.apply(
            THREAD_A,
            {
                "op": "prepare_remote_mutation",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "action": platform_action(),
            },
        )
        journal = state["items"][item_id]["remote_mutations"][0]
        first = journal["attempts"][0]
        first.update(
            {
                "status": "failed",
                "started_at": "2026-07-16T00:00:01+00:00",
                "finished_at": "2026-07-16T00:00:02+00:00",
                "summary": "Confirmed not applied.",
                "confirmed_not_applied": True,
            }
        )
        duplicate = copy.deepcopy(first)
        duplicate.update(
            {
                "id": str(uuid.uuid4()),
                "status": "pending",
                "created_at": "2026-07-16T00:00:03+00:00",
                "started_at": None,
                "finished_at": None,
                "summary": "",
                "confirmed_not_applied": False,
            }
        )
        journal["attempts"].append(duplicate)
        with self.assertRaisesRegex(review_state.StateError, "authorization IDs must be unique"):
            review_state.validate_state(state, THREAD_A)

    def test_old_completed_local_slot_must_be_reconciled_before_new_close(self) -> None:
        state, item_id = self.analyzed_and_approved()
        state = self.apply(
            THREAD_A,
            {"op": "start_local_work", "expected_revision": state["revision"], "item_id": item_id, "area": "src/module.py", "change_kind": "code"},
        )
        state = self.apply(
            THREAD_A,
            {"op": "complete_local_work", "expected_revision": state["revision"], "item_id": item_id, "validation_summary": "Old work validated."},
        )
        state = self.apply(THREAD_A, analysis_candidate(state, item_id, action_suffix="replacement"))
        state = self.apply(
            THREAD_A,
            {"op": "request_decision", "expected_revision": state["revision"], "item_id": item_id, "question": "Choose no-op?"},
        )
        state = self.apply(
            THREAD_A,
            {"op": "record_decision", "expected_revision": state["revision"], "item_id": item_id, "request_id": state["pending_request"]["request_id"], "choice_id": "decline"},
        )
        close = {"op": "close_authorization", "expected_revision": state["revision"], "item_id": item_id, "reason": "No-op is terminal."}
        with self.assertRaisesRegex(review_state.StateError, "reconcile"):
            self.apply(THREAD_A, close)
        state = self.apply(
            THREAD_A,
            {"op": "reconcile_local_work", "expected_revision": state["revision"], "item_id": item_id, "outcome": "completed", "reason": "Archive old completed work.", "validation_summary": ""},
        )
        close["expected_revision"] = state["revision"]
        state = self.apply(THREAD_A, close)
        self.assertEqual("completed", state["items"][item_id]["local_attempt_history"][-1]["status"])

    def test_authorization_closes_only_after_every_approved_action_is_terminal(self) -> None:
        state, item_id = self.analyzed_and_approved(with_remote=True)
        close = lambda value: self.apply(
            THREAD_A,
            {
                "op": "close_authorization",
                "expected_revision": value["revision"],
                "item_id": item_id,
                "reason": "All approved work is terminal.",
            },
        )
        with self.assertRaises(review_state.StateError):
            close(state)
        state = self.apply(
            THREAD_A,
            {"op": "start_local_work", "expected_revision": state["revision"], "item_id": item_id, "area": "src/module.py", "change_kind": "code"},
        )
        state = self.apply(
            THREAD_A,
            {"op": "complete_local_work", "expected_revision": state["revision"], "item_id": item_id, "validation_summary": "Unit tests passed."},
        )
        with self.assertRaises(review_state.StateError):
            close(state)
        state = self.apply(
            THREAD_A,
            {"op": "prepare_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "action": platform_action()},
        )
        journal = state["items"][item_id]["remote_mutations"][0]
        attempt = journal["attempts"][0]
        state = self.apply(
            THREAD_A,
            {"op": "start_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "journal_id": journal["id"], "attempt_id": attempt["id"]},
        )
        state = self.apply(
            THREAD_A,
            {"op": "finish_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "journal_id": journal["id"], "attempt_id": attempt["id"], "outcome": "succeeded", "summary": "Reply posted.", "confirmed_not_applied": False},
        )
        state = close(state)
        self.assertIsNone(state["items"][item_id]["active_authorization"])

    def test_completed_lifecycle_requires_ready_fully_decided_terminal_state(self) -> None:
        state = self.initialize()
        finish = lambda value: self.apply(
            THREAD_A,
            {"op": "set_session_lifecycle", "expected_revision": value["revision"], "lifecycle": "completed", "reason": "Everything is complete."},
        )
        with self.assertRaises(review_state.StateError):
            finish(state)
        item_id = state["item_order"][0]
        state = self.apply(THREAD_A, analysis_candidate(state, item_id))
        state = self.apply(
            THREAD_A,
            {"op": "request_decision", "expected_revision": state["revision"], "item_id": item_id, "question": "Decline this change?"},
        )
        request_id = state["pending_request"]["request_id"]
        with self.assertRaisesRegex(review_state.StateError, "pending"):
            finish(state)
        state = self.apply(
            THREAD_A,
            {"op": "record_decision", "expected_revision": state["revision"], "item_id": item_id, "request_id": request_id, "choice_id": "decline"},
        )
        state = self.apply(
            THREAD_A,
            {"op": "close_authorization", "expected_revision": state["revision"], "item_id": item_id, "reason": "The no-op decision is terminal."},
        )
        state = finish(state)
        self.assertEqual("completed", state["lifecycle"])

    def test_complete_pagination_requires_at_least_one_page(self) -> None:
        state = self.initialize(github_source())
        pages = pagination()
        pages["reviews"]["pages"] = 0
        with self.assertRaisesRegex(review_state.StateError, "at least one"):
            self.collect_github(state, github_snapshot(), pages=pages)

    def test_stopped_session_still_records_late_local_and_remote_results(self) -> None:
        state, item_id = self.analyzed_and_approved()
        state = self.apply(
            THREAD_A,
            {"op": "start_local_work", "expected_revision": state["revision"], "item_id": item_id, "area": "src/module.py", "change_kind": "code"},
        )
        state = self.stop(state)
        state = self.apply(
            THREAD_A,
            {"op": "reconcile_local_work", "expected_revision": state["revision"], "item_id": item_id, "outcome": "superseded", "reason": "Session stopped before completion.", "validation_summary": ""},
        )
        self.assertEqual("superseded", state["items"][item_id]["local_attempt_history"][-1]["status"])

        state = self.initialize(thread_id=THREAD_B)
        item_id = state["item_order"][0]
        state = self.apply(THREAD_B, analysis_candidate(state, item_id, with_remote=True))
        state = self.request_and_approve(state, item_id)
        state = self.apply(
            THREAD_B,
            {"op": "prepare_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "action": platform_action()},
        )
        journal = state["items"][item_id]["remote_mutations"][0]
        attempt = journal["attempts"][0]
        state = self.apply(
            THREAD_B,
            {"op": "start_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "journal_id": journal["id"], "attempt_id": attempt["id"]},
        )
        state = self.stop(state)
        state = self.apply(
            THREAD_B,
            {"op": "finish_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "journal_id": journal["id"], "attempt_id": attempt["id"], "outcome": "succeeded", "summary": "Late call completed.", "confirmed_not_applied": False},
        )
        self.assertEqual("succeeded", state["items"][item_id]["remote_mutations"][0]["attempts"][0]["status"])

    def test_orphan_html_and_non_private_managed_paths_fail_closed(self) -> None:
        _home, thread_dir = review_state.session_directory(str(self.home), THREAD_A, create=True)
        orphan = thread_dir / "review.html"
        orphan.write_text("preserve me")
        orphan.chmod(0o600)
        with self.assertRaisesRegex(review_state.StateError, "without state.json"):
            self.initialize()
        self.assertEqual("preserve me", orphan.read_text())
        orphan.unlink()
        state = self.initialize()
        state_path = self.state_path()
        state_path.chmod(0o644)
        with self.assertRaisesRegex(review_state.StateError, "0600"):
            review_state.recover_html(str(self.home), THREAD_A, TEMPLATE)
        state_path.chmod(0o600)
        state_path.parent.chmod(0o755)
        with self.assertRaisesRegex(review_state.StateError, "0700"):
            review_state.recover_html(str(self.home), THREAD_A, TEMPLATE)
        self.assertEqual(1, state["revision"])

    def test_renderer_uses_pending_question_locale_and_rejects_hardlink_alias(self) -> None:
        state = self.initialize()
        item_id = state["item_order"][0]
        state = self.apply(THREAD_A, analysis_candidate(state, item_id))
        state = self.apply(
            THREAD_A,
            {"op": "request_decision", "expected_revision": state["revision"], "item_id": item_id, "question": "Authoritative pending question?"},
        )
        state["items"][item_id]["presentation"]["question"] = "Stale presentation question"
        rendered = render_review.render_state(state, TEMPLATE.read_text())
        self.assertIn('<html lang="en">', rendered)
        self.assertIn('lang="ko-KR"', rendered)
        self.assertNotIn('<section lang="ko-KR"', rendered)
        self.assertIn("Authoritative pending question?", rendered)
        self.assertNotIn("Stale presentation question", rendered)
        state_path = self.state_path()
        before = state_path.read_bytes()
        alias = state_path.with_name("hardlink-output.html")
        os.link(state_path, alias)
        with mock.patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(1, render_review.main(["--state", str(state_path), "--output", str(alias)]))
        self.assertEqual(before, state_path.read_bytes())
        output = state_path.with_name("standalone.html")
        output.write_text("old output")
        output.chmod(0o600)
        output_tmp = output.with_name(f".{output.name}.tmp")
        os.link(output, output_tmp)
        with mock.patch.object(render_review.os, "replace", side_effect=OSError("replace failed")):
            with mock.patch("sys.stderr", new=io.StringIO()):
                self.assertEqual(1, render_review.main(["--state", str(state_path), "--output", str(output)]))
        self.assertEqual("old output", output.read_text())
        self.assertIn("currentColor", TEMPLATE.read_text())

    def test_decision_fingerprint_a_b_a_does_not_revive_authorization(self) -> None:
        state, item_id = self.analyzed_and_approved()
        item = state["items"][item_id]
        fingerprint_a = item["proposal"]["decision_fingerprint"]
        authorization_a = copy.deepcopy(item["active_authorization"])
        evidence_version = item["evidence"]["current_version"]

        state = self.apply(
            THREAD_A,
            analysis_candidate(state, item_id, evidence_suffix="A", action_suffix="B"),
        )
        item = state["items"][item_id]
        self.assertIsNone(item["active_authorization"])
        self.assertNotEqual(fingerprint_a, item["proposal"]["decision_fingerprint"])
        self.assertEqual(evidence_version, item["evidence"]["current_version"])

        state = self.apply(
            THREAD_A,
            analysis_candidate(state, item_id, evidence_suffix="A", action_suffix="A"),
        )
        item = state["items"][item_id]
        self.assertEqual(fingerprint_a, item["proposal"]["decision_fingerprint"])
        self.assertIsNone(item["active_authorization"])
        self.assertEqual(authorization_a["id"], item["authorization_history"][0]["id"])
        with self.assertRaisesRegex(review_state.StateError, "current Item"):
            self.apply(
                THREAD_A,
                {"op": "set_session_lifecycle", "expected_revision": state["revision"], "lifecycle": "completed", "reason": "Must not reuse decision A."},
            )

        state = self.apply(
            THREAD_A,
            {
                "op": "request_decision",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "question": "Approve A again?",
            },
        )
        self.assertNotEqual(authorization_a["request_id"], state["pending_request"]["request_id"])

    def test_stale_to_same_evidence_reuses_version_but_not_authorization(self) -> None:
        state, item_id = self.analyzed_and_approved()
        old = copy.deepcopy(state["items"][item_id]["evidence"]["versions"][0])
        old_proposal_id = state["items"][item_id]["proposal"]["id"]
        old_proposal_generation = state["items"][item_id]["proposal"]["generation"]
        state = self.apply(
            THREAD_A,
            {
                "op": "mark_evidence_stale",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "reason": "New source signal",
                "diff": "Must re-check semantics.",
            },
        )
        self.assertEqual("stale", state["items"][item_id]["evidence"]["current_status"])
        self.assertIsNone(state["items"][item_id]["active_authorization"])
        state = self.apply(THREAD_A, analysis_candidate(state, item_id, evidence_suffix="A"))
        evidence = state["items"][item_id]["evidence"]
        self.assertEqual("valid", evidence["current_status"])
        self.assertEqual(1, evidence["current_version"])
        self.assertEqual(old, evidence["versions"][0])
        self.assertIsNone(state["items"][item_id]["active_authorization"])
        self.assertNotEqual(old_proposal_id, state["items"][item_id]["proposal"]["id"])
        self.assertEqual(
            old_proposal_generation + 1,
            state["items"][item_id]["proposal"]["generation"],
        )
        corrupt = copy.deepcopy(state)
        corrupt["items"][item_id]["proposal"]["id"] = old_proposal_id
        with self.assertRaisesRegex(review_state.StateError, "Evidence generation"):
            review_state.validate_state(corrupt, THREAD_A)
        corrupt = copy.deepcopy(state)
        current_proposal_id = corrupt["items"][item_id]["proposal"]["id"]
        corrupt["items"][item_id]["decision_history"][-1][
            "proposal_id"
        ] = current_proposal_id
        corrupt["request_history"][-1]["proposal_id"] = current_proposal_id
        with self.assertRaisesRegex(review_state.StateError, "unknown proposal generation"):
            review_state.validate_state(corrupt, THREAD_A)
        corrupt = copy.deepcopy(state)
        forged_fingerprint = "f" * 64
        corrupt["items"][item_id]["decision_history"][-1][
            "decision_fingerprint"
        ] = forged_fingerprint
        corrupt["items"][item_id]["authorization_history"][-1][
            "decision_fingerprint"
        ] = forged_fingerprint
        corrupt["request_history"][-1][
            "decision_fingerprint"
        ] = forged_fingerprint
        with self.assertRaisesRegex(review_state.StateError, "unknown proposal generation"):
            review_state.validate_state(corrupt, THREAD_A)
        with self.assertRaisesRegex(review_state.StateError, "current Item"):
            self.apply(
                THREAD_A,
                {
                    "op": "set_session_lifecycle",
                    "expected_revision": state["revision"],
                    "lifecycle": "completed",
                    "reason": "A stale-generation decision must not be reused.",
                },
            )

    def test_changed_evidence_invalidates_old_version_and_creates_new_valid_version(self) -> None:
        state = self.initialize()
        item_id = state["item_order"][0]
        state = self.apply(THREAD_A, analysis_candidate(state, item_id, evidence_suffix="A"))
        first = copy.deepcopy(state["items"][item_id]["evidence"]["versions"][0])
        state = self.apply(
            THREAD_A,
            {
                "op": "mark_evidence_stale",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "reason": "Head changed",
                "diff": "Code must be re-evaluated.",
            },
        )
        state = self.apply(THREAD_A, analysis_candidate(state, item_id, evidence_suffix="B"))
        versions = state["items"][item_id]["evidence"]["versions"]
        self.assertEqual(["invalid", "valid"], [version["status"] for version in versions])
        self.assertEqual(2, state["items"][item_id]["evidence"]["current_version"])
        self.assertEqual(first["semantic"], versions[0]["semantic"])
        self.assertEqual(first["fingerprint"], versions[0]["fingerprint"])

    def test_only_current_pending_request_can_be_consumed_and_ids_are_not_reused(self) -> None:
        state = self.initialize()
        item_id = state["item_order"][0]
        state = self.apply(THREAD_A, analysis_candidate(state, item_id))
        state = self.apply(
            THREAD_A,
            {
                "op": "request_decision",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "question": "Approve?",
            },
        )
        request = copy.deepcopy(state["pending_request"])
        wrong = str(uuid.uuid4())
        with self.assertRaisesRegex(review_state.StateError, "current pending"):
            self.apply(
                THREAD_A,
                {
                    "op": "record_decision",
                    "expected_revision": state["revision"],
                    "item_id": item_id,
                    "request_id": wrong,
                    "choice_id": "approve",
                },
            )
        state = self.apply(
            THREAD_A,
            {
                "op": "record_decision",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "request_id": request["request_id"],
                "choice_id": "approve",
            },
        )
        self.assertIsNone(state["pending_request"])
        self.assertEqual("consumed", state["request_history"][-1]["status"])
        with self.assertRaisesRegex(review_state.StateError, "no pending"):
            self.apply(
                THREAD_A,
                {
                    "op": "record_decision",
                    "expected_revision": state["revision"],
                    "item_id": item_id,
                    "request_id": request["request_id"],
                    "choice_id": "approve",
                },
            )

    def test_fingerprint_change_invalidates_pending_request_in_same_transition(self) -> None:
        state = self.initialize()
        item_id = state["item_order"][0]
        state = self.apply(THREAD_A, analysis_candidate(state, item_id))
        state = self.apply(
            THREAD_A,
            {
                "op": "request_decision",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "question": "Approve A?",
            },
        )
        request_id = state["pending_request"]["request_id"]
        state = self.apply(
            THREAD_A,
            analysis_candidate(state, item_id, evidence_suffix="A", action_suffix="B"),
        )
        self.assertIsNone(state["pending_request"])
        self.assertEqual(request_id, state["request_history"][-1]["request_id"])
        self.assertEqual("invalidated", state["request_history"][-1]["status"])

    def test_presentation_and_choice_order_do_not_change_decision_fingerprint(self) -> None:
        state, item_id = self.analyzed_and_approved()
        before = state["items"][item_id]
        fingerprint_before = before["proposal"]["decision_fingerprint"]
        authorization_before = copy.deepcopy(before["active_authorization"])
        candidate = analysis_candidate(state, item_id)
        candidate["choices"].reverse()
        candidate["choices"][0]["label"] = "Display-only rename"
        candidate["presentation"]["alternatives"].reverse()
        candidate["presentation"]["translation"] = "Changed display wording only."
        state = self.apply(THREAD_A, candidate)
        item = state["items"][item_id]
        self.assertEqual(fingerprint_before, item["proposal"]["decision_fingerprint"])
        self.assertEqual(authorization_before, item["active_authorization"])

    def test_incomplete_github_pagination_preserves_snapshot_and_fails_closed(self) -> None:
        for incomplete_part in ("reviews", "threads", "comments"):
            with self.subTest(part=incomplete_part):
                other_thread = str(uuid.uuid4())
                state = self.initialize(github_source(), thread_id=other_thread)
                state = self.collect_github(state, github_snapshot())
                previous_snapshot = copy.deepcopy(state["source"]["snapshot"])
                pages = pagination()
                pages[incomplete_part]["complete"] = False
                state = self.collect_github(state, None, pages=pages, errors=[f"{incomplete_part} incomplete"])
                self.assertEqual(previous_snapshot, state["source"]["snapshot"])
                self.assertEqual("stale", state["source"]["status"])
                self.assertEqual("incomplete", state["source"]["collection"]["status"])
                self.assertTrue(
                    all(item["evidence"]["current_status"] == "stale" for item in state["items"].values())
                )

    def test_incomplete_github_collection_rejects_a_partial_non_null_snapshot(self) -> None:
        state = self.initialize(github_source())
        with self.assertRaisesRegex(review_state.StateError, "snapshot: null"):
            self.collect_github(
                state,
                github_snapshot(),
                pages=pagination(comments=False),
                errors=["comments cursor failed"],
            )
        persisted = review_state.load_state(self.state_path().parent, THREAD_A)
        self.assertEqual(1, persisted["revision"])
        self.assertIsNone(persisted["source"]["snapshot"])

    def test_reply_subitem_requires_an_unresolved_thread(self) -> None:
        state = self.initialize(github_source())
        with self.assertRaisesRegex(review_state.StateError, "unresolved inline thread"):
            self.collect_github(state, github_snapshot(resolved=True, with_reply=True))

    def test_state_validation_cross_checks_collection_and_item_source_identity(self) -> None:
        state = self.initialize(github_source())
        state = self.collect_github(state, github_snapshot(with_reply=True))
        corruptions = []

        bad_collection = copy.deepcopy(state)
        bad_collection["source"]["collection"]["errors"] = ["late cursor error"]
        corruptions.append(bad_collection)

        bad_item = copy.deepcopy(state)
        item_id = bad_item["item_order"][0]
        bad_item["items"][item_id]["source_key"] = "thread:OTHER"
        corruptions.append(bad_item)

        bad_actionability = copy.deepcopy(state)
        bad_actionability["source"]["snapshot"]["threads_by_id"]["THREAD_NODE"][
            "is_resolved"
        ] = True
        corruptions.append(bad_actionability)

        for index, corrupt in enumerate(corruptions):
            with self.subTest(corruption=index):
                with self.assertRaises(review_state.StateError):
                    review_state.validate_state(corrupt, THREAD_A)

        pasted = self.initialize(thread_id=THREAD_B)
        pasted_item = pasted["items"][pasted["item_order"][0]]
        pasted_item["source_state"] = "unresolved"
        with self.assertRaisesRegex(review_state.StateError, "pasted Source identity"):
            review_state.validate_state(pasted, THREAD_B)

    def test_github_collects_outdated_unresolved_and_relevant_review_once(self) -> None:
        state = self.initialize(github_source())
        state = self.collect_github(state, github_snapshot(outdated=True))
        self.assertEqual(2, len(state["items"]))  # thread plus independent review body
        thread_item = next(item for item in state["items"].values() if item["kind"] == "inline_thread")
        self.assertEqual("unresolved", thread_item["source_state"])
        self.assertTrue(thread_item["source_data"]["is_outdated"])
        self.assertEqual(["REVIEW_NODE"], list(state["source"]["snapshot"]["reviews_by_id"]))
        self.assertIn("THREAD_NODE", state["source"]["snapshot"]["threads_by_id"])

    def test_identical_complete_github_refresh_keeps_valid_evidence_and_authorization(self) -> None:
        state = self.initialize(github_source())
        snapshot = github_snapshot(outdated=False)
        state = self.collect_github(state, snapshot)
        item_id = next(
            item_id for item_id in state["item_order"] if state["items"][item_id]["kind"] == "inline_thread"
        )
        state = self.apply(THREAD_A, analysis_candidate(state, item_id))
        state = self.request_and_approve(state, item_id)
        authorization = copy.deepcopy(state["items"][item_id]["active_authorization"])
        state = self.collect_github(state, copy.deepcopy(snapshot))
        item = state["items"][item_id]
        self.assertEqual("valid", item["evidence"]["current_status"])
        self.assertEqual(authorization, item["active_authorization"])

    def test_resolved_thread_preserves_item_decision_and_execution_history(self) -> None:
        state = self.initialize(github_source())
        state = self.collect_github(state, github_snapshot(outdated=False))
        item_id = next(
            item_id for item_id in state["item_order"] if state["items"][item_id]["kind"] == "inline_thread"
        )
        state = self.apply(THREAD_A, analysis_candidate(state, item_id))
        state = self.request_and_approve(state, item_id)
        state = self.apply(
            THREAD_A,
            {
                "op": "start_local_work",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "area": "src/module.py",
                "change_kind": "code",
            },
        )
        state = self.apply(
            THREAD_A,
            {
                "op": "complete_local_work",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "validation_summary": "Targeted test passed.",
            },
        )
        decision = copy.deepcopy(state["items"][item_id]["decision_history"])
        progress = copy.deepcopy(state["items"][item_id]["local_progress"])
        state = self.collect_github(state, github_snapshot(resolved=True, outdated=False))
        item = state["items"][item_id]
        self.assertEqual("resolved_out_of_scope", item["source_state"])
        self.assertEqual(decision, item["decision_history"])
        self.assertEqual(progress, item["local_progress"])
        self.assertIsNone(item["active_authorization"])

    def test_new_reply_and_head_change_stale_existing_evidence_and_create_subitem(self) -> None:
        state = self.initialize(github_source())
        state = self.collect_github(state, github_snapshot(outdated=False))
        item_id = next(
            item_id for item_id in state["item_order"] if state["items"][item_id]["kind"] == "inline_thread"
        )
        state = self.apply(THREAD_A, analysis_candidate(state, item_id))
        state = self.request_and_approve(state, item_id)
        state = self.collect_github(
            state,
            github_snapshot(head="c" * 40, outdated=False, with_reply=True),
        )
        self.assertEqual("stale", state["items"][item_id]["evidence"]["current_status"])
        self.assertIsNone(state["items"][item_id]["active_authorization"])
        self.assertTrue(any(item["kind"] == "thread_sub_item" for item in state["items"].values()))
        root = state["items"][item_id]["source_data"]["original"]
        self.assertIn("Please guard this branch.", root)
        self.assertIn("Also cover the retry path.", root)

    def test_different_pr_identity_is_rejected_until_terminal_purge_then_can_initialize(self) -> None:
        state = self.initialize(github_source(38))
        with self.assertRaisesRegex(review_state.StateError, "different PR identity"):
            self.collect_github(state, github_snapshot(), identity_number=39)
        state = self.stop(state)
        review_state.purge_session(str(self.home), THREAD_A, state["revision"])
        new_state = self.initialize(github_source(39))
        self.assertEqual(39, new_state["source"]["identity"]["pr_number"])
        self.assertEqual(1, new_state["revision"])

    def test_local_progress_requires_active_envelope_and_resumes_from_in_progress(self) -> None:
        state, item_id = self.analyzed_and_approved()
        with self.assertRaisesRegex(review_state.StateError, "outside"):
            self.apply(
                THREAD_A,
                {
                    "op": "start_local_work",
                    "expected_revision": state["revision"],
                    "item_id": item_id,
                    "area": "other.py",
                    "change_kind": "code",
                },
            )
        state = self.apply(
            THREAD_A,
            {
                "op": "start_local_work",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "area": "src/module.py",
                "change_kind": "code",
            },
        )
        persisted = review_state.load_state(self.state_path().parent, THREAD_A)
        self.assertEqual("in_progress", persisted["items"][item_id]["local_progress"]["status"])
        state = self.apply(
            THREAD_A,
            {
                "op": "mark_evidence_stale",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "reason": "Resume found an unexpected worktree fact",
                "diff": "Reconciliation required.",
            },
        )
        with self.assertRaisesRegex(review_state.StateError, "Evidence is stale"):
            self.apply(
                THREAD_A,
                {
                    "op": "complete_local_work",
                    "expected_revision": state["revision"],
                    "item_id": item_id,
                    "validation_summary": "Not yet valid.",
                },
            )

    def test_local_completion_rechecks_current_chosen_action_after_redecision(self) -> None:
        state, item_id = self.analyzed_and_approved()
        state = self.apply(
            THREAD_A,
            {
                "op": "start_local_work",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "area": "src/module.py",
                "change_kind": "code",
            },
        )
        candidate = analysis_candidate(state, item_id, action_suffix="new-area")
        candidate["action_envelope"]["allowed_areas"] = ["src/new.py"]
        candidate["choices"][0]["semantic_action"]["local_changes"] = [
            {"area": "src/new.py", "change_kind": "code"}
        ]
        state = self.apply(THREAD_A, candidate)
        state = self.request_and_approve(state, item_id)
        with self.assertRaisesRegex(review_state.StateError, "outside the current authorization"):
            self.apply(
                THREAD_A,
                {
                    "op": "complete_local_work",
                    "expected_revision": state["revision"],
                    "item_id": item_id,
                    "validation_summary": "Old work must not complete under the new choice.",
                },
            )

    def test_remote_in_progress_becomes_uncertain_and_cannot_retry_before_reconciliation(self) -> None:
        state, item_id = self.analyzed_and_approved(with_remote=True)
        state = self.apply(
            THREAD_A,
            {
                "op": "prepare_remote_mutation",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "action": platform_action(),
            },
        )
        journal = state["items"][item_id]["remote_mutations"][0]
        attempt = journal["attempts"][0]
        state = self.apply(
            THREAD_A,
            {
                "op": "start_remote_mutation",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "journal_id": journal["id"],
                "attempt_id": attempt["id"],
            },
        )
        state = self.apply(
            THREAD_A,
            {
                "op": "mark_remote_uncertain",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "journal_id": journal["id"],
                "attempt_id": attempt["id"],
                "reason": "Process stopped after the call boundary.",
            },
        )
        item = state["items"][item_id]
        self.assertEqual("uncertain", item["remote_mutations"][0]["attempts"][0]["status"])
        self.assertEqual("stale", item["evidence"]["current_status"])
        self.assertIsNone(item["active_authorization"])
        with self.assertRaisesRegex(review_state.StateError, "Evidence is stale"):
            self.apply(
                THREAD_A,
                {
                    "op": "retry_remote_mutation",
                    "expected_revision": state["revision"],
                    "item_id": item_id,
                    "journal_id": journal["id"],
                },
            )
        state = self.apply(
            THREAD_A,
            {
                "op": "reconcile_remote_mutation",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "journal_id": journal["id"],
                "attempt_id": attempt["id"],
                "outcome": "failed",
                "summary": "Remote state confirms no reply exists.",
                "confirmed_not_applied": True,
            },
        )
        state = self.apply(THREAD_A, analysis_candidate(state, item_id, with_remote=True))
        state = self.request_and_approve(state, item_id)
        state = self.apply(
            THREAD_A,
            {
                "op": "retry_remote_mutation",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "journal_id": journal["id"],
            },
        )
        attempts = state["items"][item_id]["remote_mutations"][0]["attempts"]
        self.assertEqual(["failed", "pending"], [entry["status"] for entry in attempts])
        self.assertNotEqual(attempts[0]["id"], attempts[1]["id"])

    def test_failed_remote_outcome_requires_confirmed_non_application(self) -> None:
        state, item_id = self.analyzed_and_approved(with_remote=True)
        state = self.apply(
            THREAD_A,
            {
                "op": "prepare_remote_mutation",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "action": platform_action(),
            },
        )
        journal = state["items"][item_id]["remote_mutations"][0]
        attempt = journal["attempts"][0]
        state = self.apply(
            THREAD_A,
            {
                "op": "start_remote_mutation",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "journal_id": journal["id"],
                "attempt_id": attempt["id"],
            },
        )
        with self.assertRaisesRegex(review_state.StateError, "confirmed"):
            self.apply(
                THREAD_A,
                {
                    "op": "finish_remote_mutation",
                    "expected_revision": state["revision"],
                    "item_id": item_id,
                    "journal_id": journal["id"],
                    "attempt_id": attempt["id"],
                    "outcome": "failed",
                    "summary": "Call failed.",
                    "confirmed_not_applied": False,
                },
            )

    def test_pending_remote_attempt_can_be_cancelled_only_as_confirmed_not_applied(self) -> None:
        state, item_id = self.analyzed_and_approved(with_remote=True)
        state = self.apply(
            THREAD_A,
            {
                "op": "prepare_remote_mutation",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "action": platform_action(),
            },
        )
        journal = state["items"][item_id]["remote_mutations"][0]
        attempt = journal["attempts"][0]
        state = self.apply(
            THREAD_A,
            {
                "op": "cancel_pending_remote_mutation",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "journal_id": journal["id"],
                "attempt_id": attempt["id"],
                "reason": "The call was never started.",
            },
        )
        item = state["items"][item_id]
        cancelled = item["remote_mutations"][0]["attempts"][0]
        self.assertEqual("failed", cancelled["status"])
        self.assertTrue(cancelled["confirmed_not_applied"])
        self.assertIsNone(cancelled["started_at"])
        self.assertEqual("stale", item["evidence"]["current_status"])
        self.assertIsNone(item["active_authorization"])

    def test_existing_remote_journal_cannot_be_recreated_and_retry_rechecks_new_envelope(self) -> None:
        state, item_id = self.analyzed_and_approved(with_remote=True)
        state = self.apply(
            THREAD_A,
            {
                "op": "prepare_remote_mutation",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "action": platform_action(),
            },
        )
        journal = state["items"][item_id]["remote_mutations"][0]
        attempt = journal["attempts"][0]
        state = self.apply(
            THREAD_A,
            {
                "op": "cancel_pending_remote_mutation",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "journal_id": journal["id"],
                "attempt_id": attempt["id"],
                "reason": "Cancelled before call.",
            },
        )
        state = self.apply(THREAD_A, analysis_candidate(state, item_id, with_remote=True))
        state = self.request_and_approve(state, item_id)
        with self.assertRaisesRegex(review_state.StateError, "already has a journal"):
            self.apply(
                THREAD_A,
                {
                    "op": "prepare_remote_mutation",
                    "expected_revision": state["revision"],
                    "item_id": item_id,
                    "action": platform_action(),
                },
            )

        candidate = analysis_candidate(state, item_id, action_suffix="new-target", with_remote=True)
        new_action = platform_action("NEW_THREAD_NODE")
        candidate["action_envelope"]["platform_actions"] = [new_action]
        candidate["choices"][0]["semantic_action"]["platform_actions"] = [new_action]
        state = self.apply(THREAD_A, candidate)
        state = self.request_and_approve(state, item_id)
        with self.assertRaisesRegex(review_state.StateError, "outside the active authorization"):
            self.apply(
                THREAD_A,
                {
                    "op": "retry_remote_mutation",
                    "expected_revision": state["revision"],
                    "item_id": item_id,
                    "journal_id": journal["id"],
                },
            )

    def test_prepared_remote_action_is_rechecked_before_start_after_redecision(self) -> None:
        state, item_id = self.analyzed_and_approved(with_remote=True)
        state = self.apply(
            THREAD_A,
            {
                "op": "prepare_remote_mutation",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "action": platform_action(),
            },
        )
        journal = state["items"][item_id]["remote_mutations"][0]
        attempt = journal["attempts"][0]
        candidate = analysis_candidate(state, item_id, action_suffix="new-target", with_remote=True)
        new_action = platform_action("NEW_THREAD_NODE")
        candidate["action_envelope"]["platform_actions"] = [new_action]
        candidate["choices"][0]["semantic_action"]["platform_actions"] = [new_action]
        state = self.apply(THREAD_A, candidate)
        state = self.request_and_approve(state, item_id)
        with self.assertRaisesRegex(review_state.StateError, "outside the active authorization"):
            self.apply(
                THREAD_A,
                {
                    "op": "start_remote_mutation",
                    "expected_revision": state["revision"],
                    "item_id": item_id,
                    "journal_id": journal["id"],
                    "attempt_id": attempt["id"],
                },
            )

    def test_renderer_is_byte_deterministic_has_one_open_item_and_escapes_malicious_input(self) -> None:
        state = self.initialize(
            {
                "type": "pasted_feedback",
                "batch_text": "<script>source()</script></style>\n\nsecond",
                "items": [
                    {"original": "<script>source()</script></style>"},
                    {"original": "second item"},
                ],
            }
        )
        item_id = state["item_order"][0]
        state = self.apply(THREAD_A, analysis_candidate(state, item_id, malicious=True))
        state = self.apply(
            THREAD_A,
            {
                "op": "request_decision",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "question": "Approve <script>bad()</script>?",
            },
        )
        template = TEMPLATE.read_text()
        first = render_review.render_state(state, template)
        second = render_review.render_state(copy.deepcopy(state), template)
        self.assertEqual(first.encode(), second.encode())
        self.assertNotIn("<script", first.lower())
        self.assertNotIn('href="javascript:', first.lower())
        self.assertNotIn('src="javascript:', first.lower())
        self.assertIn("&lt;script&gt;source()&lt;/script&gt;", first)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", first)
        self.assertEqual(2, first.count("<details id=\"item-") )
        self.assertEqual(1, len(re.findall(r'<details id="item-[^"]+" open>', first)))
        self.assertEqual(1, first.count("<details id=\"item-" + item_id + "\" open>"))
        self.assertIn(f"State revision <strong>{state['revision']}</strong>", first)
        self.assertIn(f"Pending Item {item_id}", first)

    def test_html_publication_failure_does_not_commit_new_decision_request(self) -> None:
        state = self.initialize()
        item_id = state["item_order"][0]
        state = self.apply(THREAD_A, analysis_candidate(state, item_id))
        before_state = self.state_path().read_bytes()
        before_html = self.html_path().read_bytes()
        bad_template = Path(self.temporary.name) / "bad.tmpl"
        bad_template.write_text("missing tokens")
        with self.assertRaises(ValueError):
            self.apply(
                THREAD_A,
                {
                    "op": "request_decision",
                    "expected_revision": state["revision"],
                    "item_id": item_id,
                    "question": "This must not publish.",
                },
                template=bad_template,
            )
        self.assertEqual(before_state, self.state_path().read_bytes())
        self.assertEqual(before_html, self.html_path().read_bytes())
        persisted = json.loads(self.state_path().read_text())
        self.assertIsNone(persisted["pending_request"])

    def test_interruption_after_state_replace_recovers_html_without_state_change(self) -> None:
        state = self.initialize()
        item_id = state["item_order"][0]
        old_html = self.html_path().read_bytes()

        def interrupt() -> None:
            raise RuntimeError("simulated interruption")

        with self.assertRaisesRegex(RuntimeError, "simulated"):
            self.apply(
                THREAD_A,
                analysis_candidate(state, item_id),
                after=interrupt,
            )
        committed = review_state.load_state(self.state_path().parent, THREAD_A)
        self.assertEqual(2, committed["revision"])
        self.assertEqual(old_html, self.html_path().read_bytes())
        state_bytes = self.state_path().read_bytes()
        recovered = review_state.recover_html(str(self.home), THREAD_A, TEMPLATE)
        self.assertEqual(2, recovered["revision"])
        self.assertEqual(state_bytes, self.state_path().read_bytes())
        self.assertIn(b"State revision <strong>2</strong>", self.html_path().read_bytes())

    def test_html_mismatch_alone_does_not_block_valid_authorized_execution(self) -> None:
        state, item_id = self.analyzed_and_approved()
        self.html_path().write_text("stale HTML revision")
        state = self.apply(
            THREAD_A,
            {
                "op": "start_local_work",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "area": "src/module.py",
                "change_kind": "code",
            },
        )
        self.assertEqual("in_progress", state["items"][item_id]["local_progress"]["status"])

    def test_state_replace_failure_keeps_previous_committed_files(self) -> None:
        state = self.initialize()
        item_id = state["item_order"][0]
        before_state = self.state_path().read_bytes()
        before_html = self.html_path().read_bytes()
        os.link(self.state_path(), self.state_path().with_name(".state.json.tmp"))
        os.link(self.html_path(), self.html_path().with_name(".review.html.tmp"))
        real_replace = os.replace

        def fail_state_replace(source, destination):
            if Path(destination).name == "state.json":
                raise OSError("replace failed")
            return real_replace(source, destination)

        with mock.patch.object(review_state.os, "replace", side_effect=fail_state_replace):
            with self.assertRaisesRegex(OSError, "replace failed"):
                self.apply(THREAD_A, analysis_candidate(state, item_id))
        self.assertEqual(before_state, self.state_path().read_bytes())
        self.assertEqual(before_html, self.html_path().read_bytes())

    def test_corrupt_or_unsupported_state_is_preserved_and_blocks_recovery_and_writes(self) -> None:
        self.initialize()
        for corrupt in (b"{broken", json.dumps({"schema_version": 2}).encode()):
            with self.subTest(corrupt=corrupt[:20]):
                self.state_path().write_bytes(corrupt)
                before = self.state_path().read_bytes()
                with self.assertRaises(review_state.StateError):
                    review_state.recover_html(str(self.home), THREAD_A, TEMPLATE)
                self.assertEqual(before, self.state_path().read_bytes())
                with self.assertRaises(review_state.StateError):
                    self.apply(THREAD_A, {"op": "set_session_lifecycle", "expected_revision": 1, "lifecycle": "stopped", "reason": "x"})
                self.assertEqual(before, self.state_path().read_bytes())
                if corrupt.startswith(b"{broken"):
                    self.state_path().write_text(json.dumps(self.initialize(thread_id=THREAD_B)))

    def test_storage_modes_are_private(self) -> None:
        self.initialize()
        thread_dir = self.state_path().parent
        for directory in (self.home / "review-response", self.home / "review-response" / "threads", thread_dir):
            self.assertEqual(0o700, stat.S_IMODE(directory.stat().st_mode))
        for path in (self.state_path(), self.html_path()):
            self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))

    def test_purge_rejects_stale_revision_unexpected_file_and_symlink_before_unlink(self) -> None:
        state = self.stop(self.initialize())
        with self.assertRaisesRegex(review_state.StateError, "stale expected_revision"):
            review_state.purge_session(str(self.home), THREAD_A, state["revision"] - 1)
        unexpected = self.state_path().parent / "unexpected.txt"
        unexpected.write_text("do not delete")
        with mock.patch.object(review_state, "unlink_file") as unlink:
            with self.assertRaisesRegex(review_state.StateError, "unexpected"):
                review_state.purge_session(str(self.home), THREAD_A, state["revision"])
            unlink.assert_not_called()
        with self.assertRaisesRegex(review_state.StateError, "already exists"):
            self.initialize(github_source(39))
        unexpected.unlink()
        link = self.state_path().parent / ".review.html.tmp"
        link.symlink_to(self.html_path())
        with mock.patch.object(review_state, "unlink_file") as unlink:
            with self.assertRaisesRegex(review_state.StateError, "symlink"):
                review_state.purge_session(str(self.home), THREAD_A, state["revision"])
            unlink.assert_not_called()

    def test_purge_rejects_wrong_owner_before_unlink(self) -> None:
        state = self.stop(self.initialize())
        with mock.patch.object(review_state, "current_uid", return_value=os.getuid() + 1):
            with mock.patch.object(review_state, "unlink_file") as unlink:
                with self.assertRaisesRegex(review_state.StateError, "owned"):
                    review_state.purge_session(str(self.home), THREAD_A, state["revision"])
                unlink.assert_not_called()

    def test_purge_deletes_state_last_and_interrupted_purge_can_recover_html(self) -> None:
        state = self.stop(self.initialize())
        order = []
        real_unlink = review_state.unlink_file

        def recording_unlink(path: Path) -> None:
            order.append(path.name)
            real_unlink(path)

        with mock.patch.object(review_state, "unlink_file", side_effect=recording_unlink):
            review_state.purge_session(str(self.home), THREAD_A, state["revision"])
        self.assertEqual("state.json", order[-1])
        self.assertFalse(self.state_path().parent.exists())

        for interrupt_name in ("review.html", ".review.html.tmp", ".state.json.tmp"):
            with self.subTest(interrupt_name=interrupt_name):
                thread_id = str(uuid.uuid4())
                state = self.stop(self.initialize(thread_id=thread_id))
                thread_dir = self.state_path(thread_id).parent
                for temporary_name in (".review.html.tmp", ".state.json.tmp"):
                    temporary_path = thread_dir / temporary_name
                    temporary_path.write_text("temporary")
                    temporary_path.chmod(0o600)
                interrupted = False

                def interrupt_at_boundary(path: Path) -> None:
                    nonlocal interrupted
                    real_unlink(path)
                    if path.name == interrupt_name and not interrupted:
                        interrupted = True
                        raise RuntimeError("stop purge")

                with mock.patch.object(
                    review_state, "unlink_file", side_effect=interrupt_at_boundary
                ):
                    with self.assertRaisesRegex(RuntimeError, "stop purge"):
                        review_state.purge_session(
                            str(self.home), thread_id, state["revision"]
                        )
                self.assertTrue(self.state_path(thread_id).exists())
                recovered = review_state.recover_html(
                    str(self.home), thread_id, TEMPLATE
                )
                self.assertEqual(state["revision"], recovered["revision"])
                self.assertTrue(self.html_path(thread_id).exists())

    def test_purge_blocks_uncertain_remote_mutation_until_reconciled(self) -> None:
        state, item_id = self.analyzed_and_approved(with_remote=True)
        state = self.apply(
            THREAD_A,
            {"op": "prepare_remote_mutation", "expected_revision": state["revision"], "item_id": item_id, "action": platform_action()},
        )
        journal = state["items"][item_id]["remote_mutations"][0]
        attempt = journal["attempts"][0]
        state = self.apply(
            THREAD_A,
            {
                "op": "start_remote_mutation",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "journal_id": journal["id"],
                "attempt_id": attempt["id"],
            },
        )
        state = self.apply(
            THREAD_A,
            {
                "op": "mark_remote_uncertain",
                "expected_revision": state["revision"],
                "item_id": item_id,
                "journal_id": journal["id"],
                "attempt_id": attempt["id"],
                "reason": "unknown remote outcome",
            },
        )
        state = self.stop(state)
        with self.assertRaisesRegex(review_state.StateError, "remote reconciliation"):
            review_state.purge_session(str(self.home), THREAD_A, state["revision"])
        self.assertTrue(self.state_path().exists())

    def test_template_and_renderer_have_no_javascript_or_external_resources(self) -> None:
        template = TEMPLATE.read_text().lower()
        renderer = (SCRIPTS / "render_review.py").read_text().lower()
        self.assertNotIn("<script", template)
        self.assertNotIn("javascript:", template)
        self.assertNotIn("http://", template)
        self.assertNotIn("https://", template)
        self.assertNotIn("@import", template)
        self.assertNotIn("url(", template)
        self.assertIn('<meta name="viewport"', template)
        self.assertIn("focus-visible", template)
        self.assertIn("prefers-contrast: more", template)
        self.assertIn("<details", renderer)
        for control in ("<form", "<button", "<input"):
            self.assertNotIn(control, renderer)
        self.assertNotIn("active_item_id", renderer)
        self.assertNotIn("query-string", renderer)

    def test_grimoire_home_symlink_is_allowed_but_managed_symlink_is_rejected(self) -> None:
        target = Path(self.temporary.name) / "real-home"
        target.mkdir(mode=0o700)
        alias = Path(self.temporary.name) / "home-link"
        alias.symlink_to(target, target_is_directory=True)
        self.home = alias
        state = self.initialize()
        self.assertEqual(THREAD_A, state["owner"]["thread_id"])
        self.assertTrue((target / "review-response" / "threads" / THREAD_A / "state.json").exists())

        bad_home = Path(self.temporary.name) / "bad-home"
        bad_home.mkdir(mode=0o700)
        elsewhere = Path(self.temporary.name) / "elsewhere"
        elsewhere.mkdir(mode=0o700)
        (bad_home / "review-response").symlink_to(elsewhere, target_is_directory=True)
        self.home = bad_home
        with self.assertRaisesRegex(review_state.StateError, "symlink"):
            self.initialize(thread_id=THREAD_B)

    def test_standalone_renderer_uses_fixed_template_and_is_deterministic(self) -> None:
        self.initialize()
        output_a = Path(self.temporary.name) / "a.html"
        output_b = Path(self.temporary.name) / "b.html"
        command = [sys.executable, str(SCRIPTS / "render_review.py"), "--state", str(self.state_path())]
        for output in (output_a, output_b):
            result = subprocess.run(
                [*command, "--output", str(output)],
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(output_a.read_bytes(), output_b.read_bytes())

    def test_standalone_renderer_rejects_symlink_state_and_output(self) -> None:
        self.initialize()
        state_link = Path(self.temporary.name) / "state-link.json"
        state_link.symlink_to(self.state_path())
        output = Path(self.temporary.name) / "output.html"
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "render_review.py"), "--state", str(state_link), "--output", str(output)],
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("symlink", result.stderr)

        output_link = Path(self.temporary.name) / "output-link.html"
        target = Path(self.temporary.name) / "target.html"
        target.write_text("preserve")
        output_link.symlink_to(target)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "render_review.py"), "--state", str(self.state_path()), "--output", str(output_link)],
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("symlink", result.stderr)
        self.assertEqual("preserve", target.read_text())

    def test_state_authority_cli_applies_shows_recovers_and_purges(self) -> None:
        script = SCRIPTS / "review_state.py"

        def run(*arguments: str, candidate: dict | None = None) -> subprocess.CompletedProcess:
            return subprocess.run(
                [sys.executable, str(script), "--grimoire-home", str(self.home), *arguments],
                input=json.dumps(candidate) if candidate is not None else None,
                check=False,
                text=True,
                capture_output=True,
            )

        initialized = run(
            "apply",
            "--thread-id",
            THREAD_A,
            "--candidate",
            "-",
            candidate={
                "op": "initialize_session",
                "expected_revision": 0,
                "source": pasted_source(),
                "output_locale": "ko-KR",
            },
        )
        self.assertEqual(0, initialized.returncode, initialized.stderr)
        self.assertEqual(1, json.loads(initialized.stdout)["revision"])

        shown = run("show", "--thread-id", THREAD_A)
        recovered = run("recover-html", "--thread-id", THREAD_A)
        self.assertEqual(0, shown.returncode, shown.stderr)
        self.assertEqual(json.loads(shown.stdout), json.loads(recovered.stdout))

        stopped = run(
            "apply",
            "--thread-id",
            THREAD_A,
            "--candidate",
            "-",
            candidate={
                "op": "set_session_lifecycle",
                "expected_revision": 1,
                "lifecycle": "stopped",
                "reason": "CLI purge test.",
            },
        )
        self.assertEqual(0, stopped.returncode, stopped.stderr)
        purged = run("purge", "--thread-id", THREAD_A, "--expected-revision", "2")
        self.assertEqual(0, purged.returncode, purged.stderr)
        self.assertFalse(self.state_path().parent.exists())


class ReviewStateDocumentationTests(unittest.TestCase):
    def test_skill_is_explicit_only_and_has_no_runtime_subagent_workflow(self) -> None:
        skill = (SKILL / "SKILL.md").read_text()
        sidecar = (SKILL / "agents" / "openai.yaml").read_text()
        self.assertIn("$magical-review-response", skill)
        self.assertNotIn("Multi-Agent Use", skill)
        self.assertNotIn("subagent", skill.lower())
        self.assertIn("allow_implicit_invocation: false", sidecar)
        self.assertIn("$magical-review-response", sidecar)

    def test_reference_lists_every_supported_state_operation(self) -> None:
        reference = (SKILL / "references" / "review-state.md").read_text()
        operations = (
            "initialize_session",
            "update_github_source",
            "update_item_analysis",
            "mark_evidence_stale",
            "request_decision",
            "record_decision",
            "start_local_work",
            "complete_local_work",
            "reconcile_local_work",
            "prepare_remote_mutation",
            "start_remote_mutation",
            "finish_remote_mutation",
            "cancel_pending_remote_mutation",
            "mark_remote_uncertain",
            "reconcile_remote_mutation",
            "retry_remote_mutation",
            "adopt_remote_mutation",
            "close_authorization",
            "set_session_lifecycle",
        )
        for operation in operations:
            with self.subTest(operation=operation):
                self.assertIn(operation, reference)

    def test_runtime_scripts_import_only_standard_library_and_local_modules(self) -> None:
        allowed = {
            "__future__",
            "argparse",
            "copy",
            "datetime",
            "hashlib",
            "html",
            "json",
            "os",
            "pathlib",
            "re",
            "render_review",
            "review_state",
            "stat",
            "sys",
            "typing",
            "uuid",
        }
        for path in (SCRIPTS / "review_state.py", SCRIPTS / "render_review.py"):
            tree = ast.parse(path.read_text())
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module.split(".")[0])
            self.assertEqual(set(), imports - allowed, f"non-stdlib imports in {path}")

    def test_purge_implementation_has_no_recursive_delete_or_lock_layer(self) -> None:
        source = (SCRIPTS / "review_state.py").read_text()
        self.assertNotIn("shutil", source)
        self.assertNotIn("rmtree", source)
        self.assertNotIn("glob(", source)
        self.assertNotIn("flock", source)
        self.assertNotIn("Command", source)

    def test_english_and_korean_readmes_describe_same_review_session_contract(self) -> None:
        english = (ROOT / "README.md").read_text()
        korean = (ROOT / "README.ko.md").read_text()
        for token in (
            "$magical-review-response",
            "<GRIMOIRE_HOME>/review-response/threads/<thread-id>/",
            "state.json",
            "review.html",
            "state-last purge",
        ):
            with self.subTest(token=token):
                self.assertIn(token, english)
                self.assertIn(token, korean)


if __name__ == "__main__":
    unittest.main()
