"""Small standard-library HTTP client for the public QoO testbed API.

All writes are explicit methods invoked only from a user-started experiment.
No network shaping occurs just by opening the desktop application.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class TestbedAPIError(RuntimeError):
    """Clear error raised when the testbed is unreachable or rejects a request."""


class QoOTestbedClient:
    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = self.base_url + path
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
                if not raw.strip():
                    return {"http_status": response.status}
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return {"text": raw, "http_status": response.status}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise TestbedAPIError(f"{method} {path} returned HTTP {exc.code}: {body[:500]}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise TestbedAPIError(f"Could not reach {url}: {reason}") from exc

    def get_status(self) -> Any:
        return self._request("GET", "/status")

    def get_gateway_profiles(self) -> Any:
        return self._request("GET", "/profiles")

    def get_qoo_profiles(self) -> Any:
        return self._request("GET", "/qoo-profiles")

    def get_active_qoo_profile(self) -> Any:
        return self._request("GET", "/qoo-active-profile")

    def get_qoo_profile(self, name: str) -> Any:
        safe = urllib.parse.quote(name, safe="")
        return self._request("GET", f"/qoo-profiles/{safe}")

    def load_qoo_profile(self, name: str) -> Any:
        safe = urllib.parse.quote(name, safe="")
        return self._request("POST", f"/qoo-profiles/load/{safe}", {})

    def apply_gateway_profile(self, name: str) -> Any:
        safe = urllib.parse.quote(name, safe="")
        return self._request("POST", f"/profile/{safe}", {})

    def apply_custom_impairment(self, payload: dict[str, Any]) -> Any:
        # The upstream README documents POST /custom but not its exact JSON schema.
        # The caller must keep the field map consistent with the actual gateway handler.
        return self._request("POST", "/custom", payload)


def extract_names(response: Any) -> list[str]:
    """Extract names from common list/dict JSON response shapes."""
    if isinstance(response, list):
        rows = response
    elif isinstance(response, dict):
        rows = None
        for key in ("profiles", "items", "data", "names", "qoo_profiles"):
            value = response.get(key)
            if isinstance(value, list):
                rows = value
                break
        if rows is None:
            # A single named profile object is also a common response format.
            name = response.get("name") or response.get("profile")
            return [str(name)] if isinstance(name, str) and name else []
    else:
        return []

    names: list[str] = []
    for row in rows:
        if isinstance(row, str):
            names.append(row)
        elif isinstance(row, dict):
            name = row.get("name") or row.get("id") or row.get("profile")
            if isinstance(name, str) and name:
                names.append(name)
    return sorted(dict.fromkeys(names), key=str.casefold)


def extract_profile_name(response: Any) -> str | None:
    """Extract an active QoO profile name from the common API response shapes."""
    if isinstance(response, str) and response.strip():
        return response.strip()
    if not isinstance(response, dict):
        return None
    for key in ("name", "profile_name", "profile", "active_profile", "current_profile", "active"):
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = extract_profile_name(value)
            if nested:
                return nested
    return None
