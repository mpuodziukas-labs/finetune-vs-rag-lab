"""Second adversarial pass: gaps found after the first fixes. Each pin was a strict xfail for one open gap; all three are closed."""

import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ftlab import (
    PRODUCER_FILES,
    ProducerManifestError,
    code_sha,
    derive_producer_files,
    legacy_code_sha,
    read_producer_manifest,
    report,
    write_producer_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "ftlab"
_BORROWED = ["smol" + "lm", "hugging" + " face"]


def _local_imports(name: str) -> set[str]:
    """Module files of this package that `name` imports (top level and inside functions)."""
    out: set[str] = set()
    for n in ast.walk(ast.parse((SRC / name).read_text(encoding="utf-8"))):
        if isinstance(n, ast.ImportFrom) and n.module and n.module.split(".")[0] == "ftlab":
            parts = n.module.split(".")
            if len(parts) > 1:
                out.add(parts[1] + ".py")
            else:
                out |= {a.name + ".py" for a in n.names if (SRC / (a.name + ".py")).is_file()}
    return out


def test_import_helper_finds_a_known_edge() -> None:
    """Control for the closure pin: the helper sees the modeling to registry edge, so an empty result would be a bug."""
    assert "registry.py" in _local_imports("modeling.py")
    assert "config.py" in _local_imports("engine.py")


def test_derived_producer_set_covers_config_and_registry() -> None:
    assert {"config.py", "registry.py", "cli.py", "engine.py"} <= set(PRODUCER_FILES)
    assert not ({"report.py", "selftest.py", "__init__.py"} & set(PRODUCER_FILES))


def _git_pkg(tmp_path: Path, init: bool = True) -> Path:
    """Scratch copy of the package, optionally its own git work tree with every file tracked."""
    pkg = tmp_path / "ftlab"
    shutil.copytree(SRC, pkg, ignore=shutil.ignore_patterns("__pycache__", "*.bak-*"))
    if init:
        subprocess.run(["git", "init", "-q"], cwd=pkg, check=True)
        subprocess.run(["git", "add", "-A"], cwd=pkg, check=True)
    return pkg


def test_derive_producer_files_admits_a_planted_source_file(tmp_path: Path) -> None:
    """Scratch copy of the package: a new tracked source file enters the set, an excluded one stays out."""
    pkg = _git_pkg(tmp_path)
    before = set(derive_producer_files(pkg))
    (pkg / "newmod.py").write_text("X = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "newmod.py"], cwd=pkg, check=True)
    assert set(derive_producer_files(pkg)) == before | {"newmod.py"}
    assert code_sha(derive_producer_files(pkg), pkg) != code_sha(tuple(sorted(before)), pkg)


def test_derive_producer_files_ignores_an_untracked_module(tmp_path: Path) -> None:
    """An untracked module stays out of the set; once tracked it enters. The real tree derives the same set as before."""
    pkg = _git_pkg(tmp_path)
    before = set(derive_producer_files(pkg))
    assert before == set(PRODUCER_FILES) and len(before) > 0
    (pkg / "scratch_mod.py").write_text("Y = 2\n", encoding="utf-8")
    assert set(derive_producer_files(pkg)) == before
    subprocess.run(["git", "add", "scratch_mod.py"], cwd=pkg, check=True)
    assert "scratch_mod.py" in derive_producer_files(pkg)


def test_derive_producer_files_outside_a_git_work_tree_is_red(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Planted RED: no work tree means a named RED line and exit 1, never a silent glob fallback."""
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))  # a temp dir under a git checkout must not count as a work tree
    pkg = _git_pkg(tmp_path, init=False)
    with pytest.raises(SystemExit) as exc:
        derive_producer_files(pkg)
    assert exc.value.code == 1
    assert "RED producer-files" in capsys.readouterr().err


def test_manifest_equals_the_git_derivation_on_the_real_tree() -> None:
    """PRODUCERS.txt is sorted, newline-terminated, and equals git ls-files minus the exclude list; runtime PRODUCER_FILES is that file."""
    text = (SRC / "PRODUCERS.txt").read_text(encoding="utf-8")
    assert text.endswith("\n") and not text.endswith("\n\n")
    names = tuple(text.splitlines())
    assert names == tuple(sorted(names)) and len(names) > 0
    assert names == derive_producer_files() == PRODUCER_FILES


def test_manifest_drift_is_red(tmp_path: Path) -> None:
    """Planted RED: a tracked module the manifest does not list makes the derivation differ; regenerating clears it."""
    pkg = _git_pkg(tmp_path)
    write_producer_manifest(pkg)
    assert read_producer_manifest(pkg) == derive_producer_files(pkg)
    (pkg / "newmod.py").write_text("X = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "newmod.py"], cwd=pkg, check=True)
    assert read_producer_manifest(pkg) != derive_producer_files(pkg)
    write_producer_manifest(pkg)
    assert read_producer_manifest(pkg) == derive_producer_files(pkg) and "newmod.py" in read_producer_manifest(pkg)


@pytest.mark.parametrize("content", [None, "", "\n"])
def test_missing_or_empty_manifest_is_a_named_red(tmp_path: Path, content: str | None) -> None:
    pkg = tmp_path / "ftlab"
    pkg.mkdir()
    if content is not None:
        (pkg / "PRODUCERS.txt").write_text(content, encoding="utf-8")
    with pytest.raises(ProducerManifestError) as exc:
        read_producer_manifest(pkg)
    assert "PRODUCERS.txt" in str(exc.value) and "producers.py" in str(exc.value)


def _installed_copy(tmp_path: Path) -> Path:
    """The package copied without .git, as the container and a pip install see it."""
    root = tmp_path / "site"
    shutil.copytree(SRC, root / "ftlab", ignore=shutil.ignore_patterns("__pycache__", "*.bak-*"))
    return root


def _import_ftlab(root: Path, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(root), "GIT_CEILING_DIRECTORIES": str(tmp_path)}
    return subprocess.run([sys.executable, "-c", "import ftlab; print(len(ftlab.PRODUCER_FILES))"], capture_output=True, text=True, env=env, cwd=tmp_path)


def test_import_works_without_git_and_counts_the_manifest(tmp_path: Path) -> None:
    root = _installed_copy(tmp_path)
    r = _import_ftlab(root, tmp_path)
    assert r.returncode == 0, r.stderr
    assert int(r.stdout.strip()) == len((root / "ftlab" / "PRODUCERS.txt").read_text(encoding="utf-8").splitlines())


def test_import_without_the_manifest_is_a_named_red(tmp_path: Path) -> None:
    root = _installed_copy(tmp_path)
    (root / "ftlab" / "PRODUCERS.txt").write_text("", encoding="utf-8")
    r = _import_ftlab(root, tmp_path)
    assert r.returncode != 0 and "PRODUCERS.txt" in r.stderr


def test_legacy_sha_moves_on_any_other_producer_edit(tmp_path: Path) -> None:
    """The legacy sha undoes only the manifest edit in cli.py; one more byte in a legacy file changes it."""
    pkg = tmp_path / "ftlab"
    shutil.copytree(SRC, pkg, ignore=shutil.ignore_patterns("__pycache__", "*.bak-*"))
    base = legacy_code_sha(pkg)
    assert base == legacy_code_sha()
    (pkg / "engine.py").write_text((pkg / "engine.py").read_text(encoding="utf-8") + "\n#\n", encoding="utf-8")
    assert legacy_code_sha(pkg) != base


def _train_receipt_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, dict]:
    rec = tmp_path / "receipts"
    shutil.copytree(ROOT / "receipts", rec)
    monkeypatch.setattr(report, "REC", rec)
    target = rec / "train_f25.json"
    return target, json.loads(target.read_text(encoding="utf-8"))


def test_receipt_manifest_is_the_basis_of_the_sha_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target, obj = _train_receipt_copy(tmp_path, monkeypatch)
    assert report.check_receipts() == 0  # legacy receipts without a manifest still verify
    obj["producer_files"] = list(PRODUCER_FILES)
    obj["code_sha"] = code_sha()
    target.write_text(json.dumps(obj), encoding="utf-8")
    assert report.check_receipts() == 0
    obj["code_sha"] = "0" * 64
    target.write_text(json.dumps(obj), encoding="utf-8")
    assert report.check_receipts() == 1


def test_receipt_manifest_missing_a_current_producer_is_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Planted RED: a manifest that omits config.py is stale even when its own sha matches."""
    target, obj = _train_receipt_copy(tmp_path, monkeypatch)
    short = [f for f in PRODUCER_FILES if f != "config.py"]
    obj["producer_files"] = short
    obj["code_sha"] = code_sha(tuple(short))
    target.write_text(json.dumps(obj), encoding="utf-8")
    assert report.check_receipts() == 1


def test_receipt_manifest_naming_a_missing_file_is_red(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Planted RED: a listed file that no longer exists is reported, not crashed on."""
    target, obj = _train_receipt_copy(tmp_path, monkeypatch)
    obj["producer_files"] = [*PRODUCER_FILES, "ghost.py"]
    obj["code_sha"] = "0" * 64
    target.write_text(json.dumps(obj), encoding="utf-8")
    assert report.check_receipts() == 1


def test_producer_files_cover_every_imported_module() -> None:
    seen: set[str] = set()
    todo = [f for f in PRODUCER_FILES if f != "cli.py"]
    while todo:
        cur = todo.pop()
        for dep in _local_imports(cur):
            if dep not in seen:
                seen.add(dep)
                todo.append(dep)
    assert seen - set(PRODUCER_FILES) == set(), sorted(seen - set(PRODUCER_FILES))


def _prose_hits(paths: list[Path]) -> list[str]:
    """Lines naming a model family or model host; license lines are attribution and skipped."""
    found: list[str] = []
    assert paths, "zero files checked is not a pass"
    for p in paths:
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            low = ln.lower()
            if "own licenses" not in low and any(w in low for w in _BORROWED):
                found.append(f"{p.name}:{i}")
    return found


def test_prose_scan_flags_planted_term_and_passes_clean_text(tmp_path: Path) -> None:
    bad = tmp_path / "bad.md"
    bad.write_text("fine line\nloads from " + "Hugging" + " Face today\n", encoding="utf-8")
    ok = tmp_path / "ok.md"
    ok.write_text("fine line\nloads from model-a today\nModel keeps its own licenses: " + "Smol" + "LM2\n", encoding="utf-8")
    assert _prose_hits([bad]) == ["bad.md:2"]
    assert _prose_hits([ok]) == []


def test_no_model_family_or_host_names_in_prose() -> None:
    docs = [ROOT / n for n in ("README.md", "DESIGN.md", "SPEC.md", "THREAT-MODEL.md")]
    docs += [p for p in sorted((ROOT / "docs").glob("*.md"))] + sorted((ROOT / "docs" / "ADR").glob("*.md"))
    assert _prose_hits(docs) == []


def test_threat_model_has_a_row_for_stale_receipts() -> None:
    text = (ROOT / "docs" / "THREAT-MODEL.md").read_text(encoding="utf-8")
    assert "code_sha" in text and "test_check_receipts_flags_stale_code_sha" in text
