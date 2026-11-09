# Module map

The decisions and their costs are recorded in [DESIGN.md](../DESIGN.md). This file is the map from each requirement in [SPEC.md](../SPEC.md) to the code that carries it.

Data flows one way: public dataset, pinned fetch, seeded split, three approaches scored by one rule, receipts, analysis, generated README blocks.

| stage | module | requirement |
|---|---|---|
| pinned download that fails closed on a hash mismatch | `src/ftlab/data.py` | R10 |
| name to factory registries for datasets, models, adapters and retrievers | `src/ftlab/registry.py` | R11 |
| pooled, deduplicated, seeded stratified split with nested training fractions | `src/ftlab/splits.py`, `src/ftlab/data.py` | R01, R02 |
| BM25 retriever used to choose few-shot examples | `src/ftlab/retrieve.py` | R03 |
| prompts and the restricted next-token scoring rule | `src/ftlab/prompts.py`, `src/ftlab/modeling.py` | R01 |
| training, evaluation and the forgetting probe, one process per phase | `src/ftlab/engine.py`, `src/ftlab/forget.py`, `src/ftlab/cli.py` | R04 to R06 |
| bootstrap interval, exact McNemar test, latency percentiles | `src/ftlab/stats.py` | R04, R05, R06 |
| leakage, train-split evaluation and no-op adapter audit | `src/ftlab/audit.py` | R07 |
| tuning that reads only train and dev | `src/ftlab/cli.py` | R08 |
| README blocks regenerated from receipts | `src/ftlab/report.py` | R12 |
| network guard for tests | `tests/conftest.py` | R09 |

Control files outside the package: `scripts/verify.sh` is the gate battery, `scripts/mutants.py` plants defects in a copy of the tree, `scripts/sbom_stdlib.py` writes the SBOM from the freeze file, and `scripts/accountability_check.py` seals tests and README against `receipts/SHA256SUMS`.
