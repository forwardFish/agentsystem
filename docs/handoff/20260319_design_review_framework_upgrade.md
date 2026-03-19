# Design Review Framework Upgrade

## Scope

- Upgraded `browse`
- Upgraded `plan-design-review`
- Upgraded `design-review`
- Goal: make the chain more reusable across projects instead of being biased toward `agentHire` only

## What Improved

- `browse`
  - real structured observation fields now flow back into workflow state instead of only being written to JSON artifacts
  - observation payload now includes counts for nav, headings, CTAs, filters, categories, sponsor blocks, stats, and cards
  - harmless `_rsc` prefetch aborts and ORB-blocked third-party assets no longer trigger blocking browser failures
  - reference-site noise is preserved as notes instead of polluting current-surface health

- `plan-design-review`
  - moved from a hardcoded `agentHire`-leaning path to a route-aware benchmark framework
  - route scope can now be inferred from `browser_urls` or observations when `route_scope` is missing
  - benchmark/profile selection now supports:
    - `toolify_directory`
    - `product_directory`
    - `dashboard_surface`
  - outputs now include:
    - route-level scores
    - overall dimension scores
    - assumptions
    - route-aware `DESIGN.md`

- `design-review`
  - now scores route-by-route and aggregates with the lowest-route rule instead of only using one coarse global score
  - findings now include route context and better target file mapping
  - acceptance criteria and browser QA warnings are explicitly included in the review report
  - route-level findings are now useful as actual Fixer inputs for other projects

## New Shared Layer

- Added shared framework module:
  - `src/agentsystem/agents/design_review_framework.py`
- Shared responsibilities:
  - route pattern inference
  - benchmark/profile selection
  - route classification
  - route-level scoring
  - aggregated design-review scoring
  - route-to-file finding mapping
  - route-aware design contract generation

## Tests Run

- `python -m unittest tests.test_browser_runtime -v`
- `python -m unittest tests.test_design_review_framework -v`
- `python -m unittest tests.test_qa_routing -v`
- `python -m unittest tests.test_design_closure -v`

## Real Project Re-Run

- Re-ran the upgraded chain on `agentHire` against:
  - local preview: `http://127.0.0.1:3002`
  - reference: `https://www.toolify.ai/`
- Result:
  - `browser_qa_passed = true`
  - `browser_qa_health_score = 100`
  - `design_review_passed = false`

## Why The Design Review Became Stricter

- The upgraded framework now catches route-level weaknesses that the earlier global score could hide.
- On the latest `agentHire` run, the new framework flagged remaining polish gaps mainly on:
  - `/request`
  - `/content/[slug]`
  - part of `/agents`

## Current Value

- The chain is now more useful for new projects because it can:
  - infer route scope automatically
  - handle directory-style and dashboard-style surfaces
  - produce route-aware `DESIGN.md`
  - emit richer fixer-ready findings instead of one flat pass/fail

## Main Files

- `D:\lyh\agent\agent-frame\agentsystem\src\agentsystem\runtime\playwright_browser_runtime.py`
- `D:\lyh\agent\agent-frame\agentsystem\src\agentsystem\agents\browser_qa_agent.py`
- `D:\lyh\agent\agent-frame\agentsystem\src\agentsystem\agents\design_review_framework.py`
- `D:\lyh\agent\agent-frame\agentsystem\src\agentsystem\agents\plan_design_review_agent.py`
- `D:\lyh\agent\agent-frame\agentsystem\src\agentsystem\agents\qa_design_review_agent.py`
- `D:\lyh\agent\agent-frame\agentsystem\tests\test_browser_runtime.py`
- `D:\lyh\agent\agent-frame\agentsystem\tests\test_design_review_framework.py`
