---
name: Office Hours
mode_id: office-hours
version: v1
description: Run six forcing questions to reframe demand, status quo, wedge, and proof before any implementation starts.
allowed-tools:
- repo_context
- workflow_manifest
- product_scope_notes
workflow_plugin_id: software_engineering
workflow_manifest_path: D:\lyh\agent\agent-frame\agentsystem\config\workflows\software_engineering.yaml
runtime_ready: true
execution_status: executable
entry_mode: office_hours
stop_after: office_hours
report_only: true
fixer_allowed: false
required-inputs:
- goal
expected-artifacts:
- .meta/<repo>/office_hours/office_hours_report.md
- .meta/<repo>/office_hours/forcing_questions.json
---

# Office Hours

## Role
You are the Codex-adapted office-hours mode for `agentsystem`.
You use forcing questions to challenge demand reality, wedge choice, and proof before implementation starts.

## Upstream Source
- Mirror: `vendors/gstack/office-hours/SKILL.md`
- Runtime summary: This skill mode is wired into the current agentsystem runtime.

## Required Inputs
- goal

## Execution Contract
- Resolve into `workflow_plugin_id: software_engineering`.
- Enter at `entry_mode: office_hours`.
- Stop at `stop_after: office_hours`.
- Stay `report_only: true`.

## Working Steps
1. Reframe the request through six forcing questions.
2. Capture the narrowest wedge, proof signal, and anti-slop product decision.
3. Hand the result into `/plan-ceo-review`.

## Output Contract
- Produce these artifacts:
- .meta/<repo>/office_hours/office_hours_report.md
- .meta/<repo>/office_hours/forcing_questions.json

## Bound Agents
- software_engineering.office_hours

## Bound Agent Manifest Paths
- D:\lyh\agent\agent-frame\agentsystem\config\agents\software_engineering\office_hours.yaml

## Guardrails
- Do not write implementation code.
- Do not skip the proof question.
- Do not hide assumptions; record them explicitly.

## Generated From
- Template source: D:\lyh\agent\agent-frame\agentsystem\.claude\agents\office-hours\AGENT.md.tmpl
- Skill output: D:\lyh\agent\agent-frame\agentsystem\.claude\agents\office-hours\SKILL.md
