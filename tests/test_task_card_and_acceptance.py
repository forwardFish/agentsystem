from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml
from click.testing import CliRunner

from cli import cli
from agentsystem.agents.acceptance_gate_agent import acceptance_gate_node
from agentsystem.core.task_card import TaskCard


class TaskCardValidationTestCase(unittest.TestCase):
    def test_task_card_requires_acceptance_criteria(self) -> None:
        with self.assertRaises(Exception):
            TaskCard.model_validate(
                {
                    "goal": "给前端页面加副标题",
                    "blast_radius": "L1",
                    "mode": "Fast",
                    "acceptance_criteria": [],
                    "related_files": ["apps/web/src/app/(dashboard)/agents/[agentId]/page.tsx"],
                }
            )

    def test_cli_run_task_rejects_invalid_card(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            task_file = Path(tmp) / "invalid_task.yaml"
            task_file.write_text(
                yaml.safe_dump(
                    {
                        "goal": "",
                        "blast_radius": "L1",
                        "mode": "Fast",
                        "acceptance_criteria": [],
                        "related_files": [],
                    },
                    sort_keys=False,
                    allow_unicode=True,
                ),
                encoding="utf-8",
            )
            result = runner.invoke(cli, ["run-task", "--task-file", str(task_file), "--env", "test"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("任务卡校验失败", result.output)


class AcceptanceGateTestCase(unittest.TestCase):
    def test_acceptance_gate_blocks_when_subtitle_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            target_file = repo_path / "apps" / "web" / "src" / "app" / "(dashboard)" / "agents" / "[agentId]" / "page.tsx"
            target_file.parent.mkdir(parents=True)
            target_file.write_text("export default function Page() { return <div>Agent page</div>; }\n", encoding="utf-8")

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "goal": "给前端页面加一个 Reviewer 测试副标题",
                    "acceptance_criteria": ["页面顶部有副标题"],
                    "related_files": ["apps/web/src/app/(dashboard)/agents/[agentId]/page.tsx"],
                },
                "dev_results": {
                    "frontend": {
                        "updated_files": [str(target_file)],
                    }
                },
                "review_passed": True,
                "blocking_issues": [],
            }

            final_state = acceptance_gate_node(state)

            self.assertFalse(final_state["acceptance_passed"])
            self.assertIn("Acceptance unmet: 页面顶部有副标题", final_state["blocking_issues"])
            self.assertIn("Acceptance failed", final_state["acceptance_report"])

    def test_acceptance_gate_passes_when_subtitle_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp) / "repo"
            target_file = repo_path / "apps" / "web" / "src" / "app" / "(dashboard)" / "agents" / "[agentId]" / "page.tsx"
            target_file.parent.mkdir(parents=True)
            target_file.write_text(
                'export default function Page() {\n'
                '  return <div>\n'
                '      <p className="mb-2 text-sm text-slate-500">Reviewer 测试副标题</p>\n'
                '      <h1>Agent</h1>\n'
                '  </div>;\n'
                '}\n',
                encoding="utf-8",
            )

            state = {
                "repo_b_path": str(repo_path),
                "task_payload": {
                    "goal": "给前端页面加一个 Reviewer 测试副标题",
                    "acceptance_criteria": ["页面顶部有副标题"],
                    "related_files": ["apps/web/src/app/(dashboard)/agents/[agentId]/page.tsx"],
                },
                "dev_results": {
                    "frontend": {
                        "updated_files": [str(target_file)],
                    }
                },
                "review_passed": True,
                "blocking_issues": [],
            }

            final_state = acceptance_gate_node(state)

            self.assertTrue(final_state["acceptance_passed"])
            self.assertEqual(final_state["blocking_issues"], [])


if __name__ == "__main__":
    unittest.main()
