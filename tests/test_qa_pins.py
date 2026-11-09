"""Adversarial QA pins: each test kills a mutant that survived the first suite."""

import ast
import copy
import io
import json
import re
import shutil
import tokenize
from pathlib import Path

import pytest

from ftlab import legacy_code_sha, report
from ftlab.audit import audit
from ftlab.config import load_config
from test_audit import ROWS, SPEC, _clean

ROOT = Path(__file__).resolve().parents[1]


def test_zero_logit_delta_adapter_flagged() -> None:
    """An adapter with parameters but no effect on the logits is a no-op; the threshold must be a positive floor."""
    split, train, ev = _clean()
    t2 = copy.deepcopy(train)
    t2["adapter"] = {"lora_params": 100, "logit_delta": 0.0}
    assert "adapter_active" in audit(ROWS, SPEC, split, t2, ev)


def test_overlapping_split_lists_with_forged_hash_flagged() -> None:
    """The hash alone cannot catch overlap when the lists are edited and the hash is kept; the disjoint check must."""
    split, train, ev = _clean()
    forged = copy.deepcopy(split)
    forged["train"] = list(forged["train"]) + [forged["test"][0]]
    assert "split_disjoint" in audit(ROWS, SPEC, forged, train, ev)


def test_check_receipts_flags_small_accuracy_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A receipt whose accuracy differs from mean(correct) by 0.01 must be reported."""
    rec = tmp_path / "receipts"
    shutil.copytree(ROOT / "receipts", rec)
    target = rec / "eval_zeroshot_test.json"
    obj = json.loads(target.read_text(encoding="utf-8"))
    obj["accuracy"] = obj["accuracy"] + 0.01
    target.write_text(json.dumps(obj), encoding="utf-8")
    monkeypatch.setattr(report, "REC", rec)
    assert report.check_receipts() == 1


def test_check_receipts_clean_control(monkeypatch: pytest.MonkeyPatch) -> None:
    """The unedited committed receipts pass, so the drift test above is red for the drift alone."""
    monkeypatch.setattr(report, "REC", ROOT / "receipts")
    assert report.check_receipts() == 0


def test_check_receipts_flags_stale_code_sha(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A train receipt whose code_sha differs from the current producer source is stale and must be reported; a missing one too."""
    rec = tmp_path / "receipts"
    shutil.copytree(ROOT / "receipts", rec)
    monkeypatch.setattr(report, "REC", rec)
    assert report.check_receipts() == 0
    target = rec / "train_f25.json"
    obj = json.loads(target.read_text(encoding="utf-8"))
    assert obj["code_sha"] == legacy_code_sha()
    obj["code_sha"] = "0" * 64
    target.write_text(json.dumps(obj), encoding="utf-8")
    assert report.check_receipts() == 1
    del obj["code_sha"]
    target.write_text(json.dumps(obj), encoding="utf-8")
    assert report.check_receipts() == 1


def test_report_check_exits_one_on_stale_readme(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`report --check` returns 1 when a generated README number is edited by hand, 0 on the untouched copy."""
    readme = tmp_path / "README.md"
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    readme.write_text(text, encoding="utf-8")
    svg = tmp_path / "curve.svg"
    svg.write_text((ROOT / "docs" / "training_curve.svg").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(report, "README", readme)
    monkeypatch.setattr(report, "SVG", svg)
    cfg = load_config()
    assert report.dispatch("report", cfg, None, True) == 0
    start = text.index("<!-- BEGIN:results -->") + len("<!-- BEGIN:results -->")
    readme.write_text(text[:start] + "\nHAND-EDITED 0.999\n" + text[start:], encoding="utf-8")
    assert report.dispatch("report", cfg, None, True) == 1


_SKIP_DIRS = {".venv", ".git", "data", "artifacts", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", "_attic", "tmp", ".accountability"}
_WORDS = ["g" + "pt", "cl" + "aude", "gem" + "ini", "lla" + "ma", "qw" + "en", "deep" + "seek", "mis" + "tral"]
_PROSE_WORDS = [*_WORDS, "smol" + "lm", "hugging" + " face"]  # model family and its host; ADR 0004 keeps them out of prose
_CITED = {"docs/rubric/SOURCES.tsv"}  # titles of cited external pages


def _hits(subdirs: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    seen = 0
    for base in subdirs:
        start = ROOT / base if base else ROOT
        paths = [start] if start.is_file() else [p for p in start.rglob("*") if p.is_file()]
        for p in paths:
            if _SKIP_DIRS & set(p.relative_to(ROOT).parts) or p.name == "test_qa_pins.py" or str(p.relative_to(ROOT)) in _CITED:
                continue
            try:
                text = "\n".join(ln for ln in p.read_text(encoding="utf-8").lower().splitlines() if "own licenses" not in ln)
            except UnicodeDecodeError:
                continue
            seen += 1
            found += [f"{p.relative_to(ROOT)}: {w}" for w in _PROSE_WORDS if w in text]
    assert seen > 0, "zero files checked is not a pass"
    return found


def test_terms_rows_are_true() -> None:
    """Every TERMS.tsv row names an existing file and test, and its doc literally contains the term."""
    lines = (ROOT / "docs" / "TERMS.tsv").read_text(encoding="utf-8").splitlines()
    assert len(lines) > 1
    assert lines[0].split("\t") == ["term", "file", "test", "doc", "stand-in"]
    for ln in lines[1:]:
        term, file, test, doc, stand_in = ln.split("\t")
        assert stand_in == f"none: measured here by {test}" or re.fullmatch(r"(model|provider)-[a-z]: \S.*", stand_in), ln
        assert (ROOT / file).exists() and (ROOT / test).is_file(), ln
        assert term.lower() in (ROOT / doc).read_text(encoding="utf-8").lower(), f"{doc} lacks '{term}'"


def test_no_vendor_words_in_docs() -> None:
    assert _hits(("README.md", "DESIGN.md", "SPEC.md", "THREAT-MODEL.md", "docs", "CHANGELOG.md")) == []


def _code_hits(path: Path) -> list[str]:
    """ADR 0004 rule: scan strings, comments and docstrings; skip import lines and names the file imports from a library."""
    text = path.read_text(encoding="utf-8")
    if path.suffix != ".py":
        return [w for w in _WORDS if w in text.lower()]
    tree = ast.parse(text)
    imported = {
        (a.asname or a.name).split(".")[0]
        for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
        for a in n.names
    }  # fmt: skip
    found: list[str] = []
    toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    for i, t in enumerate(toks):
        low = t.string.lower()
        if t.type in (tokenize.STRING, tokenize.COMMENT):
            found += [w for w in _WORDS if w in low]
        elif t.type == tokenize.NAME and t.string not in imported and not (i and toks[i - 1].string == "."):
            found += [w for w in _WORDS if w in low]
    return found


def _src_hits() -> list[str]:
    out: list[str] = []
    seen = 0
    for base in ("src", "scripts", "configs"):
        for p in sorted((ROOT / base).rglob("*")):
            if not p.is_file() or ".bak-" in p.name or "__pycache__" in p.parts:
                continue
            seen += 1
            out += [f"{p.relative_to(ROOT)}: {w}" for w in _code_hits(p)]
    assert seen > 0, "zero files checked is not a pass"
    return out


def test_no_vendor_words_in_src() -> None:
    assert _src_hits() == []


def test_vendor_rule_flags_strings_and_passes_library_imports(tmp_path: Path) -> None:
    """Teeth for ADR 0004: the planted string and comment are flagged; the library import and its use are not."""
    word = "lla" + "ma"
    bad = tmp_path / "bad.py"
    bad.write_text(f'from lib import {word.title()}Config\nx = {word.title()}Config()\nname = "tiny_{word}"\n# {word}\n', encoding="utf-8")
    assert len(_code_hits(bad)) == 2
    ok = tmp_path / "ok.py"
    ok.write_text(f"from lib import {word.title()}Config\nx = {word.title()}Config()\nname = 'tiny_model_a'\n", encoding="utf-8")
    assert _code_hits(ok) == []
