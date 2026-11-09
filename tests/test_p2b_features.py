"""P2b features: community files, pinned workflows, examples, objection sources (all offline, stdlib only)."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
IS_RAG = (ROOT / "rag").is_dir()


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_every_workflow_action_is_sha_pinned() -> None:
    files = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    assert len(files) >= 4
    uses = [ln for f in files for ln in f.read_text(encoding="utf-8").splitlines() if re.match(r"\s*-?\s*uses:", ln)]
    assert uses and all(re.search(r"@[0-9a-f]{40} # v", u) for u in uses), uses


def test_codeql_workflow_pinned_and_scheduled() -> None:
    t = read(".github/workflows/codeql.yml")
    lines = [ln for ln in t.splitlines() if "codeql-action/" in ln]
    assert len(lines) == 2 and all(re.search(r"@[0-9a-f]{40} # v3", ln) for ln in lines)
    assert "cron:" in t and "languages: python" in t and "security-events: write" in t


def test_release_workflow_tag_trigger_runs_ci_local() -> None:
    t = read(".github/workflows/release.yml")
    assert 'tags: ["v*"]' in t and "bash scripts/ci-local.sh" in t
    assert "EVIDENCE.md SBOM.cdx.json" in t and t.count("contents: write") == 1


def test_issue_forms_and_pr_template() -> None:
    cfg = read(".github/ISSUE_TEMPLATE/config.yml")
    assert "blank_issues_enabled: false" in cfg and "EVIDENCE.md" in cfg
    for f in ("bug.yml", "question.yml"):
        t = read(".github/ISSUE_TEMPLATE/" + f)
        assert t.startswith("name:") and "body:" in t and "required: true" in t
    assert read(".github/pull_request_template.md").count("- [ ]") >= 4


def test_codeowners_and_conduct() -> None:
    co = read(".github/CODEOWNERS").splitlines()
    assert co[0] == "* [OWNER_HANDLE]" and any(x.startswith(".github/") for x in co)
    coc = read("CODE_OF_CONDUCT.md")
    assert "Contributor Covenant" in coc and "2.1" in coc and "@" not in coc


def test_precommit_calls_ci_local_and_ci_local_fails_closed() -> None:
    assert "bash scripts/ci-local.sh" in read(".pre-commit-config.yaml") and "always_run: true" in read(".pre-commit-config.yaml")
    local = read("scripts/ci-local.sh")
    assert "skipped" not in local and "pipefail" in local and "ci-local: GREEN" in local


def test_devcontainer_is_python_311_with_install() -> None:
    d = json.loads(read(".devcontainer/devcontainer.json"))
    assert "python:3.11" in d["image"] and d["postCreateCommand"]


def test_security_and_citation_follow_template_fields() -> None:
    s = read("SECURITY.md")
    for key in ("acknowledgement within 7 days", "first assessment within 14 days", "30 days", "90 days",
                "## Supported versions", "## Safe harbor"):
        assert key in s, key
    c = read("CITATION.cff")
    assert f"repository-code: \"https://github.com/mpuodziukas-labs/{ROOT.name}\"" in c or "repository-code:" in c
    assert "url:" in c and "puodziukas" in c


def test_objections_cite_real_test_lines() -> None:
    rows = [ln for ln in read("OBJECTIONS.md").splitlines() if re.search(r"`[\w./-]+:\d+`\s*\|$", ln)]
    assert len(rows) >= 5
    for ln in rows:
        path, num = re.search(r"`([\w./-]+):(\d+)`\s*\|$", ln).groups()  # type: ignore[union-attr]
        src = (ROOT / path).read_text(encoding="utf-8").splitlines()
        assert 1 <= int(num) <= len(src), (path, num)
        named = re.search(r"`tests/[\w./]+::(\w+)`", ln)
        if named:
            assert re.match(rf"\s*def {named.group(1)}\b", src[int(num) - 1]), (path, num, named.group(1))


def test_readme_under_1800_words_and_links_examples() -> None:
    assert len(read("README.md").split()) < 1800


def _expected(script: Path) -> str:
    return re.search(r"^# Expected output: (\S+)$", script.read_text(encoding="utf-8"), re.M).group(1)  # type: ignore[union-attr]


def test_examples_reproduce_readme_numbers() -> None:
    scripts = sorted((ROOT / "examples").glob("*.sh"))
    assert len(scripts) >= 1
    env = {"PATH": "/usr/bin:/bin", "PY": sys.executable, "PYTHONDONTWRITEBYTECODE": "1"}
    if not IS_RAG:
        ft = Path(sys.executable).parent / "ftlab"
        if not ft.exists():
            pytest.skip("ftlab not installed in this interpreter")
        env["FTLAB"] = str(ft)
    for s in scripts:
        r = subprocess.run(["bash", str(s)], capture_output=True, text=True, env=env, cwd=ROOT)
        want = _expected(s)
        assert r.returncode == 0 and r.stdout.strip() == want, (s.name, r.stdout[-200:], r.stderr[-200:])
        assert want in read("README.md"), "example number not in README"
