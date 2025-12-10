from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List

from .job_runner import job_logger

DEFAULT_OUTPUT_DIR = Path("/tmp/strm")


def run_strm_job(job_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Generate placeholder STRM files using the current configuration."""
    config = metadata.get("config") or {}
    strm_cfg = config.get("strm", {})
    output_dir = Path(strm_cfg.get("outputDir") or DEFAULT_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    module = (metadata.get("module") or "115").lower()
    modules = _resolve_modules(module)
    created: List[str] = []
    timestamp = int(time.time())

    for name in modules:
        mapping = _module_mapping(name, strm_cfg)
        if not mapping:
            continue
        file_name = f"{name}_{timestamp}.strm"
        file_path = output_dir / file_name
        file_path.write_text(mapping["url"].rstrip("\n") + "\n", encoding="utf-8")
        created.append(str(file_path))
        job_logger.info("[%s] STRM entry created for %s -> %s", job_id, name, mapping["url"])

    result = {"module": module, "files": created, "directory": str(output_dir)}
    return result


def _resolve_modules(module: str) -> List[str]:
    if module in ("all", "*"):
        return ["115", "123", "openlist"]
    return [module]


def _module_mapping(module: str, strm_cfg: Dict[str, Any]) -> Dict[str, str] | None:
    module = module.lower()
    timestamp = int(time.time())
    if module == "115":
        source = strm_cfg.get("sourceCid115")
        prefix = strm_cfg.get("urlPrefix115")
    elif module == "123":
        source = strm_cfg.get("sourceDir123")
        prefix = strm_cfg.get("urlPrefix123")
    elif module == "openlist":
        source = strm_cfg.get("sourcePathOpenList")
        prefix = strm_cfg.get("urlPrefixOpenList")
    else:
        return None

    if not prefix:
        return None
    source = source or ""
    normalized_prefix = prefix.rstrip("/")
    normalized_source = source.lstrip("/")
    url = f"{normalized_prefix}/{normalized_source}" if normalized_source else normalized_prefix
    url = url.rstrip("/") + f"?ts={timestamp}"
    return {"url": url}
