# gstack Agent Platform Migration Spec

Last updated: 2026-03-20

## 1. Purpose

This document is the only official migration standard for bringing the selected `gstack` Agent platform capability into `agentsystem`.

It exists to prevent a false sense of completion. A local Agent is **not** considered migrated just because:

- the directory name matches upstream
- a `SKILL.md` file was vendored
- a local workflow node can run
- a report artifact can be written

The target is **skill-level parity plus platform-level parity**, not prompt-name parity.

## 2. Source Of Truth

- Upstream repo: `https://github.com/garrytan/gstack`
- Upstream commit currently pinned in local parity manifest:
  - `8ddfab233d3999edb172bed54aaf06fc5ff92646`
- Upstream license:
  - MIT
- Local vendored mirror:
  - [vendors/gstack](D:/lyh/agent/agent-frame/agentsystem/vendors/gstack)
- Local parity manifest:
  - [config/platform/gstack_parity_manifest.yaml](D:/lyh/agent/agent-frame/agentsystem/config/platform/gstack_parity_manifest.yaml)

## 3. Non-Negotiable Rule

`agentsystem` must not claim that an Agent is "migrated from gstack" unless all of the following are true:

1. The upstream skill text and referenced helper material are vendored and pinned.
2. The local runtime preserves the same role, interaction rhythm, gating rules, and artifact contract.
3. Platform hooks relied on by the upstream skill are actually adapted locally or explicitly marked unsupported.
4. The mode is reachable from CLI/workflow entry, not only from a template.
5. The mode is covered by tests that prove the intended path can execute.

If any one of the above is missing, the correct status is:

- `partial_runtime`
- `workflow_wired`
- or `template_only`
- but **not** `full_parity`

Status meaning:

- `template_only`
  - upstream mirror exists but local runtime path is not executable
- `partial_runtime`
  - executable locally, but still missing major platform or behavior parity
- `workflow_wired`
  - executable and enforced in workflow, but still not behavior-equivalent to upstream
- `full_parity`
  - vendored, executable, workflow-enforced, behavior-matched, and covered by acceptance gates

## 4. In-Scope Agent Set

The current in-scope set is:

- `browse`
- `office-hours`
- `investigate`
- `plan-ceo-review`
- `plan-eng-review`
- `plan-design-review`
- `design-consultation`
- `design-review`
- `qa`
- `qa-only`
- `review`
- `ship`
- `document-release`
- `retro`
- `setup-browser-cookies`

## 5. What "Perfect Migration" Means

Perfect migration is defined as all of the following.

### 5.1 Skill Parity

For each Agent, local behavior must preserve:

- upstream role definition
- upstream stop/go rules
- upstream interaction cadence
- upstream required inputs
- upstream expected artifacts
- upstream hard constraints and refusal conditions

### 5.2 Platform Parity

The local host must adapt the platform assumptions that upstream skills depend on, including:

- browser runtime and persistent session behavior
- `.gstack/browse.json` compatibility and localhost daemon semantics
- cookies/session import and reuse
- session/work directory conventions
- freeze/guard style protection hooks
- upgrade/check hooks
- telemetry structure
- CLI entry conventions
- AskUserQuestion style interactive pauses where upstream depends on them

The current local compatibility contract is:

- `.gstack/`
  - upstream-compatible host/session state
- `.meta/<repo>/...`
  - local audit, evidence, workflow artifacts

`.gstack/` is the primary compatibility layer. `.meta/` mirrors evidence and workflow state, but must not become the browse host source of truth.

### 5.3 Workflow Parity

The mode must be reachable and enforceable through:

- `skill_mode` registry
- workflow manifest
- task payload schema
- `run-task`
- `auto-deliver`
- sprint hooks where relevant

### 5.4 Evidence Parity

The mode must produce durable evidence under `.meta/<repo>/...` and that evidence must be sufficient for later review without chat memory.

## 6. Current Truth On 2026-03-20

As of **March 20, 2026**, the local work is **not yet a full gstack-equivalent migration**.

What exists now is best described as:

- vendored upstream mirror: largely present
- local runtime wiring: present for most in-scope modes
- forced workflow routing: partially hardened
- full behavior parity with upstream: **not achieved yet**

## 7. Agent Parity Status

| Agent | Local Runtime Status | Current Truth | Major Remaining Gap Before Full Parity |
|---|---|---|---|
| `browse` | executable | partial runtime only | No Bun/daemon-style long-lived browser server, no near-real-time command loop parity, no full upstream browser command surface, no equivalent host command UX |
| `office-hours` | executable | partial runtime only | Local implementation is report synthesis, not upstream-style question-by-question facilitated discovery flow |
| `investigate` | executable | partial runtime only | Root-cause report exists, but upstream-style investigation rhythm, deeper diff tracing, and stronger freeze-before-fix discipline are still lighter than gstack |
| `plan-ceo-review` | executable | partial runtime only | Requirement package exists, but upstream CEO-review interaction pattern and product framing discipline are not yet fully mirrored |
| `review` | executable | partial runtime only | Risk review exists, but it is not yet the full upstream review habit with the same checklist application depth and host behavior |
| `qa` / `qa-only` | executable | partial runtime only | Browser/runtime QA loops exist, but still rely on the local adapted browser stack and not the full upstream browse/QA platform |
| `ship` | executable | partial runtime only | Local mode builds readiness artifacts only; it is not yet the full upstream ship habit with release automation depth, generated testing/PR flow, and full landing choreography |
| `document-release` | executable | partial runtime only | Report generation exists, but not full upstream document-sync and release-facing update behavior parity |
| `retro` | executable | partial runtime only | Retro artifact exists, but upstream closeout rhythm and broader platform integration are still shallower |
| `setup-browser-cookies` | executable | partial runtime only | Storage-state import exists, but browser host/session parity is still bounded by the local Playwright adapter |
| `plan-eng-review`, `plan-design-review`, `design-consultation`, `design-review` | executable | adapted workflow parity only | Workflow and artifacts are wired, but still need upstream-behavior-level review for interaction rhythm and host assumptions |

## 8. Hard Gap Assessment

The most important gaps are platform-level, not prompt-level.

### 8.1 `browse`

This is the biggest gap.

To claim parity with upstream `/browse`, local implementation must eventually support or emulate:

- thin-client plus localhost-only persistent browser host semantics
- `.gstack/browse.json` with `pid`, `port`, `token`, `startedAt`, `binaryVersion`, and `workspaceRoot`
- crash recovery, idle shutdown, and version-mismatch restart
- reusable tabs/session state across step sequences
- command-step execution parity, not only a minimal action list
- richer command surface for navigation, interaction, waiting, capture, and diagnostics
- comparable before/after evidence and step log fidelity
- comparable browser-first workflow ergonomics for downstream `/qa` and `/design-review`

### 8.2 `office-hours`

Current local implementation writes a structured report, but upstream value comes from the facilitation rhythm.

Before parity can be claimed, local implementation must preserve:

- question-first mode
- one forcing question at a time
- stronger scope reframing discipline
- explicit handoff into `plan-ceo-review`

### 8.3 `investigate`

Current local implementation produces a useful report, but parity requires the mode to feel like a real bugfix gate, not just a structured note.

Before parity can be claimed, local implementation must preserve:

- reproducible bugfix-first entry behavior
- stronger evidence gathering from code/runtime/diff context
- more explicit failed-attempt accounting
- tighter scope freeze before fix

### 8.4 `ship`

Current local `ship` is not yet equivalent to upstream `ship`.

Before parity can be claimed, local implementation must preserve or adapt:

- release branch/base diff discipline
- pre-landing review choreography
- stronger release readiness checks
- documentation/testing closeout expectations
- the surrounding release host habits that make `/ship` more than a markdown report

### 8.5 Platform Hooks

The following are still not fully adapted into a behavior-equivalent local host:

- freeze / guard enforcement
- upgrade/check lifecycle
- telemetry behavior
- upstream host-specific interaction affordances
- full session directory and host habit parity

## 9. Migration Acceptance Gates

An Agent can only move to `full_parity` after all gates below pass.

### Gate A. Upstream Mirror

- upstream skill vendored
- upstream helper files vendored if referenced
- commit pinned
- MIT attribution preserved

### Gate B. Runtime Host

- for `/browse`, the runtime must expose persistent service state, auth token, idle timeout, step log, shared storage state, and handoff/resume semantics
- for `/browse`, host state must be materialized through `.gstack/browse.json` and survive independent client invocations
- downstream `qa`, `qa-only`, `design-review`, and `setup-browser-cookies` must reuse the same browser service contract

### Gate C. Interactive Contract

- `office-hours`, `plan-ceo-review`, and any staged decision mode must preserve `awaiting_user_input`, `dialogue_state`, `next_question`, and approval/handoff semantics
- interactive pauses must be resumable without regenerating the whole artifact package

## 10. Formal Audit Gate

Before any Agent may be described as "gstack-equivalent", `agentsystem` must generate a parity audit package with:

- `parity_manifest.json`
- `acceptance_checklist.md`

CLI entry:

- `python cli.py audit-gstack-parity --project finahunt`

Default dogfood target:

- `finahunt/tasks/backlog_v1/sprint_3_linkage_and_ranking`

The audit package must state:

- per-Agent parity status
- structural checks
- acceptance-gate status
- formal dogfood blockers
- intentional deviations

Formal parity sign-off now requires both:

- parity audit green
- dogfood acceptance green

If either is red, the truthful state is still not `full_parity`.

If the audit says `formal_dogfood_ready: false`, the correct conclusion is:

- dogfood planning may continue
- but formal parity acceptance is blocked
- and no Agent may be claimed as `full_parity`

- mode is callable in local runtime
- platform assumptions are adapted, not silently dropped
- persistent artifacts are written

### Gate C. Behavioral Match

- same role
- same guardrails
- same pacing
- same hard stop conditions
- same artifact expectations

### Gate D. Workflow Reachability

- mode is routable through workflow
- mode is startable from CLI/task payload
- mode is enforced where the workflow standard requires it

### Gate E. Test Coverage

- registry test
- workflow route test
- artifact test
- at least one scenario test proving the intended chain executes

## 10. Governance Rule For Future Work

Until an Agent reaches `full_parity`, future development must treat it as:

- "usable local adaptation"
- not "upstream-equivalent"

No future Story, Sprint, or dashboard copy should state that an Agent is fully migrated unless this document and the parity manifest both say so.

## 11. Relationship To Workflow Standard

This document answers:

- which Agents must reach parity
- what "migration complete" means
- what still blocks full migration

The companion workflow standard answers:

- when each Agent must run
- what artifacts each scenario must produce
- how Stories and Sprints are judged complete

Companion document:

- [story_sprint_agent_workflow_standard.md](D:/lyh/agent/agent-frame/agentsystem/docs/standards/story_sprint_agent_workflow_standard.md)
