"""CLI. Each heavy phase is its own process so peak RSS is attributable to that phase."""

import argparse
import json
import platform
import resource
import sys
from pathlib import Path
from typing import Any

from ftlab import PRODUCER_FILES, SCHEMA_VERSION, code_sha
from ftlab.audit import audit
from ftlab.config import ROOT, LabConfig, load_config
from ftlab.data import Row
from ftlab.engine import do_eval, do_train, eval_receipt, label_first_ids
from ftlab.prompts import few_shot, tuned, zero_shot
from ftlab.registry import DATASETS, MODELS, RETRIEVERS
from ftlab.splits import make_split, subset_train

REC = ROOT / "receipts"
ART = ROOT / "artifacts"
DATA = ROOT / "data"
EXPECTED_TEST_EVALS = 7  # zeroshot + 3 retrieval fractions + 3 lora fractions


def peak_rss_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 1e6 if sys.platform == "darwin" else r / 1e3  # darwin reports bytes


def pct(frac: float) -> int:
    return round(frac * 100)


def write(name: str, obj: dict[str, Any]) -> Path:
    REC.mkdir(exist_ok=True)
    p = REC / name
    p.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return p


def read(name: str) -> dict[str, Any]:
    out: dict[str, Any] = json.loads((REC / name).read_text(encoding="utf-8"))
    return out


class Ctx:
    def __init__(self, cfg: LabConfig) -> None:
        self.cfg = cfg
        rows: list[Row] = DATASETS.get(cfg.dataset["name"])(cfg.dataset, DATA)
        self.by_id = {r.id: r for r in rows}
        self.label_of = {r.id: r.label for r in rows}
        classes: dict[str, str] = cfg.dataset["classes"]
        self.labels = sorted(classes)
        self.words = [classes[x] for x in self.labels]
        self.word_of = dict(zip(self.labels, self.words, strict=True))

    def split(self) -> dict[str, Any]:
        s = read("split.json")
        if s["hash"] != make_split(self.label_of, self.cfg.spec)["hash"]:
            raise RuntimeError("receipts/split.json does not match config seed/spec")
        return s

    def rows(self, ids: list[str]) -> list[Row]:
        return [self.by_id[i] for i in ids]


def cmd_prepare(cfg: LabConfig) -> None:
    import peft
    import torch
    import transformers

    c = Ctx(cfg)
    s = make_split(c.label_of, cfg.spec)
    write("split.json", {"schema_version": SCHEMA_VERSION, "kind": "split", "n_rows": len(c.by_id),
                         "labels": c.labels, "words": c.words, **s})  # fmt: skip
    write("env.json", {"schema_version": SCHEMA_VERSION, "kind": "env", "python": platform.python_version(),
                       "torch": torch.__version__, "transformers": transformers.__version__,
                       "peft": peft.__version__, "machine": platform.machine(),
                       "platform": platform.platform(), "torch_threads": torch.get_num_threads()})  # fmt: skip
    print(f"prepare: rows={len(c.by_id)} train={len(s['train'])} dev={len(s['dev'])} "
          f"test={len(s['test'])} hash={s['hash'][:12]}")  # fmt: skip


def cmd_train(cfg: LabConfig, frac: float) -> None:
    c = Ctx(cfg)
    s = c.split()
    model, tok = MODELS.get(cfg.model["name"])(cfg.model)
    first = label_first_ids(tok, c.words)
    ids = subset_train(s["train"], c.label_of, frac)
    model, info = do_train(model, tok, c.rows(ids), c.rows(s["dev"]), c.labels, first,
                           cfg.adapter, cfg.seed)  # fmt: skip
    model.save_pretrained(ART / f"lora_f{pct(frac)}")
    write(f"train_f{pct(frac)}.json", {
        "schema_version": SCHEMA_VERSION, "kind": "train", "frac": frac, "seed": cfg.seed,
        "split_hash": s["hash"], "peak_rss_mb": peak_rss_mb(), "code_sha": code_sha(), "producer_files": list(PRODUCER_FILES), **info})  # fmt: skip
    print(f"train frac={frac}: n={info['n_train']} secs={info['train_seconds']:.1f} "
          f"rss={peak_rss_mb():.0f}MB dev_acc={info['dev_curve'][-1]['dev_accuracy']:.3f}")  # fmt: skip


def _retrieval_prompt(c: Ctx, pool_ids: list[str], k: int) -> Any:
    pool = c.rows(pool_ids)
    bm = RETRIEVERS.get(c.cfg.raw["retriever"]["name"])([r.text for r in pool])

    def build(r: Row) -> str:
        top = bm.top_k(r.text, k)
        demos = [(pool[i].text, c.word_of[pool[i].label]) for i in reversed(top)]
        return few_shot(r.text, demos, c.words)

    return build


def cmd_eval(cfg: LabConfig, method: str, frac: float, split_name: str, k: int | None) -> None:
    from peft import PeftModel

    c = Ctx(cfg)
    s = c.split()
    model, tok = MODELS.get(cfg.model["name"])(cfg.model)
    first = label_first_ids(tok, c.words)
    rows = c.rows(s[split_name])
    extra: dict[str, Any] = {}
    if method == "zeroshot":
        build: Any = lambda r: zero_shot(r.text, c.words)  # noqa: E731
        fr: float | None = None
    elif method == "retrieval":
        if k is None:
            k = int(read("tune_k.json")["chosen_k"])
        build = _retrieval_prompt(c, subset_train(s["train"], c.label_of, frac), k)
        fr, extra["k"] = frac, k
    else:
        model = PeftModel.from_pretrained(model, ART / f"lora_f{pct(frac)}").merge_and_unload()
        build, fr = (lambda r: tuned(r.text)), frac
    ev = do_eval(model, tok, rows, build, c.labels, first)
    rec = eval_receipt(ev, method, fr, split_name, s)
    rec.update(extra, peak_rss_mb=peak_rss_mb())
    name = f"eval_{method}{'' if fr is None else f'_{pct(fr)}'}_{split_name}.json"
    write(name, rec)
    print(f"{name}: acc={ev['accuracy']:.4f} n={len(rows)} "
          f"p50={sorted(ev['latency_ms'])[len(rows) // 2]:.0f}ms")  # fmt: skip


def cmd_tune_k(cfg: LabConfig) -> None:
    c = Ctx(cfg)
    s = c.split()
    model, tok = MODELS.get(cfg.model["name"])(cfg.model)
    first = label_first_ids(tok, c.words)
    dev = c.rows(s["dev"])
    accs: dict[str, float] = {}
    for k in cfg.raw["retriever"]["ks"]:
        ev = do_eval(model, tok, dev, _retrieval_prompt(c, s["train"], k), c.labels, first)
        accs[str(k)] = ev["accuracy"]
        print(f"tune-k k={k} dev_acc={ev['accuracy']:.4f}")
    best = max(accs.values())
    chosen = min(int(k) for k, v in accs.items() if v == best)
    write("tune_k.json", {"schema_version": SCHEMA_VERSION, "kind": "tune_k", "split": "dev",
                          "dev_accuracy": accs, "chosen_k": chosen})  # fmt: skip


def cmd_forget(cfg: LabConfig) -> None:
    from peft import PeftModel

    from ftlab.forget import load_chunks, perplexity

    model, tok = MODELS.get(cfg.model["name"])(cfg.model)
    chunks = load_chunks(cfg.raw["forgetting"], tok, DATA)
    base = perplexity(model, chunks)
    pm = PeftModel.from_pretrained(model, ART / "lora_f100")
    pm.eval()
    tuned_ppl = perplexity(pm, chunks)
    with pm.disable_adapter():
        off = perplexity(pm, chunks)
    write("forget.json", {"schema_version": SCHEMA_VERSION, "kind": "forget",
                          "probe": "wikitext-2-raw test perplexity", "n_chunks": len(chunks),
                          "chunk_tokens": int(cfg.raw["forgetting"]["chunk_tokens"]),
                          "ppl_base": base, "ppl_adapter_off": off, "ppl_lora": tuned_ppl,
                          "ppl_ratio": tuned_ppl / base})  # fmt: skip
    print(f"forget: base={base:.3f} adapter_off={off:.3f} lora={tuned_ppl:.3f} ratio={tuned_ppl / base:.4f}")


def cmd_audit(cfg: LabConfig) -> int:
    c = Ctx(cfg)
    s = c.split()
    files = sorted(REC.glob("eval_*_test.json"))
    if len(files) < EXPECTED_TEST_EVALS:  # empty-input success is a lie
        print(f"AUDIT RED: {len(files)} test eval receipts < {EXPECTED_TEST_EVALS}")
        return 1
    bad = 0
    for f in files:
        ev = json.loads(f.read_text(encoding="utf-8"))
        train: dict[str, Any] | None = None
        if ev["method"] == "lora":
            train = read(f"train_f{pct(ev['frac'])}.json")
        elif ev["method"] == "retrieval":
            train = {"train_ids": subset_train(s["train"], c.label_of, ev["frac"])}
        fails = audit(c.label_of, cfg.spec, s, train, ev)
        bad += bool(fails)
        print(f"audit {f.name}: {'OK' if not fails else fails}")
    print(f"AUDIT {len(files) - bad}/{len(files)}")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ftlab")
    ap.add_argument("cmd", choices=["prepare", "train", "eval", "tune-k", "forget", "audit",
                                    "analyze", "report", "show", "check-receipts", "selftest"])  # fmt: skip
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--config")
    ap.add_argument("--frac", type=float, default=1.0)
    ap.add_argument("--method", choices=["zeroshot", "retrieval", "lora"])
    ap.add_argument("--split", default="test", choices=["dev", "test"])
    ap.add_argument("--k", type=int)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        from ftlab.selftest import main as st

        return st()
    cfg = load_config(a.config)
    if a.cmd == "prepare":
        cmd_prepare(cfg)
    elif a.cmd == "train":
        cmd_train(cfg, a.frac)
    elif a.cmd == "eval":
        cmd_eval(cfg, a.method, a.frac, a.split, a.k)
    elif a.cmd == "tune-k":
        cmd_tune_k(cfg)
    elif a.cmd == "forget":
        cmd_forget(cfg)
    elif a.cmd == "audit":
        return cmd_audit(cfg)
    else:
        from ftlab import report

        return report.dispatch(a.cmd, cfg, a.arg, a.check)
    return 0


if __name__ == "__main__":
    sys.exit(main())
