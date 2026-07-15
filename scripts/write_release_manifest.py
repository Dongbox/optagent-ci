from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys
from typing import Sequence


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(
    *,
    output: Path,
    optagent_root: Path,
    validation_wheel: Path,
    release_wheel: Path,
    data_manifest: Path,
    validation_key_id: str,
    release_key_id: str,
) -> dict[str, object]:
    payload = {
        "schema_version": 1,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version,
        "optagent_commit": subprocess.check_output(
            ["git", "-C", str(optagent_root), "rev-parse", "HEAD"], text=True
        ).strip(),
        "benchmarks_commit": subprocess.check_output(
            ["git", "-C", str(optagent_root / "benchmarks"), "rev-parse", "HEAD"],
            text=True,
        ).strip(),
        "validation_wheel": {
            "filename": validation_wheel.name,
            "sha256": _sha256(validation_wheel),
            "key_id": validation_key_id,
            "published": False,
        },
        "release_wheel": {
            "filename": release_wheel.name,
            "sha256": _sha256(release_wheel),
            "key_id": release_key_id,
            "published": True,
        },
        "data_manifest_sha256": _sha256(data_manifest),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--optagent-root", type=Path, required=True)
    parser.add_argument("--validation-wheel", type=Path, required=True)
    parser.add_argument("--release-wheel", type=Path, required=True)
    parser.add_argument("--data-manifest", type=Path, required=True)
    parser.add_argument("--validation-key-id", required=True)
    parser.add_argument("--release-key-id", required=True)
    args = parser.parse_args(argv)
    payload = write_manifest(
        output=args.output,
        optagent_root=args.optagent_root,
        validation_wheel=args.validation_wheel,
        release_wheel=args.release_wheel,
        data_manifest=args.data_manifest,
        validation_key_id=args.validation_key_id,
        release_key_id=args.release_key_id,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
