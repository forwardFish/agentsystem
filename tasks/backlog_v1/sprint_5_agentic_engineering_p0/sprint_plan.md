# Sprint 5 Agentic Engineering Control Plane P0

## Sprint Goal
Upgrade `agentsystem` from a Story delivery workflow into a planning-aware, browser-verified, ship-ready engineering control plane.

## Exit Criteria
- `software_engineering` workflow contains a first-class Architecture Review stage that writes an implementation plan and a reusable test plan.
- Browser QA has a persistent runtime scaffold, a verification node, and dashboard-visible evidence including screenshots, console health, and ship-readiness.
- Ship flow has a guarded agent path that can prepare release evidence, capture PR metadata, and expose approval status without bypassing acceptance gates.

## Not Doing
- No design-consultation or design-fix loop in this sprint.
- No weekly retro automation in this sprint.
- No repo-wide documentation rewrite workflow in this sprint.

## Epic Overview
| Epic | Story Count | Core Responsibility |
| :--- | :--- | :--- |
| Architecture Review and Test Planning | 3 | Add the missing `plan-eng-review` style planning layer before execution starts. |
| Browser QA Runtime and Verification | 3 | Give the workflow browser eyes, evidence capture, and report-only QA capability. |
| Ship Release Guardrails | 2 | Add a guarded release path that turns acceptance into an actual pre-ship control loop. |

## Delivery Order
1. Architecture review node, artifacts, and test-plan handoff
2. Browser runtime and browser QA verification
3. Ship agent, release guardrails, and dashboard visibility
