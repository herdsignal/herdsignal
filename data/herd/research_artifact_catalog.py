from __future__ import annotations

import json
from pathlib import Path


ALLOWED_STATUSES = {"ACTIVE", "REJECTED", "LEGACY", "DATA_PIPELINE"}


def load_catalog(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if set(payload.get("statuses", {})) != ALLOWED_STATUSES:
        raise ValueError("artifact status vocabulary changed")
    if payload.get("retention", {}).get("unclassified_policy") != "REVIEW_REQUIRED":
        raise ValueError("unclassified artifacts must fail closed")
    return payload


def validate_active_chain(catalog: dict, root: Path) -> list[str]:
    return [relative for relative in catalog["active_chain"] if not (root / relative).is_file()]


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    catalog = load_catalog(Path(__file__).with_suffix(".json"))
    missing = validate_active_chain(catalog, root)
    if missing:
        raise SystemExit(f"missing active research artifacts: {', '.join(missing)}")
    print(json.dumps({"status": "OK", "active_chain": len(catalog["active_chain"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
