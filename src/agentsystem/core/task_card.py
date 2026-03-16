from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _clean_string_list(values: list[str] | tuple[str, ...] | None) -> list[str]:
    return [str(item).strip() for item in (values or []) if str(item).strip()]


class TaskCard(BaseModel):
    model_config = ConfigDict(extra="allow")

    task_id: str | None = None
    task_name: str | None = None
    sprint: str | None = None
    epic: str | None = None
    story_id: str | None = None
    blast_radius: Literal["L1", "L2", "L3"]
    business_value: str | None = None
    execution_mode: Literal["Fast", "Safe"] | None = None
    mode: Literal["Fast", "Safe"] | None = None
    goal: str = Field(min_length=1)
    entry_criteria: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    explicitly_not_doing: list[str] = Field(default_factory=list)
    not_do: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(min_length=1)
    primary_files: list[str] = Field(default_factory=list)
    secondary_files: list[str] = Field(default_factory=list)
    test_cases: dict[str, list[str]] = Field(default_factory=dict)
    test_failure_info: str | None = None
    story_inputs: list[str] = Field(default_factory=list)
    story_process: list[str] = Field(default_factory=list)
    story_outputs: list[str] = Field(default_factory=list)
    verification_basis: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_fields(self) -> "TaskCard":
        goal = self.goal.strip()
        if not goal:
            raise ValueError("goal must not be empty")
        self.goal = goal

        self.acceptance_criteria = _clean_string_list(self.acceptance_criteria)
        if not self.acceptance_criteria:
            raise ValueError("acceptance_criteria must contain at least one non-empty item")

        self.constraints = _clean_string_list(self.constraints)
        self.entry_criteria = _clean_string_list(self.entry_criteria)
        self.related_files = _clean_string_list(self.related_files)
        if not self.related_files:
            raise ValueError("related_files must contain at least one file path")
        self.primary_files = _clean_string_list(self.primary_files)
        self.secondary_files = _clean_string_list(self.secondary_files)
        if not self.primary_files:
            self.primary_files = list(self.related_files)

        if not self.mode and self.execution_mode:
            self.mode = self.execution_mode
        if not self.execution_mode and self.mode:
            self.execution_mode = self.mode

        if not self.explicitly_not_doing and self.not_do:
            self.explicitly_not_doing = _clean_string_list(self.not_do)
        if not self.explicitly_not_doing and self.out_of_scope:
            self.explicitly_not_doing = _clean_string_list(self.out_of_scope)
        if not self.not_do and self.out_of_scope:
            self.not_do = _clean_string_list(self.out_of_scope)
        self.out_of_scope = _clean_string_list(self.out_of_scope)
        self.dependencies = _clean_string_list(self.dependencies)
        cleaned_test_cases: dict[str, list[str]] = {}
        for case_type, items in self.test_cases.items():
            cleaned = [str(item).strip() for item in items if str(item).strip()]
            if cleaned:
                cleaned_test_cases[str(case_type)] = cleaned
        self.test_cases = cleaned_test_cases
        self.story_inputs = _clean_string_list(self.story_inputs) or self._default_story_inputs()
        self.story_process = _clean_string_list(self.story_process) or self._default_story_process()
        self.story_outputs = _clean_string_list(self.story_outputs) or self._default_story_outputs()
        self.verification_basis = _clean_string_list(self.verification_basis) or list(self.acceptance_criteria)

        return self

    def to_runtime_dict(self) -> dict[str, object]:
        payload = self.model_dump()
        payload["mode"] = self.mode or self.execution_mode
        payload["execution_mode"] = self.execution_mode or self.mode
        return payload

    def _default_story_inputs(self) -> list[str]:
        inputs: list[str] = []
        inputs.extend(self.entry_criteria)
        scoped_files = self.primary_files or self.related_files
        if scoped_files:
            inputs.append(f"In-scope files: {', '.join(scoped_files)}")
        dependencies = [item for item in self.dependencies if item.lower() not in {"none", "n/a", "无"}]
        if dependencies:
            inputs.append(f"Dependency outputs available from: {', '.join(dependencies)}")
        if not inputs:
            inputs.append("Use the current story goal and declared in-scope files as the execution input.")
        return inputs

    def _default_story_process(self) -> list[str]:
        return [
            "Inspect the declared scope and understand the current implementation before editing.",
            "Implement only the change required for this story goal and keep the blast radius within the card.",
            "Run story-specific validation and record reusable evidence for acceptance.",
        ]

    def _default_story_outputs(self) -> list[str]:
        outputs: list[str] = []
        scoped_files = self.primary_files or self.related_files
        if scoped_files:
            outputs.append(f"Updated story artifacts in: {', '.join(scoped_files)}")
        outputs.append("Validation evidence and delivery artifacts archived for this story.")
        return outputs
