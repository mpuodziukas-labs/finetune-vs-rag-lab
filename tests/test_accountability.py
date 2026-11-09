# ruff: noqa
# fmt: off
"""Lab test for the accountability layer: pytest alone proves the layer (LANE CIA).

Runs the oracle's own selftest (a planted RED and a GREEN control for every rule) and the
heal and propose contracts. Never edit this file to make it pass.
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
CHECK = SCRIPTS / "accountability_check.py"
HEAL = SCRIPTS / "heal.sh"
PROPOSE = SCRIPTS / "propose.py"


def run(*cmd, cwd=None, env=None):
    e = dict(os.environ, **(env or {}))
    return subprocess.run(list(map(str, cmd)), capture_output=True, text=True, cwd=cwd, env=e, timeout=300)


def test_oracle_exists():
    assert CHECK.is_file(), "scripts/accountability_check.py missing"


def test_selftest_green():
    r = run(sys.executable, "-P", CHECK, "--selftest")
    last = r.stdout.strip().splitlines()[-1]
    m = re.fullmatch(r"accountability: selftest (\d+)/(\d+)", last)
    assert m and m.group(1) == m.group(2) and int(m.group(1)) >= 40, r.stdout + r.stderr
    assert r.returncode == 0


def test_red_tree_exits_nonzero():
    with tempfile.TemporaryDirectory() as d:
        r = run(sys.executable, "-P", CHECK, d)
        assert r.returncode == 1 and "accountability: RED" in r.stdout


def test_restore_transcript_ends_in_a_green_verdict():
    t = SCRIPTS.parent / "demo" / "verify.transcript.txt"  # A3: the fresh-run proof this lab can be rebuilt
    assert t.is_file(), "demo/verify.transcript.txt missing"
    last = [x for x in t.read_text(encoding="utf-8").splitlines() if x.strip()][-1]
    assert re.search(r"GREEN \d+/\d+", last), last


def test_heal_stops_after_two_rounds():
    with tempfile.TemporaryDirectory() as d:  # empty tree can never heal
        r = run("bash", HEAL, d)
        assert r.returncode == 1 and "heal: OPEN after 2 rounds" in r.stdout
        assert (Path(d) / "OPEN.tsv").is_file()


def test_propose_one_row_for_two_identical_reds():
    with tempfile.TemporaryDirectory() as d:
        t = Path(d) / "t1.log"
        t.write_text("LP1 RED no top-level permissions\nLP1 RED no top-level permissions\nI3 GREEN ok\n", encoding="utf-8")
        r = run(sys.executable, "-P", PROPOSE, "--root", d, t)
        rows = [x for x in (Path(d) / "PROPOSALS.md").read_text(encoding="utf-8").splitlines() if x.startswith("| LP1")]
        assert r.returncode == 0 and len(rows) == 1
