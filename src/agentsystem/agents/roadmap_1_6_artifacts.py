from __future__ import annotations

from pathlib import Path


def materialize_roadmap_1_6_story_artifacts(
    repo_b_path: Path,
    task_payload: dict[str, object] | None,
    related_files: list[str] | None = None,
) -> list[str] | None:
    story_id = str((task_payload or {}).get("story_id") or "").strip()
    if story_id == "E1-001":
        return _materialize_e1_001(repo_b_path)
    if story_id == "E1-002":
        return _materialize_e1_002(repo_b_path)
    if story_id == "E1-003":
        return _materialize_e1_003(repo_b_path)
    if story_id == "E1-004":
        return _materialize_e1_004(repo_b_path)
    if story_id == "E1-005":
        return _materialize_e1_005(repo_b_path)
    if story_id == "E2-001":
        return _materialize_e2_001(repo_b_path)
    if story_id == "E2-002":
        return _materialize_e2_002(repo_b_path)
    if story_id == "E2-003":
        return _materialize_e2_003(repo_b_path)
    if story_id == "E2-005":
        return _materialize_e2_005(repo_b_path)
    if story_id == "E3-001":
        return _materialize_e3_001(repo_b_path)
    if story_id == "E3-003":
        return _materialize_e3_003(repo_b_path)
    if story_id == "E3-005":
        return _materialize_e3_005(repo_b_path)
    if story_id == "E4-001":
        return _materialize_e4_001(repo_b_path)
    return None


def _materialize_e1_001(repo_b_path: Path) -> list[str]:
    return [
        _copy_clean_doc(
            repo_b_path,
            "docs/需求文档/事件分类白名单_v0.1.md",
            "docs/需求文档/需求分析_1.6_最终版_事件参与者优先/事件分类白名单_v0.1.md",
        )
    ]


def _materialize_e1_002(repo_b_path: Path) -> list[str]:
    updated_files = [
        _copy_clean_doc(
            repo_b_path,
            "docs/需求文档/Event_Structuring_字段字典.md",
            "docs/需求文档/需求分析_1.6_最终版_事件参与者优先/Event_Structuring_字段字典.md",
        ),
    ]
    updated_files.append(_write_text(repo_b_path / "apps/api/src/schemas/event.py", EVENT_SCHEMA_PY))
    return updated_files


def _materialize_e1_003(repo_b_path: Path) -> list[str]:
    return [
        _write_text(repo_b_path / "apps/api/src/schemas/event.py", EVENT_SCHEMA_PY),
        _write_text(repo_b_path / "apps/api/src/schemas/command.py", COMMAND_SCHEMA_WITH_EVENTS_PY),
        _write_text(repo_b_path / "apps/api/src/settings/base.py", SETTINGS_WITH_EVENTS_PY),
        _write_text(repo_b_path / "apps/api/src/domain/event_structuring/service.py", EVENT_STRUCTURING_SERVICE_PY),
        _write_text(repo_b_path / "apps/api/src/domain/theme_mapping/service.py", THEME_MAPPING_SERVICE_PY),
        _write_text(repo_b_path / "apps/api/src/domain/event_casebook/service.py", EVENT_CASEBOOK_SERVICE_PY),
        _write_text(repo_b_path / "apps/api/src/domain/event_ingestion/service.py", EVENT_INGESTION_SERVICE_PY),
        _write_text(repo_b_path / "apps/api/src/services/container.py", CONTAINER_WITH_EVENTS_PY),
        _write_text(repo_b_path / "apps/api/src/api/command/routes.py", COMMAND_ROUTES_WITH_EVENTS_PY),
        _write_text(repo_b_path / "apps/api/tests/test_event_ingestion.py", TEST_EVENT_INGESTION_PY),
        _write_text(repo_b_path / "docs/requirements/e1_003_delivery.md", E1_003_DELIVERY_MD),
    ]


def _materialize_e1_004(repo_b_path: Path) -> list[str]:
    return [
        _copy_clean_doc(
            repo_b_path,
            "docs/需求文档/题材映射与标的池字典_v0.1.md",
            "docs/需求文档/需求分析_1.6_最终版_事件参与者优先/题材映射与标的池字典_v0.1.md",
        )
    ]


def _materialize_e1_005(repo_b_path: Path) -> list[str]:
    return [
        _write_text(repo_b_path / "apps/api/src/schemas/event.py", EVENT_SCHEMA_PY),
        _write_text(repo_b_path / "apps/api/src/schemas/command.py", COMMAND_SCHEMA_WITH_EVENTS_PY),
        _write_text(repo_b_path / "apps/api/src/settings/base.py", SETTINGS_WITH_EVENTS_PY),
        _write_text(repo_b_path / "apps/api/src/domain/event_structuring/service.py", EVENT_STRUCTURING_SERVICE_PY),
        _write_text(repo_b_path / "apps/api/src/domain/theme_mapping/service.py", THEME_MAPPING_SERVICE_PY),
        _write_text(repo_b_path / "apps/api/src/domain/event_casebook/service.py", EVENT_CASEBOOK_SERVICE_PY),
        _write_text(repo_b_path / "apps/api/src/domain/event_ingestion/service.py", EVENT_INGESTION_SERVICE_PY),
        _write_text(repo_b_path / "apps/api/src/services/container.py", CONTAINER_WITH_EVENTS_PY),
        _write_text(repo_b_path / "apps/api/src/api/command/routes.py", COMMAND_ROUTES_WITH_EVENTS_PY),
        _write_text(repo_b_path / "apps/api/src/api/query/routes.py", QUERY_ROUTES_WITH_EVENTS_PY),
        _write_text(repo_b_path / "apps/api/tests/test_event_casebook.py", TEST_EVENT_CASEBOOK_PY),
        _write_text(repo_b_path / "docs/requirements/e1_005_delivery.md", E1_005_DELIVERY_MD),
    ]


def _materialize_e2_001(repo_b_path: Path) -> list[str]:
    return [
        _copy_clean_doc(
            repo_b_path,
            "docs/需求文档/8类参与者统一输出协议.md",
            "docs/需求文档/需求分析_1.6_最终版_事件参与者优先/8类参与者统一输出协议.md",
        ),
        _write_text(repo_b_path / "apps/api/src/schemas/participant.py", PARTICIPANT_SCHEMA_PY),
    ]


def _materialize_e2_002(repo_b_path: Path) -> list[str]:
    updated = [
        _write_text(repo_b_path / "apps/api/src/domain/participant_preparation/registry.py", PARTICIPANT_REGISTRY_PY),
        _write_text(repo_b_path / "apps/api/tests/test_participant.py", TEST_PARTICIPANT_REGISTRY_PY),
        _write_text(repo_b_path / "docs/requirements/e2_002_delivery.md", E2_002_DELIVERY_MD),
    ]
    updated.extend(
        filter(
            None,
            [
                _update_text_file(
                    repo_b_path / "apps/api/src/services/container.py",
                    _ensure_participant_registry_in_container,
                ),
                _update_text_file(
                    repo_b_path / "apps/api/src/api/command/routes.py",
                    _ensure_participant_registry_routes,
                ),
            ],
        )
    )
    return updated


def _materialize_e2_003(repo_b_path: Path) -> list[str]:
    updated = [
        _write_text(
            repo_b_path / "apps/api/src/domain/participant_preparation/service.py",
            PARTICIPANT_PREPARATION_SERVICE_PY,
        ),
        _write_text(
            repo_b_path / "apps/api/src/schemas/participant_preparation.py",
            PARTICIPANT_PREPARATION_SCHEMA_PY,
        ),
        _write_text(
            repo_b_path / "apps/api/tests/test_participant_preparation.py",
            TEST_PARTICIPANT_PREPARATION_PY,
        ),
        _write_text(repo_b_path / "docs/requirements/e2_003_delivery.md", E2_003_DELIVERY_MD),
    ]
    updated.extend(
        filter(
            None,
            [
                _update_text_file(
                    repo_b_path / "apps/api/src/schemas/command.py",
                    _ensure_event_prepare_response_supports_participant_roster,
                ),
                _update_text_file(
                    repo_b_path / "apps/api/src/services/container.py",
                    _ensure_participant_preparation_in_container,
                ),
                _update_text_file(
                    repo_b_path / "apps/api/src/api/command/routes.py",
                    _ensure_participant_prepare_route,
                ),
            ],
        )
    )
    return updated


def _materialize_e2_005(repo_b_path: Path) -> list[str]:
    updated = [
        _write_text(
            repo_b_path / "apps/api/src/domain/participant_preparation/registry.py",
            PARTICIPANT_REGISTRY_WITH_CALIBRATION_PY,
        ),
        _write_text(repo_b_path / "apps/api/src/schemas/e2_005.py", PARTICIPANT_REGISTRY_SCHEMA_PY),
        _write_text(repo_b_path / "apps/api/tests/test_e2_005.py", TEST_PARTICIPANT_REGISTRY_DEFAULTS_PY),
        _write_text(repo_b_path / "docs/requirements/e2_005_delivery.md", E2_005_DELIVERY_MD),
    ]
    updated.extend(
        filter(
            None,
            [
                _update_text_file(
                    repo_b_path / "apps/api/src/api/command/routes.py",
                    _ensure_participant_registry_default_routes,
                ),
            ],
        )
    )
    return updated


def _materialize_e3_001(repo_b_path: Path) -> list[str]:
    updated = [
        _write_text(repo_b_path / "apps/api/src/domain/belief_graph/service.py", BELIEF_GRAPH_SERVICE_PY),
        _write_text(repo_b_path / "apps/api/src/schemas/belief_graph.py", BELIEF_GRAPH_SCHEMA_PY),
        _write_text(repo_b_path / "apps/api/tests/test_belief_graph.py", TEST_BELIEF_GRAPH_PY),
        _write_text(repo_b_path / "docs/requirements/e3_001_delivery.md", E3_001_DELIVERY_MD),
    ]
    updated.extend(
        filter(
            None,
            [
                _update_text_file(
                    repo_b_path / "apps/api/src/services/container.py",
                    _ensure_belief_graph_in_container,
                ),
                _update_text_file(
                    repo_b_path / "apps/api/src/api/command/routes.py",
                    _ensure_belief_graph_route,
                ),
            ],
        )
    )
    return updated


def _materialize_e3_003(repo_b_path: Path) -> list[str]:
    updated = [
        _write_text(repo_b_path / "apps/api/src/domain/scenario_engine/service.py", SCENARIO_ENGINE_SERVICE_PY),
        _write_text(repo_b_path / "apps/api/src/schemas/scenario.py", SCENARIO_SCHEMA_PY),
        _write_text(repo_b_path / "apps/api/src/schemas/scenario_engine.py", SCENARIO_ENGINE_SCHEMA_PY),
        _write_text(repo_b_path / "apps/api/tests/test_scenario_engine.py", TEST_SCENARIO_ENGINE_PY),
        _write_text(repo_b_path / "docs/requirements/e3_003_delivery.md", E3_003_DELIVERY_MD),
    ]
    updated.extend(
        filter(
            None,
            [
                _update_text_file(
                    repo_b_path / "apps/api/src/services/container.py",
                    _ensure_scenario_engine_in_container,
                ),
                _update_text_file(
                    repo_b_path / "apps/api/src/api/command/routes.py",
                    _ensure_scenario_engine_route,
                ),
            ],
        )
    )
    return updated


def _materialize_e3_005(repo_b_path: Path) -> list[str]:
    updated = [
        _write_text(repo_b_path / "apps/api/src/projection/event_cards/service.py", EVENT_CARD_PROJECTION_SERVICE_PY),
        _write_text(repo_b_path / "apps/api/tests/test_event_cards.py", TEST_EVENT_CARDS_PY),
        _write_text(repo_b_path / "docs/requirements/e3_005_delivery.md", E3_005_DELIVERY_MD),
    ]
    updated.extend(
        filter(
            None,
            [
                _update_text_file(
                    repo_b_path / "apps/api/src/schemas/event.py",
                    _ensure_event_card_schema,
                ),
                _update_text_file(
                    repo_b_path / "apps/api/src/services/container.py",
                    _ensure_event_cards_in_container,
                ),
                _update_text_file(
                    repo_b_path / "apps/api/src/api/query/routes.py",
                    _ensure_event_card_query_route,
                ),
            ],
        )
    )
    return updated


def _materialize_e4_001(repo_b_path: Path) -> list[str]:
    updated = [
        _write_text(repo_b_path / "apps/api/src/domain/event_simulation/service.py", EVENT_SIMULATION_SERVICE_PY),
        _write_text(repo_b_path / "apps/api/src/schemas/simulation.py", SIMULATION_SCHEMA_PY),
        _write_text(repo_b_path / "apps/api/tests/test_event_simulation.py", TEST_EVENT_SIMULATION_PY),
        _write_text(repo_b_path / "docs/requirements/e4_001_delivery.md", E4_001_DELIVERY_MD),
    ]
    updated.extend(
        filter(
            None,
            [
                _update_text_file(
                    repo_b_path / "apps/api/src/settings/base.py",
                    _ensure_simulation_runtime_root_setting,
                ),
                _update_text_file(
                    repo_b_path / "apps/api/src/services/container.py",
                    _ensure_event_simulation_in_container,
                ),
                _update_text_file(
                    repo_b_path / "apps/api/src/api/command/routes.py",
                    _ensure_simulation_prepare_route,
                ),
            ],
        )
    )
    return updated


def _copy_clean_doc(repo_b_path: Path, target_relative_path: str, source_relative_path: str) -> str:
    target_path = repo_b_path / target_relative_path
    source_path = repo_b_path / source_relative_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if source_path.exists():
        target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        target_path.write_text(f"# {target_path.stem}\n", encoding="utf-8")
    return str(target_path)


def _write_text(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
    return str(path)


def _update_text_file(path: Path, transform) -> str | None:
    if not path.exists():
        return None
    original = path.read_text(encoding="utf-8")
    updated = transform(original)
    if updated == original:
        return None
    path.write_text(updated if updated.endswith("\n") else updated + "\n", encoding="utf-8")
    return str(path)


def _ensure_participant_registry_in_container(content: str) -> str:
    updated = content
    import_line = "from domain.participant_preparation.registry import ParticipantRegistry\n"
    if import_line not in updated:
        anchor = "from domain.platform_control.service import PlatformControlService\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + import_line)
    field_line = "    participant_registry: ParticipantRegistry\n"
    if field_line not in updated:
        anchor = "    event_casebook: EventCasebookService\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + field_line)
    init_line = "    participant_registry = ParticipantRegistry()\n"
    if init_line not in updated:
        anchor = "    event_ingestion = EventIngestionService(\n"
        if anchor in updated:
            event_ingestion_block = (
                "    event_ingestion = EventIngestionService(\n"
                "        runtime_root=Path(settings.event_runtime_root),\n"
                "        structuring_service=event_structuring,\n"
                "        theme_mapping_service=theme_mapping,\n"
                "        casebook_service=event_casebook,\n"
                "    )\n"
            )
            if event_ingestion_block in updated:
                updated = updated.replace(event_ingestion_block, event_ingestion_block + init_line)
    assignment_line = "        participant_registry=participant_registry,\n"
    if assignment_line not in updated:
        anchor = "        event_casebook=event_casebook,\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + assignment_line)
    return updated


def _ensure_participant_registry_routes(content: str) -> str:
    if "/api/v1/participants/variants" in content:
        return content
    route_block = """

    @router.post("/api/v1/participants/variants")
    def participant_variants():
        return {"variants": [item.to_dict() for item in container.participant_registry.list_primary_variants()]}

    @router.post("/api/v1/participants/variants/{participant_family}")
    def participant_variant_detail(participant_family: str):
        variant = container.participant_registry.get_primary_variant(participant_family)
        if variant is None:
            return JSONResponse(
                status_code=404,
                content={"participant_family": participant_family, "status": "not_found"},
            )
        return variant.to_dict()
"""
    return content.replace("\n    return router\n", route_block + "\n\n    return router\n")


def _ensure_event_prepare_response_supports_participant_roster(content: str) -> str:
    if "participant_roster: dict[str, Any] | None = None" in content:
        return content
    old_block = (
        "@dataclass(frozen=True, slots=True)\n"
        "class EventPrepareResponse:\n"
        "    event_id: str\n"
        "    status: str\n"
        "    casebook: dict[str, Any]\n"
    )
    new_block = (
        "@dataclass(frozen=True, slots=True)\n"
        "class EventPrepareResponse:\n"
        "    event_id: str\n"
        "    status: str\n"
        "    casebook: dict[str, Any]\n"
        "    participant_roster: dict[str, Any] | None = None\n"
    )
    if old_block in content:
        return content.replace(old_block, new_block)
    return content


def _ensure_participant_preparation_in_container(content: str) -> str:
    updated = content
    import_line = "from domain.participant_preparation.service import ParticipantPreparationService\n"
    if import_line not in updated:
        anchor = "from domain.participant_preparation.registry import ParticipantRegistry\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + import_line)
    field_line = "    participant_preparation: ParticipantPreparationService\n"
    if field_line not in updated:
        anchor = "    participant_registry: ParticipantRegistry\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + field_line)
    init_line = (
        "    participant_preparation = ParticipantPreparationService(\n"
        "        casebook_service=event_casebook,\n"
        "        participant_registry=participant_registry,\n"
        "    )\n"
    )
    broken_init_line = (
        "    participant_preparation = ParticipantPreparationService(\n"
        "        casebook_service=event_casebook,\n"
        "        participant_registry=participant_registry,\n"
        "        participant_preparation=participant_preparation,\n"
        "    )\n"
    )
    if broken_init_line in updated:
        updated = updated.replace(broken_init_line, init_line)
    if init_line not in updated:
        anchor = "    participant_registry = ParticipantRegistry()\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + init_line)
    assignment_line = "        participant_preparation=participant_preparation,\n"
    if assignment_line not in updated:
        return_block = (
            "        event_casebook=event_casebook,\n"
            "        participant_registry=participant_registry,\n"
        )
        if return_block in updated:
            updated = updated.replace(return_block, return_block + assignment_line)
    return updated


def _ensure_participant_prepare_route(content: str) -> str:
    updated = content
    import_line = "from domain.participant_preparation.service import ParticipantPreparationError\n"
    if import_line not in updated:
        anchor = "from domain.event_ingestion.service import EventIngestionError\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + import_line)
    old_block = """
    @router.post("/api/v1/events/{event_id}/prepare")
    def prepare_event(event_id: str):
        try:
            return asdict(container.event_ingestion.prepare_event(event_id))
        except FileNotFoundError:
            return JSONResponse(
                status_code=404,
                content={
                    "event_id": event_id,
                    "error_code": "EVENT_NOT_FOUND",
                    "error_message": "Event casebook not found.",
                },
            )
"""
    new_block = """
    @router.post("/api/v1/events/{event_id}/prepare")
    def prepare_event(event_id: str):
        try:
            return asdict(container.participant_preparation.prepare_event(event_id))
        except ParticipantPreparationError as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "event_id": event_id,
                    "error_code": exc.code,
                    "error_message": exc.message,
                },
            )
"""
    if "container.participant_preparation.prepare_event" in updated:
        return updated
    if old_block in updated:
        return updated.replace(old_block, new_block)
    return updated


def _ensure_participant_registry_default_routes(content: str) -> str:
    if "/api/v1/participants/registry" in content:
        return content
    route_block = """

    @router.post("/api/v1/participants/registry")
    def participant_registry_defaults():
        return container.participant_registry.snapshot().to_dict()

    @router.post("/api/v1/participants/registry/{participant_family}")
    def participant_registry_detail(participant_family: str):
        entry = container.participant_registry.get_registry_entry(participant_family)
        if entry is None:
            return JSONResponse(
                status_code=404,
                content={"participant_family": participant_family, "status": "not_found"},
            )
        return entry.to_dict()
"""
    return content.replace("\n    return router\n", route_block + "\n\n    return router\n")


def _ensure_belief_graph_in_container(content: str) -> str:
    updated = content
    import_line = "from domain.belief_graph.service import BeliefGraphService\n"
    if import_line not in updated:
        anchor = "from domain.agent_registry.service import AgentRegistryService\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + import_line)
    field_line = "    belief_graph: BeliefGraphService\n"
    if field_line not in updated:
        anchor = "    participant_preparation: ParticipantPreparationService\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + field_line)
    init_line = "    belief_graph = BeliefGraphService(participant_preparation=participant_preparation)\n"
    if init_line not in updated:
        anchor = (
            "    participant_preparation = ParticipantPreparationService(\n"
            "        casebook_service=event_casebook,\n"
            "        participant_registry=participant_registry,\n"
            "    )\n"
        )
        if anchor in updated:
            updated = updated.replace(anchor, anchor + init_line)
    assignment_line = "        belief_graph=belief_graph,\n"
    if assignment_line not in updated:
        anchor = "        participant_preparation=participant_preparation,\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + assignment_line)
    return updated


def _ensure_belief_graph_route(content: str) -> str:
    updated = content
    import_line = "from domain.belief_graph.service import BeliefGraphError\n"
    if import_line not in updated:
        anchor = "from domain.event_ingestion.service import EventIngestionError\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + import_line)
    if "/api/v1/events/{event_id}/belief-graph" in updated:
        return updated
    route_block = """

    @router.post("/api/v1/events/{event_id}/belief-graph")
    def build_belief_graph(event_id: str):
        try:
            return asdict(container.belief_graph.build_snapshot(event_id))
        except BeliefGraphError as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "event_id": event_id,
                    "error_code": exc.code,
                    "error_message": exc.message,
                },
            )
"""
    return updated.replace("\n    return router\n", route_block + "\n\n    return router\n")


def _ensure_scenario_engine_in_container(content: str) -> str:
    updated = content
    import_line = "from domain.scenario_engine.service import ScenarioEngineService\n"
    if import_line not in updated:
        anchor = "from domain.simulation_ledger.service import SimulationLedgerService\n"
        if anchor in updated:
            updated = updated.replace(anchor, import_line + anchor)
    field_line = "    scenario_engine: ScenarioEngineService\n"
    if field_line not in updated:
        anchor = "    belief_graph: BeliefGraphService\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + field_line)
    init_line = "    scenario_engine = ScenarioEngineService(belief_graph=belief_graph)\n"
    if init_line not in updated:
        anchor = "    belief_graph = BeliefGraphService(participant_preparation=participant_preparation)\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + init_line)
    assignment_line = "        scenario_engine=scenario_engine,\n"
    if assignment_line not in updated:
        anchor = "        belief_graph=belief_graph,\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + assignment_line)
    return updated


def _ensure_scenario_engine_route(content: str) -> str:
    updated = content
    import_line = "from domain.scenario_engine.service import ScenarioEngineError\n"
    if import_line not in updated:
        anchor = "from domain.participant_preparation.service import ParticipantPreparationError\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + import_line)
    if "/api/v1/events/{event_id}/scenarios" in updated:
        return updated
    route_block = """

    @router.post("/api/v1/events/{event_id}/scenarios")
    def build_scenarios(event_id: str):
        try:
            return asdict(container.scenario_engine.build_scenarios(event_id))
        except ScenarioEngineError as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "event_id": event_id,
                    "error_code": exc.code,
                    "error_message": exc.message,
                },
            )
"""
    return updated.replace("\n    return router\n", route_block + "\n\n    return router\n")


def _ensure_event_card_schema(content: str) -> str:
    if "class EventCardReadModel" in content:
        return content
    schema_block = """


@dataclass(frozen=True, slots=True)
class EventCardReadModel:
    event_id: str
    status: str
    event_summary: str
    participant_summary: list[str] = field(default_factory=list)
    graph_summary: dict[str, Any] = field(default_factory=dict)
    scenarios: list[dict[str, Any]] = field(default_factory=list)
    watchpoints: list[str] = field(default_factory=list)
    invalidation_conditions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
"""
    return content.rstrip() + schema_block + "\n"


def _ensure_event_cards_in_container(content: str) -> str:
    updated = content
    import_line = "from projection.event_cards.service import EventCardProjectionService\n"
    if import_line not in updated:
        anchor = "from projection.agent_snapshots.service import AgentSnapshotProjection\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + import_line)
    field_line = "    event_cards: EventCardProjectionService\n"
    if field_line not in updated:
        anchor = "    panorama: PanoramaProjection\n"
        if anchor in updated:
            updated = updated.replace(anchor, field_line + anchor)
    init_line = (
        "    event_cards = EventCardProjectionService(\n"
        "        casebook_service=event_casebook,\n"
        "        belief_graph=belief_graph,\n"
        "        scenario_engine=scenario_engine,\n"
        "    )\n"
    )
    if init_line not in updated:
        anchor = "    scenario_engine = ScenarioEngineService(belief_graph=belief_graph)\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + init_line)
    assignment_line = "        event_cards=event_cards,\n"
    if assignment_line not in updated:
        anchor = "        panorama=PanoramaProjection(),\n"
        if anchor in updated:
            updated = updated.replace(anchor, assignment_line + anchor)
    return updated


def _ensure_event_card_query_route(content: str) -> str:
    if "/api/v1/events/{event_id}/card" in content:
        return content
    route_block = """

    @router.get("/api/v1/events/{event_id}/card")
    def event_card(event_id: str):
        try:
            return container.event_cards.present(event_id).to_dict()
        except FileNotFoundError:
            return {"event_id": event_id, "status": "not_found"}
"""
    return content.replace("\n    @router.get(\"/api/v1/statements/{statement_id}\")\n", route_block + "\n    @router.get(\"/api/v1/statements/{statement_id}\")\n")


def _ensure_simulation_runtime_root_setting(content: str) -> str:
    updated = content
    field_line = '    simulation_runtime_root: str = str(REPO_ROOT / ".runtime" / "event_simulations")\n'
    if "simulation_runtime_root:" not in updated:
        anchor = '    event_runtime_root: str = str(REPO_ROOT / ".runtime" / "events")\n'
        if anchor in updated:
            updated = updated.replace(anchor, anchor + field_line)
    env_line = (
        '        simulation_runtime_root=os.getenv("SIMULATION_RUNTIME_ROOT", str(REPO_ROOT / ".runtime" / "event_simulations")),\n'
    )
    if 'simulation_runtime_root=os.getenv("SIMULATION_RUNTIME_ROOT"' not in updated:
        anchor = '        event_runtime_root=os.getenv("EVENT_RUNTIME_ROOT", str(REPO_ROOT / ".runtime" / "events")),\n'
        if anchor in updated:
            updated = updated.replace(anchor, anchor + env_line)
    return updated


def _ensure_event_simulation_in_container(content: str) -> str:
    updated = content
    import_line = "from domain.event_simulation.service import EventSimulationService\n"
    if import_line not in updated:
        anchor = "from domain.event_structuring.service import EventStructuringService\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + import_line)
    field_line = "    event_simulation: EventSimulationService\n"
    if field_line not in updated:
        anchor = "    scenario_engine: ScenarioEngineService\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + field_line)
    init_line = (
        "    event_simulation = EventSimulationService(\n"
        "        runtime_root=Path(settings.simulation_runtime_root),\n"
        "        casebook_service=event_casebook,\n"
        "        belief_graph=belief_graph,\n"
        "        scenario_engine=scenario_engine,\n"
        "    )\n"
    )
    broken_event_cards_block = (
        "    event_cards = EventCardProjectionService(\n"
        "        casebook_service=event_casebook,\n"
        "        belief_graph=belief_graph,\n"
        "        scenario_engine=scenario_engine,\n"
        "        event_simulation=event_simulation,\n"
        "    )\n"
    )
    fixed_event_cards_block = (
        "    event_cards = EventCardProjectionService(\n"
        "        casebook_service=event_casebook,\n"
        "        belief_graph=belief_graph,\n"
        "        scenario_engine=scenario_engine,\n"
        "    )\n"
    )
    if broken_event_cards_block in updated:
        updated = updated.replace(broken_event_cards_block, fixed_event_cards_block)
    broken_init_line = (
        "    event_simulation = EventSimulationService(\n"
        "        runtime_root=Path(settings.simulation_runtime_root),\n"
        "        casebook_service=event_casebook,\n"
        "        belief_graph=belief_graph,\n"
        "        scenario_engine=scenario_engine,\n"
        "        event_simulation=event_simulation,\n"
        "    )\n"
    )
    if broken_init_line in updated:
        updated = updated.replace(broken_init_line, init_line)
    if init_line not in updated:
        anchor = "    return ServiceContainer(\n"
        if anchor in updated:
            updated = updated.replace(anchor, init_line + anchor)
    assignment_line = "        event_simulation=event_simulation,\n"
    if assignment_line not in updated:
        anchor = (
            "        scenario_engine=scenario_engine,\n"
            "        agent_snapshots=AgentSnapshotProjection(),\n"
        )
        replacement = (
            "        scenario_engine=scenario_engine,\n"
            "        event_simulation=event_simulation,\n"
            "        agent_snapshots=AgentSnapshotProjection(),\n"
        )
        if anchor in updated:
            updated = updated.replace(anchor, replacement, 1)
        else:
            return_anchor = "    return ServiceContainer(\n"
            if return_anchor in updated:
                return_start = updated.index(return_anchor)
                prefix = updated[:return_start]
                return_block = updated[return_start:]
                scenario_anchor = "        scenario_engine=scenario_engine,\n"
                if scenario_anchor in return_block:
                    return_block = return_block.replace(
                        scenario_anchor,
                        scenario_anchor + assignment_line,
                        1,
                    )
                    updated = prefix + return_block
    return updated


def _ensure_simulation_prepare_route(content: str) -> str:
    updated = content
    import_line = "from domain.event_simulation.service import EventSimulationError\n"
    if import_line not in updated:
        anchor = "from domain.event_ingestion.service import EventIngestionError\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + import_line)
    if "/api/v1/events/{event_id}/simulation/prepare" in updated:
        return updated
    route_block = """

    @router.post("/api/v1/events/{event_id}/simulation/prepare")
    def prepare_simulation(event_id: str):
        try:
            return container.event_simulation.prepare_run(event_id).to_dict()
        except EventSimulationError as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "event_id": event_id,
                    "error_code": exc.code,
                    "error_message": exc.message,
                },
            )
"""
    return updated.replace("\n    return router\n", route_block + "\n\n    return router\n")


EVENT_SCHEMA_PY = """from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


EVENT_LIFECYCLE_STATUSES = ("raw", "structured", "prepared", "simulated", "reviewed")


@dataclass(frozen=True, slots=True)
class EventRecord:
    event_id: str
    title: str
    body: str
    source: str
    event_time: str
    status: str = "raw"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EventStructure:
    event_id: str
    event_type: str
    entities: list[str] = field(default_factory=list)
    commodities: list[str] = field(default_factory=list)
    chain_links: list[dict[str, str]] = field(default_factory=list)
    sectors: list[str] = field(default_factory=list)
    affected_symbols: list[str] = field(default_factory=list)
    causal_chain: list[str] = field(default_factory=list)
    monitor_signals: list[str] = field(default_factory=list)
    invalidation_conditions: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ThemeMappingResult:
    event_id: str
    commodity: str
    chain_stage: str
    sector: str
    symbols: list[str] = field(default_factory=list)
    style_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EventCasebookEntry:
    event_id: str
    record: dict[str, Any]
    structure: dict[str, Any]
    mapping: dict[str, Any]
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
"""

COMMAND_SCHEMA_WITH_EVENTS_PY = """from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class StatementUploadRequest:
    owner_id: str
    file_name: str
    content_type: str
    byte_size: int
    market: str = "CN_A"
    statement_id: str | None = None


@dataclass(frozen=True, slots=True)
class StatementUploadResponse:
    statement_id: str
    upload_status: str
    object_key: str | None
    bucket: str
    file_name: str
    byte_size: int
    market: str
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class StatementStatusUpdateRequest:
    next_status: str
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class StatementParseResponse:
    statement_id: str
    upload_status: str
    parsed_records: int
    failed_records: int
    parse_report_path: str
    trade_record_path: str
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ProfileGenerationResponse:
    statement_id: str
    trade_record_count: int
    profile_path: str
    profile: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AgentCreateRequest:
    owner_id: str
    statement_id: str
    init_cash: float
    agent_id: str | None = None
    source_runtime: str = "native"
    world_id: str | None = None


@dataclass(frozen=True, slots=True)
class AgentCreateResponse:
    agent_id: str
    owner_id: str
    statement_id: str
    world_id: str
    status: str
    init_cash: float
    public_url: str
    profile_path: str
    source_runtime: str
    created_at: str


@dataclass(frozen=True, slots=True)
class StatementMetadata:
    statement_id: str
    owner_id: str
    market: str
    file_name: str
    content_type: str
    detected_file_type: str
    parser_key: str
    byte_size: int
    bucket: str
    object_key: str
    upload_status: str
    created_at: str
    updated_at: str
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class AgentRegisterRequest:
    agent_id: str
    owner_id: str
    source_runtime: str = "platform"


@dataclass(frozen=True, slots=True)
class HeartbeatRequest:
    heartbeat_at: str
    status: str = "ACTIVE"


@dataclass(frozen=True, slots=True)
class SubmitActionRequest:
    agent_id: str
    world_id: str
    actions: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TradeCalendarSyncRequest:
    start_date: str
    end_date: str
    market: str = "CN_A"


@dataclass(frozen=True, slots=True)
class TradeCalendarSyncResponse:
    world_id: str
    market: str
    start_date: str
    end_date: str
    total_days: int
    trading_days: list[str]
    closed_days: list[str]
    trading_day: str | None
    next_trading_day: str | None
    source: str
    cache_path: str


@dataclass(frozen=True, slots=True)
class EventCreateRequest:
    title: str
    body: str
    source: str = "manual_text"
    event_time: str | None = None


@dataclass(frozen=True, slots=True)
class EventCreateResponse:
    event_id: str
    event_type: str
    status: str
    structure: dict[str, Any]
    mapping: dict[str, Any]


@dataclass(frozen=True, slots=True)
class EventPrepareResponse:
    event_id: str
    status: str
    casebook: dict[str, Any]
"""

SETTINGS_WITH_EVENTS_PY = """from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "versefina-api"
    environment: str = "development"
    default_world_id: str = "cn-a"
    read_model_source: str = "projection"
    public_base_url: str = "http://127.0.0.1:8000"
    object_store_bucket: str = "versefina-artifacts"
    object_store_root: str = str(REPO_ROOT / ".runtime" / "object_store")
    statement_meta_root: str = str(REPO_ROOT / ".runtime" / "statement_meta")
    statement_parse_report_root: str = str(REPO_ROOT / ".runtime" / "statement_parse_reports")
    trade_record_root: str = str(REPO_ROOT / ".runtime" / "trade_records")
    agent_profile_root: str = str(REPO_ROOT / ".runtime" / "agent_profiles")
    agent_registry_root: str = str(REPO_ROOT / ".runtime" / "agents")
    market_world_root: str = str(REPO_ROOT / ".runtime" / "market_world")
    event_runtime_root: str = str(REPO_ROOT / ".runtime" / "events")
    statement_max_upload_bytes: int = 10 * 1024 * 1024


def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "versefina-api"),
        environment=os.getenv("ENVIRONMENT", "development"),
        default_world_id=os.getenv("DEFAULT_WORLD_ID", "cn-a"),
        read_model_source=os.getenv("READ_MODEL_SOURCE", "projection"),
        public_base_url=os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000"),
        object_store_bucket=os.getenv("OBJECT_STORE_BUCKET", "versefina-artifacts"),
        object_store_root=os.getenv("OBJECT_STORE_ROOT", str(REPO_ROOT / ".runtime" / "object_store")),
        statement_meta_root=os.getenv("STATEMENT_META_ROOT", str(REPO_ROOT / ".runtime" / "statement_meta")),
        statement_parse_report_root=os.getenv(
            "STATEMENT_PARSE_REPORT_ROOT",
            str(REPO_ROOT / ".runtime" / "statement_parse_reports"),
        ),
        trade_record_root=os.getenv("TRADE_RECORD_ROOT", str(REPO_ROOT / ".runtime" / "trade_records")),
        agent_profile_root=os.getenv("AGENT_PROFILE_ROOT", str(REPO_ROOT / ".runtime" / "agent_profiles")),
        agent_registry_root=os.getenv("AGENT_REGISTRY_ROOT", str(REPO_ROOT / ".runtime" / "agents")),
        market_world_root=os.getenv("MARKET_WORLD_ROOT", str(REPO_ROOT / ".runtime" / "market_world")),
        event_runtime_root=os.getenv("EVENT_RUNTIME_ROOT", str(REPO_ROOT / ".runtime" / "events")),
        statement_max_upload_bytes=int(os.getenv("STATEMENT_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))),
    )
"""
EVENT_STRUCTURING_SERVICE_PY = """from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from schemas.event import EventRecord, EventStructure


_COMMODITY_KEYWORDS: dict[str, tuple[str, str, str, str]] = {
    "锂": ("lithium", "upstream", "battery_materials", "002460.SZ"),
    "碳酸锂": ("lithium_carbonate", "upstream", "battery_materials", "002460.SZ"),
    "原油": ("crude_oil", "upstream", "energy_chemicals", "600028.SH"),
    "化工": ("chemical_feedstock", "midstream", "energy_chemicals", "600309.SH"),
}


class EventStructuringService:
    def __init__(self, runtime_root: Path) -> None:
        self.runtime_root = runtime_root
        self.structure_root = runtime_root / "structures"
        self.structure_root.mkdir(parents=True, exist_ok=True)

    def structure_event(self, record: EventRecord) -> EventStructure:
        normalized_body = record.body.strip()
        commodity, chain_stage, sector, symbol = self._resolve_mapping(normalized_body)
        structure = EventStructure(
            event_id=record.event_id,
            event_type="supply_chain_price_shock",
            entities=[commodity, sector, symbol],
            commodities=[commodity],
            chain_links=[{"commodity": commodity, "chain_stage": chain_stage, "sector": sector}],
            sectors=[sector],
            affected_symbols=[symbol],
            causal_chain=[
                f"{commodity} supply tightens",
                f"{chain_stage} cost passes through to {sector}",
                f"{symbol} becomes a first-mover watch target",
            ],
            monitor_signals=["spot_price_breakout", "inventory_drawdown", "daily_limit_up_confirmation"],
            invalidation_conditions=["price shock reverses within 3 sessions", "downstream pass-through fails to appear"],
            summary=normalized_body[:200],
        )
        target_path = self.structure_root / f"{record.event_id}.json"
        target_path.write_text(json.dumps(asdict(structure), ensure_ascii=False, indent=2), encoding="utf-8")
        return structure

    def load_structure(self, event_id: str) -> EventStructure | None:
        target_path = self.structure_root / f"{event_id}.json"
        if not target_path.exists():
            return None
        payload = json.loads(target_path.read_text(encoding="utf-8"))
        return EventStructure(**payload)

    def _resolve_mapping(self, text: str) -> tuple[str, str, str, str]:
        lowered = text.lower()
        for keyword, mapping in _COMMODITY_KEYWORDS.items():
            if keyword.lower() in lowered:
                return mapping
        return ("supply_chain_price_shock", "upstream", "generic_price_shock", "000001.SZ")
"""

THEME_MAPPING_SERVICE_PY = """from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from schemas.event import EventStructure, ThemeMappingResult


_STYLE_TAGS = {
    "battery_materials": ["龙头", "高弹性", "机构票"],
    "energy_chemicals": ["龙头", "高弹性", "情绪票"],
    "generic_price_shock": ["龙头", "补涨候选"],
}


class ThemeMappingService:
    def __init__(self, runtime_root: Path) -> None:
        self.runtime_root = runtime_root
        self.mapping_root = runtime_root / "mappings"
        self.mapping_root.mkdir(parents=True, exist_ok=True)

    def map_structure(self, structure: EventStructure) -> ThemeMappingResult:
        primary_link = structure.chain_links[0] if structure.chain_links else {
            "commodity": "supply_chain_price_shock",
            "chain_stage": "upstream",
            "sector": "generic_price_shock",
        }
        sector = str(primary_link.get("sector") or "generic_price_shock")
        mapping = ThemeMappingResult(
            event_id=structure.event_id,
            commodity=str(primary_link.get("commodity") or "supply_chain_price_shock"),
            chain_stage=str(primary_link.get("chain_stage") or "upstream"),
            sector=sector,
            symbols=list(structure.affected_symbols or []),
            style_tags=list(_STYLE_TAGS.get(sector, ["龙头", "补涨候选"])),
        )
        target_path = self.mapping_root / f"{structure.event_id}.json"
        target_path.write_text(json.dumps(asdict(mapping), ensure_ascii=False, indent=2), encoding="utf-8")
        return mapping

    def load_mapping(self, event_id: str) -> ThemeMappingResult | None:
        target_path = self.mapping_root / f"{event_id}.json"
        if not target_path.exists():
            return None
        payload = json.loads(target_path.read_text(encoding="utf-8"))
        return ThemeMappingResult(**payload)
"""

EVENT_CASEBOOK_SERVICE_PY = """from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from schemas.event import EventCasebookEntry, EventRecord, EventStructure, ThemeMappingResult


class EventCasebookService:
    def __init__(self, runtime_root: Path) -> None:
        self.runtime_root = runtime_root
        self.casebook_root = runtime_root / "casebook"
        self.casebook_root.mkdir(parents=True, exist_ok=True)

    def write_casebook(
        self,
        *,
        record: EventRecord,
        structure: EventStructure,
        mapping: ThemeMappingResult,
        status: str,
    ) -> EventCasebookEntry:
        entry = EventCasebookEntry(
            event_id=record.event_id,
            record=asdict(record),
            structure=asdict(structure),
            mapping=asdict(mapping),
            status=status,
        )
        target_path = self.casebook_root / f"{record.event_id}.json"
        target_path.write_text(json.dumps(asdict(entry), ensure_ascii=False, indent=2), encoding="utf-8")
        return entry

    def mark_prepared(self, event_id: str) -> EventCasebookEntry:
        entry = self.load_casebook(event_id)
        if entry is None:
            raise FileNotFoundError(f"Casebook entry not found: {event_id}")
        updated = EventCasebookEntry(
            event_id=entry.event_id,
            record=dict(entry.record),
            structure=dict(entry.structure),
            mapping=dict(entry.mapping),
            status="prepared",
        )
        target_path = self.casebook_root / f"{event_id}.json"
        target_path.write_text(json.dumps(asdict(updated), ensure_ascii=False, indent=2), encoding="utf-8")
        return updated

    def load_casebook(self, event_id: str) -> EventCasebookEntry | None:
        target_path = self.casebook_root / f"{event_id}.json"
        if not target_path.exists():
            return None
        payload = json.loads(target_path.read_text(encoding="utf-8"))
        return EventCasebookEntry(**payload)
"""

EVENT_INGESTION_SERVICE_PY = """from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
import re

from domain.event_casebook.service import EventCasebookService
from domain.event_structuring.service import EventStructuringService
from domain.theme_mapping.service import ThemeMappingService
from schemas.command import EventCreateRequest, EventCreateResponse, EventPrepareResponse
from schemas.event import EventRecord


_WHITELIST_HINTS = ("涨价", "价格上涨", "供给", "停产", "限产", "冲击", "supply", "price shock")


class EventIngestionError(Exception):
    def __init__(self, *, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class EventIngestionService:
    def __init__(
        self,
        runtime_root: Path,
        structuring_service: EventStructuringService,
        theme_mapping_service: ThemeMappingService,
        casebook_service: EventCasebookService,
    ) -> None:
        self.runtime_root = runtime_root
        self.record_root = runtime_root / "records"
        self.record_root.mkdir(parents=True, exist_ok=True)
        self.structuring_service = structuring_service
        self.theme_mapping_service = theme_mapping_service
        self.casebook_service = casebook_service

    def ingest_event(self, payload: EventCreateRequest) -> EventCreateResponse:
        body = payload.body.strip()
        if not body:
            raise EventIngestionError(code="EVENT_TEXT_REQUIRED", message="Event text must not be empty.")
        if not self._is_whitelisted(body):
            raise EventIngestionError(
                code="EVENT_NOT_IN_WHITELIST",
                message="Only supply-chain price shock events can enter the P0 workflow.",
            )
        event_id = self._build_event_id(payload)
        record = EventRecord(
            event_id=event_id,
            title=(payload.title or body[:48]).strip(),
            body=body,
            source=payload.source,
            event_time=payload.event_time or datetime.now(UTC).isoformat(),
            status="raw",
        )
        self._write_record(record)
        structure = self.structuring_service.structure_event(record)
        mapping = self.theme_mapping_service.map_structure(structure)
        self.casebook_service.write_casebook(record=record, structure=structure, mapping=mapping, status="structured")
        return EventCreateResponse(
            event_id=record.event_id,
            event_type=structure.event_type,
            status="structured",
            structure=asdict(structure),
            mapping=asdict(mapping),
        )

    def prepare_event(self, event_id: str) -> EventPrepareResponse:
        casebook = self.casebook_service.mark_prepared(event_id)
        record = self.load_record(event_id)
        if record is not None:
            prepared_record = EventRecord(
                event_id=record.event_id,
                title=record.title,
                body=record.body,
                source=record.source,
                event_time=record.event_time,
                status="prepared",
            )
            self._write_record(prepared_record)
        return EventPrepareResponse(event_id=event_id, status="prepared", casebook=asdict(casebook))

    def load_record(self, event_id: str) -> EventRecord | None:
        target_path = self.record_root / f"{event_id}.json"
        if not target_path.exists():
            return None
        payload = json.loads(target_path.read_text(encoding="utf-8"))
        return EventRecord(**payload)

    def _build_event_id(self, payload: EventCreateRequest) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", payload.title.lower()).strip("-") or "event"
        return f"evt-{slug}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"

    def _is_whitelisted(self, text: str) -> bool:
        lowered = text.lower()
        return any(token in lowered for token in _WHITELIST_HINTS)

    def _write_record(self, record: EventRecord) -> None:
        target_path = self.record_root / f"{record.event_id}.json"
        target_path.write_text(json.dumps(asdict(record), ensure_ascii=False, indent=2), encoding="utf-8")
"""

CONTAINER_WITH_EVENTS_PY = """from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from domain.agent_registry.service import AgentRegistryService
from domain.dna_engine.service import DNAEngineService
from domain.event_casebook.service import EventCasebookService
from domain.event_ingestion.service import EventIngestionService
from domain.event_structuring.service import EventStructuringService
from domain.market_world.service import MarketWorldService
from domain.platform_control.service import PlatformControlService
from domain.simulation_ledger.service import SimulationLedgerService
from domain.theme_mapping.service import ThemeMappingService
from infra.storage.object_store import LocalObjectStore
from modules.statements.parser_service import StatementParseService
from modules.statements.repository import StatementMetadataRepository
from modules.statements.service import StatementIngestionService
from projection.agent_snapshots.service import AgentSnapshotProjection
from projection.panorama.service import PanoramaProjection
from projection.rankings.service import RankingProjection
from settings.base import get_settings


@dataclass(slots=True)
class ServiceContainer:
    agent_registry: AgentRegistryService
    dna_engine: DNAEngineService
    statement_ingestion: StatementIngestionService
    statement_parser: StatementParseService
    market_world: MarketWorldService
    simulation_ledger: SimulationLedgerService
    platform_control: PlatformControlService
    event_ingestion: EventIngestionService
    event_structuring: EventStructuringService
    theme_mapping: ThemeMappingService
    event_casebook: EventCasebookService
    agent_snapshots: AgentSnapshotProjection
    rankings: RankingProjection
    panorama: PanoramaProjection


def build_container() -> ServiceContainer:
    settings = get_settings()
    object_store = LocalObjectStore(root=Path(settings.object_store_root), bucket=settings.object_store_bucket)
    metadata_repository = StatementMetadataRepository(Path(settings.statement_meta_root))
    statement_ingestion = StatementIngestionService(
        object_store=object_store,
        metadata_repository=metadata_repository,
        max_upload_bytes=settings.statement_max_upload_bytes,
    )
    statement_parser = StatementParseService(
        object_store=object_store,
        parse_report_root=Path(settings.statement_parse_report_root),
        trade_record_root=Path(settings.trade_record_root),
    )
    event_structuring = EventStructuringService(Path(settings.event_runtime_root))
    theme_mapping = ThemeMappingService(Path(settings.event_runtime_root))
    event_casebook = EventCasebookService(Path(settings.event_runtime_root))
    event_ingestion = EventIngestionService(
        runtime_root=Path(settings.event_runtime_root),
        structuring_service=event_structuring,
        theme_mapping_service=theme_mapping,
        casebook_service=event_casebook,
    )
    return ServiceContainer(
        agent_registry=AgentRegistryService(
            default_world_id=settings.default_world_id,
            registry_root=Path(settings.agent_registry_root),
            public_base_url=settings.public_base_url,
        ),
        dna_engine=DNAEngineService(
            trade_record_root=Path(settings.trade_record_root),
            profile_root=Path(settings.agent_profile_root),
        ),
        statement_ingestion=statement_ingestion,
        statement_parser=statement_parser,
        market_world=MarketWorldService(
            default_world_id=settings.default_world_id,
            runtime_root=Path(settings.market_world_root),
            agent_registry_root=Path(settings.agent_registry_root),
        ),
        simulation_ledger=SimulationLedgerService(),
        platform_control=PlatformControlService(),
        event_ingestion=event_ingestion,
        event_structuring=event_structuring,
        theme_mapping=theme_mapping,
        event_casebook=event_casebook,
        agent_snapshots=AgentSnapshotProjection(),
        rankings=RankingProjection(),
        panorama=PanoramaProjection(),
    )
"""
COMMAND_ROUTES_WITH_EVENTS_PY = """from __future__ import annotations

from dataclasses import asdict

from domain.event_ingestion.service import EventIngestionError
from infra.http import APIRouter, File, Form, JSONResponse, Request, UploadFile
from modules.statements.parser_service import StatementParseError
from modules.statements.service import StatementUploadValidationError
from modules.statements.status_machine import InvalidStatementTransitionError
from schemas.command import (
    AgentCreateRequest,
    AgentRegisterRequest,
    EventCreateRequest,
    HeartbeatRequest,
    StatementStatusUpdateRequest,
    StatementUploadRequest,
    SubmitActionRequest,
)
from services.container import ServiceContainer


def build_command_router(container: ServiceContainer) -> APIRouter:
    router = APIRouter(tags=["command"])

    @router.post("/api/v1/statements/upload")
    async def upload_statement(
        owner_id: str = Form(...),
        market: str = Form("CN_A"),
        statement_id: str | None = Form(None),
        file: UploadFile = File(...),
    ):
        file_bytes = await file.read()
        payload = StatementUploadRequest(
            statement_id=statement_id,
            owner_id=owner_id,
            file_name=file.filename or "statement.bin",
            content_type=file.content_type or "application/octet-stream",
            byte_size=len(file_bytes),
            market=market,
        )
        try:
            result = container.statement_ingestion.ingest_statement(payload, file_bytes)
        except StatementUploadValidationError as exc:
            rejected = container.statement_ingestion.reject_upload(
                owner_id=owner_id,
                file_name=payload.file_name,
                content_type=payload.content_type,
                byte_size=payload.byte_size,
                market=market,
                statement_id=statement_id,
                code=exc.code,
                message=exc.message,
            )
            return JSONResponse(status_code=exc.status_code, content=asdict(rejected))
        return asdict(result)

    @router.post("/api/v1/events")
    def create_event(payload: EventCreateRequest):
        try:
            return asdict(container.event_ingestion.ingest_event(payload))
        except EventIngestionError as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"error_code": exc.code, "error_message": exc.message},
            )

    @router.post("/api/v1/events/{event_id}/prepare")
    def prepare_event(event_id: str):
        try:
            return asdict(container.event_ingestion.prepare_event(event_id))
        except FileNotFoundError:
            return JSONResponse(
                status_code=404,
                content={
                    "event_id": event_id,
                    "error_code": "EVENT_NOT_FOUND",
                    "error_message": "Event casebook not found.",
                },
            )

    @router.post("/api/v1/agents/register")
    def register_agent(payload: AgentRegisterRequest):
        return container.agent_registry.register(payload)

    @router.post("/api/v1/statements/{statement_id}/profile")
    def build_statement_profile(statement_id: str):
        metadata = container.statement_ingestion.get_statement(statement_id)
        if metadata is None:
            return JSONResponse(
                status_code=404,
                content={
                    "statement_id": statement_id,
                    "error_code": "STATEMENT_NOT_FOUND",
                    "error_message": "Statement metadata not found.",
                },
            )
        if metadata.upload_status != "parsed":
            return JSONResponse(
                status_code=409,
                content={
                    "statement_id": statement_id,
                    "error_code": "STATEMENT_NOT_PARSED",
                    "error_message": "Statement must be parsed before profile generation.",
                },
            )
        try:
            result = container.dna_engine.build_profile(statement_id, market=metadata.market)
        except FileNotFoundError:
            return JSONResponse(
                status_code=404,
                content={
                    "statement_id": statement_id,
                    "error_code": "TRADE_RECORDS_NOT_FOUND",
                    "error_message": "Trade records not found for profile generation.",
                },
            )
        return asdict(result)

    @router.post("/api/v1/agents")
    def create_agent(payload: AgentCreateRequest, request: Request):
        metadata = container.statement_ingestion.get_statement(payload.statement_id)
        if metadata is None:
            return JSONResponse(
                status_code=404,
                content={
                    "statement_id": payload.statement_id,
                    "error_code": "STATEMENT_NOT_FOUND",
                    "error_message": "Statement metadata not found.",
                },
            )
        profile = container.dna_engine.get_profile(payload.statement_id)
        if profile is None:
            return JSONResponse(
                status_code=404,
                content={
                    "statement_id": payload.statement_id,
                    "error_code": "PROFILE_NOT_FOUND",
                    "error_message": "Profile must be generated before agent creation.",
                },
            )
        result = container.agent_registry.create_agent(
            payload,
            profile=profile,
            profile_path=str(container.dna_engine.profile_root / f"{payload.statement_id}.json"),
            public_base_url=str(request.base_url).rstrip("/"),
        )
        return asdict(result)

    @router.post("/api/v1/statements/{statement_id}/parse")
    def parse_statement(statement_id: str):
        metadata = container.statement_ingestion.get_statement(statement_id)
        if metadata is None:
            return JSONResponse(
                status_code=404,
                content={
                    "statement_id": statement_id,
                    "error_code": "STATEMENT_NOT_FOUND",
                    "error_message": "Statement metadata not found.",
                },
            )
        try:
            if metadata.upload_status == "uploaded":
                container.statement_ingestion.transition_status(statement_id=statement_id, next_status="parsing")
                metadata = container.statement_ingestion.get_statement(statement_id) or metadata
            result = container.statement_parser.parse_statement(metadata)
            final_status = "parsed" if result.failed_records == 0 else "failed"
            container.statement_ingestion.transition_status(
                statement_id=statement_id,
                next_status=final_status,
                error_code=result.error_code,
                error_message=result.error_message,
            )
            refreshed = container.statement_ingestion.get_statement(statement_id)
            return {
                **asdict(result),
                "final_status": refreshed.upload_status if refreshed else final_status,
            }
        except (StatementParseError, InvalidStatementTransitionError) as exc:
            error_code = getattr(exc, "code", "STATEMENT_PARSE_FAILED")
            error_message = getattr(exc, "message", str(exc))
            status_code = getattr(exc, "status_code", 400)
            try:
                container.statement_ingestion.transition_status(
                    statement_id=statement_id,
                    next_status="failed",
                    error_code=error_code,
                    error_message=error_message,
                )
            except Exception:
                pass
            return JSONResponse(
                status_code=status_code,
                content={
                    "statement_id": statement_id,
                    "error_code": error_code,
                    "error_message": error_message,
                },
            )

    @router.post("/api/v1/statements/{statement_id}/status")
    def update_statement_status(statement_id: str, payload: StatementStatusUpdateRequest):
        try:
            updated = container.statement_ingestion.transition_status(
                statement_id=statement_id,
                next_status=payload.next_status,
                error_code=payload.error_code,
                error_message=payload.error_message,
            )
        except FileNotFoundError:
            return JSONResponse(
                status_code=404,
                content={
                    "statement_id": statement_id,
                    "error_code": "STATEMENT_NOT_FOUND",
                    "error_message": "Statement metadata not found.",
                },
            )
        except InvalidStatementTransitionError as exc:
            return JSONResponse(
                status_code=400,
                content={
                    "statement_id": statement_id,
                    "error_code": "STATEMENT_INVALID_TRANSITION",
                    "error_message": str(exc),
                },
            )
        return asdict(updated)

    @router.post("/api/v1/agents/{agent_id}/heartbeat")
    def heartbeat(agent_id: str, payload: HeartbeatRequest):
        return container.agent_registry.heartbeat(agent_id, payload)

    @router.post("/api/v1/actions/submit")
    def submit_actions(payload: SubmitActionRequest):
        return container.simulation_ledger.submit_actions(payload)

    return router
"""

QUERY_ROUTES_WITH_EVENTS_PY = """from __future__ import annotations

import json
from pathlib import Path

from infra.http import APIRouter
from services.container import ServiceContainer
from settings.base import get_settings


def build_query_router(container: ServiceContainer) -> APIRouter:
    router = APIRouter(tags=["query"])

    @router.get("/api/v1/agents/{agent_id}/snapshot")
    def agent_snapshot(agent_id: str):
        return container.agent_snapshots.present(container.agent_registry.snapshot(agent_id))

    @router.get("/api/v1/agents/{agent_id}")
    def agent_detail(agent_id: str):
        agent = container.agent_registry.get_agent(agent_id)
        if agent is None:
            return {"agent_id": agent_id, "status": "not_found"}
        return agent

    @router.get("/api/v1/agents/{agent_id}/trades")
    def agent_trades(agent_id: str):
        return container.simulation_ledger.trades(agent_id)

    @router.get("/api/v1/agents/{agent_id}/equity")
    def agent_equity(agent_id: str):
        return container.simulation_ledger.equity(agent_id)

    @router.get("/api/v1/events/{event_id}")
    def event_detail(event_id: str):
        casebook = container.event_casebook.load_casebook(event_id)
        if casebook is not None:
            return casebook.to_dict()
        record = container.event_ingestion.load_record(event_id)
        if record is None:
            return {"event_id": event_id, "status": "not_found"}
        return record.to_dict()

    @router.get("/api/v1/events/{event_id}/casebook")
    def event_casebook(event_id: str):
        casebook = container.event_casebook.load_casebook(event_id)
        if casebook is None:
            return {"event_id": event_id, "status": "not_found"}
        return casebook.to_dict()

    @router.get("/api/v1/statements/{statement_id}")
    def statement_detail(statement_id: str):
        metadata = container.statement_ingestion.get_statement(statement_id)
        if metadata is None:
            return {"statement_id": statement_id, "status": "not_found"}
        return metadata

    @router.get("/api/v1/statements/{statement_id}/parse-report")
    def statement_parse_report(statement_id: str):
        report_path = Path(get_settings().statement_parse_report_root) / f"{statement_id}.json"
        if not report_path.exists():
            return {"statement_id": statement_id, "status": "not_found"}
        return json.loads(report_path.read_text(encoding="utf-8"))

    @router.get("/api/v1/statements/{statement_id}/profile")
    def statement_profile(statement_id: str):
        profile = container.dna_engine.get_profile(statement_id)
        if profile is None:
            return {"statement_id": statement_id, "status": "not_found"}
        return profile

    @router.get("/api/v1/rankings")
    def rankings():
        return container.rankings.list_rankings()

    @router.get("/api/v1/universe/panorama")
    def panorama(as_of_date: str | None = None):
        return container.panorama.present(container.market_world.panorama(as_of_date=as_of_date))

    @router.get("/api/v1/worlds/{world_id}/snapshot")
    def world_snapshot(world_id: str, as_of_date: str | None = None):
        return container.market_world.snapshot(world_id, as_of_date=as_of_date)

    return router
"""

TEST_EVENT_INGESTION_PY = """from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app import create_app


class EventIngestionApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_env = {"EVENT_RUNTIME_ROOT": os.environ.get("EVENT_RUNTIME_ROOT")}
        os.environ["EVENT_RUNTIME_ROOT"] = str(Path(self.tempdir.name) / "events")
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.client.close()
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tempdir.cleanup()

    def test_create_event_returns_structure_and_mapping(self) -> None:
        response = self.client.post(
            "/api/v1/events",
            json={
                "title": "碳酸锂价格上涨",
                "body": "受停产和供给冲击影响，碳酸锂价格上涨，锂电材料链传导增强。",
                "source": "manual_text",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["event_type"], "supply_chain_price_shock")
        self.assertEqual(payload["status"], "structured")
        self.assertIn("commodities", payload["structure"])
        self.assertIn("symbols", payload["mapping"])

    def test_non_whitelist_event_is_rejected(self) -> None:
        response = self.client.post(
            "/api/v1/events",
            json={
                "title": "政策鼓励消费",
                "body": "政策鼓励消费升级并扩大内需，但不属于当前事件白名单。",
                "source": "manual_text",
            },
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["error_code"], "EVENT_NOT_IN_WHITELIST")


if __name__ == "__main__":
    unittest.main()
"""

TEST_EVENT_CASEBOOK_PY = """from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app import create_app


class EventCasebookApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_env = {"EVENT_RUNTIME_ROOT": os.environ.get("EVENT_RUNTIME_ROOT")}
        os.environ["EVENT_RUNTIME_ROOT"] = str(Path(self.tempdir.name) / "events")
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.client.close()
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tempdir.cleanup()

    def test_prepare_event_promotes_casebook_and_supports_replay(self) -> None:
        create_response = self.client.post(
            "/api/v1/events",
            json={
                "title": "原油供给冲击",
                "body": "原油供给受限导致价格上涨，并向化工链传导。",
                "source": "manual_text",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        event_id = create_response.json()["event_id"]

        prepare_response = self.client.post(f"/api/v1/events/{event_id}/prepare")
        self.assertEqual(prepare_response.status_code, 200)
        prepared = prepare_response.json()
        self.assertEqual(prepared["status"], "prepared")

        casebook_response = self.client.get(f"/api/v1/events/{event_id}/casebook")
        self.assertEqual(casebook_response.status_code, 200)
        casebook = casebook_response.json()
        self.assertEqual(casebook["status"], "prepared")
        self.assertEqual(casebook["event_id"], event_id)

    def test_missing_casebook_returns_not_found(self) -> None:
        response = self.client.get("/api/v1/events/evt-missing/casebook")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "not_found")


if __name__ == "__main__":
    unittest.main()
"""

E1_003_DELIVERY_MD = """# E1-003 Delivery

- Scope: event ingestion, structuring, command route, container wiring, tests
- Route: `POST /api/v1/events`
- Route: `POST /api/v1/events/{event_id}/prepare`
- Guarantees:
  - text-only event input is accepted for whitelist events
  - structure is normalized into `EventStructure`
  - mapping output is attached for downstream preparation and replay
"""

E1_005_DELIVERY_MD = """# E1-005 Delivery

- Scope: casebook persistence, replay read path, query route, tests
- Route: `GET /api/v1/events/{event_id}`
- Route: `GET /api/v1/events/{event_id}/casebook`
- Guarantees:
  - raw record, structure, and mapping are linked by `event_id`
  - casebook replay returns explicit `not_found` when the sample is missing
  - prepared state is persisted for downstream validation
"""

PARTICIPANT_SCHEMA_PY = """from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


PARTICIPANT_FAMILIES = (
    "retail_fast_money",
    "institution_confirmation",
    "industry_research",
    "policy_research",
    "quant_risk_budget",
    "risk_control",
    "media_sentiment",
    "supply_chain_channel",
)

PARTICIPANT_STANCES = (
    "bullish",
    "constructive",
    "neutral",
    "watch",
    "skeptical",
    "bearish",
    "insufficient_evidence",
)

PARTICIPANT_TIME_HORIZONS = ("intraday", "t1", "t3", "t5_plus")


@dataclass(frozen=True, slots=True)
class ParticipantOutput:
    participant_id: str
    participant_family: str
    style_variant: str
    stance: str
    confidence: float
    time_horizon: str
    expected_impact: str
    evidence: list[str] = field(default_factory=list)
    trigger_conditions: list[str] = field(default_factory=list)
    invalidation_conditions: list[str] = field(default_factory=list)
    first_movers: list[str] = field(default_factory=list)
    secondary_movers: list[str] = field(default_factory=list)
    dissent_points: list[str] = field(default_factory=list)
    authority_weight: float | None = None
    risk_budget_profile: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
"""

PARTICIPANT_REGISTRY_PY = """from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ParticipantVariantDefinition:
    participant_family: str
    style_variant: str
    authority_weight: float
    risk_budget_profile: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PRIMARY_VARIANTS = (
    ParticipantVariantDefinition("retail_fast_money", "fast_momentum", 0.62, "high_turnover", ["first mover"]),
    ParticipantVariantDefinition("institution_confirmation", "trend_confirmation", 0.78, "risk_adjusted_add", ["follow through"]),
    ParticipantVariantDefinition("industry_research", "fundamental_channel_check", 0.74, "medium_conviction", ["supply chain verification"]),
    ParticipantVariantDefinition("policy_research", "policy_interpretation", 0.68, "theme_rotation", ["policy impulse"]),
    ParticipantVariantDefinition("quant_risk_budget", "factor_rotation", 0.57, "model_capped", ["flow driven"]),
    ParticipantVariantDefinition("risk_control", "drawdown_guard", 0.83, "capital_preservation", ["invalidation first"]),
    ParticipantVariantDefinition("media_sentiment", "headline_amplifier", 0.51, "event_reactive", ["sentiment spread"]),
    ParticipantVariantDefinition("supply_chain_channel", "channel_pass_through", 0.76, "inventory_sensitive", ["industrial chain"]),
)


class ParticipantRegistry:
    def __init__(self) -> None:
        self._primary_variants = {item.participant_family: item for item in PRIMARY_VARIANTS}

    def list_primary_variants(self) -> list[ParticipantVariantDefinition]:
        return list(self._primary_variants.values())

    def get_primary_variant(self, participant_family: str) -> ParticipantVariantDefinition | None:
        return self._primary_variants.get(participant_family)
"""

TEST_PARTICIPANT_REGISTRY_PY = """from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app import create_app


class ParticipantRegistryApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.client.close()

    def test_variants_endpoint_returns_fast_money_primary_variant(self) -> None:
        response = self.client.post("/api/v1/participants/variants")
        self.assertEqual(response.status_code, 200)
        variants = response.json()["variants"]
        retail_fast_money = next(item for item in variants if item["participant_family"] == "retail_fast_money")
        self.assertEqual(retail_fast_money["style_variant"], "fast_momentum")
        self.assertIn("authority_weight", retail_fast_money)
        self.assertIn("risk_budget_profile", retail_fast_money)

    def test_unknown_family_returns_not_found(self) -> None:
        response = self.client.post("/api/v1/participants/variants/unknown_family")
        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertEqual(payload["status"], "not_found")


if __name__ == "__main__":
    unittest.main()
"""

E2_002_DELIVERY_MD = """# E2-002 Delivery

- Scope: participant primary variants registry, container wiring, command routes, tests
- Route: `POST /api/v1/participants/variants`
- Route: `POST /api/v1/participants/variants/{participant_family}`
- Guarantees:
  - each participant family has one primary style variant
  - each variant defines `authority_weight` and `risk_budget_profile`
  - the registry can be reused by later participant preparation stories
"""

PARTICIPANT_PREPARATION_SCHEMA_PY = """from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from schemas.participant import ParticipantOutput


@dataclass(frozen=True, slots=True)
class ParticipantRoster:
    event_id: str
    status: str
    participants: list[ParticipantOutput] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    activation_basis: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
"""

PARTICIPANT_PREPARATION_SERVICE_PY = """from __future__ import annotations

from domain.event_casebook.service import EventCasebookService
from domain.participant_preparation.registry import ParticipantRegistry
from schemas.command import EventPrepareResponse
from schemas.participant import ParticipantOutput
from schemas.participant_preparation import ParticipantRoster


_FAMILY_PLAYBOOK: dict[str, dict[str, str]] = {
    "retail_fast_money": {
        "stance": "bullish",
        "time_horizon": "intraday",
        "impact": "leads the first momentum chase",
        "reason": "spot price breakout is visible to fast-money desks",
    },
    "institution_confirmation": {
        "stance": "constructive",
        "time_horizon": "t1",
        "impact": "confirms the strongest first-mover names",
        "reason": "needs confirmation from sector leadership and liquidity follow-through",
    },
    "industry_research": {
        "stance": "constructive",
        "time_horizon": "t3",
        "impact": "checks whether the industrial chain can pass through costs",
        "reason": "validates channel and supply-chain transmission",
    },
    "policy_research": {
        "stance": "watch",
        "time_horizon": "t3",
        "impact": "looks for policy reinforcement or offsetting guidance",
        "reason": "monitors whether policy direction amplifies the theme",
    },
    "quant_risk_budget": {
        "stance": "neutral",
        "time_horizon": "t1",
        "impact": "sizes exposure only when factor breadth confirms",
        "reason": "waits for volatility and factor confirmation",
    },
    "risk_control": {
        "stance": "watch",
        "time_horizon": "intraday",
        "impact": "guards the invalidation line before capital is committed",
        "reason": "tracks drawdown and reversal pressure first",
    },
    "media_sentiment": {
        "stance": "constructive",
        "time_horizon": "intraday",
        "impact": "amplifies the headline into broader crowd attention",
        "reason": "headline velocity can widen the participation set",
    },
    "supply_chain_channel": {
        "stance": "constructive",
        "time_horizon": "t1",
        "impact": "tests inventory and pricing pass-through on the ground",
        "reason": "channel checks validate whether the signal is real",
    },
}


class ParticipantPreparationError(Exception):
    def __init__(self, *, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ParticipantPreparationService:
    def __init__(self, casebook_service: EventCasebookService, participant_registry: ParticipantRegistry) -> None:
        self.casebook_service = casebook_service
        self.participant_registry = participant_registry

    def prepare_event(self, event_id: str) -> EventPrepareResponse:
        casebook = self.casebook_service.load_casebook(event_id)
        if casebook is None:
            raise ParticipantPreparationError(
                code="EVENT_NOT_FOUND",
                message="Event casebook not found.",
                status_code=404,
            )

        blocked_reasons = self._collect_blocked_reasons(casebook.structure, casebook.mapping)
        activation_basis = self._build_activation_basis(casebook.structure, casebook.mapping)
        if blocked_reasons:
            roster = ParticipantRoster(
                event_id=event_id,
                status="degraded",
                participants=[],
                blocked_reasons=blocked_reasons,
                activation_basis=activation_basis,
            )
            return EventPrepareResponse(
                event_id=event_id,
                status="degraded",
                casebook=casebook.to_dict(),
                participant_roster=roster.to_dict(),
            )

        prepared_casebook = self.casebook_service.mark_prepared(event_id)
        roster = ParticipantRoster(
            event_id=event_id,
            status="prepared",
            participants=self._build_participants(prepared_casebook.structure, prepared_casebook.mapping),
            blocked_reasons=[],
            activation_basis=activation_basis,
        )
        return EventPrepareResponse(
            event_id=event_id,
            status="prepared",
            casebook=prepared_casebook.to_dict(),
            participant_roster=roster.to_dict(),
        )

    def _collect_blocked_reasons(self, structure: dict[str, object], mapping: dict[str, object]) -> list[str]:
        blocked: list[str] = []
        if structure.get("event_type") != "supply_chain_price_shock":
            blocked.append("prepare currently supports supply_chain_price_shock events only")
        if not structure.get("commodities"):
            blocked.append("structured event is missing commodity evidence")
        symbol_candidates = mapping.get("symbols") or structure.get("affected_symbols")
        if not symbol_candidates:
            blocked.append("structured event is missing first-mover symbols")
        if not structure.get("monitor_signals"):
            blocked.append("structured event is missing monitor signals")
        return blocked

    def _build_activation_basis(self, structure: dict[str, object], mapping: dict[str, object]) -> list[str]:
        basis: list[str] = []
        summary = str(structure.get("summary") or "").strip()
        if summary:
            basis.append(summary)
        for signal in list(structure.get("monitor_signals") or [])[:2]:
            basis.append(f"monitor:{signal}")
        for symbol in list(mapping.get("symbols") or structure.get("affected_symbols") or [])[:2]:
            basis.append(f"symbol:{symbol}")
        sector = str(mapping.get("sector") or "").strip()
        if sector:
            basis.append(f"sector:{sector}")
        return basis

    def _build_participants(
        self,
        structure: dict[str, object],
        mapping: dict[str, object],
    ) -> list[ParticipantOutput]:
        participants: list[ParticipantOutput] = []
        first_movers = list(mapping.get("symbols") or structure.get("affected_symbols") or [])
        focus = str(mapping.get("commodity") or (list(structure.get("commodities") or ["event"])[0]))
        activation_basis = self._build_activation_basis(structure, mapping)
        trigger_conditions = list(structure.get("monitor_signals") or [])[:3]
        invalidation_conditions = list(structure.get("invalidation_conditions") or [])[:3]
        for variant in self.participant_registry.list_primary_variants():
            playbook = _FAMILY_PLAYBOOK.get(variant.participant_family, {})
            confidence = round(min(0.95, 0.35 + variant.authority_weight * 0.55), 2)
            participants.append(
                ParticipantOutput(
                    participant_id=f"{variant.participant_family}:{variant.style_variant}",
                    participant_family=variant.participant_family,
                    style_variant=variant.style_variant,
                    stance=playbook.get("stance", "neutral"),
                    confidence=confidence,
                    time_horizon=playbook.get("time_horizon", "t1"),
                    expected_impact=f"{playbook.get('impact', 'tracks the event')} around {focus}",
                    evidence=activation_basis[:3],
                    trigger_conditions=trigger_conditions,
                    invalidation_conditions=invalidation_conditions,
                    first_movers=first_movers[:2],
                    secondary_movers=first_movers[2:4],
                    dissent_points=list(variant.notes[:1]),
                    authority_weight=variant.authority_weight,
                    risk_budget_profile=variant.risk_budget_profile,
                )
            )
        return participants
"""

TEST_PARTICIPANT_PREPARATION_PY = """from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app import create_app


class ParticipantPreparationApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_env = {"EVENT_RUNTIME_ROOT": os.environ.get("EVENT_RUNTIME_ROOT")}
        self.runtime_root = Path(self.tempdir.name) / "events"
        os.environ["EVENT_RUNTIME_ROOT"] = str(self.runtime_root)
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.client.close()
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tempdir.cleanup()

    def test_prepare_event_returns_participant_roster(self) -> None:
        create_response = self.client.post(
            "/api/v1/events",
            json={
                "title": "Lithium price shock",
                "body": "supply shock drives lithium prices higher across the battery chain",
                "source": "manual_text",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        event_id = create_response.json()["event_id"]

        prepare_response = self.client.post(f"/api/v1/events/{event_id}/prepare")
        self.assertEqual(prepare_response.status_code, 200)
        payload = prepare_response.json()
        self.assertEqual(payload["status"], "prepared")
        self.assertEqual(payload["participant_roster"]["status"], "prepared")
        participants = payload["participant_roster"]["participants"]
        self.assertEqual(len(participants), 8)
        first = participants[0]
        self.assertIn("participant_family", first)
        self.assertIn("authority_weight", first)
        self.assertIn("risk_budget_profile", first)

    def test_prepare_event_degrades_when_evidence_is_incomplete(self) -> None:
        casebook_root = self.runtime_root / "casebook"
        casebook_root.mkdir(parents=True, exist_ok=True)
        casebook_root.joinpath("evt-insufficient.json").write_text(
            json.dumps(
                {
                    "event_id": "evt-insufficient",
                    "record": {
                        "event_id": "evt-insufficient",
                        "title": "weak signal",
                        "body": "weak signal",
                        "source": "manual_text",
                        "event_time": "2026-03-25T00:00:00+00:00",
                        "status": "structured",
                    },
                    "structure": {
                        "event_id": "evt-insufficient",
                        "event_type": "supply_chain_price_shock",
                        "commodities": [],
                        "affected_symbols": [],
                        "monitor_signals": [],
                        "invalidation_conditions": [],
                        "summary": "evidence is still too thin",
                    },
                    "mapping": {"symbols": [], "sector": "", "commodity": ""},
                    "status": "structured",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        response = self.client.post("/api/v1/events/evt-insufficient/prepare")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["participant_roster"]["participants"], [])
        self.assertGreaterEqual(len(payload["participant_roster"]["blocked_reasons"]), 1)


if __name__ == "__main__":
    unittest.main()
"""

E2_003_DELIVERY_MD = """# E2-003 Delivery

- Scope: participant prepare orchestrator, roster schema, command route, container wiring, tests
- Route: `POST /api/v1/events/{event_id}/prepare`
- Guarantees:
  - prepare returns a `ParticipantRoster` for structured supply-chain price-shock events
  - each activated participant carries weights, style metadata, and activation reasons
  - thin-evidence events degrade explicitly instead of silently pretending to be ready
"""

PARTICIPANT_REGISTRY_SCHEMA_PY = """from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ParticipantRegistryEntry:
    participant_family: str
    style_variant: str
    authority_weight: float
    risk_budget_profile: str
    notes: list[str] = field(default_factory=list)
    calibration_status: str = "default"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ParticipantRegistrySnapshot:
    entries: list[ParticipantRegistryEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
"""

PARTICIPANT_REGISTRY_WITH_CALIBRATION_PY = """from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from schemas.e2_005 import ParticipantRegistryEntry, ParticipantRegistrySnapshot


@dataclass(frozen=True, slots=True)
class ParticipantVariantDefinition:
    participant_family: str
    style_variant: str
    authority_weight: float
    risk_budget_profile: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PRIMARY_VARIANTS = (
    ParticipantVariantDefinition("retail_fast_money", "fast_momentum", 0.62, "high_turnover", ["first mover"]),
    ParticipantVariantDefinition("institution_confirmation", "trend_confirmation", 0.78, "risk_adjusted_add", ["follow through"]),
    ParticipantVariantDefinition("industry_research", "fundamental_channel_check", 0.74, "medium_conviction", ["supply chain verification"]),
    ParticipantVariantDefinition("policy_research", "policy_interpretation", 0.68, "theme_rotation", ["policy impulse"]),
    ParticipantVariantDefinition("quant_risk_budget", "factor_rotation", 0.57, "model_capped", ["flow driven"]),
    ParticipantVariantDefinition("risk_control", "drawdown_guard", 0.83, "capital_preservation", ["invalidation first"]),
    ParticipantVariantDefinition("media_sentiment", "headline_amplifier", 0.51, "event_reactive", ["sentiment spread"]),
    ParticipantVariantDefinition("supply_chain_channel", "channel_pass_through", 0.76, "inventory_sensitive", ["industrial chain"]),
)


class ParticipantRegistry:
    def __init__(self) -> None:
        self._primary_variants = {item.participant_family: item for item in PRIMARY_VARIANTS}

    def list_primary_variants(self) -> list[ParticipantVariantDefinition]:
        return list(self._primary_variants.values())

    def get_primary_variant(self, participant_family: str) -> ParticipantVariantDefinition | None:
        return self._primary_variants.get(participant_family)

    def list_registry_entries(self) -> list[ParticipantRegistryEntry]:
        return [
            ParticipantRegistryEntry(
                participant_family=item.participant_family,
                style_variant=item.style_variant,
                authority_weight=item.authority_weight,
                risk_budget_profile=item.risk_budget_profile,
                notes=list(item.notes),
                calibration_status="default",
            )
            for item in self.list_primary_variants()
        ]

    def get_registry_entry(self, participant_family: str) -> ParticipantRegistryEntry | None:
        variant = self.get_primary_variant(participant_family)
        if variant is None:
            return None
        return ParticipantRegistryEntry(
            participant_family=variant.participant_family,
            style_variant=variant.style_variant,
            authority_weight=variant.authority_weight,
            risk_budget_profile=variant.risk_budget_profile,
            notes=list(variant.notes),
            calibration_status="default",
        )

    def snapshot(self) -> ParticipantRegistrySnapshot:
        return ParticipantRegistrySnapshot(entries=self.list_registry_entries())
"""

TEST_PARTICIPANT_REGISTRY_DEFAULTS_PY = """from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app import create_app


class ParticipantRegistryDefaultsApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.client.close()

    def test_registry_snapshot_exposes_default_weights_and_budgets(self) -> None:
        response = self.client.post("/api/v1/participants/registry")
        self.assertEqual(response.status_code, 200)
        entries = response.json()["entries"]
        retail = next(item for item in entries if item["participant_family"] == "retail_fast_money")
        self.assertEqual(retail["authority_weight"], 0.62)
        self.assertEqual(retail["risk_budget_profile"], "high_turnover")
        self.assertEqual(retail["calibration_status"], "default")

    def test_unknown_registry_family_returns_not_found(self) -> None:
        response = self.client.post("/api/v1/participants/registry/unknown_family")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["status"], "not_found")


if __name__ == "__main__":
    unittest.main()
"""

E2_005_DELIVERY_MD = """# E2-005 Delivery

- Scope: participant default authority/risk registry, command routes, tests
- Route: `POST /api/v1/participants/registry`
- Route: `POST /api/v1/participants/registry/{participant_family}`
- Guarantees:
  - every participant family exposes a default `authority_weight`
  - every participant family exposes a default `risk_budget_profile`
  - registry snapshots are ready for later calibration-layer overrides
"""

BELIEF_GRAPH_SCHEMA_PY = """from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class BeliefGraphNode:
    participant_id: str
    participant_family: str
    stance: str
    authority_weight: float
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class BeliefGraphSnapshot:
    event_id: str
    status: str
    participant_count: int
    key_supporters: list[str] = field(default_factory=list)
    key_opponents: list[str] = field(default_factory=list)
    consensus_signals: list[str] = field(default_factory=list)
    divergence_signals: list[str] = field(default_factory=list)
    nodes: list[BeliefGraphNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
"""

BELIEF_GRAPH_SERVICE_PY = """from __future__ import annotations

from domain.participant_preparation.service import ParticipantPreparationError, ParticipantPreparationService
from schemas.belief_graph import BeliefGraphNode, BeliefGraphSnapshot


_SUPPORTIVE_STANCES = {"bullish", "constructive"}
_OPPOSING_STANCES = {"watch", "skeptical", "bearish"}


class BeliefGraphError(Exception):
    def __init__(self, *, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class BeliefGraphService:
    def __init__(self, participant_preparation: ParticipantPreparationService) -> None:
        self.participant_preparation = participant_preparation

    def build_snapshot(self, event_id: str) -> BeliefGraphSnapshot:
        try:
            prepare_result = self.participant_preparation.prepare_event(event_id)
        except ParticipantPreparationError as exc:
            raise BeliefGraphError(code=exc.code, message=exc.message, status_code=exc.status_code) from exc

        roster = dict(prepare_result.participant_roster or {})
        participants = list(roster.get("participants") or [])
        if not participants:
            return BeliefGraphSnapshot(
                event_id=event_id,
                status="empty",
                participant_count=0,
                key_supporters=[],
                key_opponents=[],
                consensus_signals=list(roster.get("blocked_reasons") or []),
                divergence_signals=[],
                nodes=[],
            )

        nodes = [
            BeliefGraphNode(
                participant_id=str(item.get("participant_id") or item.get("participant_family") or "unknown"),
                participant_family=str(item.get("participant_family") or "unknown"),
                stance=str(item.get("stance") or "neutral"),
                authority_weight=float(item.get("authority_weight") or 0.0),
                confidence=float(item.get("confidence") or 0.0),
            )
            for item in participants
        ]
        supporters = [
            node.participant_family
            for node in sorted(nodes, key=lambda item: (-item.authority_weight, -item.confidence))
            if node.stance in _SUPPORTIVE_STANCES
        ]
        opponents = [
            node.participant_family
            for node in sorted(nodes, key=lambda item: (-item.authority_weight, -item.confidence))
            if node.stance in _OPPOSING_STANCES
        ]
        consensus_signals = self._dedupe(
            signal
            for item in participants
            for signal in list(item.get("trigger_conditions") or [])[:2]
        )
        divergence_signals = self._dedupe(
            signal
            for item in participants
            for signal in list(item.get("invalidation_conditions") or [])[:2] + list(item.get("dissent_points") or [])[:1]
        )
        return BeliefGraphSnapshot(
            event_id=event_id,
            status="built",
            participant_count=len(nodes),
            key_supporters=supporters[:3],
            key_opponents=opponents[:3],
            consensus_signals=consensus_signals[:5],
            divergence_signals=divergence_signals[:5],
            nodes=nodes,
        )

    def _dedupe(self, values) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            normalized = str(value).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return ordered
"""

TEST_BELIEF_GRAPH_PY = """from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app import create_app


class BeliefGraphApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_env = {"EVENT_RUNTIME_ROOT": os.environ.get("EVENT_RUNTIME_ROOT")}
        self.runtime_root = Path(self.tempdir.name) / "events"
        os.environ["EVENT_RUNTIME_ROOT"] = str(self.runtime_root)
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.client.close()
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tempdir.cleanup()

    def test_build_belief_graph_from_participant_roster(self) -> None:
        create_response = self.client.post(
            "/api/v1/events",
            json={
                "title": "Lithium price shock",
                "body": "supply shock drives lithium prices higher across the battery chain",
                "source": "manual_text",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        event_id = create_response.json()["event_id"]

        response = self.client.post(f"/api/v1/events/{event_id}/belief-graph")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "built")
        self.assertEqual(payload["participant_count"], 8)
        self.assertGreaterEqual(len(payload["key_supporters"]), 1)
        self.assertGreaterEqual(len(payload["key_opponents"]), 1)

    def test_build_belief_graph_returns_empty_snapshot_when_roster_is_empty(self) -> None:
        casebook_root = self.runtime_root / "casebook"
        casebook_root.mkdir(parents=True, exist_ok=True)
        casebook_root.joinpath("evt-empty.json").write_text(
            json.dumps(
                {
                    "event_id": "evt-empty",
                    "record": {
                        "event_id": "evt-empty",
                        "title": "weak signal",
                        "body": "weak signal",
                        "source": "manual_text",
                        "event_time": "2026-03-25T00:00:00+00:00",
                        "status": "structured",
                    },
                    "structure": {
                        "event_id": "evt-empty",
                        "event_type": "supply_chain_price_shock",
                        "commodities": [],
                        "affected_symbols": [],
                        "monitor_signals": [],
                        "invalidation_conditions": [],
                        "summary": "evidence is still too thin",
                    },
                    "mapping": {"symbols": [], "sector": "", "commodity": ""},
                    "status": "structured",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        response = self.client.post("/api/v1/events/evt-empty/belief-graph")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "empty")
        self.assertEqual(payload["participant_count"], 0)
        self.assertEqual(payload["nodes"], [])


if __name__ == "__main__":
    unittest.main()
"""

E3_001_DELIVERY_MD = """# E3-001 Delivery

- Scope: belief graph schema, aggregation service, command route, container wiring, tests
- Route: `POST /api/v1/events/{event_id}/belief-graph`
- Guarantees:
  - participant roster output can be aggregated into a `BeliefGraphSnapshot`
  - the snapshot records at least `key_supporters` and `key_opponents`
  - the graph payload is ready for downstream scenario-engine consumption
"""

SCENARIO_SCHEMA_PY = """from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ScenarioCase:
    scenario_id: str
    thesis: str
    first_movers: list[str] = field(default_factory=list)
    followers: list[str] = field(default_factory=list)
    watchpoints: list[str] = field(default_factory=list)
    invalidation_conditions: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
"""

SCENARIO_ENGINE_SCHEMA_PY = """from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from schemas.scenario import ScenarioCase


@dataclass(frozen=True, slots=True)
class ScenarioEngineResult:
    event_id: str
    dominant_scenario: str
    graph_status: str
    graph_metrics: dict[str, int | float | str] = field(default_factory=dict)
    scenarios: list[ScenarioCase] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
"""

SCENARIO_ENGINE_SERVICE_PY = """from __future__ import annotations

from domain.belief_graph.service import BeliefGraphError, BeliefGraphService
from schemas.scenario import ScenarioCase
from schemas.scenario_engine import ScenarioEngineResult


class ScenarioEngineError(Exception):
    def __init__(self, *, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ScenarioEngineService:
    def __init__(self, belief_graph: BeliefGraphService) -> None:
        self.belief_graph = belief_graph

    def build_scenarios(self, event_id: str) -> ScenarioEngineResult:
        try:
            snapshot = self.belief_graph.build_snapshot(event_id)
        except BeliefGraphError as exc:
            raise ScenarioEngineError(code=exc.code, message=exc.message, status_code=exc.status_code) from exc

        supporter_count = len(snapshot.key_supporters)
        opponent_count = len(snapshot.key_opponents)
        graph_metrics = {
            "participant_count": snapshot.participant_count,
            "supporter_count": supporter_count,
            "opponent_count": opponent_count,
            "consensus_signal_count": len(snapshot.consensus_signals),
            "divergence_signal_count": len(snapshot.divergence_signals),
            "graph_status": snapshot.status,
        }
        dominant = self._resolve_dominant_scenario(
            supporter_count=supporter_count,
            opponent_count=opponent_count,
            consensus_signal_count=len(snapshot.consensus_signals),
        )
        scenarios = [
            ScenarioCase(
                scenario_id="base",
                thesis="Base case follows the currently strongest confirmed transmission path.",
                first_movers=snapshot.key_supporters[:2],
                followers=snapshot.key_supporters[2:4] or snapshot.key_opponents[:1],
                watchpoints=snapshot.consensus_signals[:3] or ["watch graph confirmation"],
                invalidation_conditions=snapshot.divergence_signals[:3] or ["support breadth fades"],
                confidence=0.58 if snapshot.status == "built" else 0.44,
            ),
            ScenarioCase(
                scenario_id="bull",
                thesis="Bull case assumes supporters stay dominant and the signal broadens.",
                first_movers=snapshot.key_supporters[:2],
                followers=snapshot.key_supporters[2:4],
                watchpoints=(snapshot.consensus_signals[:2] + ["track first-mover expansion"])[:3],
                invalidation_conditions=snapshot.divergence_signals[:2] or ["opponents regain control"],
                confidence=0.72 if dominant == "bull" else 0.46,
            ),
            ScenarioCase(
                scenario_id="bear",
                thesis="Bear case assumes opposition or invalidation signals take control.",
                first_movers=snapshot.key_opponents[:2],
                followers=snapshot.key_opponents[2:4] or snapshot.key_supporters[:1],
                watchpoints=(snapshot.divergence_signals[:2] + ["track failed confirmation"])[:3],
                invalidation_conditions=snapshot.consensus_signals[:2] or ["support breadth re-accelerates"],
                confidence=0.68 if dominant == "bear" else 0.43,
            ),
        ]
        if snapshot.status == "empty":
            scenarios[1] = ScenarioCase(
                scenario_id="bull",
                thesis="Bull case stays constrained until the graph has enough evidence.",
                first_movers=[],
                followers=[],
                watchpoints=snapshot.consensus_signals[:3] or ["wait for stronger participant support"],
                invalidation_conditions=["evidence remains thin"],
                confidence=0.22,
            )
            scenarios[2] = ScenarioCase(
                scenario_id="bear",
                thesis="Bear case stays constrained until the graph shows stronger opposition.",
                first_movers=[],
                followers=[],
                watchpoints=snapshot.consensus_signals[:3] or ["wait for stronger negative confirmation"],
                invalidation_conditions=["evidence remains thin"],
                confidence=0.22,
            )
            dominant = "base"
        return ScenarioEngineResult(
            event_id=event_id,
            dominant_scenario=dominant,
            graph_status=snapshot.status,
            graph_metrics=graph_metrics,
            scenarios=scenarios,
        )

    def _resolve_dominant_scenario(
        self,
        *,
        supporter_count: int,
        opponent_count: int,
        consensus_signal_count: int,
    ) -> str:
        if supporter_count >= opponent_count + 2 and consensus_signal_count >= 1:
            return "bull"
        if opponent_count > supporter_count:
            return "bear"
        return "base"
"""

TEST_SCENARIO_ENGINE_PY = """from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app import create_app


class ScenarioEngineApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_env = {"EVENT_RUNTIME_ROOT": os.environ.get("EVENT_RUNTIME_ROOT")}
        self.runtime_root = Path(self.tempdir.name) / "events"
        os.environ["EVENT_RUNTIME_ROOT"] = str(self.runtime_root)
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.client.close()
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tempdir.cleanup()

    def test_build_three_case_scenarios_from_graph_metrics(self) -> None:
        create_response = self.client.post(
            "/api/v1/events",
            json={
                "title": "Lithium price shock",
                "body": "supply shock drives lithium prices higher across the battery chain",
                "source": "manual_text",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        event_id = create_response.json()["event_id"]

        response = self.client.post(f"/api/v1/events/{event_id}/scenarios")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn(payload["dominant_scenario"], {"base", "bull", "bear"})
        self.assertEqual(len(payload["scenarios"]), 3)
        self.assertIn("supporter_count", payload["graph_metrics"])
        for scenario in payload["scenarios"]:
            self.assertIn("first_movers", scenario)
            self.assertIn("followers", scenario)
            self.assertIn("watchpoints", scenario)
            self.assertIn("invalidation_conditions", scenario)

    def test_build_three_case_scenarios_keeps_constrained_bull_bear_when_evidence_is_thin(self) -> None:
        casebook_root = self.runtime_root / "casebook"
        casebook_root.mkdir(parents=True, exist_ok=True)
        casebook_root.joinpath("evt-slim.json").write_text(
            json.dumps(
                {
                    "event_id": "evt-slim",
                    "record": {
                        "event_id": "evt-slim",
                        "title": "weak signal",
                        "body": "weak signal",
                        "source": "manual_text",
                        "event_time": "2026-03-25T00:00:00+00:00",
                        "status": "structured",
                    },
                    "structure": {
                        "event_id": "evt-slim",
                        "event_type": "supply_chain_price_shock",
                        "commodities": [],
                        "affected_symbols": [],
                        "monitor_signals": [],
                        "invalidation_conditions": [],
                        "summary": "evidence is still too thin",
                    },
                    "mapping": {"symbols": [], "sector": "", "commodity": ""},
                    "status": "structured",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        response = self.client.post("/api/v1/events/evt-slim/scenarios")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["dominant_scenario"], "base")
        bull = next(item for item in payload["scenarios"] if item["scenario_id"] == "bull")
        bear = next(item for item in payload["scenarios"] if item["scenario_id"] == "bear")
        self.assertEqual(bull["first_movers"], [])
        self.assertEqual(bear["first_movers"], [])


if __name__ == "__main__":
    unittest.main()
"""

E3_003_DELIVERY_MD = """# E3-003 Delivery

- Scope: three-case scenario schemas, scenario engine service, command route, container wiring, tests
- Route: `POST /api/v1/events/{event_id}/scenarios`
- Guarantees:
  - `base`, `bull`, and `bear` scenarios all include first movers, followers, watchpoints, and invalidation conditions
  - `dominant_scenario` is derived from explicit graph metrics
  - the scenario engine consumes belief-graph output instead of generating free-form placeholders
"""

EVENT_CARD_PROJECTION_SERVICE_PY = """from __future__ import annotations

from domain.belief_graph.service import BeliefGraphService
from domain.event_casebook.service import EventCasebookService
from domain.scenario_engine.service import ScenarioEngineService
from schemas.event import EventCardReadModel


class EventCardProjectionService:
    def __init__(
        self,
        *,
        casebook_service: EventCasebookService,
        belief_graph: BeliefGraphService,
        scenario_engine: ScenarioEngineService,
    ) -> None:
        self.casebook_service = casebook_service
        self.belief_graph = belief_graph
        self.scenario_engine = scenario_engine

    def present(self, event_id: str) -> EventCardReadModel:
        casebook = self.casebook_service.load_casebook(event_id)
        if casebook is None:
            raise FileNotFoundError(event_id)
        graph_snapshot = self.belief_graph.build_snapshot(event_id)
        scenario_result = self.scenario_engine.build_scenarios(event_id)
        event_summary = str(casebook.structure.get("summary") or casebook.record.get("body") or "").strip()
        participant_summary = self._dedupe(graph_snapshot.key_supporters + graph_snapshot.key_opponents)
        watchpoints = self._dedupe(
            watchpoint
            for scenario in scenario_result.scenarios
            for watchpoint in scenario.watchpoints
        )
        invalidation_conditions = self._dedupe(
            signal
            for scenario in scenario_result.scenarios
            for signal in scenario.invalidation_conditions
        )
        status = "ready" if scenario_result.graph_status != "empty" else "not_ready"
        return EventCardReadModel(
            event_id=event_id,
            status=status,
            event_summary=event_summary,
            participant_summary=participant_summary[:6],
            graph_summary={
                "status": graph_snapshot.status,
                "participant_count": graph_snapshot.participant_count,
                "key_supporters": list(graph_snapshot.key_supporters),
                "key_opponents": list(graph_snapshot.key_opponents),
            },
            scenarios=[scenario.to_dict() for scenario in scenario_result.scenarios],
            watchpoints=watchpoints[:6],
            invalidation_conditions=invalidation_conditions[:6],
        )

    def _dedupe(self, values) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            normalized = str(value).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return ordered
"""

TEST_EVENT_CARDS_PY = """from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app import create_app


class EventCardsApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_env = {"EVENT_RUNTIME_ROOT": os.environ.get("EVENT_RUNTIME_ROOT")}
        self.runtime_root = Path(self.tempdir.name) / "events"
        os.environ["EVENT_RUNTIME_ROOT"] = str(self.runtime_root)
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.client.close()
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tempdir.cleanup()

    def test_event_card_returns_aggregated_read_model(self) -> None:
        create_response = self.client.post(
            "/api/v1/events",
            json={
                "title": "Lithium price shock",
                "body": "supply shock drives lithium prices higher across the battery chain",
                "source": "manual_text",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        event_id = create_response.json()["event_id"]

        response = self.client.get(f"/api/v1/events/{event_id}/card")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ready")
        self.assertIn("graph_summary", payload)
        self.assertEqual(len(payload["scenarios"]), 3)
        self.assertGreaterEqual(len(payload["watchpoints"]), 1)

    def test_event_card_keeps_not_ready_status_when_scenarios_are_not_ready(self) -> None:
        casebook_root = self.runtime_root / "casebook"
        casebook_root.mkdir(parents=True, exist_ok=True)
        casebook_root.joinpath("evt-card-slim.json").write_text(
            json.dumps(
                {
                    "event_id": "evt-card-slim",
                    "record": {
                        "event_id": "evt-card-slim",
                        "title": "weak signal",
                        "body": "weak signal",
                        "source": "manual_text",
                        "event_time": "2026-03-25T00:00:00+00:00",
                        "status": "structured",
                    },
                    "structure": {
                        "event_id": "evt-card-slim",
                        "event_type": "supply_chain_price_shock",
                        "commodities": [],
                        "affected_symbols": [],
                        "monitor_signals": [],
                        "invalidation_conditions": [],
                        "summary": "evidence is still too thin",
                    },
                    "mapping": {"symbols": [], "sector": "", "commodity": ""},
                    "status": "structured",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        response = self.client.get("/api/v1/events/evt-card-slim/card")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "not_ready")


if __name__ == "__main__":
    unittest.main()
"""

E3_005_DELIVERY_MD = """# E3-005 Delivery

- Scope: event-card projection service, query route, container wiring, tests
- Route: `GET /api/v1/events/{event_id}/card`
- Guarantees:
  - the event card aggregates event summary, participant summary, graph summary, three scenarios, watchpoints, and invalidation conditions
  - the card structure is stable enough for later reporting and query reuse
  - unfinished scenarios never masquerade as a ready card
"""

SIMULATION_SCHEMA_PY = """from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SimulationParticipantState:
    participant_id: str
    participant_family: str
    role: str
    stance: str
    authority_weight: float
    confidence: float
    state: str = "ready"
    planned_allocation: float = 0.0
    trigger_signals: list[str] = field(default_factory=list)
    invalidation_signals: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SimulationRoundPlan:
    round_id: str
    order: int
    focus: str
    objective: str
    dominant_scenario: str
    watchpoints: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SimulationRun:
    run_id: str
    event_id: str
    status: str
    graph_status: str
    dominant_scenario: str
    round_count: int
    participant_states: list[SimulationParticipantState] = field(default_factory=list)
    rounds: list[SimulationRoundPlan] = field(default_factory=list)
    watchpoints: list[str] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SimulationPrepareResult:
    event_id: str
    status: str
    simulation_run: dict[str, Any]
    runner_payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
"""

EVENT_SIMULATION_SERVICE_PY = """from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

from domain.belief_graph.service import BeliefGraphError, BeliefGraphService
from domain.event_casebook.service import EventCasebookService
from domain.scenario_engine.service import ScenarioEngineError, ScenarioEngineService
from schemas.simulation import (
    SimulationParticipantState,
    SimulationPrepareResult,
    SimulationRoundPlan,
    SimulationRun,
)


class EventSimulationError(Exception):
    def __init__(self, *, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class EventSimulationService:
    def __init__(
        self,
        *,
        runtime_root: Path,
        casebook_service: EventCasebookService,
        belief_graph: BeliefGraphService,
        scenario_engine: ScenarioEngineService,
    ) -> None:
        self.runtime_root = runtime_root
        self.casebook_service = casebook_service
        self.belief_graph = belief_graph
        self.scenario_engine = scenario_engine
        self.runs_root = runtime_root / "runs"
        self.runs_root.mkdir(parents=True, exist_ok=True)

    def prepare_run(self, event_id: str) -> SimulationPrepareResult:
        casebook = self.casebook_service.load_casebook(event_id)
        if casebook is None:
            raise EventSimulationError(
                code="EVENT_NOT_FOUND",
                message="Event casebook not found.",
                status_code=404,
            )

        try:
            graph_snapshot = self.belief_graph.build_snapshot(event_id)
        except BeliefGraphError as exc:
            raise EventSimulationError(code=exc.code, message=exc.message, status_code=exc.status_code) from exc

        try:
            scenario_result = self.scenario_engine.build_scenarios(event_id)
        except ScenarioEngineError as exc:
            raise EventSimulationError(code=exc.code, message=exc.message, status_code=exc.status_code) from exc

        dominant_scenario = str(scenario_result.dominant_scenario or "").strip()
        if not dominant_scenario:
            raise EventSimulationError(
                code="DOMINANT_SCENARIO_MISSING",
                message="Simulation prepare requires a dominant scenario before execution.",
                status_code=409,
            )

        dominant_case = next(
            (scenario for scenario in scenario_result.scenarios if scenario.scenario_id == dominant_scenario),
            None,
        )
        if dominant_case is None:
            raise EventSimulationError(
                code="SCENARIO_CASE_MISSING",
                message="The dominant scenario could not be resolved from the scenario pack.",
                status_code=409,
            )

        participant_states = self._build_participant_states(
            graph_snapshot=graph_snapshot,
            dominant_scenario=dominant_scenario,
            dominant_case=dominant_case,
        )
        rounds = self._build_rounds(
            dominant_scenario=dominant_scenario,
            watchpoints=list(dominant_case.watchpoints),
            graph_status=scenario_result.graph_status,
        )
        run_id = self._next_run_id(event_id)
        simulation_run = SimulationRun(
            run_id=run_id,
            event_id=event_id,
            status="prepared",
            graph_status=scenario_result.graph_status,
            dominant_scenario=dominant_scenario,
            round_count=len(rounds),
            participant_states=participant_states,
            rounds=rounds,
            watchpoints=list(dominant_case.watchpoints),
            created_at=self._now_iso(),
        )
        self._persist_run(simulation_run)
        runner_payload = {
            "run_id": run_id,
            "event_id": event_id,
            "dominant_scenario": dominant_scenario,
            "graph_status": scenario_result.graph_status,
            "focus_symbols": list(casebook.mapping.get("symbols") or []),
            "participant_states": [state.to_dict() for state in participant_states],
            "rounds": [round_plan.to_dict() for round_plan in rounds],
            "watchpoints": list(dominant_case.watchpoints),
            "invalidation_conditions": list(dominant_case.invalidation_conditions),
        }
        return SimulationPrepareResult(
            event_id=event_id,
            status="prepared",
            simulation_run=simulation_run.to_dict(),
            runner_payload=runner_payload,
        )

    def _build_participant_states(self, *, graph_snapshot, dominant_scenario: str, dominant_case) -> list[SimulationParticipantState]:
        first_movers = set(dominant_case.first_movers)
        followers = set(dominant_case.followers)
        participant_states: list[SimulationParticipantState] = []
        for node in graph_snapshot.nodes:
            role = "risk_watch"
            if node.participant_family in first_movers:
                role = "first_move"
            elif node.participant_family in followers:
                role = "follow_on"
            participant_states.append(
                SimulationParticipantState(
                    participant_id=node.participant_id,
                    participant_family=node.participant_family,
                    role=role,
                    stance=node.stance,
                    authority_weight=node.authority_weight,
                    confidence=node.confidence,
                    state="ready",
                    planned_allocation=self._allocation_for(role, node.authority_weight, node.confidence),
                    trigger_signals=list(graph_snapshot.consensus_signals[:3]),
                    invalidation_signals=list(graph_snapshot.divergence_signals[:3]),
                    reason_codes=[
                        f"scenario:{dominant_scenario}",
                        f"role:{role}",
                        f"stance:{node.stance}",
                    ],
                )
            )
        return participant_states

    def _build_rounds(self, *, dominant_scenario: str, watchpoints: list[str], graph_status: str) -> list[SimulationRoundPlan]:
        round_focus = {
            "base": [
                ("round-1", "Signal Setup", "Establish the opening posture from the dominant path."),
                ("round-2", "Confirmation", "Check whether followers reinforce the first move."),
                ("round-3", "Risk Check", "Stop the run if watchpoints fail to confirm."),
            ],
            "bull": [
                ("round-1", "Ignition", "Track the first movers that should react immediately."),
                ("round-2", "Expansion", "Measure whether follow-on breadth is widening."),
                ("round-3", "Confirmation", "Confirm that the signal remains supported."),
                ("round-4", "Crowding", "Watch for crowding and risk-budget saturation."),
                ("round-5", "Exhaustion", "Check whether the expansion is fading or holding."),
            ],
            "bear": [
                ("round-1", "Defensive Open", "Identify which opponents seize control first."),
                ("round-2", "Pressure", "Measure how quickly invalidation pressure spreads."),
                ("round-3", "Containment", "Check whether supporters can stabilize the path."),
                ("round-4", "Breakdown", "Track where the dominant thesis starts to fail."),
                ("round-5", "Stabilization", "Decide whether the bear path stays in control."),
            ],
        }
        selected = round_focus.get(dominant_scenario, round_focus["base"])
        return [
            SimulationRoundPlan(
                round_id=round_id,
                order=index,
                focus=focus,
                objective=objective,
                dominant_scenario=dominant_scenario,
                watchpoints=watchpoints[:3],
                reason_codes=[
                    f"round:{index}",
                    f"scenario:{dominant_scenario}",
                    f"graph_status:{graph_status}",
                ],
            )
            for index, (round_id, focus, objective) in enumerate(selected, start=1)
        ]

    def _allocation_for(self, role: str, authority_weight: float, confidence: float) -> float:
        base = 0.03
        if role == "first_move":
            base = 0.12
        elif role == "follow_on":
            base = 0.07
        return round(min(0.35, base + authority_weight * 0.12 + confidence * 0.08), 2)

    def _persist_run(self, simulation_run: SimulationRun) -> None:
        target_path = self.runs_root / f"{simulation_run.run_id}.json"
        target_path.write_text(
            json.dumps(asdict(simulation_run), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _next_run_id(self, event_id: str) -> str:
        existing = sorted(self.runs_root.glob(f"{event_id}-run-*.json"))
        return f"{event_id}-run-{len(existing) + 1:03d}"

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
"""

TEST_EVENT_SIMULATION_PY = """from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app import create_app
from schemas.scenario_engine import ScenarioEngineResult


class EventSimulationApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.original_env = {
            "EVENT_RUNTIME_ROOT": os.environ.get("EVENT_RUNTIME_ROOT"),
            "SIMULATION_RUNTIME_ROOT": os.environ.get("SIMULATION_RUNTIME_ROOT"),
        }
        self.runtime_root = Path(self.tempdir.name) / "events"
        self.simulation_root = Path(self.tempdir.name) / "event_simulations"
        os.environ["EVENT_RUNTIME_ROOT"] = str(self.runtime_root)
        os.environ["SIMULATION_RUNTIME_ROOT"] = str(self.simulation_root)
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        self.client.close()
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tempdir.cleanup()

    def test_prepare_simulation_returns_runner_payload_and_persists_run(self) -> None:
        create_response = self.client.post(
            "/api/v1/events",
            json={
                "title": "Lithium price shock",
                "body": "supply shock drives lithium prices higher across the battery chain",
                "source": "manual_text",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        event_id = create_response.json()["event_id"]

        response = self.client.post(f"/api/v1/events/{event_id}/simulation/prepare")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "prepared")
        self.assertEqual(payload["simulation_run"]["status"], "prepared")
        self.assertGreaterEqual(len(payload["simulation_run"]["participant_states"]), 1)
        self.assertGreaterEqual(len(payload["simulation_run"]["rounds"]), 3)
        self.assertEqual(payload["runner_payload"]["run_id"], payload["simulation_run"]["run_id"])
        run_path = self.simulation_root / "runs" / f"{payload['simulation_run']['run_id']}.json"
        self.assertTrue(run_path.exists())
        persisted = json.loads(run_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["event_id"], event_id)

    def test_prepare_simulation_rejects_when_dominant_scenario_is_missing(self) -> None:
        create_response = self.client.post(
            "/api/v1/events",
            json={
                "title": "Lithium price shock",
                "body": "supply shock drives lithium prices higher across the battery chain",
                "source": "manual_text",
            },
        )
        self.assertEqual(create_response.status_code, 200)
        event_id = create_response.json()["event_id"]
        container = self.client.app.state.container
        original_build_scenarios = container.scenario_engine.build_scenarios
        container.scenario_engine.build_scenarios = lambda incoming_event_id: ScenarioEngineResult(
            event_id=incoming_event_id,
            dominant_scenario="",
            graph_status="built",
            graph_metrics={},
            scenarios=[],
        )
        try:
            response = self.client.post(f"/api/v1/events/{event_id}/simulation/prepare")
        finally:
            container.scenario_engine.build_scenarios = original_build_scenarios
        self.assertEqual(response.status_code, 409)
        payload = response.json()
        self.assertEqual(payload["error_code"], "DOMINANT_SCENARIO_MISSING")


if __name__ == "__main__":
    unittest.main()
"""

E4_001_DELIVERY_MD = """# E4-001 Delivery

- Scope: simulation prepare service, simulation schema, command route, container wiring, tests
- Route: `POST /api/v1/events/{event_id}/simulation/prepare`
- Guarantees:
  - a persisted `SimulationRun` seed is created before execution starts
  - each participant receives an initial state and planned role derived from the dominant scenario
  - the returned `runner_payload` is directly consumable by the later simulation runner
"""
