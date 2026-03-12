import json
import tempfile
import unittest
from pathlib import Path

from agent_system_framework.core.agent_meta_model import AgentMetaModel, AgentStatus, AgentType, Plane
from agent_system_framework.core.lifecycle import LifecycleError, LifecycleManager
from agent_system_framework.core.state_schema import TaskState
from agent_system_framework.execution_system.agent_pool import KernelArtifact
from agent_system_framework.framework import AgentSystemFramework
from agent_system_framework.spec_system.parser import FileSpecLoader


class FrameworkTestCase(unittest.TestCase):
    def test_lifecycle_rejects_invalid_transition(self) -> None:
        lifecycle = LifecycleManager()
        with self.assertRaises(LifecycleError):
            lifecycle.transition(AgentStatus.DRAFT, AgentStatus.RUNNING)

    def test_framework_runs_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec_root = write_spec_dir(Path(tmp))
            framework = AgentSystemFramework()
            agent = GenericKernelAgent()
            framework.register_agent(agent, spec_root)

            result = framework.run_agent(agent.meta.agent_id, "input://kernel")

            self.assertTrue(result.approved)
            self.assertTrue(result.task.output_ref.startswith("output::"))
            self.assertTrue(result.task.artifact_refs)
            self.assertEqual(
                framework.read_store.dashboard[result.task.task_id]["events"],
                ["artifact.ready", "agent.completed", "verification.passed", "governance.final_gate"],
            )
            self.assertEqual(framework.audit_logger.records[0].action, "final_gate")

    def test_spec_loader_validates_kernel_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = FileSpecLoader(write_spec_dir(Path(tmp))).load()
            self.assertEqual(bundle.repo_policy.rule_version, "kernel-v1")
            self.assertIn("runtime-task-input", bundle.contracts)
            self.assertIn("runtime-task-output", bundle.contracts)
            self.assertEqual(bundle.tool_policy.permission_scope, "task")

    def test_contract_rule_blocks_invalid_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            spec_root = write_spec_dir(Path(tmp))
            framework = AgentSystemFramework()
            agent = BrokenKernelAgent()
            framework.register_agent(agent, spec_root)

            result = framework.run_agent(agent.meta.agent_id, "input://broken")

            self.assertFalse(result.approved)
            self.assertIn("contract:runtime-task-output:missing:result", result.reasons)


class GenericKernelAgent:
    def __init__(self) -> None:
        self._meta = AgentMetaModel(
            agent_id="kernel.runtime.agent",
            agent_type=AgentType.BUSINESS,
            plane=Plane.RUNTIME,
            capabilities=["transform"],
            input_contract="runtime-task-input",
            output_contract="runtime-task-output",
            allowed_tools=["emit_event", "write_artifact"],
            allowed_events=["artifact.ready"],
            owner="test",
        )

    @property
    def meta(self) -> AgentMetaModel:
        return self._meta

    def can_handle(self, task: TaskState) -> bool:
        return True

    def execute(self, task: TaskState) -> KernelArtifact:
        artifact_id = f"artifact::{task.task_id}"
        return KernelArtifact(
            output_ref=f"output::{task.task_id}",
            output_payload={
                "result": f"normalized:{task.input_ref}",
                "task_id": task.task_id,
                "agent_id": self.meta.agent_id,
                "trace_id": task.metadata.trace_id,
                "artifact_refs": [artifact_id],
                "events": ["artifact.ready"],
            },
            artifacts={artifact_id: {"task_id": task.task_id, "kind": "generic_artifact"}},
            emitted_events=[("artifact.ready", {"task_id": task.task_id, "artifact_id": artifact_id})],
        )


class BrokenKernelAgent(GenericKernelAgent):
    def __init__(self) -> None:
        super().__init__()
        self._meta.agent_id = "broken.kernel.agent"

    def execute(self, task: TaskState) -> KernelArtifact:
        artifact_id = f"artifact::{task.task_id}"
        return KernelArtifact(
            output_ref=f"output::{task.task_id}",
            output_payload={
                "task_id": task.task_id,
                "agent_id": self.meta.agent_id,
                "trace_id": task.metadata.trace_id,
                "artifact_refs": [artifact_id],
                "events": ["artifact.ready"],
            },
            artifacts={artifact_id: {"task_id": task.task_id}},
            emitted_events=[("artifact.ready", {"task_id": task.task_id})],
        )


def write_spec_dir(root: Path) -> Path:
    write(root / "RepoPolicy.yaml", json.dumps({
        "rule_version": "kernel-v1",
        "shard_affinity": "agent_id",
        "resource_limits": {"max_artifacts": 4, "max_events": 4},
        "compliance_base_rules": [
            "output_ref.required",
            "artifact_refs.min_1",
            "trace_id.required",
            "output.result.required",
            "output.result.non_empty",
        ],
    }, ensure_ascii=False, indent=2))
    write(root / "ToolPolicy.yaml", json.dumps({
        "allowlist": ["emit_event", "write_artifact"],
        "denylist": ["shell_exec", "network_call"],
        "permission_scope": "task",
    }, ensure_ascii=False, indent=2))
    write(root / "ContractSpec.json", json.dumps({
        "contracts": {
            "runtime-task-input": {
                "description": "Kernel task input contract",
                "required_fields": [
                    "task_id",
                    "run_id",
                    "shard_id",
                    "graph_type",
                    "stage",
                    "status",
                    "input_ref",
                    "rule_version",
                    "metadata.agent_id",
                    "metadata.agent_version",
                    "metadata.trace_id",
                    "metadata.upstream_event"
                ]
            },
            "runtime-task-output": {
                "description": "Kernel task output contract",
                "required_fields": [
                    "result",
                    "task_id",
                    "agent_id",
                    "trace_id",
                    "artifact_refs",
                    "events"
                ]
            }
        }
    }, ensure_ascii=False, indent=2))
    write(root / "StyleGuide.md", "# Kernel Style Guide\n\n```json\n" + json.dumps({
        "language_rules": {"python_version": ">=3.11", "type_hints": "required"},
        "format_rules": {"line_length": 100},
        "review_checkpoints": [
            "Kernel must remain business-agnostic",
            "Cross-agent coordination must happen through EventBus"
        ]
    }, ensure_ascii=False, indent=2) + "\n```\n")
    write(root / "TestTargets.yaml", json.dumps({
        "unit_test": {"command": "python -m unittest discover -s tests -v"},
        "integration_test": {"command": "python -m unittest discover -s tests -v"},
        "contract_test": {"command": "python -m agent_system_framework.spec_system.validate"}
    }, ensure_ascii=False, indent=2))
    return root


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
