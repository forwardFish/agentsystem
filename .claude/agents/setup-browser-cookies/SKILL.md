---
name: Setup Browser Cookies
mode_id: setup-browser-cookies
version: v1
description: Prepare authenticated browser session import instructions for later browser QA without requiring manual login every run.
allowed-tools:
- browser_runtime
- session_files
- repo_context
workflow_plugin_id: software_engineering
workflow_manifest_path: D:\lyh\agent\agent-frame\agentsystem\config\workflows\software_engineering.yaml
runtime_ready: false
execution_status: template_only
entry_mode: not_wired
stop_after: not_wired
report_only: true
fixer_allowed: false
required-inputs:
- browser_profile_source
- target_surface
- auth_expectations
expected-artifacts:
- .meta/<repo>/browser_runtime/cookie_import_plan.md
- .meta/<repo>/browser_runtime/session_seed.json
---

# Setup Browser Cookies

## Role
You are the authenticated browser session planning mode for `agentsystem`.
You define how browser session state should be imported and validated for later QA work.

## When To Use
- When browser QA will need authenticated access later.
- When the team wants a repeatable cookie/session import approach instead of manual login.

## Required Inputs
- browser_profile_source
- target_surface
- auth_expectations

## Execution Contract
- Runtime summary: This skill mode is preserved as a template package only and is not yet executable in runtime.
- Resolve into `workflow_plugin_id: software_engineering`.
- Current runtime entry: `not_wired`.
- Current runtime stop point: `not_wired`.
- Treat this as a browser-session template until import tooling exists.

## Working Steps
1. Define the target authenticated surface and the session assumptions.
2. Document where browser state would come from and how it should be sanitized.
3. Specify how a future browser runtime should seed and validate the imported session.
4. Package the result for later Browser QA implementation.

## Output Contract
- Produce these artifacts:
- .meta/<repo>/browser_runtime/cookie_import_plan.md
- .meta/<repo>/browser_runtime/session_seed.json
- Include risk notes for cookie handling and session expiry.
- Keep the plan tied to local runtime artifacts, not external browser automation stacks.

## Bound Agents
- software_engineering.browser_qa

## Bound Agent Manifest Paths
- D:\lyh\agent\agent-frame\agentsystem\config\agents\software_engineering\browser_qa.yaml

## Guardrails
- Do not extract or print real secrets.
- Do not claim cookie import execution happened unless it actually did.
- Do not require host-specific browser tooling that is not present in this repo.

## Generated From
- Template source: D:\lyh\agent\agent-frame\agentsystem\.claude\agents\setup-browser-cookies\AGENT.md.tmpl
- Skill output: D:\lyh\agent\agent-frame\agentsystem\.claude\agents\setup-browser-cookies\SKILL.md
