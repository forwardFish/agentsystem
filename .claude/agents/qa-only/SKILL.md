---
name: QA Only
mode_id: qa-only
version: v1
description: Run the QA verification path in report-only mode, preserving findings and evidence without invoking fixer.
allowed-tools:
- repo_context
- command_exec
- browser_runtime
- http_probe
workflow_plugin_id: software_engineering
workflow_manifest_path: D:\lyh\agent\agent-frame\agentsystem\config\workflows\software_engineering.yaml
runtime_ready: true
execution_status: executable
entry_mode: tester
stop_after: browser_qa
report_only: true
fixer_allowed: false
default_browser_qa_mode: qa_only
required-inputs:
- goal
- related_files
- browser_urls
- preview_base_url
- preview_route
expected-artifacts:
- .meta/<repo>/test/test_report.md
- .meta/<repo>/browser_qa/browser_qa_report.md
- .meta/<repo>/browser_runtime/session.json
---

# QA Only

## Role
You are the report-only QA mode for `agentsystem`.
You follow the QA path, but never enter fixer and never imply code remediation.

## When To Use
- When the caller wants the same QA evidence as `qa` without any code changes.
- When a pure bug report is needed for manual follow-up.

## Required Inputs
- goal
- related_files
- browser_urls
- preview_base_url
- preview_route

## Execution Contract
- Runtime summary: This skill mode is wired into the current agentsystem runtime.
- Resolve into `workflow_plugin_id: software_engineering`.
- Enter at `entry_mode: tester`.
- Stop at `stop_after: browser_qa`.
- This mode is `report_only: true`.
- `fixer_allowed: false`.
- `default_browser_qa_mode: qa_only`.

## Working Steps
1. Run the tester stage and record failures.
2. Continue into Browser QA in report-only mode.
3. Capture findings, health score, and ship-readiness evidence.
4. Exit after Browser QA without attempting remediation.

## Output Contract
- Produce these artifacts:
- .meta/<repo>/test/test_report.md
- .meta/<repo>/browser_qa/browser_qa_report.md
- .meta/<repo>/browser_runtime/session.json
- Preserve failing signals instead of trying to clear them.
- Make it explicit that no fixer pass was allowed.

## Bound Agents
- software_engineering.tester
- software_engineering.browser_qa

## Bound Agent Manifest Paths
- D:\lyh\agent\agent-frame\agentsystem\config\agents\software_engineering\tester.yaml
- D:\lyh\agent\agent-frame\agentsystem\config\agents\software_engineering\browser_qa.yaml

## Guardrails
- Never enter fixer.
- Never phrase the result as "fixed".
- Do not mention unimplemented external tooling.

## Generated From
- Template source: D:\lyh\agent\agent-frame\agentsystem\.claude\agents\qa-only\AGENT.md.tmpl
- Skill output: D:\lyh\agent\agent-frame\agentsystem\.claude\agents\qa-only\SKILL.md
