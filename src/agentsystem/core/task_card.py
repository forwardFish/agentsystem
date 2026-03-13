from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TaskCard(BaseModel):
    model_config = ConfigDict(extra="allow")

    task_id: str | None = None
    task_name: str | None = None
    sprint: str | None = None
    story_id: str | None = None
    blast_radius: Literal["L1", "L2", "L3"]
    execution_mode: Literal["Fast", "Safe"] | None = None
    mode: Literal["Fast", "Safe"] | None = None
    goal: str = Field(min_length=1)
    acceptance_criteria: list[str] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    explicitly_not_doing: list[str] = Field(default_factory=list)
    not_do: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(min_length=1)
    primary_files: list[str] = Field(default_factory=list)
    secondary_files: list[str] = Field(default_factory=list)
    test_failure_info: str | None = None

    @model_validator(mode="after")
    def normalize_fields(self) -> "TaskCard":
        goal = self.goal.strip()
        if not goal:
            raise ValueError("goal must not be empty")
        self.goal = goal

        self.acceptance_criteria = [item.strip() for item in self.acceptance_criteria if item and item.strip()]
        if not self.acceptance_criteria:
            raise ValueError("acceptance_criteria must contain at least one non-empty item")

        self.constraints = [item.strip() for item in self.constraints if item and item.strip()]
        self.related_files = [item.strip() for item in self.related_files if item and item.strip()]
        if not self.related_files:
            raise ValueError("related_files must contain at least one file path")
        self.primary_files = [item.strip() for item in self.primary_files if item and item.strip()]
        self.secondary_files = [item.strip() for item in self.secondary_files if item and item.strip()]
        if not self.primary_files:
            self.primary_files = list(self.related_files)

        if not self.mode and self.execution_mode:
            self.mode = self.execution_mode
        if not self.execution_mode and self.mode:
            self.execution_mode = self.mode

        if not self.explicitly_not_doing and self.not_do:
            self.explicitly_not_doing = [item.strip() for item in self.not_do if item and item.strip()]

        return self

    def to_runtime_dict(self) -> dict[str, object]:
        payload = self.model_dump()
        payload["mode"] = self.mode or self.execution_mode
        payload["execution_mode"] = self.execution_mode or self.mode
        return payload
