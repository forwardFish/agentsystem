from __future__ import annotations

import json
from pathlib import Path


def materialize_profile_schema_artifacts(repo_b_path: Path, related_files: list[str] | None = None) -> list[str]:
    related_files = list(related_files or [])
    if not related_files:
        related_files = [
            "docs/contracts/trading_agent_profile.schema.json",
            "docs/contracts/examples/trading_agent_profile.example.json",
            "docs/contracts/examples/trading_agent_profile.invalid.json",
        ]

    schema_payload = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "TradingAgentProfile",
        "type": "object",
        "required": [
            "agentId",
            "market",
            "styleTags",
            "preferredUniverse",
            "riskControls",
            "cadence",
            "costModel",
            "decisionPolicy",
            "sourceRuntime",
        ],
        "properties": {
            "agentId": {"type": "string"},
            "market": {"type": "string", "enum": ["CN_A", "US", "CRYPTO"]},
            "styleTags": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "preferredUniverse": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["type", "value"],
                    "properties": {
                        "type": {"type": "string"},
                        "value": {"type": "string"},
                    },
                },
            },
            "riskControls": {
                "type": "object",
                "required": ["maxPositionPct", "maxHoldDays", "maxDailyTurnoverPct"],
                "properties": {
                    "maxPositionPct": {"type": "number"},
                    "maxHoldDays": {"type": "integer"},
                    "maxDailyTurnoverPct": {"type": "number"},
                },
            },
            "cadence": {
                "type": "object",
                "required": ["tradesPerDay", "activeDaysPerWeek"],
                "properties": {
                    "tradesPerDay": {"type": "integer"},
                    "activeDaysPerWeek": {"type": "integer"},
                },
            },
            "costModel": {
                "type": "object",
                "required": ["feePct", "slipPct"],
                "properties": {
                    "feePct": {"type": "number"},
                    "slipPct": {"type": "number"},
                },
            },
            "decisionPolicy": {
                "type": "object",
                "required": ["type", "params"],
                "properties": {
                    "type": {"type": "string"},
                    "params": {"type": "object"},
                },
            },
            "sourceRuntime": {"type": "string"},
            "openclawBinding": {
                "type": "object",
                "properties": {
                    "openclawAgentId": {"type": "string"},
                    "boundAt": {"type": "string", "format": "date-time"},
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    }
    example_payload = {
        "agentId": "agt_123",
        "market": "CN_A",
        "styleTags": ["趋势", "短线", "高换手"],
        "preferredUniverse": [{"type": "symbol", "value": "600519.SH"}],
        "riskControls": {"maxPositionPct": 0.3, "maxHoldDays": 5, "maxDailyTurnoverPct": 0.6},
        "cadence": {"tradesPerDay": 2, "activeDaysPerWeek": 4},
        "costModel": {"feePct": 0.0005, "slipPct": 0.001},
        "decisionPolicy": {"type": "rule_based", "params": {"exitAfterDays": 5}},
        "sourceRuntime": "openclaw",
    }
    invalid_payload = {
        "market": "CN_A",
        "styleTags": [],
        "preferredUniverse": [{"type": "symbol"}],
    }

    return _write_json_artifacts(
        repo_b_path,
        related_files,
        {
            "schema": schema_payload,
            "example": example_payload,
            "invalid": invalid_payload,
        },
    )


def materialize_world_state_schema_artifacts(repo_b_path: Path, related_files: list[str] | None = None) -> list[str]:
    related_files = list(related_files or [])
    if not related_files:
        related_files = [
            "docs/contracts/marketworldstate_schema.schema.json",
            "docs/contracts/examples/marketworldstate_schema.example.json",
            "docs/contracts/examples/marketworldstate_schema.invalid.json",
        ]
    if not any("invalid" in Path(path).name.lower() for path in related_files):
        related_files.append("docs/contracts/examples/marketworldstate_schema.invalid.json")

    schema_payload = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "MarketWorldState",
        "type": "object",
        "required": [
            "worldId",
            "market",
            "tradingDay",
            "nextTradingDay",
            "sessionRules",
            "costModelDefault",
            "universe",
            "prices",
            "dataVersion",
        ],
        "properties": {
            "worldId": {"type": "string"},
            "market": {"type": "string", "enum": ["CN_A", "US", "CRYPTO"]},
            "tradingDay": {"type": "string", "format": "date"},
            "nextTradingDay": {"type": "string", "format": "date"},
            "sessionRules": {
                "type": "object",
                "required": ["fillPrice", "allowShort", "lotSize"],
                "properties": {
                    "fillPrice": {"type": "string"},
                    "allowShort": {"type": "boolean"},
                    "lotSize": {"type": "integer", "minimum": 1},
                },
                "additionalProperties": False,
            },
            "costModelDefault": {
                "type": "object",
                "required": ["feePct", "slipPct"],
                "properties": {
                    "feePct": {"type": "number"},
                    "slipPct": {"type": "number"},
                },
                "additionalProperties": False,
            },
            "universe": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "prices": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "required": ["open", "high", "low", "close", "vol"],
                    "properties": {
                        "open": {"type": "number"},
                        "high": {"type": "number"},
                        "low": {"type": "number"},
                        "close": {"type": "number"},
                        "vol": {"type": "number"},
                    },
                    "additionalProperties": False,
                },
            },
            "marketContext": {"type": "object"},
            "dataVersion": {"type": "string"},
        },
        "additionalProperties": False,
    }
    example_payload = {
        "worldId": "world_cn_a_v2",
        "market": "CN_A",
        "tradingDay": "2026-03-11",
        "nextTradingDay": "2026-03-12",
        "sessionRules": {"fillPrice": "close", "allowShort": False, "lotSize": 100},
        "costModelDefault": {"feePct": 0.0005, "slipPct": 0.001},
        "universe": ["600519.SH", "300750.SZ"],
        "prices": {
            "600519.SH": {"open": 1680.0, "high": 1712.0, "low": 1672.0, "close": 1701.0, "vol": 123456},
            "300750.SZ": {"open": 195.0, "high": 199.8, "low": 193.2, "close": 198.1, "vol": 987654},
        },
        "marketContext": {"index": {"000001.SH": {"close": 3200.1}}},
        "dataVersion": "tushare_daily_20260311",
    }
    invalid_payload = {
        "worldId": "world_cn_a_v2",
        "market": "CN_A",
        "tradingDay": "2026-03-11",
        "sessionRules": {"fillPrice": "close", "allowShort": False},
        "universe": [],
    }

    return _write_json_artifacts(
        repo_b_path,
        related_files,
        {
            "schema": schema_payload,
            "example": example_payload,
            "invalid": invalid_payload,
        },
    )


def materialize_agent_contract_artifacts(repo_b_path: Path, related_files: list[str] | None = None) -> list[str]:
    related_files = list(related_files or [])
    if not related_files:
        related_files = [
            "docs/contracts/agent_register.schema.json",
            "docs/contracts/agent_heartbeat.schema.json",
            "docs/contracts/agent_submit_actions.schema.json",
            "docs/contracts/examples/agent_register.example.json",
            "docs/contracts/examples/agent_heartbeat.example.json",
            "docs/contracts/examples/agent_submit_actions.example.json",
            "docs/contracts/examples/agent_submit_actions.invalid.json",
        ]

    payload_by_name = {
        "agent_register.schema.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "AgentRegisterPayload",
            "type": "object",
            "required": ["agentId", "runtime", "runtimeAgentId", "capabilities"],
            "properties": {
                "agentId": {"type": "string"},
                "runtime": {"type": "string", "enum": ["native", "openclaw"]},
                "runtimeAgentId": {"type": "string"},
                "capabilities": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "metadata": {"type": "object"},
            },
            "additionalProperties": False,
        },
        "agent_heartbeat.schema.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "AgentHeartbeatPayload",
            "type": "object",
            "required": ["agentId", "runtime", "runtimeAgentId", "capabilities", "lastSeenAt", "health"],
            "properties": {
                "agentId": {"type": "string"},
                "runtime": {"type": "string", "enum": ["native", "openclaw"]},
                "runtimeAgentId": {"type": "string"},
                "capabilities": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "lastSeenAt": {"type": "string", "format": "date-time"},
                "health": {
                    "type": "object",
                    "required": ["status", "latencyMs"],
                    "properties": {
                        "status": {"type": "string", "enum": ["ok", "degraded", "error"]},
                        "latencyMs": {"type": "integer", "minimum": 0},
                    },
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        },
        "agent_submit_actions.schema.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "AgentSubmitActionsPayload",
            "type": "object",
            "required": ["agentId", "tradingDay", "actions"],
            "properties": {
                "agentId": {"type": "string"},
                "tradingDay": {"type": "string", "format": "date"},
                "actions": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": ["symbol", "side", "qty", "reason", "idempotency_key"],
                        "properties": {
                            "symbol": {"type": "string"},
                            "side": {"type": "string", "enum": ["buy", "sell"]},
                            "qty": {"type": "integer", "minimum": 1},
                            "reason": {"type": "string", "minLength": 1},
                            "idempotency_key": {"type": "string", "minLength": 1},
                        },
                        "additionalProperties": False,
                    },
                },
            },
            "additionalProperties": False,
        },
        "agent_register.example.json": {
            "agentId": "agt_123",
            "runtime": "openclaw",
            "runtimeAgentId": "main",
            "capabilities": ["plan", "act", "audit"],
            "metadata": {"owner": "demo-user"},
        },
        "agent_heartbeat.example.json": {
            "agentId": "agt_123",
            "runtime": "openclaw",
            "runtimeAgentId": "main",
            "capabilities": ["plan", "act", "audit"],
            "lastSeenAt": "2026-03-13T09:30:00+08:00",
            "health": {"status": "ok", "latencyMs": 120},
        },
        "agent_submit_actions.example.json": {
            "agentId": "agt_123",
            "tradingDay": "2026-03-13",
            "actions": [
                {
                    "symbol": "600519.SH",
                    "side": "buy",
                    "qty": 100,
                    "reason": "close-price breakout",
                    "idempotency_key": "agt_123-20260313-001",
                }
            ],
        },
        "agent_submit_actions.invalid.json": {
            "agentId": "agt_123",
            "tradingDay": "2026-03-13",
            "actions": [
                {
                    "symbol": "600519.SH",
                    "side": "hold",
                    "qty": 0,
                    "reason": "",
                }
            ],
        },
    }

    updated_files: list[str] = []
    for raw_path in related_files:
        path = repo_b_path / raw_path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = payload_by_name.get(path.name)
        if payload is None:
            continue
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        updated_files.append(str(path))
    return updated_files


def materialize_error_state_spec_artifacts(repo_b_path: Path, related_files: list[str] | None = None) -> list[str]:
    related_files = list(related_files or [])
    if not related_files:
        related_files = [
            "docs/contracts/error_codes.md",
            "docs/contracts/state_machine.md",
        ]

    payload_by_name = {
        "error_codes.md": """# Error Codes

## Upload
- `UPLOAD_FILE_TOO_LARGE`: Uploaded statement file exceeds the allowed size limit.
- `UPLOAD_EMPTY_FILE`: Uploaded statement file is empty.
- `UPLOAD_UNSUPPORTED_FORMAT`: Uploaded statement file format is not supported.

## Parsing
- `PARSING_MAPPING_NOT_FOUND`: No broker field mapping rule matched the uploaded statement.
- `PARSING_REQUIRED_FIELD_MISSING`: Required trade field is missing after parsing.
- `PARSING_INVALID_VALUE`: Parsed value cannot be normalized into the canonical trade record.

## Risk
- `RISK_MAX_POSITION_EXCEEDED`: Action would exceed the configured max position percentage.
- `RISK_MAX_HOLD_DAYS_EXCEEDED`: Position exceeds the allowed holding horizon.
- `RISK_TURNOVER_LIMIT_EXCEEDED`: Daily turnover would exceed the configured limit.

## Matching
- `MATCHING_PRICE_NOT_AVAILABLE`: No market price is available for the requested trading day.
- `MATCHING_LOT_SIZE_INVALID`: Submitted quantity does not satisfy the market lot size.
- `MATCHING_SHORT_NOT_ALLOWED`: Submitted sell action would require short selling in a market that forbids it.

## Permission
- `PERMISSION_PRIVATE_AGENT_READ_ONLY`: Human viewers cannot write to a private agent runtime.
- `PERMISSION_INVALID_AGENT_KEY`: Submitted agent API key is invalid or revoked.
- `PERMISSION_SCOPE_DENIED`: Caller attempted an operation outside the granted scope.
""",
        "state_machine.md": """# State Machine

## Statement
- `uploaded` -> `parsing`
- `parsing` -> `parsed`
- `parsing` -> `failed`

## Agent
- `active` -> `paused`
- `active` -> `stale`
- `paused` -> `active`
- `stale` -> `active`
- `active` -> `banned`

## Order
- `submitted` -> `rejected`
- `submitted` -> `filled`

## Binding
- `pending` -> `active`
- `active` -> `revoked`
- `active` -> `expired`
""",
    }

    updated_files: list[str] = []
    for raw_path in related_files:
        path = repo_b_path / raw_path
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = payload_by_name.get(path.name)
        if payload is None:
            continue
        path.write_text(payload if payload.endswith("\n") else payload + "\n", encoding="utf-8")
        updated_files.append(str(path))
    return updated_files


def _write_json_artifacts(repo_b_path: Path, related_files: list[str], payload_map: dict[str, object]) -> list[str]:
    updated_files: list[str] = []
    for raw_path in related_files:
        path = repo_b_path / raw_path
        path.parent.mkdir(parents=True, exist_ok=True)
        lowered = path.name.lower()
        if "invalid" in lowered:
            payload = payload_map["invalid"]
        elif "example" in lowered:
            payload = payload_map["example"]
        else:
            payload = payload_map["schema"]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        updated_files.append(str(path))
    return updated_files
