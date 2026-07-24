"""HerdSignal 로컬 데이터와 생성 캐시의 용량을 읽기 전용으로 감사한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TARGETS = (
    "data/reports",
    "data/reference",
    "data/snapshots",
    "data/walk_forward",
)
GENERATED_DIRECTORY_NAMES = {"__pycache__", ".pytest_cache", "dist", "build"}


def directory_stats(path: Path) -> dict:
    files = 0
    bytes_used = 0
    if path.exists():
        for item in path.rglob("*"):
            if item.is_file() and not item.is_symlink():
                try:
                    bytes_used += item.stat().st_size
                    files += 1
                except FileNotFoundError:
                    continue
    return {"path": str(path), "files": files, "bytes": bytes_used}


def generated_stats(root: Path) -> dict:
    directories = [
        path
        for path in root.rglob("*")
        if path.is_dir()
        and path.name in GENERATED_DIRECTORY_NAMES
        and ".venv" not in path.parts
        and "node_modules" not in path.parts
    ]
    # 중첩된 생성 디렉터리를 두 번 합산하지 않는다.
    top_level = [
        path
        for path in directories
        if not any(parent in directories for parent in path.parents)
    ]
    stats = [directory_stats(path) for path in sorted(top_level)]
    return {
        "directories": len(stats),
        "files": sum(item["files"] for item in stats),
        "bytes": sum(item["bytes"] for item in stats),
    }


def audit_storage(root: Path = PROJECT_ROOT) -> dict:
    targets = {
        relative: directory_stats(root / relative)
        for relative in TARGETS
    }
    generated = generated_stats(root)
    warnings = []
    if targets["data/reference"]["bytes"] >= 10 * 1024**3:
        warnings.append("LOCAL_REFERENCE_OVER_10_GIB")
    if targets["data/reports"]["files"] >= 300:
        warnings.append("REPORT_FILE_COUNT_OVER_300")
    if generated["bytes"] >= 100 * 1024**2:
        warnings.append("GENERATED_CACHE_OVER_100_MIB")
    return {
        "status": "REVIEW" if warnings else "OK",
        "targets": targets,
        "generated": generated,
        "warnings": warnings,
        "policy": "READ_ONLY_NO_AUTOMATIC_DELETE",
    }


def human_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TiB"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = audit_storage()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for relative, stats in report["targets"].items():
            print(f"{relative}: {stats['files']} files · {human_bytes(stats['bytes'])}")
        print(
            "generated caches: "
            f"{report['generated']['directories']} dirs · "
            f"{report['generated']['files']} files · "
            f"{human_bytes(report['generated']['bytes'])}"
        )
        print(f"status: {report['status']} ({', '.join(report['warnings']) or 'no warnings'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
