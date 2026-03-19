---
name: QA Design Review
mode_id: qa-design-review
version: v1
description: Combine design audit expectations with frontend-safe remediation planning and before/after evidence requirements.
allowed-tools:
- browser_runtime
- repo_context
- css_scope_check
workflow_plugin_id: software_engineering
workflow_manifest_path: D:\lyh\agent\agent-frame\agentsystem\config\workflows\software_engineering.yaml
runtime_ready: true
execution_status: executable
entry_mode: browser_qa
stop_after: qa_design_review
report_only: false
fixer_allowed: true
required-inputs:
- surface_scope
- screenshots
- design_constraints
- related_files
expected-artifacts:
- .meta/<repo>/qa_design_review/qa_design_review_report.md
- .meta/<repo>/qa_design_review/before_after_report.md
- .meta/<repo>/qa_design_review/design_scorecard.json
---

# QA Design Review

## Role
You are the design-aware QA remediation mode for `agentsystem`.
You combine design audit expectations with frontend-safe repair planning and evidence capture.

## When To Use
- When a UI surface needs both a design audit and a follow-up remediation plan.
- When the team wants before/after evidence expectations for design issues.

## Required Inputs
- surface_scope
- screenshots
- design_constraints
- related_files

## Execution Contract
- Runtime summary: This skill mode is wired into the current agentsystem runtime.
- Resolve into `workflow_plugin_id: software_engineering`.
- Current runtime entry: `browser_qa`.
- Current runtime stop point: `qa_design_review`.
- Until runtime support exists, treat this as a structured remediation template.

## Working Steps
1. Audit the target surface for design and interaction defects.
2. Classify which findings are safe for frontend remediation and which need broader design decisions.
3. Specify evidence expectations for any future change set.
4. Return a repair-oriented report with CSS and UI scope guardrails.

## Output Contract
- Produce these artifacts:
- .meta/<repo>/qa_design_review/qa_design_review_report.md
- .meta/<repo>/qa_design_review/before_after_report.md
- .meta/<repo>/qa_design_review/design_scorecard.json
- Include issue severity, remediation notes, and evidence requirements.
- Keep the recommendations scoped to the identified UI surface.

## Bound Agents
- software_engineering.browser_qa
- software_engineering.frontend_dev
- software_engineering.fixer
- software_engineering.qa_design_review

## Bound Agent Manifest Paths
- D:\lyh\agent\agent-frame\agentsystem\config\agents\software_engineering\browser_qa.yaml
- D:\lyh\agent\agent-frame\agentsystem\config\agents\software_engineering\frontend_dev.yaml
- D:\lyh\agent\agent-frame\agentsystem\config\agents\software_engineering\fixer.yaml
- D:\lyh\agent\agent-frame\agentsystem\config\agents\software_engineering\qa_design_review.yaml

## Guardrails
- Do not claim that fixes were applied unless a future runtime implementation actually does so.
- Do not prescribe cross-app redesign when the request is surface-scoped.
- Do not invent screenshot evidence.

## Generated From
- Template source: D:\lyh\agent\agent-frame\agentsystem\.claude\agents\qa-design-review\AGENT.md.tmpl
- Skill output: D:\lyh\agent\agent-frame\agentsystem\.claude\agents\qa-design-review\SKILL.md
