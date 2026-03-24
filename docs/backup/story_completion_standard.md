# Story Completion Standard

## Purpose
A Story is the smallest execution and acceptance unit in the system. A Story is only considered complete when implementation, validation, review, code acceptance, final acceptance, and delivery reporting all succeed with evidence.

## Definition of Done
- The task card is valid and passes `TaskCard` schema validation.
- The execution scope is explicit and limited to files allowed by the Story.
- The expected output artifacts are written into the target repository and can be reused by downstream stories.
- Configured project checks and Story-specific validation both pass.
- Reviewer reports no blocking issues.
- Code Acceptance Agent reports no style-consistency or file-hygiene blockers.
- Acceptance Gate passes all checklist items and confirms there is no out-of-scope change.
- A delivery report is generated and archived.

## Acceptance OK
- Every acceptance criterion has explicit evidence recorded in the delivery report.
- The test report contains no failing checks.
- Review, Code Acceptance, and Acceptance Gate all pass.
- Output artifacts, reports, and logs are readable UTF-8 content.

## Standard Flow
1. Requirement Agent parses the task card and clarifies the intent, scope, and constraints.
2. Builder Agent modifies only the files allowed by the Story.
3. Test Agent runs project checks plus Story-specific validation.
4. Review Agent checks requirement fit, structure, and risk.
5. Code Acceptance Agent checks style consistency and artifact hygiene.
6. Acceptance Gate performs the final hard stop against acceptance criteria and scope.
7. Doc Agent outputs the standardized delivery report.

## Minimum Delivery Report Content
- Story summary
- Acceptance criteria checklist
- Acceptance evidence
- Test results
- Review results
- Code acceptance results
- Final verdict
