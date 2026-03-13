# requirements_analyst

## Skill Description
Turn a large product requirement into a sprint plan plus executable L1/L2 story task cards.

## Input Parameters
- requirement
- sprint
- project_context

## Execution Rules
- Only plan. Never modify business code.
- Every generated story must be L1 or L2.
- Every story must have concrete, testable acceptance criteria.
- Every story must include `related_files`, `primary_files`, and `secondary_files`.
- Prefer existing pages, components, and modules instead of inventing new architecture.

## Output Requirements
- Produce a sprint plan document.
- Produce one YAML task card per story.
- Produce a recommended execution order.

## Forbidden
- Do not generate any L3 story.
- Do not generate a story that cannot be completed inside the current repository.
- Do not enter the coding workflow.
