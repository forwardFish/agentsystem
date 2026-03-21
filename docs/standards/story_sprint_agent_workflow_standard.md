# Unified Story And Sprint Agent Workflow Standard

Last updated: 2026-03-20

## 1. Purpose

This document is the only official workflow standard for Story and Sprint delivery in `agentsystem`.

All later development in:

- `agentsystem`
- `versefina`
- `finahunt`

must follow this document unless a repo-specific exception is written explicitly and linked back to this standard.

## 2. Completion Vocabulary

The system must track outcome completion and process completion separately.

- `implemented`
  - code or artifact change exists
- `verified`
  - tests, browser evidence, or runtime evidence passed
- `agentized`
  - the required Agent chain actually ran
- `accepted`
  - acceptance gate or sprint closeout explicitly passed

A Story is not fully done if it is only `implemented`.

## 3. Global Hard Rules

The following rules are mandatory.

1. No bugfix may skip `investigate`.
2. No UI Story may skip `browse`, `plan-design-review`, `design-consultation`, `design-review`, or `qa`.
3. No new demand / new epic / new sprint may skip `office-hours`, `plan-ceo-review`, or `plan-eng-review`.
4. No sprint may be marked closed without `ship`, `document-release`, and `retro`.
5. Authenticated browser evidence must run through `setup-browser-cookies` before browser verification when session reuse is part of acceptance.
6. `agentsystem` is the workflow source of truth; product repos may only define explicit exceptions, not private alternate workflows.

## 4. Mandatory Flow Table

| Scenario | Trigger / Scope | Required Agents | Optional Agents | Input Preconditions | Expected Artifacts | Done Rule | Blocker Handling |
|---|---|---|---|---|---|---|---|
| New demand / new epic / new sprint | Goal is still above Story level | `office-hours`, `plan-ceo-review`, `plan-eng-review` | `plan-design-review`, `design-consultation` | Goal exists but implementation scope is not yet locked | Office hours report, requirement doc, opportunity map, architecture review report | Planning package is explicit enough for Story decomposition | Stop before Builder; do not enter implementation with only a loose requirement |
| Ordinary Story | Scoped Story with clear file boundary | `plan-eng-review`, `build`, `review`, `qa` or `qa-only`, `code_acceptance`, `acceptance_gate`, `doc_writer` | `plan-ceo-review` | Valid Story card, scoped files, acceptance criteria | Architecture review, code change, QA report, review report, acceptance evidence, delivery doc | `implemented + verified + agentized + accepted` | Stop on current Story; do not silently skip downstream gates |
| UI Story | Any Story with route/surface impact | `browse`, `plan-design-review`, `design-consultation`, `build`, `design-review`, `qa`, `review`, `acceptance_gate` | `setup-browser-cookies` | Real route scope, preview URL or equivalent surface evidence path | Browse evidence, `DESIGN.md`, design review report, before/after screenshots, QA evidence | All blocking route-level design and browser issues are closed | Do not bypass design chain; if auth is required, route through session setup first |
| Bugfix / regression | Defect correction, rollback-style fix, incident follow-up | `investigate`, `build/fix`, `review`, `qa` | `browse`, `setup-browser-cookies` | Repro, symptom, or evidence exists | Investigation report, fix evidence, regression verification | Root cause is recorded before fix and regression evidence exists after fix | If investigation is missing, stop the fix path immediately |
| Sprint closeout | Sprint release, handoff, or formal close | `ship`, `document-release`, `retro` | none | Stories already accepted or explicitly release-candidate scoped | Ship readiness report, doc release report, retro report | Closeout package exists and blockers are explicit | Do not mark sprint closed without closeout artifacts |

## 5. Routing And Enforcement

The workflow standard must be enforced in all of the following places:

- workflow manifest
- skill mode registry
- task payload schema
- sprint hooks
- `run-task`
- `auto-deliver`
- dashboard interpretation of delivery status

Required control fields include:

- `story_type`
- `risk_level`
- `session_policy`
- `cookie_source`
- `auth_expectations`
- `investigation_context`
- `bug_scope`
- `release_scope`
- `doc_targets`
- `retro_window`
- `workflow_enforcement_policy`
- `upstream_agent_parity`
- `awaiting_user_input`
- `dialogue_state`
- `next_question`
- `approval_required`

## 6. Artifact Rules

The workflow must deposit durable artifacts under `.meta/<repo>/...` so a fresh Codex session can continue without chat history.

For browse compatibility, the workflow must also preserve upstream-compatible host state under:

- `.gstack/browse.json`
- `.gstack/browse-console.log`
- `.gstack/browse-network.log`
- `.gstack/browse-dialog.log`

Minimum artifact families:

- `office_hours/`
- `plan_ceo_review/`
- `architecture_review/`
- `browser_runtime/`
- `browse/` or `browser_qa/`
- `investigate/`
- `qa/`
- `design_review/`
- `ship/`
- `document_release/`
- `retro/`

Mode entry is also part of the standard:

- required Agent chains must be reachable by direct mode entry, not only by starting from build
- at least one formal acceptance run must enter through a real mode entry path

## 7. Enforcement Interpretation

The process is only considered complete when:

- required Agent chain ran
- required artifacts exist
- blockers are either resolved or explicitly recorded
- acceptance state is visible in status tracking

For formal `gstack` dogfood acceptance:

- run `python cli.py audit-gstack-parity --project finahunt`
- use `finahunt Sprint 3` as the first full-sprint dogfood target
- include at least one authenticated UI story in the broader platform acceptance set
- if the audit reports `formal_dogfood_ready: false`, the sprint may still be used for iterative validation, but not for parity sign-off

If code exists but required Agents did not run, the Story is:

- implemented
- but not agentized
- and therefore not fully complete

## 8. Governance Rule For Later Development

All later development must follow this order of authority:

1. This workflow standard
2. The gstack migration spec for parity truth
3. Repo-specific exception notes

If there is a conflict, `agentsystem` workflow standard wins unless a newer formal standard replaces it.

Companion document:

- [gstack_platform_migration_spec.md](D:/lyh/agent/agent-frame/agentsystem/docs/standards/gstack_platform_migration_spec.md)
