"""Platform files: CI parity, pinned actions, evidence, SBOM, citation, rubric copy, objections, comparisons, threat model.
Each check has a planted-defect twin so it can fail."""
import csv
import hashlib
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IS_RAG = (ROOT / "rag").is_dir()  # by content, not by directory name: a clone into any folder must pass
README = (ROOT / "README.md").read_text(encoding="utf-8")


def _section(text: str, tag: str) -> str:
    m = re.search(rf"<!-- P2:{tag}:BEGIN -->(.*?)<!-- P2:{tag}:END -->", text, re.S)
    assert m, f"README has no P2:{tag} block"
    return m.group(1)


def unpinned_uses(text: str) -> list[str]:
    bad = []
    for line in text.splitlines():
        if "uses:" in line and not re.search(r"uses: [^@\s]+@[0-9a-f]{40} # v\d", line):
            bad.append(line.strip())
    return bad


def cited_names_exist(text: str) -> list[str]:
    missing = []
    for path, name in re.findall(r"`(tests/[\w./]+)::(\w+)`", text):
        f = ROOT / path
        if not f.exists() or f"def {name}" not in f.read_text(encoding="utf-8"):
            missing.append(f"{path}::{name}")
    for path, line in re.findall(r"`([\w./-]+\.\w+):(\d+)`", text):
        f = ROOT / path
        if not f.exists() or len(f.read_text(encoding="utf-8").splitlines()) < int(line):
            missing.append(f"{path}:{line}")
    return missing


def test_actions_pinned() -> None:
    assert unpinned_uses("      - uses: actions/checkout@v4\n") != []  # planted: tag pin is caught
    assert unpinned_uses("      - uses: actions/checkout@" + "a" * 40 + " # v4.2.2\n") == []  # control
    wfs = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    assert wfs
    for wf in wfs:
        assert unpinned_uses(wf.read_text(encoding="utf-8")) == [], wf.name


def test_ci_calls_ci_local_and_dependabot() -> None:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "scripts/ci-local.sh" in ci and "permissions:" in ci
    local = (ROOT / "scripts" / "ci-local.sh").read_text(encoding="utf-8")
    assert "ci-local: GREEN" in local and "pipefail" in local
    dep = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    assert "package-ecosystem: pip" in dep and "package-ecosystem: github-actions" in dep


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_evidence_matches_sources() -> None:
    ev = _load("evidence_md")
    text = ev.build()
    assert (ROOT / "EVIDENCE.md").read_text(encoding="utf-8") == text
    pub_rows = len(list(csv.DictReader((ROOT / "PUBLISH.tsv").open(encoding="utf-8"), delimiter="\t")))
    assert text.count("\n| ") >= pub_rows  # every PUBLISH row is a table row
    assert (ROOT / "EVIDENCE.md").read_text(encoding="utf-8") != text.replace("GREEN", "RED")  # planted drift differs


def test_sbom_parses() -> None:
    d = json.loads((ROOT / "SBOM.cdx.json").read_text(encoding="utf-8"))
    assert d["bomFormat"] == "CycloneDX" and len(d["components"]) > 5
    assert all(c["purl"].startswith("pkg:pypi/") for c in d["components"])


def test_citation_and_references() -> None:
    cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-untyped]

        data = yaml.safe_load(cff)
        assert data["cff-version"] == "1.2.0" and data["title"] and data["authors"]
    except ImportError:
        for key in ("cff-version: 1.2.0", "title:", "authors:", "license: MIT"):
            assert key in cff
    zen = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
    assert zen["title"] == re.search(r'^title: "?([^"\n]+)"?', cff, re.M).group(1) and zen["creators"]  # type: ignore[union-attr]
    src = csv.DictReader((ROOT / "docs/rubric/SOURCES.tsv").open(encoding="utf-8"), delimiter="\t")
    grounded = [r for r in src if r["status"] == "GROUNDED"]
    refs = (ROOT / "REFERENCES.md").read_text(encoding="utf-8")
    assert len(re.findall(r"^\| .* \| https?://", refs, re.M)) == len(grounded) > 0


def test_rubric_copy_and_score() -> None:
    assert (ROOT / "docs/rubric/RUBRIC.md").stat().st_size > 1000
    rows = list(csv.DictReader((ROOT / "docs/rubric/SCORECARD.tsv").open(encoding="utf-8"), delimiter="\t"))
    na = sum(r["met"] == "na" for r in rows)
    yes = sum(r["met"] == "yes" for r in rows)
    assert f"scored {yes}/{len(rows) - na} against a published rubric" in _section(README, "FOLD")
    assert all(r["met"] in {"yes", "partial", "no", "na"} for r in rows)


def test_transcript_matches_readme() -> None:
    t = (ROOT / "demo" / "verify.transcript.txt").read_text(encoding="utf-8")
    sha = (ROOT / "demo" / "verify.transcript.sha256").read_text().strip()
    assert hashlib.sha256(t.encode()).hexdigest() == sha
    fold = _section(README, "FOLD")
    assert sha[:16] in fold and t.rstrip("\n").split("\n")[-1] in fold
    assert re.search(r"GREEN \d+/\d+ checks", t.rstrip("\n").split("\n")[-1])


def test_objections_and_compared_with() -> None:
    obj = [ln for ln in _section(README, "OBJ").splitlines() if ln.startswith("| ") and "---" not in ln][1:]
    assert len(obj) == 5
    for ln in obj:
        assert re.search(r"(`tests/[\w./]+::\w+`|`[\w./-]+\.\w+:\d+`)", ln), ln
    cmp_rows = [ln for ln in _section(README, "CMP").splitlines() if ln.startswith("| ") and "---" not in ln][1:]
    assert len(cmp_rows) >= 3
    assert cited_names_exist(_section(README, "OBJ") + _section(README, "CMP")) == []
    assert cited_names_exist("`tests/test_nope.py::test_missing`") == ["tests/test_nope.py::test_missing"]  # planted


def test_threat_model_rows() -> None:
    tm = (ROOT / "THREAT-MODEL.md").read_text(encoding="utf-8")
    rows = [ln for ln in tm.splitlines() if ln.startswith("| ") and re.search(r"\| (LLM\d\d[^|]*|none) \|", ln)]
    assert len(rows) >= 7
    for ln in rows:
        assert "OPEN" in ln or re.search(r"tests/[\w./]+::\w+", ln), ln
    assert cited_names_exist(tm) == []


def test_readme_budget() -> None:
    assert len(README.split()) <= 1800
    seen: set[str] = set()
    for ln in README.splitlines():
        if len(ln) > 60 and not ln.startswith("|"):
            assert ln not in seen, ln
            seen.add(ln)


if IS_RAG:

    def test_readme_metrics_section() -> None:
        m = _section(README, "METRICS")
        assert "recall@k" in m and "nDCG@k" in m and "empty gold" in m and "Ties" in m
        assert cited_names_exist(m) == []

    def test_headline_interval_matches_receipt() -> None:
        d = json.loads((ROOT / "receipts" / "matrix.json").read_text(encoding="utf-8"))
        r = next(x for x in d["rows"] if x["chunker"] == "h110" and x["mode"] == "hybrid_rerank")
        lo, hi = r["recall10_ci"]
        assert f"95% bootstrap CI {lo:.3f} to {hi:.3f}" in README

else:

    def test_fetch_pinned_fails_closed_on_sha_mismatch(tmp_path: Path, monkeypatch) -> None:
        import importlib

        huggingface_hub = importlib.import_module("huggingface_hub")
        fetch_pinned = importlib.import_module("ftlab.data").fetch_pinned

        good = tmp_path / "f.txt"
        good.write_text("abc")
        want = hashlib.sha256(b"abc").hexdigest()
        monkeypatch.setattr(huggingface_hub, "hf_hub_download", lambda *a, **k: str(good))
        assert fetch_pinned("o/r", "rev", {"f.txt": want}, tmp_path / "cache") == tmp_path / "cache" / "o__r"  # control
        try:
            fetch_pinned("o/r", "rev", {"f.txt": "0" * 64}, tmp_path / "cache")
        except RuntimeError as e:
            assert "sha256 mismatch" in str(e)
        else:
            raise AssertionError("mismatched pin must fail closed")
