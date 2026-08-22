"""Machine-readable API registry access and safety validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml


class RiskLevel(StrEnum):
    READ = "READ"
    DRAFT_WRITE = "DRAFT_WRITE"
    STATE_CHANGE = "STATE_CHANGE"
    DESTRUCTIVE = "DESTRUCTIVE"
    FINANCIAL = "FINANCIAL"


DEFAULT_EXPOSED_RISKS = {RiskLevel.READ, RiskLevel.DRAFT_WRITE}


def default_registry_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "api_registry.yaml"


def load_registry(path: str | Path | None = None) -> list[dict[str, Any]]:
    value = yaml.safe_load(Path(path or default_registry_path()).read_text(encoding="utf-8"))
    entries = value.get("apis") if isinstance(value, dict) else None
    if not isinstance(entries, list):
        raise ValueError("api_registry.yaml must contain an apis list")
    return entries


def validate_registry(entries: list[dict[str, Any]]) -> None:
    names: set[str] = set()
    required = {
        "name", "method", "path", "domain", "description", "request", "response",
        "auth_required", "mutation", "risk_level", "discovered_from", "status", "mcp_exposed",
    }
    for entry in entries:
        missing = required.difference(entry)
        if missing:
            raise ValueError(f"registry entry {entry.get('name')} missing: {sorted(missing)}")
        if entry["name"] in names:
            raise ValueError(f"duplicate registry name: {entry['name']}")
        names.add(entry["name"])
        risk = RiskLevel(entry["risk_level"])
        if entry["mcp_exposed"] and risk not in DEFAULT_EXPOSED_RISKS:
            raise ValueError(f"unsafe MCP exposure: {entry['name']} ({risk})")
