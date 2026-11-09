# RUBRIC R1: publishable RAG evaluation and finetune-vs-RAG repos

53 binary criteria. 41 core + 12 from the coordinator addendum (OSI layers 1-7: 6 rows; debug and deslop: 6 rows). Source ids S01-S30 are in SOURCES.tsv (fetch sha pinned). Rows applying only to one repo type say so in the pass condition; mark `na` in a scorecard only when the repo has no such stage.


## Reproducibility

| id | criterion | why a reviewer cares | pass (binary) | oracle a stranger runs |
|---|---|---|---|---|
| R1-01 | One command runs every gate and ends with N/N | Reviewers will run exactly one command before reading anything (S02, S21) | Command exits 0 only when every check passes; last line matches ^GREEN [0-9]+/[0-9]+ | `bash scripts/verify.sh \| tail -1; echo $?` |
| R1-02 | Dependencies pinned by lockfile or hashes and installed from it in CI | Unpinned deps make numbers drift (S01 code/data questions, S18 Pinned-Dependencies) | Lock check passes and CI installs with --frozen or --require-hashes | `uv lock --check  OR  grep -c '^    --hash=sha256' requirements.txt` |
| R1-03 | Every number in README regenerated from a committed receipt by a listed command | A hand-typed number is unverifiable (S02 results table, S21) | PUBLISH.tsv (or equivalent) replay equals README literals, 0 mismatches | `bash scripts/verify.sh (publish replay step) or python3 scripts/pub.py check` |
| R1-04 | ML Code Completeness: dependencies, training code, evaluation code, released weights or stated reason, results table | The five MLCC items are the community minimum (S02) | All 5 present, or README states why an item is not applicable | `manual: README Layout + Reproduce sections map to the 5 items` |
| R1-05 | Public CI green on a fresh clone with no secrets, status badge in README | Reviewers check the Actions tab first (S18, S22, S19 badges) | Workflow on push+PR, last run success, badge links to it | `gh run list --limit 1 --json conclusion; grep -c 'actions/workflows' README.md` |
| R1-06 | Data and model pinned by revision or commit plus sha256, checkable offline | Silent upstream change invalidates results (S01, S12) | Manifest re-hash passes with network off | `python3 corpus/fetch.py --check  OR  grep -c 'revision:' configs/default.yaml` |
| R1-07 | Git history exists and a tagged release matches the published numbers | A repo with no history or tag cannot be cited or bisected (S18, S02) | >=1 commit, a tag whose tree reproduces README | `git rev-list --count HEAD; git tag --list \| wc -l` |
| R1-08 | Hardware, wall time and offline mode stated | Replication needs the cost of replication (S01 compute questions) | README states device, wall time and whether network is needed | `grep -n -i 'wall time\\|cpu\\|gpu\\|offline' README.md` |

## Evaluation validity

| id | criterion | why a reviewer cares | pass (binary) | oracle a stranger runs |
|---|---|---|---|---|
| R1-09 | Frozen split; tuning on dev only; split hash checked by a gate | Test-set peeking is the first thing a hostile reviewer looks for (S20 data leakage) | Gate fails on a planted test-set tune; split hash recomputed from seed | `bash scripts/selftest.sh \| tail -1` |
| R1-10 | Duplicate and near-duplicate leakage across splits measured, not just exact-dedup | Paraphrase leakage inflates accuracy (S20, S27 reports multiple hyperparameter regimes) | A receipt reports max train-test similarity or near-dup count; value stated in README | `python3 scripts/leakage_check.py (or equivalent) prints near_dup=<n>` |
| R1-11 | All stochastic stages seeded and the seeds recorded in receipts | Seeds are the first reproducibility question (S01) | Every receipt carries its seed; reruns reproduce bit-for-bit or within stated tolerance | `grep -L '"seed"' receipts/*.json  (must list nothing relevant)` |
| R1-12 | At least 3 seeds for any trained or sampled stage, mean and sd reported | One seed cannot separate method from luck (S01 error bars, S20 uncertainty, S27 Table 4 variation) | >=3 seeds in receipts; README shows mean +/- sd or range | `python3 -c "import json,glob;print(len(glob.glob('receipts/*seed*.json')))" >= 3` |
| R1-13 | Confidence interval on every headline metric (method named) and a paired test between compared systems | NeurIPS requires stated variability source and method (S01 item 7); ranx offers paired Fisher randomization (S25) | CI method + resamples in README; pairwise p-value or paired bootstrap for each claimed win | `grep -n -i 'bootstrap\\|mcnemar\\|randomization\\|paired' README.md` |
| R1-14 | Metric definitions in README: formula, k, relevance grade, tie handling, empty-gold rule | nDCG@10 and recall@k have variants; ties and unjudged docs change the number (S04 nDCG@10, S11 trec_eval, S10) | README (or METRICS.md) states each formula and tie rule | `grep -n -i 'ndcg\\|recall@' README.md METRICS.md` |
| R1-15 | Metric code cross-checked against a reference library in a test | A home-grown nDCG is distrusted unless it matches trec_eval (S10, S11, S25) | Test compares our value to pytrec_eval or ranx on >=100 random runs at 1e-9 | `pytest tests/test_metrics_reference.py` |
| R1-16 | Baselines: lexical or classical non-LLM baseline plus a published number on the same task | BEIR shows BM25 is a strong baseline (S04, S29); BANKING77 has published accuracies (S27) | Table lists baseline and a cited external number | `grep -n -i 'bm25\\|tf-idf\\|logistic\\|published' README.md` |
| R1-17 | Runs a recognised public benchmark, not only a custom set | Custom-only results cannot be compared with anything (S03, S04, S05, S23) | At least one public dataset run with number beside published figure, difference explained | `manual: README results table has a row citing BEIR/MTEB/BANKING77 full` |
| R1-18 | Experiment matrix covers the factors claimed and states n for every cell | Claims about k, chunking, position, train fraction need the sweep (S17) | Each claimed factor has >=3 levels or a stated reason for fewer; n in every row | `manual: matrix receipt rows vs README claims` |
| R1-19 | Generation quality: faithfulness, answer relevancy, context precision and recall defined (RAGAS or DeepEval formulas) or an explicit proxy, with the judge validated against a human-labelled sample | RAG eval repos report these four (S06, S07, S08, S09, S24); judge validity is the usual attack | Formulas cited; judge agreement vs >=50 human labels reported | `manual: groundedness receipt shows human agreement count` |
| R1-20 | Context-position study follows Lost in the Middle protocol: >=3 context sizes, gold position sweep, closed-book and oracle baselines, >=3 shuffles | Single order at one size is anecdote (S16, S17) | Receipt has n_ctx in {10,20,30}, closed-book and oracle rows, shuffle seeds | `python3 -c "import json;d=json.load(open('receipts/position.json'));print(d['n_ctx'])"` |
| R1-21 | Finetune hyperparameters fully reported; none selected on test | LoRA results depend on rank, alpha, lr, epochs, modules (S15, S14) | Config lists all; audit gate proves test untouched | `cat configs/default.yaml; ftlab audit` |
| R1-22 | Finetune versus RAG compared under matched information and matched tuning effort | Unfair tuning is the standard rebuttal (S20 modeling module) | Same labelled examples feed both; both get a dev-set search of equal size; prompt differences disclosed | `manual: DESIGN.md states the search budget per arm` |
| R1-23 | Cost and latency reported with method, hardware and an estimate label | Cost claims without method are discounted (S01) | p50/p95, n, device, and 'estimate' label where assumed | `grep -n -i 'p95\\|estimate' README.md` |

## Data and licences

| id | criterion | why a reviewer cares | pass (binary) | oracle a stranger runs |
|---|---|---|---|---|
| R1-24 | Licence table for every dataset and model with commit or revision | BEIR itself disclaims dataset licences; the user must check (S03, S12) | Table lists source, licence, revision for each | `cat corpus/LICENSE-NOTES.md  OR  README licence line` |
| R1-25 | Dataset card or data statement: source, size, collection, splits, class list, known biases | HF dataset card standard (S12) | File with licence metadata, size, collection method, limitations | `head -20 DATASET_CARD.md` |
| R1-26 | Model card for any released adapter or model, no template placeholders | HF model card standard: intended use, limitations, training, eval (S13, S14) | Card has zero '[More Information Needed]' strings | `grep -rc 'More Information Needed' artifacts/*/README.md` |
| R1-27 | Code LICENSE present and third-party model/data licences stated | Open-source baseline (S18 License check, S01) | LICENSE file + README licence line | `ls LICENSE; grep -n -i licen README.md` |
| R1-28 | Synthetic or model-generated labels disclosed and a human-audited sample reported | Label noise bounds the ceiling (S20, S12) | README discloses generator and reports audit n and error rate | `grep -n -i 'generated\\|audit' README.md` |

## Code quality and CI

| id | criterion | why a reviewer cares | pass (binary) | oracle a stranger runs |
|---|---|---|---|---|
| R1-29 | CI runs the same lint, strict type check and tests as local | Local-only green is not evidence (S18, S22) | ci.yml contains ruff, mypy, pytest or calls verify.sh | `grep -n 'ruff\\|mypy\\|pytest\\|verify' .github/workflows/*.yml` |
| R1-30 | Planted-defect (mutation) selftest and property tests for metrics | Shows the gates can fail (S20 leakage) | selftest reports N/N planted defects caught | `bash scripts/selftest.sh \| tail -1` |
| R1-31 | Coverage floor enforced | Untested eval code is suspect (S02) | --cov-fail-under or equivalent in the gate | `grep -n 'cov' scripts/verify.sh Makefile` |
| R1-32 | CI hardening: least-privilege permissions, actions pinned by SHA, dependency update bot | OpenSSF Scorecard Token-Permissions, Pinned-Dependencies, Dependency-Update-Tool (S18) | permissions block, uses: lines with 40-hex SHA, dependabot.yml present | `grep -c 'uses: .*@[0-9a-f]\{40\}' .github/workflows/*.yml; ls .github/dependabot.yml` |
| R1-33 | Community files: SECURITY.md, CONTRIBUTING.md, CITATION.cff | Scorecard Security-Policy; RAGChecker and FlashRAG carry citation and policy (S18, S23, S24) | All three exist and are non-empty | `ls SECURITY.md CONTRIBUTING.md CITATION.cff` |

## README and reporting

| id | criterion | why a reviewer cares | pass (binary) | oracle a stranger runs |
|---|---|---|---|---|
| R1-34 | README order follows Standard Readme: title, badges, short description, TOC, install, usage, license | Familiar order lowers reviewer effort (S19) | Sections present in that order | `grep -n '^#' README.md` |
| R1-35 | Headline claim in the first screen with n and 95% CI | Skeptics read the first 20 lines (S22, S23) | Headline sentence has value, n, interval | `sed -n 1,20p README.md` |
| R1-36 | Results table puts baselines and published external numbers beside ours, each with source | Leaderboard convention (S02, S21, S04, S27) | Every external number has a citation link | `manual: table rows vs references` |
| R1-37 | How to cite and a references list | Papers-with-code convention; FlashRAG and RAGChecker both carry a citation block (S23, S24) | CITATION.cff valid; README references section | `cffconvert --validate` |

## Limits and threats to validity

| id | criterion | why a reviewer cares | pass (binary) | oracle a stranger runs |
|---|---|---|---|---|
| R1-38 | Threats to validity section (internal, external, construct) plus a not-measured list | REFORMS generalizability and metrics modules (S20) | Section names each threat and what was not measured | `grep -n -i 'limitation\\|threat\\|not measured' README.md DESIGN.md` |
| R1-39 | Ties reported as ties and negative results kept | Honest nulls are the strongest credibility signal (S01 'no is not grounds for rejection') | README marks non-significant differences as ties | `grep -n -i 'tie' README.md` |

## Security and secrets

| id | criterion | why a reviewer cares | pass (binary) | oracle a stranger runs |
|---|---|---|---|---|
| R1-40 | No secrets in tree or history; keys read from environment only; scan runs in gate | Scorecard Vulnerabilities and Token checks (S18) | Secret scan exit 0 over tree and history | `python3 scripts/secret_scan.py; git log -p \| grep -c 'sk-'` |
| R1-41 | Untrusted-corpus handling (prompt injection) and provider data-retention disclosed | RAG repos are read for injection posture (S24 security policy) | Threat model with measured injection rate; retention route stated | `grep -n -i 'injection\\|retention' THREAT-MODEL.md README.md` |

## OSI layers 1 to 7

| id | criterion | why a reviewer cares | pass (binary) | oracle a stranger runs |
|---|---|---|---|---|
| R1-42 | L1-L2: runs fully offline after fetch; device declared; HF_HUB_OFFLINE or equivalent set to 1 in the gate | Hidden network or hardware dependence breaks replication (S01) | Gate passes with network disabled | `HF_HUB_OFFLINE=1 bash scripts/verify.sh; grep -n OFFLINE scripts/*.sh` |
| R1-43 | L3: tests cannot reach non-loopback addresses; egress hosts are constants in code | Tests that call the internet are flaky and leak data | autouse socket guard raises on non-loopback; one BASE url constant | `grep -n 'socket' tests/conftest.py; grep -rn 'https://' --include=*.py . \| wc -l` |
| R1-44 | L4: every urlopen, requests or download call has a finite timeout | Unbounded sockets hang CI | grep finds 0 network calls without timeout | `grep -rn 'urlopen(' --include=*.py . \| grep -v timeout` |
| R1-45 | L5: retries are bounded with backoff, honour Retry-After, and calls are idempotent (request key or cassette) | Retry storms and double-charging are common reviewer finds | max attempts constant, sleep grows, Retry-After parsed, request id/hash key | `grep -rn -i 'retry-after\\|backoff\\|attempt' --include=*.py .` |
| R1-46 | L6: TLS verification never disabled; every file open names encoding utf-8 | Disabled verify and locale-dependent decoding are classic defects | 0 matches for verify=False / CERT_NONE / _create_unverified_context; 0 open() without encoding | `grep -rn 'verify=False\\|CERT_NONE\\|_create_unverified' --include=*.py .; ruff check --select PLW1514 .` |
| R1-47 | L7: responses schema-validated; HTTP and DNS failures raise typed errors; keys never logged | Untyped KeyError on a provider change is unreviewable | Typed exception for HTTPError, URLError(gaierror), malformed body; scrubber test for key | `grep -rn 'gaierror\\|class .*Error' --include=*.py .; pytest -k scrub` |

## Debug and deslop

| id | criterion | why a reviewer cares | pass (binary) | oracle a stranger runs |
|---|---|---|---|---|
| R1-48 | ruff clean over all code including scripts, with dead-code rules (F401, F841) on | Lint noise signals carelessness | ruff check . exits 0 with no per-file ignore of scripts | `ruff check .` |
| R1-49 | No scratch, backup or one-off patch files tracked; no commented-out code | A .bak next to source reads as unfinished work | 0 files matching *.bak, *.orig, _patch_*; ruff ERA001 clean | `git ls-files \| grep -E '\.bak$\|\.orig$\|_patch_'; ruff check --select ERA001 .` |
| R1-50 | README and CLI text free of filler, hedges and marketing words | Marketing tone triggers distrust in technical readers | dewatermark --check exit 0 AND banned-word grep 0 hits | `dewatermark --check README.md DESIGN.md; grep -n -i -E 'seamless\|robust\|powerful\|blazing\|cutting-edge\|leverage\|state-of-the-art' README.md` |
| R1-51 | README word budget and no duplicated paragraphs | Padding hides the result | README <=1800 words; 0 repeated lines >60 chars | `wc -w README.md; sort README.md \| uniq -d \| awk 'length>60' \| wc -l` |
| R1-52 | Skips and xfails carry an issue id; tests pass 3 consecutive runs | Untracked flakiness destroys trust | 0 bare skip/xfail; 3 runs identical | `grep -rn 'skip\\|xfail' tests \| grep -v '#[0-9]'; for i in 1 2 3; do pytest -q; done` |
| R1-53 | TODO and FIXME carry an issue id | Orphan TODOs are dead intent | 0 bare TODO/FIXME | `grep -rn 'TODO\\|FIXME' --include=*.py --include=*.md . \| grep -v '#[0-9]'` |

Note on INFERRED: trec_eval tie handling (sort by score descending, ties by docid) was not found in the fetched pages (SOURCES.tsv last row). R1-14 asks the lab to state its own rule and pin it with a tie fixture test; do not cite trec_eval for the rule.
