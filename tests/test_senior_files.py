"""Senior files: container, ownership, SBOM drift, threat model rows, SLO, mutants, receipt pins, third-party text.
Each check has a planted-defect twin so it can fail. Nothing here builds an image or opens a network."""

import ast
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def run(*cmd: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=300, check=False)


def func_names(path: Path) -> set[str]:
    return {n.name for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))) if isinstance(n, ast.FunctionDef)}


# ---- container ----
def container_problems(dockerfile: str) -> list[str]:
    bad = []
    if len(re.findall(r"^FROM\s", dockerfile, re.M)) < 2:
        bad.append("not multi-stage")
    users = re.findall(r"^USER\s+(\S+)", dockerfile, re.M)
    if not users or users[-1] in {"root", "0"}:
        bad.append("final user is root or unset")
    if not re.search(r"^HEALTHCHECK\s", dockerfile, re.M):
        bad.append("no HEALTHCHECK")
    return bad


def test_dockerfile_nonroot_healthcheck() -> None:
    assert container_problems((ROOT / "Dockerfile").read_text(encoding="utf-8")) == []
    planted = "FROM python:3.11-slim\nUSER root\n"
    assert set(container_problems(planted)) == {"not multi-stage", "final user is root or unset", "no HEALTHCHECK"}


def test_compose_hardened() -> None:
    doc = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    svc = doc["services"]
    assert svc, "compose declares no service"
    for name, s in svc.items():
        assert s.get("read_only") is True, name
        assert s.get("network_mode") == "none", name
        assert "ALL" in s.get("cap_drop", []), name
        assert "no-new-privileges:true" in s.get("security_opt", []), name


# ---- ownership and third-party text ----
def test_root_codeowners() -> None:
    root = (ROOT / "CODEOWNERS").read_text(encoding="utf-8").splitlines()
    assert root[0] == "* [OWNER_HANDLE]"
    assert root == (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8").splitlines()


def test_third_party_text_section() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    sec = readme.split("## Third-party text", 1)[1].split("\n## ", 1)[0]
    assert "verbatim upstream" in sec and "license" in sec and "data/" in sec
    allow = ROOT / ".publish-allow"
    if allow.exists():
        assert "data/" in allow.read_text(encoding="utf-8")


# ---- SBOM follows the freeze file ----
def sbom(*extra: object) -> subprocess.CompletedProcess[str]:
    return run(sys.executable, "-P", SCRIPTS / "sbom_stdlib.py", *extra)


def test_freeze_is_pinned() -> None:
    lines = [ln for ln in (ROOT / "requirements.freeze.txt").read_text(encoding="utf-8").splitlines() if ln and ln[0] not in "# "]
    assert len(lines) > 50
    unpinned = [ln for ln in lines if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*(\[[^\]]+\])?==\S+", ln)]
    assert unpinned == [], unpinned


def test_sbom_matches_freeze() -> None:
    r = sbom("--input", ROOT / "requirements.freeze.txt", "--out", ROOT / "SBOM.cdx.json", "--name", "finetune-vs-rag-lab", "--check")
    assert r.returncode == 0 and "OK" in r.stdout, r.stdout + r.stderr


def test_sbom_drift_red(tmp_path: Path) -> None:
    lock = tmp_path / "requirements.freeze.txt"
    shutil.copy(ROOT / "requirements.freeze.txt", lock)
    lock.write_text(lock.read_text(encoding="utf-8") + "zzz-drifted==9.9.9\n", encoding="utf-8")
    r = sbom("--input", lock, "--out", ROOT / "SBOM.cdx.json", "--name", "finetune-vs-rag-lab", "--check")
    assert r.returncode == 1 and "DRIFT" in r.stdout, r.stdout
    empty = tmp_path / "empty.txt"
    empty.write_text("# nothing\n", encoding="utf-8")
    assert sbom("--input", empty, "--out", tmp_path / "x.json").returncode == 2


# ---- docs/THREAT-MODEL.md ----
STRIDE = {"Spoofing", "Tampering", "Repudiation", "Information disclosure", "Denial of service", "Elevation of privilege"}
TOPICS = ("data poisoning", "receipt tampering", "metric gaming", "dependency")


def threat_rows(text: str) -> list[list[str]]:
    return [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in text.splitlines() if re.match(r"\| T\d+ \|", ln)]


def threat_problems(text: str) -> list[str]:
    rows = threat_rows(text)
    bad = []
    if {r[1] for r in rows} < STRIDE:
        bad.append("STRIDE class missing")
    for topic in TOPICS:
        if not any(topic in r[2].lower() for r in rows):
            bad.append(f"topic {topic} has no row")
    for r in rows:
        m = re.fullmatch(r"`(tests/[\w./]+\.py)::(\w+)`", r[4])
        base = ROOT / m.group(1) if m else None
        if not (m and base and base.is_file() and m.group(2) in func_names(base)) or not r[3]:
            bad.append(f"{r[0]}: control or covering test missing")
    return bad


def test_docs_threat_model_rows() -> None:
    text = (ROOT / "docs" / "THREAT-MODEL.md").read_text(encoding="utf-8")
    assert len(threat_rows(text)) >= 10 and threat_problems(text) == []
    planted = text.replace("test_leak_flagged", "test_no_such_test")
    assert threat_problems(planted), "a phantom covering test must be reported"


# ---- docs/SLO.md ----
def test_slo_doc() -> None:
    text = (ROOT / "docs" / "SLO.md").read_text(encoding="utf-8")
    obj = float(re.search(r"^objective: ([0-9.]+)$", text, re.M).group(1))  # type: ignore[union-attr]
    budget = float(re.search(r"^error budget: ([0-9.]+)$", text, re.M).group(1))  # type: ignore[union-attr]
    assert abs((1 - obj) - budget) < 1e-9
    windows = re.findall(r"^\| (long|short) \| (\d+) runs \|", text, re.M)
    assert [w[0] for w in windows] == ["long", "short"] and int(windows[0][1]) > int(windows[1][1])
    threshold = float(re.search(r"^page: both windows burn above ([0-9.]+)$", text, re.M).group(1))  # type: ignore[union-attr]
    ex = re.search(r"^worked example: (\d+) failures in (\d+) runs, burn ([0-9.]+)$", text, re.M)
    assert ex and abs((int(ex.group(1)) / int(ex.group(2))) / budget - float(ex.group(3))) < 1e-9
    assert float(ex.group(3)) >= threshold


# ---- mutants ----
def test_mutants_applicable() -> None:
    r = run(sys.executable, "-P", SCRIPTS / "mutants.py", "--check")
    m = re.search(r"mutants: (\d+)/(\d+) applicable", r.stdout)
    assert r.returncode == 0 and m and m.group(1) == m.group(2) and int(m.group(2)) >= 3, r.stdout + r.stderr


def test_mutants_selftest() -> None:
    r = run(sys.executable, "-P", SCRIPTS / "mutants.py", "--selftest")
    assert r.returncode == 0 and "selftest 2/2" in r.stdout, r.stdout + r.stderr


# ---- receipt hash pins ----
def pin_problems(root: Path) -> list[str]:
    bad = []
    listed = set()
    for ln in (root / "receipts" / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, _, rel = ln.partition("  ")
        listed.add(rel)
        f = root / rel
        if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest() != digest:
            bad.append(rel)
    bad += [f"unlisted: receipts/{p.name}" for p in sorted((root / "receipts").glob("*.json")) if f"receipts/{p.name}" not in listed]
    return bad


def test_receipt_pins_verify(tmp_path: Path) -> None:
    assert pin_problems(ROOT) == []
    copy = tmp_path / "lab"
    shutil.copytree(ROOT / "receipts", copy / "receipts")
    for rel in ("README.md", "demo", "tests"):
        src = ROOT / rel
        if src.is_dir():
            shutil.copytree(src, copy / rel)
        else:
            shutil.copy(src, copy / rel)
    assert pin_problems(copy) == []
    target = copy / "receipts" / "results.json"
    target.write_text(target.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert pin_problems(copy) == ["receipts/results.json"]
