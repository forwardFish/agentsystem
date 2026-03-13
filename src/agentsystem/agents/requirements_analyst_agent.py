from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from agentsystem.adapters.context_assembler import ContextAssembler


FRONTEND_FALLBACK_PAGE = "apps/web/src/app/(dashboard)/onboarding/page.tsx"
FRONTEND_LAYOUT = "apps/web/src/app/(dashboard)/layout.tsx"


class RequirementsAnalystAgent:
    """Planning-layer agent that turns a large requirement into sprint artifacts."""

    def __init__(self, repo_b_path: str | Path, tasks_root: str | Path):
        self.repo_b_path = Path(repo_b_path).resolve()
        self.tasks_root = Path(tasks_root).resolve()
        self.context_assembler = ContextAssembler(self.repo_b_path)

    def analyze(self, requirement: str, sprint: str = "1") -> dict[str, Any]:
        requirement = requirement.strip()
        if not requirement:
            raise ValueError("requirement must not be empty")

        sprint_number = str(sprint).strip() or "1"
        sprint_dir = self.tasks_root / f"sprint_{sprint_number}"
        sprint_dir.mkdir(parents=True, exist_ok=True)
        self._clear_existing_artifacts(sprint_dir)

        project_context = self._build_project_context()
        scope = self._extract_scope(requirement)
        story_items = self._extract_story_items(requirement)
        story_cards = [self._build_story_card(item, index + 1, sprint_number) for index, item in enumerate(story_items)]
        execution_order = [card["story_id"] for card in story_cards]
        sprint_plan = self._build_sprint_plan(requirement, sprint_number, story_cards, project_context, scope)

        (sprint_dir / "sprint_plan.md").write_text(sprint_plan, encoding="utf-8")
        (sprint_dir / "execution_order.txt").write_text("\n".join(execution_order) + "\n", encoding="utf-8")

        for card in story_cards:
            slug = self._slugify(card["task_name"])
            target = sprint_dir / f"{card['story_id']}_{slug}.yaml"
            target.write_text(yaml.safe_dump(card, allow_unicode=True, sort_keys=False), encoding="utf-8")

        return {
            "sprint_dir": str(sprint_dir),
            "sprint_plan_path": str(sprint_dir / "sprint_plan.md"),
            "execution_order_path": str(sprint_dir / "execution_order.txt"),
            "story_cards": story_cards,
            "execution_order": execution_order,
            "project_context": project_context,
        }

    def _clear_existing_artifacts(self, sprint_dir: Path) -> None:
        for path in sprint_dir.glob("*.yaml"):
            path.unlink(missing_ok=True)
        for name in ("sprint_plan.md", "execution_order.txt"):
            (sprint_dir / name).unlink(missing_ok=True)

    def _build_project_context(self) -> dict[str, Any]:
        constitution = self.context_assembler.build_constitution()
        web_pages = sorted(
            str(path.relative_to(self.repo_b_path)).replace("\\", "/")
            for path in (self.repo_b_path / "apps" / "web" / "src" / "app").rglob("page.tsx")
        )
        api_modules = sorted(
            str(path.relative_to(self.repo_b_path)).replace("\\", "/")
            for path in (self.repo_b_path / "apps" / "api" / "src").rglob("*.py")
        )
        return {
            "constitution_length": len(constitution),
            "web_pages": web_pages,
            "api_modules": api_modules,
        }

    def _extract_scope(self, requirement: str) -> dict[str, list[str]]:
        sentences = [part.strip() for part in re.split(r"[。！？!?\n]+", requirement) if part.strip()]
        constraints: list[str] = []
        not_do: list[str] = []

        for sentence in sentences:
            if any(keyword in sentence for keyword in ["只做", "必须", "遵循", "复用", "仅限", "限制"]):
                constraints.append(sentence)
            if any(keyword in sentence for keyword in ["不动", "不得", "不要", "不新增", "不修改", "不做"]):
                not_do.append(sentence)

        constraints = list(dict.fromkeys(constraints))
        not_do = list(dict.fromkeys(not_do))
        return {"constraints": constraints, "not_do": not_do}

    def _extract_story_items(self, requirement: str) -> list[str]:
        numbered_items = re.findall(r"(?:^|\n)\s*\d+[.、]\s*([^\n]+)", requirement)
        if numbered_items:
            return [self._clean_text(item) for item in numbered_items if self._clean_text(item)]

        include_match = re.search(r"包括(?P<body>.+?)(?:。|；|;|只做|不动|必须|不得|不要|$)", requirement)
        if include_match:
            body = include_match.group("body")
            items = [self._clean_text(part) for part in re.split(r"[、,，；;]", body) if self._clean_text(part)]
            if items:
                return items

        segments = [self._clean_text(part) for part in re.split(r"[；;。！？!?\n]", requirement) if self._clean_text(part)]
        feature_segments = [
            part
            for part in segments
            if not any(keyword in part for keyword in ["只做", "必须", "不动", "不新增", "不修改", "不得", "不要"])
        ]
        if feature_segments:
            return feature_segments

        cleaned = self._clean_text(requirement)
        return [cleaned] if cleaned else []

    def _build_story_card(self, item: str, index: int, sprint_number: str) -> dict[str, Any]:
        story_id = f"S{sprint_number}-{index:03d}"
        level = "L1" if self._is_l1_story(item) else "L2"
        mode = "Fast" if level == "L1" else "Safe"
        primary_files, secondary_files = self._resolve_files(item)
        related_files = list(dict.fromkeys(primary_files + secondary_files))
        task_name = self._story_name(item)

        return {
            "task_id": story_id,
            "task_name": task_name,
            "sprint": f"Sprint {sprint_number}",
            "story_id": story_id,
            "blast_radius": level,
            "execution_mode": mode,
            "mode": mode,
            "goal": item,
            "acceptance_criteria": self._acceptance_criteria(item, level),
            "constraints": self._constraints(primary_files),
            "not_do": self._not_do(item),
            "related_files": related_files,
            "primary_files": primary_files,
            "secondary_files": secondary_files,
        }

    def _is_l1_story(self, item: str) -> bool:
        lowered = item.lower()
        l1_keywords = [
            "标题",
            "副标题",
            "文案",
            "按钮",
            "入口",
            "样式",
            "骨架",
            "布局",
            "title",
            "subtitle",
            "button",
            "layout",
        ]
        return any(keyword in item or keyword in lowered for keyword in l1_keywords)

    def _resolve_files(self, item: str) -> tuple[list[str], list[str]]:
        lowered = item.lower()
        if any(keyword in item for keyword in ["用户", "个人中心", "头像", "昵称", "订单", "设置"]):
            return ([FRONTEND_FALLBACK_PAGE], [FRONTEND_LAYOUT])
        if any(keyword in lowered for keyword in ["agent", "position", "snapshot"]) or any(
            keyword in item for keyword in ["观测", "持仓", "快照"]
        ):
            return (
                ["apps/web/src/app/(dashboard)/agents/[agentId]/page.tsx"],
                ["apps/api/src/domain/agent_registry/service.py"],
            )
        if any(keyword in lowered for keyword in ["ranking", "rank"]) or any(keyword in item for keyword in ["排行", "排名"]):
            return (
                ["apps/web/src/app/(dashboard)/rankings/page.tsx"],
                ["apps/api/src/projection/rankings/service.py"],
            )
        if any(keyword in lowered for keyword in ["universe", "market"]) or any(keyword in item for keyword in ["市场", "股票池"]):
            return (
                ["apps/web/src/app/(dashboard)/universe/page.tsx"],
                ["apps/api/src/domain/market_world/service.py"],
            )
        if any(keyword in lowered for keyword in ["api", "backend"]) or any(keyword in item for keyword in ["接口", "后端"]):
            return (
                ["apps/api/src/api/query/routes.py"],
                ["apps/api/src/schemas/query.py"],
            )
        return ([FRONTEND_FALLBACK_PAGE], [FRONTEND_LAYOUT])

    def _acceptance_criteria(self, item: str, level: str) -> list[str]:
        criteria = [
            f"完成“{item}”对应的页面或逻辑改动",
            "改动仅限任务相关文件，并保持现有项目结构不变",
        ]
        if level == "L1":
            criteria.append("代码通过 prettier 格式化")
        else:
            criteria.extend(
                [
                    "复用现有页面结构或服务模块，不新增无关依赖",
                    "修改后页面或接口入口可正常访问",
                ]
            )
        return criteria

    def _constraints(self, primary_files: list[str]) -> list[str]:
        constraints = ["严格遵循现有代码规范和样式体系", "不得新增第三方依赖"]
        if primary_files:
            constraints.append(f"优先修改这些主文件: {', '.join(primary_files)}")
        return constraints

    def _not_do(self, item: str) -> list[str]:
        rules = ["不做与当前 Story 无关的重构", "不修改未列入 related_files 的模块"]
        if any(keyword in item for keyword in ["页面", "按钮", "标题", "头像", "昵称", "订单", "设置", "前端"]):
            rules.append("不新增后端 API")
        return rules

    def _build_sprint_plan(
        self,
        requirement: str,
        sprint_number: str,
        story_cards: list[dict[str, Any]],
        project_context: dict[str, Any],
        scope: dict[str, list[str]],
    ) -> str:
        table_rows = "\n".join(
            f"| {card['story_id']} | {card['task_name']} | {card['blast_radius']} | 无 | {len(card['acceptance_criteria'])} |"
            for card in story_cards
        )
        do_items = "\n".join(f"- [ ] {card['task_name']}" for card in story_cards)
        not_do_items = "\n".join(f"- {item}" for item in scope["not_do"]) or "- 不进入 L3 级别改动"
        constraints = "\n".join(f"- {item}" for item in scope["constraints"]) or "- 必须复用现有页面、布局和服务模块"
        order = "\n".join(f"{index}. {card['story_id']}" for index, card in enumerate(story_cards, start=1))

        return (
            "\n".join(
                [
                    f"# Sprint {sprint_number} 规划",
                    "",
                    "## Sprint 目标",
                    requirement,
                    "",
                    "## 业务边界",
                    "### 做什么",
                    do_items,
                    "",
                    "### 不做什么",
                    not_do_items,
                    "",
                    "## 技术约束",
                    constraints,
                    f"- 当前可用前端页面数: {len(project_context['web_pages'])}",
                    "",
                    "## Story List 总览",
                    "| Story ID | Story 名称 | 级别 | 依赖 | 验收标准数 |",
                    "| :--- | :--- | :--- | :--- | :--- |",
                    table_rows,
                    "",
                    "## 推荐执行顺序",
                    order,
                ]
            ).strip()
            + "\n"
        )

    def _story_name(self, item: str) -> str:
        item = self._clean_text(item)
        if len(item) <= 24:
            return item
        return item[:24]

    def _slugify(self, name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
        return slug or "story"

    def _clean_text(self, value: str) -> str:
        return value.strip(" \t\r\n，。；;、:：")


def analyze_requirement(
    repo_b_path: str | Path,
    tasks_root: str | Path,
    requirement: str,
    sprint: str = "1",
) -> dict[str, Any]:
    agent = RequirementsAnalystAgent(repo_b_path, tasks_root)
    return agent.analyze(requirement, sprint)
