from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class Connector(Protocol):
    name: str
    description: str

    async def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(slots=True)
class VendorRegistryConnector:
    name: str = "vendor_registry"
    description: str = "Deterministic demo connector for corporate-registration and vendor-master data."

    async def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action != "lookup_vendor":
            raise ValueError(f"Unsupported action for {self.name}: {action}")
        vendor_name = str(payload.get("vendor_name", "")).strip()
        if not vendor_name:
            raise ValueError("vendor_name is required")
        digest = hashlib.sha256(vendor_name.lower().encode()).digest()
        years = 2 + digest[0] % 24
        jurisdictions = ["Illinois", "Delaware", "New York", "Texas", "California"]
        return {
            "vendor_name": vendor_name,
            "registration_status": "active" if digest[1] % 10 else "review_required",
            "jurisdiction": jurisdictions[digest[2] % len(jurisdictions)],
            "years_registered": years,
            "vendor_id": f"VR-{int.from_bytes(digest[3:7], 'big') % 10_000_000:07d}",
            "source": "demo_enterprise_vendor_registry",
        }


@dataclass(slots=True)
class RiskSignalsConnector:
    name: str = "risk_signals"
    description: str = "Deterministic demo connector for sanctions, adverse-media, and continuity signals."

    async def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action != "check_risk_signals":
            raise ValueError(f"Unsupported action for {self.name}: {action}")
        vendor_name = str(payload.get("vendor_name", "")).strip()
        if not vendor_name:
            raise ValueError("vendor_name is required")
        digest = hashlib.sha256((vendor_name.lower() + "::risk").encode()).digest()
        sanctions_hit = digest[0] == 255
        adverse_media_count = digest[1] % 4
        continuity_score = 55 + digest[2] % 46
        cyber_signal = ["low", "moderate", "elevated"][digest[3] % 3]
        return {
            "vendor_name": vendor_name,
            "sanctions_hit": sanctions_hit,
            "adverse_media_count": adverse_media_count,
            "business_continuity_score": continuity_score,
            "cyber_signal": cyber_signal,
            "source": "demo_external_risk_feed",
        }


@dataclass(slots=True)
class HTTPJSONConnector:
    """Allowlisted REST connector for enterprise JSON APIs.

    This is disabled unless instantiated with an explicit base URL and allowed host.
    It demonstrates the production-shaped connector contract without allowing arbitrary SSRF.
    """

    name: str
    base_url: str
    allowed_host: str
    description: str = "Allowlisted REST/JSON enterprise connector"
    timeout_seconds: float = 10.0

    async def execute(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        path = payload.pop("path", action)
        method = str(payload.pop("method", "POST")).upper()
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("Connector base_url must be HTTP(S)")
        parsed_host = httpx.URL(self.base_url).host
        if parsed_host != self.allowed_host:
            raise ValueError("Connector host is not allowlisted")
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout_seconds) as client:
            response = await client.request(method, path, json=payload)
            response.raise_for_status()
            data = response.json()
            return {"status_code": response.status_code, "data": data}


class ConnectorRegistry:
    def __init__(self):
        self._connectors: dict[str, Connector] = {}

    def register(self, connector: Connector) -> None:
        if connector.name in self._connectors:
            raise ValueError(f"Connector already registered: {connector.name}")
        self._connectors[connector.name] = connector

    def list(self) -> list[dict[str, str]]:
        return [
            {"name": connector.name, "description": connector.description}
            for connector in self._connectors.values()
        ]

    async def execute(self, name: str, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        connector = self._connectors.get(name)
        if not connector:
            raise KeyError(f"Unknown connector: {name}")
        return await connector.execute(action, dict(payload))
