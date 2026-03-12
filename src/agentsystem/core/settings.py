from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field


class Settings(BaseModel):
    repo_b_local_path: Path = Field(alias="REPO_B_LOCAL_PATH")
    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")
    github_owner: str | None = Field(default=None, alias="GITHUB_OWNER")
    github_repo_b_name: str | None = Field(default=None, alias="GITHUB_REPO_B_NAME")

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls.model_validate(os.environ)
