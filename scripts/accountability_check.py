#!/usr/bin/env python3
# ruff: noqa
# fmt: off
# Vendored byte-identical into every lab (sha compared across labs); each lab has its own ruff style, so style is pinned by the sha, not by the lab config.
"""Accountability oracle: least privilege, CIA triad, bounded self-heal. Stdlib only, offline.

    python3 -P scripts/accountability_check.py [ROOT] [--live]   verdict lines, then one summary line
    python3 -P scripts/accountability_check.py --selftest        planted RED + GREEN control per rule
    python3 -P scripts/accountability_check.py ROOT --reseal     rewrite receipts/SHA256SUMS (heal path)

Exit 0 only when every applicable rule is GREEN. --live also runs scripts/verify.sh twice (I4, A1).
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".hypothesis",
    ".terraform",
    "tmp",
    "work",
    "_attic",
    ".accountability",
    "htmlcov",
    ".verify",
}
SKIP_SUFFIX = {
    ".npz",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pyc",
    ".bin",
    ".gz",
    ".pdf",
    ".db",
    ".sqlite",
    ".parquet",
    ".tiktoken",
    ".zip",
    ".woff",
    ".woff2",
    ".ico",
}
SELF_NAMES = {"accountability_check.py", "test_accountability.py", "heal.sh", "propose.py", "ACCOUNTABILITY.md"}
SUMS = "receipts/SHA256SUMS"
SEALED = ("tests/", "README.md")  # a mismatch here is a human edit: heal refuses, owner reseals
LIVE_LIMIT_S = 120
RULE_IDS = ["LP1", "LP2", "LP3", "LP4", "LP5", "C1", "C2", "C3", "I1", "I2", "I3", "I4", "A1", "A2", "A3", "SH1", "SH2", "SH3", "DOC"]
LIVE_ONLY = {"I4", "A1"}


def files(root: Path) -> list[Path]:
    if (root / ".git").exists():
        r = subprocess.run(["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"], capture_output=True, check=False)
        if r.returncode == 0 and r.stdout:
            out = [root / n for n in r.stdout.decode().split("\0") if n]
            return sorted(p for p in out if p.is_file())
    out = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        out += [Path(dp) / f for f in fn]
    return sorted(out)


def text(p: Path) -> str | None:
    if p.suffix in SKIP_SUFFIX or p.stat().st_size > 2_000_000:
        return None
    try:
        return p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def rel(root: Path, p: Path) -> str:
    return str(p.relative_to(root))


def workflows(root: Path) -> list[Path]:
    d = root / ".github" / "workflows"
    return sorted(d.glob("*.y*ml")) if d.is_dir() else []


# ---- workflow parsing (line based, stdlib) ----
def perm_blocks(lines: list[str]):
    """Yield (indent, inline_value, [(scope, value, line)]) for every permissions: key."""
    for i, ln in enumerate(lines):
        m = re.match(r"^(\s*)permissions:\s*(\S.*)?$", ln)
        if not m:
            continue
        ind = len(m.group(1))
        inline = (m.group(2) or "").split("#")[0].strip()
        scopes = []
        for nxt in lines[i + 1 :]:
            if not nxt.strip() or nxt.lstrip().startswith("#"):
                continue
            ni = len(nxt) - len(nxt.lstrip())
            if ni <= ind:
                break
            mm = re.match(r"^\s+([\w-]+):\s*(\w[\w-]*)", nxt)
            if mm:
                scopes.append((mm.group(1), mm.group(2), nxt))
        yield ind, inline, scopes


def job_chunks(lines: list[str]) -> dict[str, list[str]]:
    jobs: dict[str, list[str]] = {}
    cur = None
    injobs = False
    for ln in lines:
        if re.match(r"^jobs:\s*$", ln):
            injobs = True
            continue
        if injobs and re.match(r"^\S", ln):
            injobs = False
        m = re.match(r"^  ([\w-]+):\s*$", ln) if injobs else None
        if m:
            cur = m.group(1)
            jobs[cur] = []
        elif cur and injobs:
            jobs[cur].append(ln)
    return jobs


def r_lp1(root, opts):
    wf = workflows(root)
    if not wf:
        return "NA", "no workflows"
    bad = []
    for p in wf:
        lines = p.read_text(encoding="utf-8").splitlines()
        top = [b for b in perm_blocks(lines) if b[0] == 0]
        if not top:
            bad.append(f"{p.name}: no top-level permissions")
            continue
        _, inline, scopes = top[0]
        if inline in ("write-all",) or any(v == "write" for _, v, _ in scopes):
            bad.append(f"{p.name}: top-level write scope")
        elif not (inline in ("read-all", "{}") or ("contents", "read") in [(s, v) for s, v, _ in scopes]):
            bad.append(f"{p.name}: top-level default is not contents: read")
        for ind, _inl, sc in perm_blocks(lines):
            if ind == 0:
                continue
            for s, v, ln in sc:
                if v == "write" and "# why:" not in ln:
                    bad.append(f"{p.name}: job write {s} without '# why:'")
    return ("RED", "; ".join(bad)) if bad else ("GREEN", f"{len(wf)} workflows")


def r_lp2(root, opts):
    wf = workflows(root)
    if not wf:
        return "NA", "no workflows"
    bad = []
    for p in wf:
        lines = p.read_text(encoding="utf-8").splitlines()
        top = {s: v for ind, _, sc in perm_blocks(lines) if ind == 0 for s, v, _ in sc}
        for name, body in job_chunks(lines).items():
            jp = {s: v for _, _, sc in perm_blocks(body) for s, v, _ in sc}
            eff = jp if jp else top
            if eff.get("contents") == "write" and eff.get("pull-requests") == "write":
                bad.append(f"{p.name}:{name}")
    return ("RED", "contents+pull-requests write in one job: " + ", ".join(bad)) if bad else ("GREEN", "no combined write")


LP3_PATTERNS = [
    (re.compile(r"\bsudo\b"), "sudo"),
    (re.compile(r"chmod\s+(-R\s+)?0?777"), "chmod 777"),
    (re.compile(r"(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh\b"), "pipe to shell"),
    (re.compile(r">>?\s*(/etc|/usr|/opt|/Library|/System|/Users|/var/(?!folders|tmp)|~/|\$HOME|\$\{HOME\})"), "write outside repo"),
]


def lp3_targets(root: Path):
    for p in files(root):
        r = rel(root, p)
        if p.name in SELF_NAMES:
            continue
        if r.startswith(("scripts/", ".github/", ".devcontainer/", "deploy/")) or p.name == "Makefile":
            yield p


def r_lp3(root, opts):
    bad = []
    n = 0
    for p in lp3_targets(root):
        t = text(p)
        if t is None:
            continue
        n += 1
        for i, ln in enumerate(t.splitlines(), 1):
            if ln.lstrip().startswith("#"):
                continue
            for rx, label in LP3_PATTERNS:
                if rx.search(ln):
                    bad.append(f"{rel(root, p)}:{i} {label}")
    if n == 0:
        return "RED", "zero scripts scanned"
    return ("RED", "; ".join(bad[:6])) if bad else ("GREEN", f"{n} files")


def r_lp4(root, opts):
    dc = root / ".devcontainer" / "devcontainer.json"
    dockerfiles = [p for p in files(root) if p.name.startswith("Dockerfile")]
    if not dc.is_file() and not dockerfiles:
        return "NA", "no devcontainer or Dockerfile"
    bad = []
    if dc.is_file():
        m = re.search(r'"remoteUser"\s*:\s*"([^"]*)"', dc.read_text(encoding="utf-8"))
        if not m or m.group(1) in ("", "root"):
            bad.append("devcontainer remoteUser unset or root")
    for d in dockerfiles:
        users = re.findall(r"^USER\s+(\S+)", d.read_text(encoding="utf-8"), re.M)
        if not users or users[-1] in ("root", "0"):
            bad.append(f"{d.name} final user is root")
    return ("RED", "; ".join(bad)) if bad else ("GREEN", "non-root")


def r_lp5(root, opts):
    dep = root / ".github" / "dependabot.yml"
    pc = root / ".pre-commit-config.yaml"
    bad = []
    if not dep.is_file() or "github-actions" not in dep.read_text(encoding="utf-8"):
        bad.append("dependabot.yml missing or no github-actions ecosystem")
    if not pc.is_file():
        bad.append(".pre-commit-config.yaml missing")
    return ("RED", "; ".join(bad)) if bad else ("GREEN", "dependabot + pre-commit")


SECRET_PATTERNS = [
    re.compile(x)
    for x in (r"AKIA[0-9A-Z]{16}", r"sk-or-" r"v1-[A-Za-z0-9]{20,}", r"sk-[A-Za-z0-9_-]{32,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"gh[pousr]_[A-Za-z0-9]{36,}")
]


def r_c1(root, opts):
    bad = []
    n = 0
    for p in files(root):
        r = rel(root, p)
        if p.name == ".env" or (p.name.startswith(".env.") and p.name != ".env.example"):
            bad.append(f"{r}: env file in tree")
            continue
        if p.name in SELF_NAMES:
            continue
        t = text(p)
        if t is None:
            continue
        n += 1
        for rx in SECRET_PATTERNS:
            if rx.search(t):
                bad.append(f"{r}: key shape")
                break
    if n == 0:
        return "RED", "zero files scanned"
    return ("RED", "; ".join(bad[:6])) if bad else ("GREEN", f"{n} files clean")


def r_c2(root, opts):
    gi = root / ".gitignore"
    if not gi.is_file():
        return "RED", ".gitignore missing"
    pats = [x.strip().strip("/") for x in gi.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith(("#", "!"))]
    ledger_tracked = (
        any(p.name.startswith(".cost-ledger") for p in files(root) if p.parent == root)
        and subprocess.run(["git", "-C", str(root), "ls-files", "--error-unmatch", ".cost-ledger.tsv"], capture_output=True, check=False).returncode == 0
    )
    bad = []
    for sample in (".env", ".env.local", "x.pem", "x.key", ".cost-ledger.tsv"):
        if sample == ".cost-ledger.tsv" and ledger_tracked:
            continue  # deliberate committed ledger: recorded exception, not flipped
        if not any(fnmatch.fnmatch(sample, pt) for pt in pats):
            bad.append(sample)
    return ("RED", "not ignored: " + ", ".join(bad)) if bad else ("GREEN", "ignore patterns cover secrets")


C3_PATTERNS = [
    # private, CGNAT and link-local ranges only: those are the cluster and home addresses that must not publish
    (
        re.compile(
            r"(?<![\d.])(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01])|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])"
            r"|169\.254)\.\d{1,3}\.\d{1,3}(?![\d.]*\d)(?!/)"
        ),
        "private IP literal",
    ),
    (re.compile("/Use" + r"rs/[A-Za-z]"), "owner home path"),
    (re.compile(r"Obsi" + r"dian/|~/\.e" + r"xo|api-ke" + r"ys\.json"), "vault or key path"),
    (re.compile(r"[?&](api[_-]?key|key|token)=[A-Za-z0-9_-]{16,}"), "key param in URL"),
]


def r_c3(root, opts):
    bad = []
    n = 0
    for p in files(root):
        if p.name in SELF_NAMES or p.name.endswith((".lock", ".cdx.json")) or p.name == "uv.lock":
            continue
        t = text(p)
        if t is None:
            continue
        n += 1
        for rx, label in C3_PATTERNS:
            m = rx.search(t)
            if m and label.startswith("private IP") and rel(root, p).startswith(("corpus/docs/", "cassettes/")):
                continue  # upstream docs and recorded replies quote documentation addresses; hash-verified elsewhere
            if m:
                bad.append(f"{rel(root, p)}: {label}")
                break
    if n == 0:
        return "RED", "zero files scanned"
    return ("RED", "; ".join(bad[:6]) + (f" (+{len(bad) - 6})" if len(bad) > 6 else "")) if bad else ("GREEN", f"{n} files clean")


def r_i1(root, opts):
    pub = root / "PUBLISH.tsv"
    if not pub.is_file():
        return "RED", "PUBLISH.tsv missing"
    rows = [ln.split("\t") for ln in pub.read_text(encoding="utf-8").splitlines() if ln.strip()]
    hdr = rows[0]
    if "literal" not in hdr or "command" not in hdr or len(rows) < 2:
        return "RED", "PUBLISH.tsv header lacks literal/command or has no rows"
    li, ci = hdr.index("literal"), hdr.index("command")
    if any(len(r) <= max(li, ci) or not r[li].strip() or not r[ci].strip() for r in rows[1:]):
        return "RED", "PUBLISH.tsv row with empty literal or command"
    readme = root / "README.md"
    if not readme.is_file():
        return "RED", "README.md missing"
    fold = "\n".join([x for x in readme.read_text(encoding="utf-8").splitlines() if x.strip()][:12])
    backing = pub.read_text(encoding="utf-8")
    for q in (root / "demo", root / "docs"):
        if q.is_dir():
            for p in sorted(q.rglob("*")):
                if p.is_file() and p.suffix in (".txt", ".tsv", ".md", ".json"):
                    backing += "\n" + (text(p) or "")

    def cited(n: str) -> bool:  # backed by a row or file text, or its line links to an existing local file
        if n in backing:
            return True
        for ln in fold.splitlines():
            if n in ln and any((root / lk.split("#")[0]).is_file() for lk in re.findall(r"\]\(([^)\s:]+)\)", ln)):
                return True
        return False

    missing = [n for n in sorted(set(re.findall(r"(?<![\w./-])\d+/\d+(?![\w/])", fold))) if not cited(n)]
    return ("RED", "fold ratio without backing: " + ", ".join(missing)) if missing else ("GREEN", f"{len(rows) - 1} rows, fold backed")


def sums_map(root: Path) -> dict[str, str] | None:
    s = root / SUMS
    if not s.is_file():
        return None
    out = {}
    for ln in s.read_text(encoding="utf-8").splitlines():
        m = re.fullmatch(r"([0-9a-f]{64})  (\S.*)", ln)
        if not m:
            return None
        out[m.group(2)] = m.group(1)
    return out


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sum_targets(root: Path) -> list[str]:
    out = []
    u = root / "receipts" / "UNSEALED.txt"  # optional: receipts re-measured without a reseal, one path per line
    unsealed = set(u.read_text(encoding="utf-8").split()) if u.is_file() else set()
    for p in files(root):
        r = rel(root, p)
        if r == SUMS or r in unsealed or p.name in (".DS_Store",):
            continue
        if r.startswith(("receipts/", "demo/", "tests/")) or r == "README.md":
            if "__pycache__" not in r and "/tmp/" not in r:
                out.append(r)
    return sorted(out)


def r_i2(root, opts):
    m = sums_map(root)
    if m is None:
        return "RED", f"{SUMS} missing or malformed"
    tg = sum_targets(root)
    if not any(t.startswith(("receipts/", "demo/")) for t in tg):
        return "RED", "zero receipts to seal"
    bad = [t for t in tg if t not in m] + [t for t in m if t not in tg and not (root / t).is_file()]
    bad += [t for t in tg if t in m and sha(root / t) != m[t]]
    return ("RED", "sha mismatch or unlisted: " + ", ".join(sorted(set(bad))[:6])) if bad else ("GREEN", f"{len(tg)} files sealed")


def sealed_drift(root: Path) -> list[str]:
    """Sealed paths (tests, README) whose sha differs from the sums file, or that are new: human edits."""
    m = sums_map(root)
    if m is None:
        return []
    return [t for t in sum_targets(root) if t.startswith(SEALED) and (t not in m or sha(root / t) != m[t])] + [
        t for t in m if t.startswith(SEALED) and not (root / t).is_file()
    ]


def reseal(root: Path, quiet: bool = False) -> int:
    if not any(t.startswith(("receipts/", "demo/")) for t in sum_targets(root)):
        print("reseal: nothing to seal")
        return 1
    lines = [f"{sha(root / t)}  {t}" for t in sum_targets(root)]
    (root / "receipts").mkdir(exist_ok=True)
    (root / SUMS).write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not quiet:
        print(f"reseal: {len(lines)} files")
    return 0


def r_i3(root, opts):
    wf = workflows(root)
    if not wf:
        return "NA", "no workflows"
    bad = []
    for p in wf:
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            m = re.match(r"^\s*-?\s*uses:\s*(\S+)", ln)
            if m and not m.group(1).startswith(("./", "docker://")) and not re.search(r"@[0-9a-f]{40}$", m.group(1)):
                bad.append(f"{p.name}:{i}")
    return ("RED", f"{len(bad)} unpinned uses: " + ", ".join(bad[:5])) if bad else ("GREEN", "all pinned to 40-hex")


def verdict_line(out: str) -> str:
    ls = [x.strip() for x in out.splitlines() if x.strip()]
    return ls[-1] if ls else ""


def run_verify(root: Path):
    t0 = time.time()
    r = subprocess.run(
        ["bash", str(root / "scripts" / "verify.sh")], cwd=root, capture_output=True, text=True, env=dict(os.environ, HEAVY="0"), timeout=900, check=False
    )
    return time.time() - t0, verdict_line(r.stdout + r.stderr), r.returncode


def live_runs(root: Path, opts):
    if "_live" not in opts:
        if not (root / "scripts" / "verify.sh").is_file():
            opts["_live"] = None
        else:
            opts["_live"] = [run_verify(root), run_verify(root)]
    return opts["_live"]


def r_i4(root, opts):
    runs = live_runs(root, opts)
    if runs is None:
        return "RED", "scripts/verify.sh missing"
    (_, v1, _), (_, v2, _) = runs
    return ("GREEN", v1) if v1 and v1 == v2 else ("RED", f"two runs differ: {v1!r} vs {v2!r}")


def r_a1(root, opts):
    runs = live_runs(root, opts)
    if runs is None:
        return "RED", "scripts/verify.sh missing"
    (t, v, rc) = runs[0]
    lim = opts.get("limit", LIVE_LIMIT_S)
    if rc != 0:
        return "RED", f"HEAVY=0 verify exit {rc}: {v}"
    return ("GREEN", f"{t:.0f}s, {v}") if t < lim else ("RED", f"{t:.0f}s over {lim}s")


A2_BAD = re.compile(
    r"\bSKIP\b|(ruff|mypy|pytest|verify\.sh)[^\n]*\|\|\s*(true|:)\s*(;|$)|"
    r"(command -v|which)\s+(ruff|mypy|pytest)[^\n]*\|\|\s*(echo|true|:)\s*$|continue-on-error"
)


def r_a2(root, opts):
    p = root / "scripts" / "ci-local.sh"
    if not p.is_file():
        return "RED", "scripts/ci-local.sh missing"
    t = p.read_text(encoding="utf-8")
    hits = [ln.strip() for ln in t.splitlines() if not ln.lstrip().startswith("#") and A2_BAD.search(ln)]
    if hits:
        return "RED", "soft-fail pattern: " + hits[0][:70]
    if not re.search(r"exit\s+[1-9]|\|\|\s*exit|set\s+-\w*e|RED", t):
        return "RED", "no failing path in ci-local.sh"
    return "GREEN", "fails closed (static)"


def r_a3(root, opts):
    cands = [root / "demo" / "rollback.transcript.txt", root / "scripts" / "restore_check.sh", root / "demo" / "verify.transcript.txt"]
    have = [c for c in cands if c.is_file()]
    if not have:
        return "RED", "no rollback transcript, restore_check.sh or verify transcript"
    tests = "\n".join((text(p) or "") for p in files(root) if rel(root, p).startswith("tests/"))
    cited = [c.name for c in have if c.name in tests or "verify.transcript" in tests and c.name.startswith("verify")]
    return ("GREEN", "restore proof " + cited[0]) if cited else ("RED", "restore proof exists but no test cites it")


def r_sh1(root, opts):
    h = root / "scripts" / "heal.sh"
    if not h.is_file():
        return "RED", "scripts/heal.sh missing"
    t = h.read_text(encoding="utf-8")
    need = ["OPEN.tsv", "accountability_check.py", "REFUSED"]
    miss = [n for n in need if n not in t]
    return ("RED", "heal.sh lacks " + ", ".join(miss)) if miss else ("GREEN", "heal.sh present")


def r_sh2(root, opts):
    return ("GREEN", "propose.py present") if (root / "scripts" / "propose.py").is_file() else ("RED", "scripts/propose.py missing")


def r_sh3(root, opts):
    h = root / "scripts" / "heal.sh"
    if not h.is_file():
        return "RED", "scripts/heal.sh missing"
    return ("GREEN", "MAX_ROUNDS=2") if re.search(r"^MAX_ROUNDS=2\s*$", h.read_text(encoding="utf-8"), re.M) else ("RED", "MAX_ROUNDS=2 not set")


def r_doc(root, opts):
    p = root / "docs" / "ACCOUNTABILITY.md"
    if not p.is_file():
        return "RED", "docs/ACCOUNTABILITY.md missing"
    t = p.read_text(encoding="utf-8")
    miss = [i for i in RULE_IDS if i != "DOC" and not re.search(rf"\|\s*{i}\s*\|", t)]
    return ("RED", "table lacks " + ", ".join(miss)) if miss else ("GREEN", "table lists every rule")


FN = {
    "LP1": r_lp1,
    "LP2": r_lp2,
    "LP3": r_lp3,
    "LP4": r_lp4,
    "LP5": r_lp5,
    "C1": r_c1,
    "C2": r_c2,
    "C3": r_c3,
    "I1": r_i1,
    "I2": r_i2,
    "I3": r_i3,
    "I4": r_i4,
    "A1": r_a1,
    "A2": r_a2,
    "A3": r_a3,
    "SH1": r_sh1,
    "SH2": r_sh2,
    "SH3": r_sh3,
    "DOC": r_doc,
}


def evaluate(root: Path, live: bool = False, opts=None) -> list[tuple[str, str, str]]:
    opts = {} if opts is None else opts
    res = []
    for rid in RULE_IDS:
        if rid in LIVE_ONLY and not live:
            continue
        st, why = FN[rid](root, opts)
        res.append((rid, st, why))
    return res


def report(res) -> int:
    for rid, st, why in res:
        print(f"{rid} {st} {why}")
    app = [r for r in res if r[1] != "NA"]
    red = [r[0] for r in app if r[1] == "RED"]
    n = len(app)
    if red:
        print(f"accountability: RED {n - len(red)}/{n} ({','.join(red)})")
        return 1
    print(f"accountability: GREEN {n}/{n}")
    return 0


# ---------------------------------------------------------------- selftest
PIN = "0123456789abcdef0123456789abcdef01234567"
DOC_TABLE = "# Accountability\n\n| rule | letter |\n|---|---|\n" + "\n".join(f"| {i} | x |" for i in RULE_IDS if i != "DOC") + "\n"
WF = f"name: ci\non: push\npermissions:\n  contents: read\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@{PIN} # v4\n"


def w(root: Path, name: str, body: str) -> None:
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def good_tree(root: Path) -> None:
    w(root, ".github/workflows/ci.yml", WF)
    w(root, ".github/dependabot.yml", "version: 2\nupdates:\n  - package-ecosystem: github-actions\n    directory: /\n")
    w(root, ".pre-commit-config.yaml", "repos: []\n")
    w(root, ".gitignore", ".env*\n*.pem\n*.key\n.cost-ledger*\n")
    w(root, ".devcontainer/devcontainer.json", '{"image": "x", "remoteUser": "vscode"}\n')
    w(root, "scripts/ci-local.sh", "#!/bin/bash\nset -e\nruff check . || exit 1\necho 'ci-local: GREEN 1/1'\n")
    w(root, "scripts/verify.sh", "#!/bin/bash\necho 'verify: GREEN 1/1'\n")
    for n in ("heal.sh", "propose.py"):
        w(root, f"scripts/{n}", (HERE / n).read_text(encoding="utf-8") if (HERE / n).is_file() else "")
    w(root, "README.md", "# lab\nResult: GREEN 3/3 checks\n")
    w(root, "PUBLISH.tsv", "schema_version\tid\tliteral\tcommand\n1\ta\t3/3 checks\techo ok\n")
    w(root, "demo/verify.transcript.txt", "GREEN 3/3 checks\n")
    w(root, "receipts/a.json", '{"n": 1}\n')
    w(root, "tests/test_x.py", "import scripts_check\n")
    w(root, "tests/test_y.py", "# cites verify.transcript.txt\n")
    w(root, "docs/ACCOUNTABILITY.md", DOC_TABLE)
    reseal(root, quiet=True)


def sub(path: str, old: str, new: str):
    def f(root: Path):
        p = root / path
        p.write_text(p.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")

    return f


def planted(root: Path, name: str, body: str):
    w(root, name, body)


def flip_receipt(root: Path):
    p = root / "receipts" / "a.json"
    b = bytearray(p.read_bytes())
    b[2] ^= 1
    p.write_bytes(bytes(b))


MUTANTS = {
    "LP1": lambda r: w(r, ".github/workflows/ci.yml", WF.replace("permissions:\n  contents: read\n", "")),
    "LP2": lambda r: w(
        r,
        ".github/workflows/ci.yml",
        WF.replace("    runs-on", "    permissions:\n      contents: write # why: x\n      pull-requests: write # why: y\n    runs-on"),
    ),
    "LP3": lambda r: w(r, "scripts/x.sh", "#!/bin/bash\nsu" + "do apt-get install x\n"),
    "LP4": lambda r: w(r, ".devcontainer/devcontainer.json", '{"image": "x"}\n'),
    "LP5": lambda r: (r / ".github/dependabot.yml").write_text("version: 2\nupdates: []\n", encoding="utf-8"),
    "C1": lambda r: w(r, "docs/leak.md", "key AK" + "IA" + "ABCDEFGHIJKLMNOP\n"),
    "C2": lambda r: (r / ".gitignore").write_text("*.pem\n", encoding="utf-8"),
    "C3": lambda r: w(r, "docs/x.md", "run on 10.20." + "30.40 now\n"),
    "C3b": lambda r: w(r, "docs/x.md", "see /Use" + "rs/someone/notes\n"),
    "I1": lambda r: w(r, "README.md", "# lab\nResult: GREEN 99/100 checks\n"),
    "I2": flip_receipt,
    "I3": lambda r: w(r, ".github/workflows/ci.yml", WF.replace("@" + PIN, "@v4")),
    "A2": lambda r: w(r, "scripts/ci-local.sh", "#!/bin/bash\ncommand -v ruff || echo SKIP\n"),
    "A3": lambda r: ((r / "demo/verify.transcript.txt").write_text("x\n", encoding="utf-8"), (r / "tests/test_y.py").write_text("pass\n", encoding="utf-8")),
    "SH1": lambda r: (r / "scripts/heal.sh").write_text("echo hi\n", encoding="utf-8"),
    "SH2": lambda r: (r / "scripts/propose.py").rename(r / "scripts/propose.py.moved"),
    "SH3": lambda r: (r / "scripts/heal.sh").write_text((r / "scripts/heal.sh").read_text(encoding="utf-8").replace("MAX_ROUNDS=2", "MAX_ROUNDS=9"), encoding="utf-8"),
    "DOC": lambda r: (r / "docs/ACCOUNTABILITY.md").write_text("| LP1 |\n", encoding="utf-8"),
}


def selftest() -> int:
    ok = total = 0

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal ok, total
        total += 1
        ok += bool(cond)
        print(("ok   " if cond else "FAIL ") + name + ("" if cond else f"  {detail}"))

    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "base"
        base.mkdir()
        good_tree(base)
        res = evaluate(base)
        check("base tree GREEN for every static rule", all(s == "GREEN" for _, s, _ in res), str(res))
        for key, mut in MUTANTS.items():
            rid = key[:-1] if key.endswith("b") else key
            t = Path(d) / f"m_{key}"
            t.mkdir()
            good_tree(t)
            mut(t)
            if rid not in ("I2",):
                reseal(t, quiet=True)  # keep I2 GREEN so only the planted rule is red
            st = dict((a, b) for a, b, _ in evaluate(t))
            check(f"{rid} planted RED", st[rid] == "RED", str(st))
            others = [k for k, v in st.items() if k != rid and v == "RED"]
            check(f"{rid} planted defect is isolated", not others or rid in ("A3", "SH1", "SH2"), str(others))  # these overlap by construction
        # LP1 exceptions: a job-level write needs a why comment; with it, GREEN
        t = Path(d) / "lp1ok"
        t.mkdir()
        good_tree(t)
        w(t, ".github/workflows/ci.yml", WF.replace("    runs-on", "    permissions:\n      contents: write # why: release upload\n    runs-on"))
        check("LP1 job write with why comment is GREEN", r_lp1(t, {})[0] == "GREEN")
        w(t, ".github/workflows/ci.yml", WF.replace("    runs-on", "    permissions:\n      contents: write\n    runs-on"))
        check("LP1 job write without why is RED", r_lp1(t, {})[0] == "RED")
        # C1 control: key-less env example is GREEN; a real .env is RED
        w(t, ".env.example", "X=\n")
        check("C1 .env.example is not a leak", r_c1(t, {})[0] == "GREEN")
        w(t, ".env", "X=1\n")
        check("C1 .env file is RED", r_c1(t, {})[0] == "RED")
        # empty tree must not pass vacuously
        e = Path(d) / "empty"
        e.mkdir()
        check("empty tree is RED not GREEN", report_quiet(evaluate(e)) == 1)
        # I2: tamper detection after reseal, and heal refusal on edited tests
        t2 = Path(d) / "tests_edited"
        t2.mkdir()
        good_tree(t2)
        (t2 / "tests/test_x.py").write_text("assert True\n", encoding="utf-8")
        r = subprocess.run(["bash", str(HERE / "heal.sh"), str(t2)], capture_output=True, text=True, check=False)
        check("heal refuses a planted 'tests edited' tree", r.returncode == 2 and "heal: REFUSED" in r.stdout, r.stdout[-200:])
        check("heal left the edited test untouched", (t2 / "tests/test_x.py").read_text(encoding="utf-8") == "assert True\n")
        # I2 receipt tamper is healable (receipts only)
        t3 = Path(d) / "receipt_tamper"
        t3.mkdir()
        good_tree(t3)
        flip_receipt(t3)
        check("I2 tamper RED before heal", r_i2(t3, {})[0] == "RED")
        r = subprocess.run(["bash", str(HERE / "heal.sh"), str(t3)], capture_output=True, text=True, check=False)
        check(
            "heal reseals a receipts-only drift or stops bounded",
            ("accountability: GREEN" in r.stdout and r.returncode == 0) or "heal: OPEN after 2 rounds" in r.stdout,
            r.stdout[-300:],
        )
        # SH3: never-healing fixture stops after 2 rounds
        t4 = Path(d) / "never"
        t4.mkdir()
        good_tree(t4)
        w(t4, ".github/workflows/ci.yml", WF.replace("permissions:\n  contents: read\n", ""))
        reseal(t4, quiet=True)
        r = subprocess.run(["bash", str(HERE / "heal.sh"), str(t4)], capture_output=True, text=True, check=False)
        check("heal on unhealable tree prints OPEN after 2 rounds", "heal: OPEN after 2 rounds" in r.stdout and r.returncode == 1, r.stdout[-300:])
        check("heal wrote exactly one OPEN.tsv row", len((t4 / "OPEN.tsv").read_text(encoding="utf-8").strip().splitlines()) == 1)
        r2 = subprocess.run(["bash", str(HERE / "heal.sh"), str(t4)], capture_output=True, text=True, check=False)
        check("heal is idempotent: second run same verdict", r2.stdout.strip().splitlines()[-1] == r.stdout.strip().splitlines()[-1])
        # live rules
        lv = Path(d) / "live_ok"
        lv.mkdir()
        good_tree(lv)
        st = dict((a, b) for a, b, _ in evaluate(lv, live=True))
        check("I4 and A1 GREEN on stable fast verify", st["I4"] == "GREEN" and st["A1"] == "GREEN", str(st))
        lv2 = Path(d) / "live_flap"
        lv2.mkdir()
        good_tree(lv2)
        w(lv2, "scripts/verify.sh", '#!/bin/bash\necho "verify: GREEN $RANDOM"\n')
        check("I4 RED when two runs differ", r_i4(lv2, {})[0] == "RED")
        lv3 = Path(d) / "live_slow"
        lv3.mkdir()
        good_tree(lv3)
        w(lv3, "scripts/verify.sh", "#!/bin/bash\nsleep 2\necho 'verify: GREEN 1/1'\n")
        check("A1 RED when verify exceeds the limit", r_a1(lv3, {"limit": 1})[0] == "RED")
        # A2 dynamic: a fail-closed script with the tool missing exits non-zero
        w(t, "scripts/ci-local.sh", "#!/bin/bash\ncommand -v nosuchtool_zz >/dev/null || { echo 'ci-local: RED missing tool'; exit 1; }\n")
        r = subprocess.run(["bash", str(t / "scripts/ci-local.sh")], capture_output=True, text=True, check=False)
        check("A2 missing tool gives RED exit 1, never SKIP", r.returncode == 1 and "SKIP" not in r.stdout)
        w(t, "scripts/ci-local.sh", '#!/bin/bash\nBIN="$(dirname "$(command -v ruff || echo /nonexistent/ruff)")"\nruff check . || exit 1\n')
        check("A2 path-fallback line is not a soft-fail", r_a2(t, {})[0] == "GREEN")
        w(t, "README.md", "# lab\nscored 34/50 ([scorecard](docs/ACCOUNTABILITY.md))\n")
        check("I1 ratio with a link to an existing file is backed", r_i1(t, {})[0] == "GREEN")
    print(f"accountability: selftest {ok}/{total}")
    return 0 if ok == total else 1


def report_quiet(res) -> int:
    return 1 if any(s == "RED" for _, s, _ in res if s != "NA") else 0


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return selftest()
    args = [a for a in argv if not a.startswith("--")]
    root = Path(args[0]).resolve() if args else HERE.parent
    if "--reseal" in argv:
        return reseal(root)
    if "--sealed-drift" in argv:
        d = sealed_drift(root)
        print("sealed-drift: " + (", ".join(d) if d else "none"))
        return 1 if d else 0
    return report(evaluate(root, live="--live" in argv))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
