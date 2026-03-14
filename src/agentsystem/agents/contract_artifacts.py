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


def materialize_core_db_schema_artifacts(repo_b_path: Path, related_files: list[str] | None = None) -> list[str]:
    related_files = list(related_files or [])
    if not related_files:
        related_files = [
            "scripts/init_schema.sql",
        ]

    sql_payload = """-- Core write-model schema for Sprint 0 / S0-005
BEGIN;

CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    world_id TEXT NOT NULL,
    source_runtime TEXT NOT NULL,
    status TEXT NOT NULL,
    trust_level TEXT DEFAULT 'standard',
    dna_version TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_heartbeat_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS statements (
    statement_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    market TEXT NOT NULL,
    object_key TEXT,
    parsed_status TEXT NOT NULL,
    broker_hint TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trade_records (
    record_id TEXT PRIMARY KEY,
    statement_id TEXT NOT NULL REFERENCES statements(statement_id),
    ts TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    qty NUMERIC(18, 4) NOT NULL,
    price NUMERIC(18, 6) NOT NULL,
    fee NUMERIC(18, 6) NOT NULL DEFAULT 0,
    tax NUMERIC(18, 6) NOT NULL DEFAULT 0,
    raw_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_profiles (
    agent_id TEXT PRIMARY KEY REFERENCES agents(agent_id),
    profile_json JSONB NOT NULL,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    risk_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    universe_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS world_snapshots (
    world_id TEXT NOT NULL,
    trading_day DATE NOT NULL,
    snapshot_json JSONB NOT NULL,
    data_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (world_id, trading_day)
);

CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
    trading_day DATE NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    actions_json JSONB NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fills (
    fill_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    qty NUMERIC(18, 4) NOT NULL,
    fill_price NUMERIC(18, 6) NOT NULL,
    fee NUMERIC(18, 6) NOT NULL DEFAULT 0,
    slippage NUMERIC(18, 6) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS portfolios (
    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
    trading_day DATE NOT NULL,
    cash NUMERIC(18, 6) NOT NULL,
    equity NUMERIC(18, 6) NOT NULL,
    realized_pnl NUMERIC(18, 6) NOT NULL DEFAULT 0,
    unrealized_pnl NUMERIC(18, 6) NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (agent_id, trading_day)
);

CREATE TABLE IF NOT EXISTS positions (
    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
    symbol TEXT NOT NULL,
    qty NUMERIC(18, 4) NOT NULL,
    avg_cost NUMERIC(18, 6) NOT NULL,
    last_price NUMERIC(18, 6),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (agent_id, symbol)
);

CREATE TABLE IF NOT EXISTS equity_points (
    agent_id TEXT NOT NULL REFERENCES agents(agent_id),
    trading_day DATE NOT NULL,
    equity NUMERIC(18, 6) NOT NULL,
    drawdown NUMERIC(18, 6) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (agent_id, trading_day)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id TEXT PRIMARY KEY,
    actor_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    payload_ref TEXT,
    trace_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    idempotency_key TEXT PRIMARY KEY,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    result_ref TEXT,
    status TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trade_records_statement_id ON trade_records(statement_id);
CREATE INDEX IF NOT EXISTS idx_orders_agent_day ON orders(agent_id, trading_day);
CREATE INDEX IF NOT EXISTS idx_fills_order_id ON fills(order_id);
CREATE INDEX IF NOT EXISTS idx_equity_points_agent_day ON equity_points(agent_id, trading_day);
CREATE INDEX IF NOT EXISTS idx_audit_logs_trace_id ON audit_logs(trace_id);

COMMIT;
"""

    updated_files: list[str] = []
    for raw_path in related_files:
        path = repo_b_path / raw_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.name == "init_schema.sql":
            path.write_text(sql_payload, encoding="utf-8")
            updated_files.append(str(path))
    return updated_files


def materialize_statement_storage_artifacts(repo_b_path: Path, related_files: list[str] | None = None) -> list[str]:
    related_files = list(related_files or [])
    if not related_files:
        related_files = [
            "apps/api/src/modules/statements/storage.py",
            "apps/api/src/modules/statements/repository.py",
        ]

    payload_by_name = {
        "storage.py": """from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ALLOWED_STATEMENT_SUFFIXES = {".csv", ".xls", ".xlsx"}


def build_statement_object_key(owner_id: str, statement_id: str, original_filename: str) -> str:
    suffix = Path(original_filename).suffix.lower()
    if suffix not in ALLOWED_STATEMENT_SUFFIXES:
        raise ValueError(f"Unsupported statement suffix: {suffix}")
    return f"statements/{owner_id}/{statement_id}/{Path(original_filename).name}"


@dataclass(frozen=True)
class StoredStatementObject:
    object_key: str
    size_bytes: int


class LocalStatementObjectStore:
    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)

    def save_statement_object(
        self,
        owner_id: str,
        statement_id: str,
        original_filename: str,
        payload: bytes,
    ) -> StoredStatementObject:
        object_key = build_statement_object_key(owner_id, statement_id, original_filename)
        target_path = self.root_dir / object_key
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(payload)
        return StoredStatementObject(object_key=object_key, size_bytes=len(payload))

    def delete_statement_object(self, object_key: str) -> None:
        target_path = self.root_dir / object_key
        if target_path.exists():
            target_path.unlink()
""",
        "repository.py": """from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

INSERT_STATEMENT_METADATA_SQL = '''
INSERT INTO statements (
    statement_id,
    owner_id,
    market,
    object_key,
    parsed_status,
    broker_hint
) VALUES (
    %(statement_id)s,
    %(owner_id)s,
    %(market)s,
    %(object_key)s,
    %(parsed_status)s,
    %(broker_hint)s
);
'''.strip()

SELECT_STATEMENT_METADATA_SQL = '''
SELECT
    statement_id,
    owner_id,
    market,
    object_key,
    parsed_status,
    broker_hint
FROM statements
WHERE statement_id = %(statement_id)s;
'''.strip()

ROLLBACK_STATEMENT_METADATA_SQL = '''
DELETE FROM statements
WHERE statement_id = %(statement_id)s;
'''.strip()


@dataclass(frozen=True)
class StatementMetadata:
    statement_id: str
    owner_id: str
    market: str
    object_key: str
    parsed_status: str
    broker_hint: str | None = None


def create_statement_metadata_payload(metadata: StatementMetadata) -> dict[str, Any]:
    return asdict(metadata)


def get_statement_metadata_query(statement_id: str) -> tuple[str, dict[str, Any]]:
    return SELECT_STATEMENT_METADATA_SQL, {"statement_id": statement_id}


def rollback_statement_metadata_query(statement_id: str) -> tuple[str, dict[str, Any]]:
    return ROLLBACK_STATEMENT_METADATA_SQL, {"statement_id": statement_id}
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
