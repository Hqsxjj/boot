from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests

DEFAULT_TIMEOUT = 8


def normalize_server_url(url: str) -> str:
    if not url:
        raise ValueError("Emby server URL is required")
    cleaned = url.strip()
    if not cleaned.startswith("http"):
        raise ValueError("Emby server URL must start with http or https")
    return cleaned.rstrip("/") + "/"


def build_session(api_key: Optional[str]) -> requests.Session:
    session = requests.Session()
    if api_key:
        session.headers["X-Emby-Token"] = api_key.strip()
    session.headers["Accept"] = "application/json"
    return session


def test_connection(server_url: str, api_key: Optional[str]) -> Dict[str, Any]:
    base = normalize_server_url(server_url)
    session = build_session(api_key)
    resp = session.get(urljoin(base, "System/Info"), timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    return {
        "serverUrl": base.rstrip("/"),
        "version": data.get("Version"),
        "productName": data.get("ServerName") or data.get("ProductName"),
        "operatingSystem": data.get("OperatingSystemDisplayName") or data.get("OperatingSystem"),
        "supportsHardwareAcceleration": data.get("SupportsTrueHd"),
        "raw": data,
    }


def fetch_missing_episodes(server_url: str, api_key: Optional[str], limit: int = 50) -> List[Dict[str, Any]]:
    base = normalize_server_url(server_url)
    session = build_session(api_key)
    params = {
        "IncludeItemTypes": "Episode",
        "IsMissing": "true",
        "Recursive": "true",
        "Limit": str(limit),
        "Fields": "SeriesInfo,SeasonInfo,Path,ProviderIds,PrimaryImageAspectRatio",
    }
    resp = session.get(urljoin(base, "Items"), params=params, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    results: List[Dict[str, Any]] = []
    for item in payload.get("Items", []):
        results.append(
            {
                "series": item.get("SeriesName") or item.get("SeriesTitle"),
                "episodeName": item.get("Name"),
                "seasonNumber": item.get("ParentIndexNumber"),
                "episodeNumber": item.get("IndexNumber"),
                "providerIds": item.get("ProviderIds", {}),
                "premiereDate": item.get("PremiereDate"),
                "id": item.get("Id"),
                "imageUrl": _build_primary_image_url(base, item.get("Id")),
                "raw": item,
            }
        )
    return results


def _build_primary_image_url(base: str, item_id: Optional[str]) -> Optional[str]:
    if not item_id:
        return None
    return urljoin(base, f"Items/{item_id}/Images/Primary")
