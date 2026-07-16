#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable


def escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def paragraphs(value: str) -> str:
    if not value:
        return '<p class="empty">Not recorded.</p>'
    return "".join(f"<p>{escape(part)}</p>" for part in value.split("\n\n"))


def text_list(values: Iterable[str], empty: str = "None recorded.") -> str:
    entries = list(values)
    if not entries:
        return f'<p class="empty">{escape(empty)}</p>'
    return '<ul class="plain-list">' + "".join(f"<li>{escape(value)}</li>" for value in entries) + "</ul>"


def section(title: str, body: str, css_class: str = "") -> str:
    class_name = f' class="{css_class}"' if css_class else ""
    return f"<section{class_name}><h3>{escape(title)}</h3>{body}</section>"


def localized(body: str, locale: str) -> str:
    return f'<div lang="{escape(locale)}">{body}</div>'


def render_code(
    excerpts: list[dict[str, Any]], locations: list[dict[str, int]]
) -> str:
    if not excerpts:
        return '<p class="empty">No code excerpt recorded.</p>'
    parts = []
    for excerpt, location in zip(excerpts, locations):
        label = (
            f"{excerpt['path']} · {excerpt['revision']} · "
            f"lines {location['start_line']}–{location['end_line']}"
        )
        parts.append(
            '<figure class="code"><figcaption>'
            + escape(label)
            + "</figcaption><pre><code>"
            + escape(excerpt["text"])
            + "</code></pre></figure>"
        )
    return "".join(parts)


def render_examples(examples: list[dict[str, str]]) -> str:
    if not examples:
        return '<p class="empty">No concrete example recorded.</p>'
    parts = []
    for index, example in enumerate(examples, start=1):
        parts.append(
            '<div class="example"><h4>'
            + escape(f"Example {index}")
            + "</h4><dl>"
            + f"<dt>Input</dt><dd>{escape(example['input'])}</dd>"
            + f"<dt>Behavior</dt><dd>{escape(example['behavior'])}</dd>"
            + f"<dt>Outcome</dt><dd>{escape(example['outcome'])}</dd>"
            + "</dl></div>"
        )
    return "".join(parts)


def render_alternatives(item: dict[str, Any]) -> str:
    proposal = item["proposal"]
    if proposal is None:
        return '<p class="empty">No alternatives recorded.</p>'
    presentation_by_id = {
        entry["choice_id"]: entry for entry in item["presentation"]["alternatives"]
    }
    parts = ['<ol class="alternatives">']
    for choice_id in proposal["choice_order"]:
        choice = proposal["choices_by_id"][choice_id]
        display = presentation_by_id.get(choice_id, {})
        recommended = choice_id == proposal["recommended_choice_id"]
        badge = '<span class="badge recommended">Recommended</span>' if recommended else ""
        label = display.get("label") or choice["label"] or choice_id
        tradeoff = display.get("tradeoff") or choice["tradeoff"]
        action = choice["semantic_action"]
        parts.append(
            "<li><div class=\"choice-title\">"
            + f"<code>{escape(choice_id)}</code><strong>{escape(label)}</strong>{badge}"
            + "</div>"
            + f"<p>{escape(action['summary'])}</p>"
            + f"<p class=\"tradeoff\"><strong>Trade-off:</strong> {escape(tradeoff)}</p></li>"
        )
    parts.append("</ol>")
    return "".join(parts)


def render_platform_actions(actions: list[dict[str, Any]]) -> str:
    if not actions:
        return '<p class="empty">No platform mutation is authorized.</p>'
    parts = ['<ul class="plain-list">']
    for action in actions:
        authored = " · reviewer-authored thread" if action["reviewer_authored"] else ""
        parts.append(
            "<li><code>"
            + escape(action["kind"])
            + "</code> · "
            + escape(action["target"])
            + authored
            + "<br>"
            + escape(action["summary"])
            + "<br><strong>Exact payload:</strong><pre class=\"review-text\">"
            + escape(
                json.dumps(
                    action["payload"],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            + "</pre>"
            + "</li>"
        )
    parts.append("</ul>")
    return "".join(parts)


def render_envelope(item: dict[str, Any]) -> str:
    proposal = item["proposal"]
    if proposal is None:
        return '<p class="empty">No Action Envelope recorded.</p>'
    envelope = proposal["action_envelope"]
    return (
        f"<p>{escape(envelope['purpose'])}</p>"
        + "<dl class=\"envelope\">"
        + f"<dt>Allowed areas</dt><dd>{text_list(envelope['allowed_areas'])}</dd>"
        + f"<dt>Change kinds</dt><dd>{text_list(envelope['allowed_change_kinds'])}</dd>"
        + f"<dt>Excluded</dt><dd>{text_list(envelope['excluded'])}</dd>"
        + f"<dt>Validation</dt><dd>{text_list(envelope['validations'])}</dd>"
        + f"<dt>Repository actions</dt><dd>{text_list(envelope['repository_actions'], 'None authorized.')}</dd>"
        + f"<dt>Platform actions</dt><dd>{render_platform_actions(envelope['platform_actions'])}</dd>"
        + "</dl>"
    )


def render_evidence(item: dict[str, Any]) -> str:
    evidence = item["evidence"]
    if evidence["current_version"] is None:
        return (
            '<div class="status-callout stale"><strong>Evidence: stale</strong>'
            + f"<p>{escape(evidence['last_diff'])}</p></div>"
        )
    current = evidence["versions"][evidence["current_version"] - 1]
    semantic = current["semantic"]
    history = " · ".join(
        f"v{version['version']} {version['status']}" for version in evidence["versions"]
    )
    return (
        f'<div class="status-callout {escape(evidence["current_status"])}">'
        + f"<strong>Evidence: {escape(evidence['current_status'])} · v{current['version']}</strong>"
        + f"<p class=\"mono-wrap\">{escape(current['fingerprint'])}</p>"
        + f"<p>{escape(evidence['last_diff'])}</p></div>"
        + f"<p class=\"history\"><strong>Version history:</strong> {escape(history)}</p>"
        + "<h4>Reviewer ask</h4>"
        + paragraphs(semantic["reviewer_ask"])
        + "<h4>Claims</h4>"
        + text_list(semantic["claims"])
        + "<h4>Assumptions</h4>"
        + text_list(semantic["assumptions"])
        + "<h4>Gaps</h4>"
        + text_list(semantic["gaps"])
    )


def latest_remote_status(item: dict[str, Any]) -> str:
    statuses = [journal["attempts"][-1]["status"] for journal in item["remote_mutations"]]
    return ", ".join(statuses) if statuses else "none"


def render_item(
    item: dict[str, Any], pending_request: Any, output_locale: str
) -> str:
    item_id = item["id"]
    is_pending = pending_request is not None and item_id == pending_request["item_id"]
    open_attribute = " open" if is_pending else ""
    pending_badge = '<span class="badge pending">Decision pending</span>' if is_pending else ""
    outdated_badge = (
        '<span class="badge outdated">Outdated diff · still unresolved</span>'
        if item["source_data"]["is_outdated"] and item["source_state"] == "unresolved"
        else ""
    )
    evidence = item["evidence"]
    semantic = (
        evidence["versions"][evidence["current_version"] - 1]["semantic"]
        if evidence["current_version"] is not None
        else {"code": [], "examples": []}
    )
    decision_fingerprint = item["proposal"]["decision_fingerprint"] if item["proposal"] else "Not available"
    authorization = "active" if item["active_authorization"] else "none"
    summary = (
        '<summary><span class="summary-main"><span class="item-number">'
        + escape(item["kind"].replace("_", " "))
        + "</span><span>"
        + escape(item["presentation"]["title"] or item["source_key"])
        + "</span></span><span class=\"summary-badges\">"
        + outdated_badge
        + pending_badge
        + "</span></summary>"
    )
    body = (
        '<div class="item-meta">'
        + f"<span>Item <code>{escape(item_id)}</code></span>"
        + f"<span>Source state <strong>{escape(item['source_state'])}</strong></span>"
        + f"<span>Local <strong>{escape(item['local_progress']['status'])}</strong></span>"
        + f"<span>Remote <strong>{escape(latest_remote_status(item))}</strong></span>"
        + f"<span>Authorization <strong>{authorization}</strong></span>"
        + "</div>"
        + section("Original", '<pre class="review-text">' + escape(item["source_data"]["original"]) + "</pre>")
        + section(
            "Translation",
            localized(paragraphs(item["presentation"]["translation"]), output_locale),
        )
        + section(
            "Interpretation and reviewer intent",
            localized(paragraphs(item["presentation"]["interpretation"]), output_locale)
            + '<h4>Reviewer intent</h4>'
            + localized(paragraphs(item["presentation"]["reviewer_intent"]), output_locale),
        )
        + section(
            "Relevant code",
            render_code(semantic["code"], item["presentation"]["code_locations"]),
        )
        + section("Input → behavior → outcome", render_examples(semantic["examples"]))
        + section("Evidence Set and diff", render_evidence(item))
        + section("Alternatives and trade-offs", render_alternatives(item))
        + section(
            "Recommendation",
            localized(paragraphs(item["presentation"]["recommendation"]), output_locale),
            "recommendation",
        )
        + section("Action Envelope", render_envelope(item))
        + section(
            "Decision fingerprint",
            '<p class="mono-wrap">' + escape(decision_fingerprint) + "</p>",
        )
        + section(
            "Exact decision question",
            localized(
                paragraphs(
                    pending_request["question"]
                    if is_pending
                    else item["presentation"]["question"]
                ),
                output_locale,
            ),
            "decision-question",
        )
    )
    return f'<details id="item-{item_id}"{open_attribute}>{summary}<div class="item-body">{body}</div></details>'


def render_state(state: dict[str, Any], template: str) -> str:
    if template.count("{{TITLE}}") != 1 or template.count("{{BODY}}") != 1:
        raise ValueError("template must contain exactly one {{TITLE}} and one {{BODY}} token")
    pending = state["pending_request"]
    if pending:
        pending_text = (
            f"Pending Item {pending['item_id']} · request {pending['request_id']}"
        )
    else:
        pending_text = "No pending decision"
    source = state["source"]
    if source["type"] == "github_pr":
        identity = source["identity"]
        source_label = (
            f"{identity['host']}/{identity['owner']}/{identity['repo']}#{identity['pr_number']}"
        )
    else:
        source_label = f"Pasted feedback batch {source['identity']['batch_id']}"
    navigation = '<nav aria-label="Review items"><h2>Review Items</h2><ol>'
    for item_id in state["item_order"]:
        item = state["items"][item_id]
        navigation += (
            f'<li><a href="#item-{item_id}">{escape(item["presentation"]["title"] or item["source_key"])}</a>'
            + f' <span>{escape(item["source_state"])}</span></li>'
        )
    navigation += "</ol></nav>"
    items = "".join(
        render_item(state["items"][item_id], pending, state["output_locale"])
        for item_id in state["item_order"]
    )
    if not items:
        items = '<p class="empty-state">No in-scope Review Item has been collected yet.</p>'
    body = (
        '<header class="snapshot"><div><p class="eyebrow">Thread-owned Review Session</p>'
        + f"<h1>{escape(source_label)}</h1>"
        + f"<p class=\"snapshot-line\">State revision <strong>{state['revision']}</strong> · "
        + f"Source <strong>{escape(source['status'])}</strong> · Session <strong>{escape(state['lifecycle'])}</strong></p>"
        + "</div><div class=\"pending-panel\"><span>Decision gate</span>"
        + f"<strong>{escape(pending_text)}</strong></div></header>"
        + navigation
        + '<main aria-label="Review item details">'
        + items
        + "</main>"
        + '<footer><p>This snapshot is read-only. Record decisions and approvals in the Codex task.</p></footer>'
    )
    return template.replace("{{TITLE}}", "Review Session").replace("{{BODY}}", body)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render deterministic review HTML from validated state.")
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        script_dir = Path(__file__).resolve().parent
        if str(script_dir) not in sys.path:
            sys.path.insert(0, str(script_dir))
        import review_state

        data = review_state.read_owned_file(args.state, "state.json")
        state = review_state.validate_state(review_state.decode_json_bytes(data, "state.json"))
        template_path = Path(__file__).resolve().parents[1] / "assets" / "review.html.tmpl"
        review_state.require_owned_regular_file(template_path, "review HTML template")
        output_normalized = args.output.resolve(strict=False)
        for input_path, label in ((args.state, "state.json"), (template_path, "HTML template")):
            input_normalized = input_path.resolve(strict=False)
            aliased = output_normalized == input_normalized
            if args.output.exists() and input_path.exists():
                aliased = aliased or os.path.samefile(args.output, input_path)
            if aliased:
                raise review_state.StateError(f"HTML output must not alias {label}")
        template = template_path.read_text(encoding="utf-8")
        output = render_state(state, template).encode("utf-8")
        if args.output.exists() or args.output.is_symlink():
            review_state.require_owned_regular_file(args.output, "HTML output", 0o600)
        output_tmp = args.output.with_name(f".{args.output.name}.tmp")
        for input_path in (args.state, template_path):
            temp_aliased = output_tmp.resolve(strict=False) == input_path.resolve(strict=False)
            if output_tmp.exists() and input_path.exists():
                temp_aliased = temp_aliased or os.path.samefile(output_tmp, input_path)
            if temp_aliased:
                raise review_state.StateError("HTML temporary output aliases an input")
        try:
            review_state.write_fixed_temp(output_tmp, output)
            os.replace(output_tmp, args.output)
        except Exception:
            review_state.unlink_file(output_tmp)
            raise
        return 0
    except (OSError, ValueError, review_state.StateError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
