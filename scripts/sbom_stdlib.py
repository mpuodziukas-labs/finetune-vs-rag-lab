"""Pinned lock file to a CycloneDX 1.5 JSON SBOM. Stdlib only (syft and cyclonedx are not required).

    sbom_stdlib.py --input requirements.lock --out SBOM.cdx.json --name NAME [--check]

--check exits 1 with DRIFT when the component list in --out differs from the lock. Exit 2 on bad input.
The timestamp comes from SOURCE_DATE_EPOCH when set, else the current UTC time; --check ignores it.
"""

import argparse
import datetime
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse(lines: list[str]) -> list[tuple[str, str]]:
    comps = []
    for raw in lines:
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)", raw.strip())
        if m:
            comps.append((norm(m.group(1)), m.group(2)))
    return sorted(comps)


def build(comps: list[tuple[str, str]], name: str, ts: str) -> dict[str, Any]:
    serial = uuid.uuid5(uuid.NAMESPACE_URL, "|".join(f"{n}@{v}" for n, v in comps) + "|" + name)
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {"timestamp": ts, "component": {"type": "application", "name": name}},
        "components": [
            {"type": "library", "bom-ref": f"pkg:pypi/{n}@{v}", "name": n, "version": v, "purl": f"pkg:pypi/{n}@{v}"} for n, v in comps
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--name", default="finetune-vs-rag-lab")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    try:
        lines = Path(a.input).read_text(encoding="utf-8").splitlines()
    except OSError as e:
        print(f"sbom_stdlib: cannot read {a.input}: {e}", file=sys.stderr)
        return 2
    comps = parse(lines)
    if not comps:
        print("sbom_stdlib: no pinned components found", file=sys.stderr)
        return 2
    sde = os.environ.get("SOURCE_DATE_EPOCH")
    when = datetime.datetime.fromtimestamp(int(sde), datetime.UTC) if sde else datetime.datetime.now(datetime.UTC)
    bom = build(comps, a.name, when.strftime("%Y-%m-%dT%H:%M:%SZ"))
    out = Path(a.out)
    if a.check:
        try:
            cur = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            print(f"sbom_stdlib: DRIFT {a.out} missing or unreadable")
            return 1
        if cur.get("components") != bom["components"]:
            print(f"sbom_stdlib: DRIFT components differ from lock ({len(cur.get('components', []))} vs {len(comps)})")
            return 1
        print(f"sbom_stdlib: OK {len(comps)} components")
        return 0
    out.write_text(json.dumps(bom, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"sbom_stdlib: wrote {a.out} with {len(comps)} components")
    return 0


if __name__ == "__main__":
    sys.exit(main())
