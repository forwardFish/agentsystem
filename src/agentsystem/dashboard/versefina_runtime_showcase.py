from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any


def load_versefina_runtime_showcase_data(
    runtime_root: Path,
    tasks_dir: Path,
    story_status_registry: Path,
    story_acceptance_review_registry: Path,
) -> dict[str, Any]:
    runtime_data = _load_runtime_data(runtime_root)
    validation_packs = _load_validation_packs(runtime_root)
    bundle = _build_evidence_bundle(runtime_data, validation_packs)
    registry_by_story = {
        str(entry.get("story_id")): entry
        for entry in _load_story_status_registry(story_status_registry)
        if str(entry.get("story_id") or "").startswith(("S1-", "S2-"))
    }
    reviews = _load_story_acceptance_reviews(story_acceptance_review_registry)
    review_index = {
        (str(item.get("backlog_id")), str(item.get("sprint_id")), str(item.get("story_id"))): item
        for item in reviews
    }

    sprint_groups = [
        {
            "sprint_id": "sprint_1_statement_to_agent",
            "title": "Sprint 1 交割单到 Agent",
            "summary": "当前已经能看到真实上传、解析、画像生成和 Agent 创建产物。",
            "stories": _build_story_cards(
                backlog_id="backlog_v1",
                sprint_id="sprint_1_statement_to_agent",
                tasks_dir=tasks_dir,
                registry_by_story=registry_by_story,
                review_index=review_index,
                bundle=bundle,
            ),
        },
        {
            "sprint_id": "sprint_2_world_ledger_loop",
            "title": "Sprint 2 世界与账本",
            "summary": "市场世界已有真实缓存与 world snapshot，模拟账本链路目前仍以合同和占位实现为主。",
            "stories": _build_story_cards(
                backlog_id="backlog_v1",
                sprint_id="sprint_2_world_ledger_loop",
                tasks_dir=tasks_dir,
                registry_by_story=registry_by_story,
                review_index=review_index,
                bundle=bundle,
            ),
        },
    ]
    all_story_cards = [story for group in sprint_groups for story in group["stories"]]

    return {
        "runtime_root": str(runtime_root),
        "sample_ids": {
            "statement_id": (bundle.get("current_statement") or {}).get("statement_id"),
            "agent_id": (bundle.get("current_agent") or {}).get("agent_id"),
            "world_id": (bundle.get("current_calendar") or {}).get("world_id"),
        },
        "stats": {
            "statement_count": len(runtime_data.get("statement_meta") or []),
            "parse_report_count": len(runtime_data.get("parse_reports") or []),
            "trade_record_file_count": len(runtime_data.get("trade_records") or []),
            "trade_record_count": sum(int(item.get("record_count") or 0) for item in runtime_data.get("trade_records") or []),
            "profile_count": len(runtime_data.get("agent_profiles") or []),
            "agent_count": len(runtime_data.get("agents") or []),
            "market_world_count": len(runtime_data.get("market_world") or []),
            "registry_done_story_count": sum(1 for story in all_story_cards if story.get("status") == "done"),
            "real_evidence_story_count": sum(1 for story in all_story_cards if story.get("evidence_status") == "real"),
            "placeholder_story_count": sum(1 for story in all_story_cards if story.get("evidence_status") == "placeholder"),
            "registry_only_story_count": sum(1 for story in all_story_cards if story.get("evidence_status") == "registry_only"),
            "missing_story_count": sum(1 for story in all_story_cards if story.get("evidence_status") == "missing"),
        },
        "acceptance_lines": _build_acceptance_lines(bundle),
        "pipeline": _build_pipeline(runtime_data),
        "artifact_samples": _build_artifact_samples(bundle),
        "validation_packs": validation_packs,
        "story_groups": sprint_groups,
        "evidence_notes": _build_evidence_notes(all_story_cards, bundle),
    }


def _load_runtime_data(runtime_root: Path) -> dict[str, Any]:
    return {
        "statement_meta": _load_json_object_records(runtime_root / "statement_meta"),
        "parse_reports": _load_json_object_records(runtime_root / "statement_parse_reports"),
        "trade_records": _load_json_list_records(runtime_root / "trade_records"),
        "agent_profiles": _load_json_object_records(runtime_root / "agent_profiles"),
        "agents": _load_json_object_records(runtime_root / "agents"),
        "market_world": _load_json_object_records(runtime_root / "market_world"),
    }


def _load_json_object_records(directory: Path) -> list[dict[str, Any]]:
    if not directory.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        payload = _read_json_file(path)
        if isinstance(payload, dict):
            record = dict(payload)
            record["_artifact_path"] = str(path)
            record["_artifact_file"] = path.name
            records.append(record)
    return records


def _load_json_list_records(directory: Path) -> list[dict[str, Any]]:
    if not directory.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        payload = _read_json_file(path)
        if isinstance(payload, list):
            records.append(
                {
                    "statement_id": path.stem,
                    "record_count": len(payload),
                    "sample": payload[0] if payload else None,
                    "_artifact_path": str(path),
                    "_artifact_file": path.name,
                }
            )
    return records


def _load_validation_packs(runtime_root: Path) -> list[dict[str, Any]]:
    if not runtime_root.exists():
        return []
    packs: list[dict[str, Any]] = []
    for pack_dir in sorted((item for item in runtime_root.iterdir() if item.is_dir() and item.name.startswith("live_")), key=lambda item: item.stat().st_mtime, reverse=True):
        pack_data = _load_runtime_data(pack_dir)
        statement_sample = _first_record(pack_data["statement_meta"])
        parse_report_sample = _matching_record(pack_data["parse_reports"], (statement_sample or {}).get("statement_id"))
        trade_record_sample = _matching_trade_record(pack_data["trade_records"], (statement_sample or {}).get("statement_id"))
        profile_sample = _matching_record(pack_data["agent_profiles"], (statement_sample or {}).get("statement_id"))
        agent_sample = _matching_agent(pack_data["agents"], (statement_sample or {}).get("statement_id"))
        packs.append(
            {
                "pack_id": pack_dir.name,
                "label": _label_for_pack(pack_dir.name),
                "artifact_dir": str(pack_dir),
                "focus_story_ids": _focus_story_ids_for_pack(pack_dir.name),
                "statement_count": len(pack_data["statement_meta"]),
                "parse_report_count": len(pack_data["parse_reports"]),
                "trade_record_file_count": len(pack_data["trade_records"]),
                "profile_count": len(pack_data["agent_profiles"]),
                "agent_count": len(pack_data["agents"]),
                "input_sample": statement_sample,
                "output_sample": agent_sample or profile_sample or parse_report_sample or statement_sample,
                "samples": {
                    "statement_meta": statement_sample,
                    "parse_report": parse_report_sample,
                    "trade_record": trade_record_sample,
                    "profile": profile_sample,
                    "agent": agent_sample,
                },
            }
        )
    return packs


def _build_evidence_bundle(runtime_data: dict[str, Any], validation_packs: list[dict[str, Any]]) -> dict[str, Any]:
    current_statement = _first_record(runtime_data.get("statement_meta") or [])
    statement_id = (current_statement or {}).get("statement_id")
    current_parse_report = _matching_record(runtime_data.get("parse_reports") or [], statement_id)
    current_trade_record = _matching_trade_record(runtime_data.get("trade_records") or [], statement_id)
    current_profile = _matching_record(runtime_data.get("agent_profiles") or [], statement_id)
    current_agent = _matching_agent(runtime_data.get("agents") or [], statement_id)
    current_calendar = _first_record(runtime_data.get("market_world") or [])
    current_world_snapshot = _build_world_snapshot(current_calendar, len(runtime_data.get("agents") or []))
    packs_by_id = {str(pack.get("pack_id")): pack for pack in validation_packs}
    return {
        "packs_by_id": packs_by_id,
        "current_statement": current_statement,
        "current_parse_report": current_parse_report,
        "current_trade_record": current_trade_record,
        "current_profile": current_profile,
        "current_agent": current_agent,
        "current_calendar": current_calendar,
        "current_world_snapshot": current_world_snapshot,
        "placeholder_samples": _build_placeholder_samples(current_agent, current_world_snapshot),
    }


def _build_world_snapshot(calendar_record: dict[str, Any] | None, agent_count: int) -> dict[str, Any] | None:
    if not calendar_record:
        return None
    trading_days = list(calendar_record.get("trading_days") or [])
    today = date.today().isoformat()
    trading_day = next((item for item in trading_days if item == today), None)
    next_trading_day = next((item for item in trading_days if item > today), None)
    if trading_day is None:
        past_days = [item for item in trading_days if item <= today]
        trading_day = past_days[-1] if past_days else (trading_days[0] if trading_days else None)
    return {
        "world_id": calendar_record.get("world_id"),
        "market": calendar_record.get("market"),
        "trading_day": trading_day,
        "next_trading_day": next_trading_day,
        "available_trading_days": trading_days[:10],
        "total_agents": agent_count,
        "source": calendar_record.get("source"),
    }


def _build_placeholder_samples(current_agent: dict[str, Any] | None, world_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    agent_id = (current_agent or {}).get("agent_id") or "agt_demo"
    trading_day = (world_snapshot or {}).get("trading_day") or "2026-03-16"
    return {
        "actions_payload": {
            "agent_id": agent_id,
            "trading_day": trading_day,
            "actions": [{"symbol": "600519.SH", "side": "BUY", "qty": 100}],
        },
        "submit_actions": {"status": "accepted", "task_id": f"actions::{agent_id}"},
        "trade_log": {"agent_id": agent_id, "items": [{"symbol": "600519.SH", "side": "BUY", "qty": "100"}]},
        "equity_curve": {"agent_id": agent_id, "points": [{"trading_day": "2026-03-12", "equity": "1000000"}]},
    }


def _build_acceptance_lines(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "key": "sprint_1",
            "title": "Sprint 1 主链",
            "summary": "交割单上传 -> 解析 -> 画像 -> Agent 创建",
            "input_label": "上传输入样本",
            "input_sample": _subset(
                bundle.get("current_statement"),
                ["statement_id", "owner_id", "market", "file_name", "content_type", "byte_size", "object_key"],
            ),
            "output_label": "Agent 输出样本",
            "output_sample": _subset(
                bundle.get("current_agent"),
                ["agent_id", "statement_id", "world_id", "status", "init_cash", "cash", "equity", "profile_path", "public_url"],
            ),
        },
        {
            "key": "sprint_2",
            "title": "Sprint 2 当前世界状态",
            "summary": "市场世界日历缓存与当前 world snapshot",
            "input_label": "日历同步结果样本",
            "input_sample": _subset(bundle.get("current_calendar"), ["world_id", "market", "start_date", "end_date", "source", "synced_at", "_artifact_path"]),
            "output_label": "World Snapshot 样本",
            "output_sample": bundle.get("current_world_snapshot"),
        },
    ]


def _build_pipeline(runtime_data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"stage": "statement_meta", "label": "交割单元数据", "count": len(runtime_data.get("statement_meta") or []), "mode": "real"},
        {"stage": "parse_reports", "label": "解析报告", "count": len(runtime_data.get("parse_reports") or []), "mode": "real"},
        {"stage": "trade_records", "label": "标准化成交记录", "count": len(runtime_data.get("trade_records") or []), "mode": "real"},
        {"stage": "agent_profiles", "label": "交易画像", "count": len(runtime_data.get("agent_profiles") or []), "mode": "real"},
        {"stage": "agents", "label": "Agent 注册记录", "count": len(runtime_data.get("agents") or []), "mode": "real"},
        {"stage": "market_world", "label": "市场世界缓存", "count": len(runtime_data.get("market_world") or []), "mode": "real"},
        {"stage": "simulation_ledger", "label": "模拟账本链路", "count": 0, "mode": "placeholder"},
    ]


def _build_artifact_samples(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    placeholders = bundle.get("placeholder_samples") or {}
    return [
        {"label": "当前交割单元数据", "artifact_type": "statement_meta", "status": "real", "path": (bundle.get("current_statement") or {}).get("_artifact_path"), "sample": bundle.get("current_statement")},
        {"label": "当前解析报告", "artifact_type": "parse_report", "status": "real", "path": (bundle.get("current_parse_report") or {}).get("_artifact_path"), "sample": bundle.get("current_parse_report")},
        {"label": "当前标准化成交记录", "artifact_type": "trade_record", "status": "real", "path": (bundle.get("current_trade_record") or {}).get("_artifact_path"), "sample": bundle.get("current_trade_record")},
        {"label": "当前交易画像", "artifact_type": "profile", "status": "real", "path": (bundle.get("current_profile") or {}).get("_artifact_path"), "sample": bundle.get("current_profile")},
        {"label": "当前 Agent 记录", "artifact_type": "agent", "status": "real", "path": (bundle.get("current_agent") or {}).get("_artifact_path"), "sample": bundle.get("current_agent")},
        {"label": "当前市场世界缓存", "artifact_type": "market_world", "status": "real", "path": (bundle.get("current_calendar") or {}).get("_artifact_path"), "sample": bundle.get("current_calendar")},
        {"label": "当前 world snapshot", "artifact_type": "world_snapshot", "status": "real", "path": None, "sample": bundle.get("current_world_snapshot")},
        {"label": "当前 actions 提交返回（占位实现）", "artifact_type": "submit_actions", "status": "placeholder", "path": None, "sample": placeholders.get("submit_actions")},
        {"label": "当前 trades 查询返回（占位实现）", "artifact_type": "trade_log", "status": "placeholder", "path": None, "sample": placeholders.get("trade_log")},
        {"label": "当前 equity 查询返回（占位实现）", "artifact_type": "equity_curve", "status": "placeholder", "path": None, "sample": placeholders.get("equity_curve")},
    ]


def _build_evidence_notes(all_story_cards: list[dict[str, Any]], bundle: dict[str, Any]) -> list[str]:
    notes = [
        f"当前验收页总共展示 {len(all_story_cards)} 条 Versefina Story。",
        f"其中有真实 artifact 证据的 Story 数量是 {sum(1 for item in all_story_cards if item.get('evidence_status') == 'real')}。",
        "Sprint 1 的真实证据链已经覆盖上传、解析、TradeRecord 标准化、Profile 生成和 Agent 创建。",
        "Sprint 2 目前最完整的真实证据是市场世界日历缓存与 world snapshot；simulation ledger 相关链路仍是占位或缺证据状态。",
    ]
    if not bundle.get("current_statement"):
        notes.append("当前 .runtime 中没有找到可展示的 statement 元数据。")
    if not bundle.get("current_calendar"):
        notes.append("当前 .runtime 中没有找到 market world 缓存文件。")
    return notes


def _build_story_cards(
    backlog_id: str,
    sprint_id: str,
    tasks_dir: Path,
    registry_by_story: dict[str, dict[str, Any]],
    review_index: dict[tuple[str, str, str], dict[str, Any]],
    bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    sprint_dir = tasks_dir / backlog_id / sprint_id
    if not sprint_dir.exists():
        return []
    cards: list[dict[str, Any]] = []
    for story_file in sorted(sprint_dir.rglob("S*.yaml")):
        spec = _yaml_safe_load(story_file)
        story_id = str(spec.get("story_id") or spec.get("task_id") or "")
        registry_entry = registry_by_story.get(story_id, {})
        evidence = _story_evidence(story_id, bundle, registry_entry)
        review = review_index.get((backlog_id, sprint_id, story_id))
        completion = {
            "acceptance_passed": registry_entry.get("status") == "done",
            "tests_passed": registry_entry.get("status") == "done",
            "review_passed": registry_entry.get("status") == "done",
            "code_acceptance_passed": registry_entry.get("status") == "done",
        }
        cards.append(
            {
                "story_id": story_id,
                "task_name": spec.get("task_name") or story_id,
                "status": registry_entry.get("status") or "not_started",
                "registry_summary": registry_entry.get("summary") or registry_entry.get("validation_summary") or "",
                "registry_evidence": registry_entry.get("evidence") or [],
                "story_inputs": spec.get("story_inputs") or [],
                "story_process": spec.get("story_process") or [],
                "story_outputs": spec.get("story_outputs") or [],
                "verification_basis": spec.get("verification_basis") or [],
                "acceptance_criteria": spec.get("acceptance_criteria") or [],
                "input_label": evidence.get("input_label"),
                "input_sample": evidence.get("input_sample"),
                "input_count": evidence.get("input_count"),
                "output_label": evidence.get("output_label"),
                "output_sample": evidence.get("output_sample"),
                "output_count": evidence.get("output_count"),
                "evidence_status": evidence.get("evidence_status"),
                "evidence_note": evidence.get("evidence_note"),
                "validation_hint": evidence.get("validation_hint"),
                "human_review": review,
                "acceptance_template": _build_acceptance_template(spec, completion, review),
            }
        )
    return cards


def _story_evidence(story_id: str, bundle: dict[str, Any], registry_entry: dict[str, Any]) -> dict[str, Any]:
    current_statement = bundle.get("current_statement")
    current_parse_report = bundle.get("current_parse_report")
    current_trade_record = bundle.get("current_trade_record")
    current_profile = bundle.get("current_profile")
    current_agent = bundle.get("current_agent")
    current_calendar = bundle.get("current_calendar")
    current_world_snapshot = bundle.get("current_world_snapshot")
    placeholders = bundle.get("placeholder_samples") or {}
    packs = bundle.get("packs_by_id") or {}
    upload_pack = packs.get("live_upload_check") or packs.get("live_upload_check_s1_004") or {}
    parse_pack = packs.get("live_parse_check") or {}
    parse_pack_en = packs.get("live_parse_check_en") or {}

    registry_summary = registry_entry.get("summary") or registry_entry.get("validation_summary") or ""
    registry_note = f"业务验证登记：{registry_summary}" if registry_summary else "当前没有单独的业务验证登记。"

    if story_id == "S1-001":
        return _evidence("上传文件与表单参数", _subset(upload_pack.get("input_sample") or current_statement, ["statement_id", "owner_id", "market", "file_name", "content_type", "byte_size"]), "statement 元数据", _subset(current_statement, ["statement_id", "upload_status", "object_key", "bucket", "created_at", "_artifact_path"]), "real" if current_statement else "missing", "当前 .runtime 已保留真实上传后的 statement 元数据与对象存储路径。", "检查 statement_id、upload_status、object_key 是否能对应到 object_store 里的实际文件。")
    if story_id == "S1-002":
        return _evidence("状态流转请求", {"statement_id": (current_statement or {}).get("statement_id"), "next_status": "uploaded -> parsing -> parsed"}, "当前状态元数据", _subset(current_statement, ["statement_id", "upload_status", "error_code", "error_message", "updated_at"]), "registry_only" if registry_entry else "missing", f"{registry_note} 当前 runtime 只保留最终状态，没有保留完整流转历史样本。", "结合 story_status_registry 与当前 statement 元数据确认状态机行为。")
    if story_id == "S1-003":
        return _evidence("文件类型识别输入", _subset(current_statement, ["file_name", "content_type", "byte_size"]), "文件类型识别结果", _subset(current_statement, ["statement_id", "detected_file_type", "parser_key", "content_type"]), "real" if current_statement else "missing", "当前 statement 元数据里已经保留 detected_file_type 与 parser_key。", "检查 file_name、content_type、detected_file_type 和 parser_key 是否一致。")
    if story_id == "S1-004":
        return _evidence("失败路径样本", _subset(upload_pack.get("input_sample"), ["file_name", "content_type", "byte_size"]), "失败处理结果", None, "registry_only" if registry_entry else "missing", f"{registry_note} 当前 runtime 没有保留失败响应样本。", "如需强验收，后续建议把失败响应样本一并落盘。")
    if story_id == "S1-005":
        return _evidence("解析映射输入", _subset(parse_pack.get("input_sample") or parse_pack_en.get("input_sample") or current_statement, ["statement_id", "file_name", "detected_file_type", "parser_key"]), "映射与券商识别结果", _subset(current_parse_report, ["statement_id", "broker", "detected_file_type", "parser_key"]), "real" if current_parse_report else "missing", "当前解析报告里已经保留 broker、detected_file_type 和 parser_key。", "检查中文、英文样本目录的解析报告是否都能映射出正确 broker。")
    if story_id == "S1-006":
        return _evidence("解析结果输入", _subset(current_parse_report, ["statement_id", "broker", "parsed_records", "failed_records"]), "标准化 TradeRecord", current_trade_record, "real" if current_trade_record else "missing", "当前 .runtime/trade_records 已落盘标准化 TradeRecord 文件。", "检查第一条标准化 TradeRecord 的 symbol、side、qty、price、fee、tax 是否已统一。")
    if story_id == "S1-007":
        return _evidence("待校验解析上下文", _subset(current_statement, ["statement_id", "upload_status", "parser_key", "error_code"]), "解析校验报告", current_parse_report, "real" if current_parse_report else "missing", "当前解析报告里保留了 parsed_records、failed_records、issues 和 trade_record_path。", "检查 parse report 是否足以单独判断解析成功或失败。")
    if story_id == "S1-008":
        return _evidence("TradeRecord 输入样本", current_trade_record, "规则版画像输出", current_profile, "real" if current_profile else "missing", "当前 .runtime/agent_profiles 已保留规则版画像结果。", "检查画像里 preferredUniverse、cadence 和 sourceRuntime 是否来自当前 TradeRecord 数据。")
    if story_id == "S1-009":
        return _evidence("画像增强输入", _subset(current_profile, ["statement_id", "market", "preferredUniverse", "cadence"]), "风格标签与风控约束", _subset(current_profile, ["styleTags", "riskControls", "costModel", "decisionPolicy"]), "real" if current_profile else "missing", "当前画像文件里已经能看到 styleTags、riskControls、costModel 和 decisionPolicy。", "检查 styleTags 与 riskControls 是否直接体现在 persisted TradingAgentProfile 里。")
    if story_id == "S1-010":
        return _evidence("Agent 创建输入", {"statement_id": (current_agent or {}).get("statement_id"), "init_cash": (current_agent or {}).get("init_cash"), "profile_path": (current_agent or {}).get("profile_path")}, "Agent 创建结果", current_agent, "real" if current_agent else "missing", "当前 .runtime/agents 已保留真实 Agent 记录，并能回链 profile_path。", "检查 agent_id、profile_path、public_url 和 statement_id 是否一致。")
    if story_id == "S2-001":
        return _evidence("交易日历同步输入", _subset(current_calendar, ["world_id", "market", "start_date", "end_date", "source"]), "交易日历缓存", current_calendar, "real" if current_calendar else "missing", "当前 .runtime/market_world 已落盘交易日历缓存。", "检查 trading_days、closed_days 和 synced_at 是否真实存在于缓存文件中。")
    if story_id == "S2-002":
        return _evidence("交易日推进输入", _subset(current_calendar, ["trading_days", "closed_days"]), "当前 world snapshot", current_world_snapshot, "real" if current_world_snapshot else "missing", "当前 world snapshot 由真实交易日历缓存推导而来。", "检查 trading_day 和 next_trading_day 是否与 trading_days 序列一致。")
    if story_id in {"S2-003", "S2-004"}:
        return _evidence("市场数据输入", _subset(current_calendar, ["world_id", "market", "trading_days"]), "行情产物", None, "missing", "当前 .runtime 里没有发现日线行情文件、行情缓存版本或对应 artifact。", "如果这部分要算完成，需要补充真实行情文件或可回放缓存。")
    if story_id == "S2-005":
        return _evidence("actions 提交输入", placeholders.get("actions_payload"), "当前提交返回", placeholders.get("submit_actions"), "placeholder", "当前 submit_actions 只返回 accepted/task_id，占位实现尚未进入真实账本链路。", "这里只能验证接口形状，不能证明 action payload 已被真实校验或执行。")
    if story_id in {"S2-006", "S2-007", "S2-008", "S2-009", "S2-010", "S2-012", "S2-013", "S2-014", "S2-015", "S2-016", "S2-017"}:
        return _evidence("计划输入样本", placeholders.get("actions_payload"), "当前输出证据", None, "missing", "当前没有发现可证明这条 story 已真实运行完成的 artifact 或结果报告样本。", "当前只能看 story 合同，不能通过 runtime 结果验收。")
    if story_id == "S2-011":
        return _evidence("仓位更新输入", _subset(current_agent, ["agent_id", "cash", "equity", "positions"]), "当前 trades/equity 查询返回", {"trades": placeholders.get("trade_log"), "equity": placeholders.get("equity_curve")}, "placeholder", "当前 trades/equity 查询仍是固定占位返回，不能证明 positions 已真实更新。", "检查页面能看到占位输出即可，但这不应视为账本链路已完成。")
    return _evidence("计划输入", None, "计划输出", None, "missing", "当前没有找到这条 story 的展示映射。", "需要补充 story 与实际 artifact 的映射关系。")


def _evidence(
    input_label: str,
    input_sample: Any,
    output_label: str,
    output_sample: Any,
    evidence_status: str,
    evidence_note: str,
    validation_hint: str,
) -> dict[str, Any]:
    return {
        "input_label": input_label,
        "input_sample": input_sample,
        "input_count": _sample_count(input_sample),
        "output_label": output_label,
        "output_sample": output_sample,
        "output_count": _sample_count(output_sample),
        "evidence_status": evidence_status,
        "evidence_note": evidence_note,
        "validation_hint": validation_hint,
    }


def _sample_count(sample: Any) -> int:
    if sample is None:
        return 0
    if isinstance(sample, list):
        return len(sample)
    if isinstance(sample, dict):
        if isinstance(sample.get("record_count"), int):
            return int(sample["record_count"])
        if isinstance(sample.get("actions"), list):
            return len(sample["actions"])
        return 1
    return 1


def _build_acceptance_template(story_payload: dict[str, Any], completion: dict[str, Any], human_review: dict[str, Any] | None) -> dict[str, Any]:
    automation_status = "passed" if completion.get("acceptance_passed") else "needs_attention" if any(completion.get(key) is False for key in ("tests_passed", "review_passed", "code_acceptance_passed")) else "pending"
    verdict = str((human_review or {}).get("verdict") or "pending_signoff")
    return {
        "template_version": "v1",
        "automation_status": automation_status,
        "human_signoff_status": verdict,
        "cards": [
            {"key": "input_review", "title": "1. 输入检查", "items": list(story_payload.get("story_inputs") or []), "status": "ready" if story_payload.get("story_inputs") else "missing"},
            {"key": "process_review", "title": "2. 过程检查", "items": list(story_payload.get("story_process") or []), "status": "ready" if story_payload.get("story_process") else "missing"},
            {"key": "output_review", "title": "3. 输出检查", "items": list(story_payload.get("story_outputs") or []), "status": "ready" if story_payload.get("story_outputs") else "missing"},
            {"key": "verification_review", "title": "4. 验收依据检查", "items": list(story_payload.get("verification_basis") or []) + list(story_payload.get("acceptance_criteria") or []), "status": "ready" if story_payload.get("verification_basis") else "missing"},
            {"key": "human_signoff", "title": "5. 人工签收", "items": [f"自动化验收状态：{automation_status}", f"当前人工结论：{verdict}"], "status": verdict if verdict != "pending_signoff" else "pending_signoff"},
        ],
    }


def _yaml_safe_load(path: Path) -> dict[str, Any]:
    try:
        import yaml

        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_story_status_registry(path: Path) -> list[dict[str, Any]]:
    payload = _read_json_file(path)
    entries = payload.get("stories") if isinstance(payload, dict) else []
    return entries if isinstance(entries, list) else []


def _load_story_acceptance_reviews(path: Path) -> list[dict[str, Any]]:
    payload = _read_json_file(path)
    entries = payload.get("reviews") if isinstance(payload, dict) else []
    return entries if isinstance(entries, list) else []


def _read_json_file(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _first_record(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    for record in records:
        if record:
            return record
    return None


def _matching_record(records: list[dict[str, Any]], statement_id: Any) -> dict[str, Any] | None:
    for record in records:
        if statement_id and record.get("statement_id") == statement_id:
            return record
    return _first_record(records)


def _matching_trade_record(records: list[dict[str, Any]], statement_id: Any) -> dict[str, Any] | None:
    for record in records:
        if statement_id and record.get("statement_id") == statement_id:
            return record
    return _first_record(records)


def _matching_agent(records: list[dict[str, Any]], statement_id: Any) -> dict[str, Any] | None:
    for record in records:
        if statement_id and record.get("statement_id") == statement_id:
            return record
    return _first_record(records)


def _subset(record: dict[str, Any] | None, keys: list[str]) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    subset = {key: record.get(key) for key in keys if key in record}
    return subset or None


def _label_for_pack(pack_id: str) -> str:
    labels = {
        "live_upload_check": "上传链路样本",
        "live_upload_check_s1_004": "上传失败处理样本",
        "live_upload_check_debug": "上传调试样本",
        "live_parse_check": "中文解析样本",
        "live_parse_check_en": "英文解析样本",
        "live_agent_creation_check": "Agent 创建样本",
    }
    return labels.get(pack_id, pack_id)


def _focus_story_ids_for_pack(pack_id: str) -> list[str]:
    mapping = {
        "live_upload_check": ["S1-001", "S1-003"],
        "live_upload_check_s1_004": ["S1-004"],
        "live_upload_check_debug": ["S1-004"],
        "live_parse_check": ["S1-005", "S1-006", "S1-007"],
        "live_parse_check_en": ["S1-005", "S1-006", "S1-007"],
        "live_agent_creation_check": ["S1-008", "S1-009", "S1-010"],
    }
    return mapping.get(pack_id, [])
