from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agentsystem.agents.roadmap_1_6_artifacts import materialize_roadmap_1_6_story_artifacts


class RoadmapArtifactsTestCase(unittest.TestCase):
    def test_e2_001_materializer_writes_schema_and_clean_doc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            source_doc = (
                repo_root
                / "docs"
                / "需求文档"
                / "需求分析_1.6_最终版_事件参与者优先"
                / "8类参与者统一输出协议.md"
            )
            source_doc.parent.mkdir(parents=True, exist_ok=True)
            source_doc.write_text("# 8类参与者统一输出协议\n\n- participant_id\n", encoding="utf-8")

            updated = materialize_roadmap_1_6_story_artifacts(
                repo_root,
                {"story_id": "E2-001"},
                ["docs/需求文档/8类参与者统一输出协议.md", "apps/api/src/schemas/participant.py"],
            )

            self.assertIsNotNone(updated)
            schema_path = repo_root / "apps" / "api" / "src" / "schemas" / "participant.py"
            doc_path = repo_root / "docs" / "需求文档" / "8类参与者统一输出协议.md"
            self.assertTrue(schema_path.exists())
            self.assertTrue(doc_path.exists())
            schema_content = schema_path.read_text(encoding="utf-8")
            self.assertIn("class ParticipantOutput", schema_content)
            self.assertIn("insufficient_evidence", schema_content)
            self.assertNotEqual(schema_content.strip(), "from __future__ import annotations")
            self.assertEqual(doc_path.read_text(encoding="utf-8"), source_doc.read_text(encoding="utf-8"))

    def test_e2_003_materializer_writes_prepare_stack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            container_path = repo_root / "apps" / "api" / "src" / "services" / "container.py"
            container_path.parent.mkdir(parents=True, exist_ok=True)
            container_path.write_text(
                "\n".join(
                    [
                        "from __future__ import annotations",
                        "",
                        "from dataclasses import dataclass",
                        "from pathlib import Path",
                        "",
                        "from domain.event_casebook.service import EventCasebookService",
                        "from domain.event_ingestion.service import EventIngestionService",
                        "from domain.event_structuring.service import EventStructuringService",
                        "from domain.participant_preparation.registry import ParticipantRegistry",
                        "from domain.theme_mapping.service import ThemeMappingService",
                        "from settings.base import get_settings",
                        "",
                        "@dataclass(slots=True)",
                        "class ServiceContainer:",
                        "    event_ingestion: EventIngestionService",
                        "    event_structuring: EventStructuringService",
                        "    theme_mapping: ThemeMappingService",
                        "    event_casebook: EventCasebookService",
                        "    participant_registry: ParticipantRegistry",
                        "",
                        "def build_container() -> ServiceContainer:",
                        "    settings = get_settings()",
                        "    event_structuring = EventStructuringService(Path(settings.event_runtime_root))",
                        "    theme_mapping = ThemeMappingService(Path(settings.event_runtime_root))",
                        "    event_casebook = EventCasebookService(Path(settings.event_runtime_root))",
                        "    event_ingestion = EventIngestionService(",
                        "        runtime_root=Path(settings.event_runtime_root),",
                        "        structuring_service=event_structuring,",
                        "        theme_mapping_service=theme_mapping,",
                        "        casebook_service=event_casebook,",
                        "    )",
                        "    participant_registry = ParticipantRegistry()",
                        "    return ServiceContainer(",
                        "        event_ingestion=event_ingestion,",
                        "        event_structuring=event_structuring,",
                        "        theme_mapping=theme_mapping,",
                        "        event_casebook=event_casebook,",
                        "        participant_registry=participant_registry,",
                        "    )",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            routes_path = repo_root / "apps" / "api" / "src" / "api" / "command" / "routes.py"
            routes_path.parent.mkdir(parents=True, exist_ok=True)
            routes_path.write_text(
                "\n".join(
                    [
                        "from __future__ import annotations",
                        "",
                        "from dataclasses import asdict",
                        "",
                        "from domain.event_ingestion.service import EventIngestionError",
                        "from infra.http import APIRouter, JSONResponse",
                        "from services.container import ServiceContainer",
                        "",
                        "def build_command_router(container: ServiceContainer) -> APIRouter:",
                        "    router = APIRouter(tags=[\"command\"])",
                        "",
                        "    @router.post(\"/api/v1/events/{event_id}/prepare\")",
                        "    def prepare_event(event_id: str):",
                        "        try:",
                        "            return asdict(container.event_ingestion.prepare_event(event_id))",
                        "        except FileNotFoundError:",
                        "            return JSONResponse(",
                        "                status_code=404,",
                        "                content={",
                        "                    \"event_id\": event_id,",
                        "                    \"error_code\": \"EVENT_NOT_FOUND\",",
                        "                    \"error_message\": \"Event casebook not found.\",",
                        "                },",
                        "            )",
                        "",
                        "    return router",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            command_schema_path = repo_root / "apps" / "api" / "src" / "schemas" / "command.py"
            command_schema_path.parent.mkdir(parents=True, exist_ok=True)
            command_schema_path.write_text(
                "\n".join(
                    [
                        "from __future__ import annotations",
                        "",
                        "from dataclasses import dataclass",
                        "from typing import Any",
                        "",
                        "@dataclass(frozen=True, slots=True)",
                        "class EventPrepareResponse:",
                        "    event_id: str",
                        "    status: str",
                        "    casebook: dict[str, Any]",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            updated = materialize_roadmap_1_6_story_artifacts(repo_root, {"story_id": "E2-003"})

            self.assertIsNotNone(updated)
            service_path = repo_root / "apps" / "api" / "src" / "domain" / "participant_preparation" / "service.py"
            roster_schema_path = repo_root / "apps" / "api" / "src" / "schemas" / "participant_preparation.py"
            test_path = repo_root / "apps" / "api" / "tests" / "test_participant_preparation.py"
            delivery_path = repo_root / "docs" / "requirements" / "e2_003_delivery.md"
            self.assertTrue(service_path.exists())
            self.assertTrue(roster_schema_path.exists())
            self.assertTrue(test_path.exists())
            self.assertTrue(delivery_path.exists())
            self.assertIn("class ParticipantPreparationService", service_path.read_text(encoding="utf-8"))
            self.assertIn("class ParticipantRoster", roster_schema_path.read_text(encoding="utf-8"))
            self.assertIn("container.participant_preparation.prepare_event", routes_path.read_text(encoding="utf-8"))
            self.assertIn("participant_roster: dict[str, Any] | None = None", command_schema_path.read_text(encoding="utf-8"))
            self.assertIn("ParticipantPreparationService", container_path.read_text(encoding="utf-8"))

    def test_e2_005_materializer_writes_registry_defaults_stack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            routes_path = repo_root / "apps" / "api" / "src" / "api" / "command" / "routes.py"
            routes_path.parent.mkdir(parents=True, exist_ok=True)
            routes_path.write_text(
                "\n".join(
                    [
                        "from __future__ import annotations",
                        "",
                        "from infra.http import APIRouter, JSONResponse",
                        "from services.container import ServiceContainer",
                        "",
                        "def build_command_router(container: ServiceContainer) -> APIRouter:",
                        "    router = APIRouter(tags=[\"command\"])",
                        "",
                        "    return router",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            updated = materialize_roadmap_1_6_story_artifacts(repo_root, {"story_id": "E2-005"})

            self.assertIsNotNone(updated)
            registry_path = repo_root / "apps" / "api" / "src" / "domain" / "participant_preparation" / "registry.py"
            schema_path = repo_root / "apps" / "api" / "src" / "schemas" / "e2_005.py"
            test_path = repo_root / "apps" / "api" / "tests" / "test_e2_005.py"
            delivery_path = repo_root / "docs" / "requirements" / "e2_005_delivery.md"
            self.assertTrue(registry_path.exists())
            self.assertTrue(schema_path.exists())
            self.assertTrue(test_path.exists())
            self.assertTrue(delivery_path.exists())
            self.assertIn("class ParticipantRegistrySnapshot", schema_path.read_text(encoding="utf-8"))
            self.assertIn("def snapshot", registry_path.read_text(encoding="utf-8"))
            self.assertIn("/api/v1/participants/registry", routes_path.read_text(encoding="utf-8"))

    def test_e3_001_materializer_writes_belief_graph_stack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            container_path = repo_root / "apps" / "api" / "src" / "services" / "container.py"
            container_path.parent.mkdir(parents=True, exist_ok=True)
            container_path.write_text(
                "\n".join(
                    [
                        "from __future__ import annotations",
                        "",
                        "from dataclasses import dataclass",
                        "from domain.agent_registry.service import AgentRegistryService",
                        "from domain.participant_preparation.service import ParticipantPreparationService",
                        "",
                        "@dataclass(slots=True)",
                        "class ServiceContainer:",
                        "    participant_preparation: ParticipantPreparationService",
                        "",
                        "def build_container() -> ServiceContainer:",
                        "    participant_preparation = ParticipantPreparationService(",
                        "        casebook_service=event_casebook,",
                        "        participant_registry=participant_registry,",
                        "    )",
                        "    return ServiceContainer(",
                        "        participant_preparation=participant_preparation,",
                        "    )",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            routes_path = repo_root / "apps" / "api" / "src" / "api" / "command" / "routes.py"
            routes_path.parent.mkdir(parents=True, exist_ok=True)
            routes_path.write_text(
                "\n".join(
                    [
                        "from __future__ import annotations",
                        "",
                        "from dataclasses import asdict",
                        "",
                        "from domain.event_ingestion.service import EventIngestionError",
                        "from infra.http import APIRouter, JSONResponse",
                        "from services.container import ServiceContainer",
                        "",
                        "def build_command_router(container: ServiceContainer) -> APIRouter:",
                        "    router = APIRouter(tags=[\"command\"])",
                        "",
                        "    return router",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            updated = materialize_roadmap_1_6_story_artifacts(repo_root, {"story_id": "E3-001"})

            self.assertIsNotNone(updated)
            service_path = repo_root / "apps" / "api" / "src" / "domain" / "belief_graph" / "service.py"
            schema_path = repo_root / "apps" / "api" / "src" / "schemas" / "belief_graph.py"
            test_path = repo_root / "apps" / "api" / "tests" / "test_belief_graph.py"
            delivery_path = repo_root / "docs" / "requirements" / "e3_001_delivery.md"
            self.assertTrue(service_path.exists())
            self.assertTrue(schema_path.exists())
            self.assertTrue(test_path.exists())
            self.assertTrue(delivery_path.exists())
            self.assertIn("class BeliefGraphService", service_path.read_text(encoding="utf-8"))
            self.assertIn("class BeliefGraphSnapshot", schema_path.read_text(encoding="utf-8"))
            self.assertIn("/api/v1/events/{event_id}/belief-graph", routes_path.read_text(encoding="utf-8"))
            self.assertIn("belief_graph=belief_graph", container_path.read_text(encoding="utf-8"))

    def test_e3_003_materializer_writes_scenario_engine_stack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            container_path = repo_root / "apps" / "api" / "src" / "services" / "container.py"
            container_path.parent.mkdir(parents=True, exist_ok=True)
            container_path.write_text(
                "\n".join(
                    [
                        "from __future__ import annotations",
                        "",
                        "from dataclasses import dataclass",
                        "from domain.belief_graph.service import BeliefGraphService",
                        "from domain.simulation_ledger.service import SimulationLedgerService",
                        "",
                        "@dataclass(slots=True)",
                        "class ServiceContainer:",
                        "    belief_graph: BeliefGraphService",
                        "",
                        "def build_container() -> ServiceContainer:",
                        "    belief_graph = BeliefGraphService(participant_preparation=participant_preparation)",
                        "    return ServiceContainer(",
                        "        belief_graph=belief_graph,",
                        "    )",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            routes_path = repo_root / "apps" / "api" / "src" / "api" / "command" / "routes.py"
            routes_path.parent.mkdir(parents=True, exist_ok=True)
            routes_path.write_text(
                "\n".join(
                    [
                        "from __future__ import annotations",
                        "",
                        "from dataclasses import asdict",
                        "",
                        "from domain.participant_preparation.service import ParticipantPreparationError",
                        "from infra.http import APIRouter, JSONResponse",
                        "from services.container import ServiceContainer",
                        "",
                        "def build_command_router(container: ServiceContainer) -> APIRouter:",
                        "    router = APIRouter(tags=[\"command\"])",
                        "",
                        "    return router",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            updated = materialize_roadmap_1_6_story_artifacts(repo_root, {"story_id": "E3-003"})

            self.assertIsNotNone(updated)
            service_path = repo_root / "apps" / "api" / "src" / "domain" / "scenario_engine" / "service.py"
            scenario_schema_path = repo_root / "apps" / "api" / "src" / "schemas" / "scenario.py"
            engine_schema_path = repo_root / "apps" / "api" / "src" / "schemas" / "scenario_engine.py"
            test_path = repo_root / "apps" / "api" / "tests" / "test_scenario_engine.py"
            delivery_path = repo_root / "docs" / "requirements" / "e3_003_delivery.md"
            self.assertTrue(service_path.exists())
            self.assertTrue(scenario_schema_path.exists())
            self.assertTrue(engine_schema_path.exists())
            self.assertTrue(test_path.exists())
            self.assertTrue(delivery_path.exists())
            self.assertIn("class ScenarioEngineService", service_path.read_text(encoding="utf-8"))
            self.assertIn("class ScenarioEngineResult", engine_schema_path.read_text(encoding="utf-8"))
            self.assertIn("/api/v1/events/{event_id}/scenarios", routes_path.read_text(encoding="utf-8"))
            self.assertIn("scenario_engine=scenario_engine", container_path.read_text(encoding="utf-8"))

    def test_e3_005_materializer_writes_event_card_stack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"
            event_schema_path = repo_root / "apps" / "api" / "src" / "schemas" / "event.py"
            event_schema_path.parent.mkdir(parents=True, exist_ok=True)
            event_schema_path.write_text(
                "\n".join(
                    [
                        "from __future__ import annotations",
                        "",
                        "from dataclasses import asdict, dataclass, field",
                        "from typing import Any",
                        "",
                        "@dataclass(frozen=True, slots=True)",
                        "class EventRecord:",
                        "    event_id: str",
                        "    title: str",
                        "    body: str",
                        "    source: str",
                        "    event_time: str",
                        "",
                        "    def to_dict(self) -> dict[str, Any]:",
                        "        return asdict(self)",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            container_path = repo_root / "apps" / "api" / "src" / "services" / "container.py"
            container_path.parent.mkdir(parents=True, exist_ok=True)
            container_path.write_text(
                "\n".join(
                    [
                        "from __future__ import annotations",
                        "",
                        "from dataclasses import dataclass",
                        "from projection.agent_snapshots.service import AgentSnapshotProjection",
                        "",
                        "@dataclass(slots=True)",
                        "class ServiceContainer:",
                        "    panorama: object",
                        "",
                        "def build_container() -> ServiceContainer:",
                        "    scenario_engine = ScenarioEngineService(belief_graph=belief_graph)",
                        "    return ServiceContainer(",
                        "        panorama=PanoramaProjection(),",
                        "    )",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            query_routes_path = repo_root / "apps" / "api" / "src" / "api" / "query" / "routes.py"
            query_routes_path.parent.mkdir(parents=True, exist_ok=True)
            query_routes_path.write_text(
                "\n".join(
                    [
                        "from __future__ import annotations",
                        "",
                        "from infra.http import APIRouter",
                        "from services.container import ServiceContainer",
                        "",
                        "def build_query_router(container: ServiceContainer) -> APIRouter:",
                        "    router = APIRouter(tags=[\"query\"])",
                        "",
                        "    @router.get(\"/api/v1/statements/{statement_id}\")",
                        "    def statement_detail(statement_id: str):",
                        "        return {\"statement_id\": statement_id}",
                        "",
                        "    return router",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            updated = materialize_roadmap_1_6_story_artifacts(repo_root, {"story_id": "E3-005"})

            self.assertIsNotNone(updated)
            projection_path = repo_root / "apps" / "api" / "src" / "projection" / "event_cards" / "service.py"
            test_path = repo_root / "apps" / "api" / "tests" / "test_event_cards.py"
            delivery_path = repo_root / "docs" / "requirements" / "e3_005_delivery.md"
            self.assertTrue(projection_path.exists())
            self.assertTrue(test_path.exists())
            self.assertTrue(delivery_path.exists())
            self.assertIn("class EventCardReadModel", event_schema_path.read_text(encoding="utf-8"))
            self.assertIn("class EventCardProjectionService", projection_path.read_text(encoding="utf-8"))
            self.assertIn("/api/v1/events/{event_id}/card", query_routes_path.read_text(encoding="utf-8"))
            self.assertIn("event_cards=event_cards", container_path.read_text(encoding="utf-8"))

    def test_e4_001_materializer_writes_simulation_prepare_stack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "repo"

            settings_path = repo_root / "apps" / "api" / "src" / "settings" / "base.py"
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(
                "\n".join(
                    [
                        "from __future__ import annotations",
                        "",
                        "from dataclasses import dataclass",
                        "import os",
                        "from pathlib import Path",
                        "",
                        "REPO_ROOT = Path(__file__).resolve().parents[4]",
                        "",
                        "@dataclass(frozen=True, slots=True)",
                        "class Settings:",
                        '    event_runtime_root: str = str(REPO_ROOT / ".runtime" / "events")',
                        "",
                        "def get_settings() -> Settings:",
                        "    return Settings(",
                        '        event_runtime_root=os.getenv("EVENT_RUNTIME_ROOT", str(REPO_ROOT / ".runtime" / "events")),',
                        "    )",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            container_path = repo_root / "apps" / "api" / "src" / "services" / "container.py"
            container_path.parent.mkdir(parents=True, exist_ok=True)
            container_path.write_text(
                "\n".join(
                    [
                        "from __future__ import annotations",
                        "",
                        "from dataclasses import dataclass",
                        "from pathlib import Path",
                        "",
                        "from domain.event_casebook.service import EventCasebookService",
                        "from domain.event_structuring.service import EventStructuringService",
                        "from domain.belief_graph.service import BeliefGraphService",
                        "from domain.scenario_engine.service import ScenarioEngineService",
                        "from settings.base import get_settings",
                        "",
                        "@dataclass(slots=True)",
                        "class ServiceContainer:",
                        "    event_casebook: EventCasebookService",
                        "    scenario_engine: ScenarioEngineService",
                        "",
                        "def build_container() -> ServiceContainer:",
                        "    settings = get_settings()",
                        "    event_casebook = EventCasebookService(Path(settings.event_runtime_root))",
                        "    belief_graph = BeliefGraphService(participant_preparation=participant_preparation)",
                        "    scenario_engine = ScenarioEngineService(belief_graph=belief_graph)",
                        "    return ServiceContainer(",
                        "        event_casebook=event_casebook,",
                        "        scenario_engine=scenario_engine,",
                        "    )",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            routes_path = repo_root / "apps" / "api" / "src" / "api" / "command" / "routes.py"
            routes_path.parent.mkdir(parents=True, exist_ok=True)
            routes_path.write_text(
                "\n".join(
                    [
                        "from __future__ import annotations",
                        "",
                        "from dataclasses import asdict",
                        "",
                        "from domain.event_ingestion.service import EventIngestionError",
                        "from infra.http import APIRouter, JSONResponse",
                        "from services.container import ServiceContainer",
                        "",
                        "def build_command_router(container: ServiceContainer) -> APIRouter:",
                        "    router = APIRouter(tags=[\"command\"])",
                        "",
                        "    return router",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            updated = materialize_roadmap_1_6_story_artifacts(repo_root, {"story_id": "E4-001"})

            self.assertIsNotNone(updated)
            service_path = repo_root / "apps" / "api" / "src" / "domain" / "event_simulation" / "service.py"
            schema_path = repo_root / "apps" / "api" / "src" / "schemas" / "simulation.py"
            test_path = repo_root / "apps" / "api" / "tests" / "test_event_simulation.py"
            delivery_path = repo_root / "docs" / "requirements" / "e4_001_delivery.md"
            self.assertTrue(service_path.exists())
            self.assertTrue(schema_path.exists())
            self.assertTrue(test_path.exists())
            self.assertTrue(delivery_path.exists())
            self.assertIn("class EventSimulationService", service_path.read_text(encoding="utf-8"))
            self.assertIn("class SimulationRun", schema_path.read_text(encoding="utf-8"))
            self.assertIn("/api/v1/events/{event_id}/simulation/prepare", routes_path.read_text(encoding="utf-8"))
            container_content = container_path.read_text(encoding="utf-8")
            self.assertIn("event_simulation=event_simulation", container_content)
            self.assertEqual(container_content.count("event_simulation=event_simulation"), 1)
            self.assertIn("simulation_runtime_root", settings_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
