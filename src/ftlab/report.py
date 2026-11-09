"""analyze (receipts -> results.json), report (results.json -> README blocks + SVG),
show (print one measured value), check-receipts (schema gate)."""

import json
import re
import sys
from typing import Any

from ftlab import PRODUCER_FILES, SCHEMA_VERSION, code_sha, legacy_code_sha
from ftlab.config import ROOT, LabConfig
from ftlab.stats import bootstrap_ci, mcnemar_exact, percentiles

REC = ROOT / "receipts"
README = ROOT / "README.md"
SVG = ROOT / "docs" / "training_curve.svg"
FRACS = (25, 50, 100)


def _p(p: float) -> str:
    return "p<0.0001" if p < 1e-4 else f"p={p:.4f}"
REQUIRED = {
    "split": ["train", "dev", "test", "hash", "spec"],
    "env": ["torch", "peft", "transformers"],
    "tune_k": ["dev_accuracy", "chosen_k"],
    "forget": ["ppl_base", "ppl_lora", "ppl_ratio"],
    "train": ["train_ids", "curve", "dev_curve", "train_seconds", "peak_rss_mb", "adapter"],
    "eval": ["ids", "gold", "preds", "correct", "accuracy", "latency_ms", "prompt_tokens"],
    "results": ["display", "decision"],
}
# split, env, tune_k, forget, results (5) + 7 test evals + 3 train runs
EXPECTED_RECEIPTS_MIN = 15


def _load(name: str) -> dict[str, Any]:
    out: dict[str, Any] = json.loads((REC / name).read_text(encoding="utf-8"))
    return out


def _metrics(ev: dict[str, Any], n_boot: int, seed: int) -> dict[str, Any]:
    acc, lo, hi = bootstrap_ci(ev["correct"], n_boot=n_boot, seed=seed)
    p50, p95 = percentiles(ev["latency_ms"])
    return {
        "acc": acc, "lo": lo, "hi": hi, "p50": p50, "p95": p95,
        "lat_mean": sum(ev["latency_ms"]) / len(ev["latency_ms"]),
        "tok_mean": sum(ev["prompt_tokens"]) / len(ev["prompt_tokens"]),
        "tok_total": sum(ev["prompt_tokens"]), "n": len(ev["correct"]),
    }  # fmt: skip


def _winner(a_better: bool, b_better: bool) -> str:
    return "fine-tune" if a_better else "retrieve" if b_better else "tie"


def analyze(cfg: LabConfig) -> dict[str, Any]:
    nb, seed = int(cfg.raw["bootstrap_n"]), cfg.seed
    zs = _load("eval_zeroshot_test.json")
    ret = {p: _load(f"eval_retrieval_{p}_test.json") for p in FRACS}
    lor = {p: _load(f"eval_lora_{p}_test.json") for p in FRACS}
    tr = {p: _load(f"train_f{p}.json") for p in FRACS}
    fg = _load("forget.json")
    tk = _load("tune_k.json")
    A, B, C = lor[100], ret[100], zs
    m = {"A": _metrics(A, nb, seed), "B": _metrics(B, nb, seed), "C": _metrics(C, nb, seed)}
    mc = {}
    for name, (x, y) in {"AB": (A, B), "AC": (A, C), "BC": (B, C)}.items():
        n01, n10, p = mcnemar_exact(x["correct"], y["correct"])
        mc[name] = {"n01": n01, "n10": n10, "p": p}
    eff = {}
    for p in FRACS:
        n01, n10, pv = mcnemar_exact(lor[p]["correct"], ret[p]["correct"])
        eff[str(p)] = {"A": _metrics(lor[p], nb, seed), "B": _metrics(ret[p], nb, seed),
                  "n_train": tr[p]["n_train"], "p_AB": pv}  # fmt: skip
    rate = float(cfg.raw["cost"]["assumed_usd_per_hour"])
    t100 = tr[100]
    train_cost = t100["train_seconds"] / 3600 * rate
    cpq = {k: m[k]["lat_mean"] / 1000 / 3600 * rate for k in ("A", "B", "C")}
    breakeven = train_cost / (cpq["B"] - cpq["A"]) if cpq["B"] > cpq["A"] else None
    curve = t100["curve"]
    k = max(1, len(curve) // 10)
    first, last = (sum(c["loss"] for c in curve[:k]) / k, sum(c["loss"] for c in curve[-k:]) / k)

    r: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION, "kind": "results", "seed": seed,
        "n_test": m["A"]["n"], "methods": m, "mcnemar": mc, "efficiency": eff,
        "train": {"seconds": t100["train_seconds"], "steps": t100["steps"],
                  "peak_rss_mb": t100["peak_rss_mb"], "loss_first": first, "loss_last": last,
                  "lora_params": t100["adapter"]["lora_params"], "rank": t100["adapter"]["rank"],
                  "dev_curve": t100["dev_curve"], "n_train": t100["n_train"]},
        "forget": fg, "chosen_k": tk["chosen_k"],
        "cost": {"usd_per_hour_assumed": rate, "train_usd": train_cost,
                 "per_1k_queries_usd": {x: cpq[x] * 1000 for x in cpq},
                 "breakeven_queries": breakeven},
    }  # fmt: skip
    r["decision"] = _decision(r)
    r["display"] = _display(r)
    return r


def _decision(r: dict[str, Any]) -> list[dict[str, str]]:
    m, ef, mc = r["methods"], r["efficiency"], r["mcnemar"]
    rows: list[dict[str, str]] = []

    def acc_row(label: str, a: dict[str, Any], b: dict[str, Any], p: float) -> None:
        sig = p < 0.05
        rows.append({
            "criterion": label,
            "fine_tune": f"{a['acc']:.3f}", "retrieve": f"{b['acc']:.3f}",
            "winner": _winner(sig and a["acc"] > b["acc"], sig and b["acc"] > a["acc"]),
            "evidence": f"McNemar exact {_p(p)} (tie unless p<0.05)",
        })  # fmt: skip

    acc_row("Accuracy, 100% of train", m["A"], m["B"], mc["AB"]["p"])
    acc_row("Accuracy, 25% of train", ef["25"]["A"], ef["25"]["B"], ef["25"]["p_AB"])
    ga, gb = ef["100"]["A"]["acc"] - ef["25"]["A"]["acc"], ef["100"]["B"]["acc"] - ef["25"]["B"]["acc"]
    rows.append({
        "criterion": "Gain from 25% to 100% of train (pp)",
        "fine_tune": f"{ga * 100:+.1f}", "retrieve": f"{gb * 100:+.1f}",
        "winner": _winner(ga - gb > 0.02, gb - ga > 0.02),
        "evidence": "larger gain wins; tie if within 2 pp",
    })  # fmt: skip
    fa, fb = m["A"]["p50"], m["B"]["p50"]
    rows.append({
        "criterion": "Latency p50 (ms, batch 1)",
        "fine_tune": f"{fa:.1f}", "retrieve": f"{fb:.1f}",
        "winner": _winner(fa < 0.9 * fb, fb < 0.9 * fa),
        "evidence": f"ratio retrieve/fine-tune = {fb / fa:.2f}x; tie if within 10%",
    })  # fmt: skip
    ta, tb = m["A"]["tok_mean"], m["B"]["tok_mean"]
    rows.append({
        "criterion": "Prompt tokens per query",
        "fine_tune": f"{ta:.0f}", "retrieve": f"{tb:.0f}",
        "winner": _winner(ta < tb, tb < ta),
        "evidence": f"ratio retrieve/fine-tune = {tb / ta:.2f}x",
    })  # fmt: skip
    c = r["cost"]
    be = c["breakeven_queries"]
    rows.append({
        "criterion": "Marginal $ per 1k queries (estimate)",
        "fine_tune": f"{c['per_1k_queries_usd']['A']:.5f}",
        "retrieve": f"{c['per_1k_queries_usd']['B']:.5f}",
        "winner": _winner(
            c["per_1k_queries_usd"]["A"] < c["per_1k_queries_usd"]["B"],
            c["per_1k_queries_usd"]["B"] < c["per_1k_queries_usd"]["A"],
        ),
        "evidence": (f"train cost ${c['train_usd']:.4f} recovered after ~{be:,.0f} queries"
                     if be else "fine-tune is not cheaper per query; no break-even"),
    })  # fmt: skip
    rows.append({
        "criterion": "Cost to absorb new labeled data",
        "fine_tune": f"retrain, {r['train']['seconds']:.0f} s measured",
        "retrieve": "append to index, no gradient step",
        "winner": "retrieve",
        "evidence": "structural; fine-tune figure is the measured 100% training time",
    })  # fmt: skip
    ratio = r["forget"]["ppl_ratio"]
    rows.append({
        "criterion": "General-text perplexity vs base (lower ratio is better)",
        "fine_tune": f"{ratio:.3f}x", "retrieve": "1.000x (weights untouched)",
        "winner": "retrieve" if ratio > 1.02 else "tie",
        "evidence": "retrieve wins only if fine-tune degrades general text by more than 2%",
    })  # fmt: skip
    return rows


def _display(r: dict[str, Any]) -> dict[str, str]:
    m, mc, tr, fg, c = r["methods"], r["mcnemar"], r["train"], r["forget"], r["cost"]
    d: dict[str, str] = {"n_test": str(r["n_test"]), "chosen_k": str(r["chosen_k"])}
    for k in ("A", "B", "C"):
        d[f"acc.{k}"] = f"{m[k]['acc']:.3f}"
        d[f"ci.{k}"] = f"[{m[k]['lo']:.3f}, {m[k]['hi']:.3f}]"
        d[f"p50.{k}"] = f"{m[k]['p50']:.1f}"
        d[f"p95.{k}"] = f"{m[k]['p95']:.1f}"
        d[f"tok.{k}"] = f"{m[k]['tok_mean']:.0f}"
    for k in ("AB", "AC", "BC"):
        d[f"p.{k}"] = _p(mc[k]["p"])
        d[f"disc.{k}"] = f"{mc[k]['n01']}/{mc[k]['n10']}"
    d["train_seconds"] = f"{tr['seconds']:.1f}"
    d["peak_rss_mb"] = f"{tr['peak_rss_mb']:.0f}"
    d["lora_params"] = f"{tr['lora_params']:,}"
    d["loss_first"] = f"{tr['loss_first']:.3f}"
    d["loss_last"] = f"{tr['loss_last']:.3f}"
    d["ppl_base"] = f"{fg['ppl_base']:.2f}"
    d["ppl_lora"] = f"{fg['ppl_lora']:.2f}"
    d["ppl_ratio"] = f"{fg['ppl_ratio']:.3f}"
    d["train_usd"] = f"{c['train_usd']:.4f}"
    d["breakeven"] = f"{c['breakeven_queries']:,.0f}" if c["breakeven_queries"] else "none"
    for p in FRACS:
        e = r["efficiency"][str(p)]
        d[f"eff.A.{p}"] = f"{e['A']['acc']:.3f}"
        d[f"eff.B.{p}"] = f"{e['B']['acc']:.3f}"
    return d


def _blocks(r: dict[str, Any]) -> dict[str, str]:
    d, m = r["display"], r["methods"]
    res = [
        "| Approach | Test accuracy | 95% bootstrap CI | p50 ms | p95 ms | Prompt tokens/query |",
        "|---|---|---|---|---|---|",
    ]
    names = {"A": "A. LoRA fine-tune", "B": f"B. BM25 retrieval few-shot (k={d['chosen_k']})",
             "C": "C. Zero-shot (control)"}  # fmt: skip
    for k in ("A", "B", "C"):
        res.append(f"| {names[k]} | {d[f'acc.{k}']} | {d[f'ci.{k}']} | {d[f'p50.{k}']} | "
                   f"{d[f'p95.{k}']} | {d[f'tok.{k}']} |")  # fmt: skip
    res += ["", f"n_test = {d['n_test']}. McNemar exact (discordant pairs shown as A-wrong-B-right / "
            f"A-right-B-wrong): A vs B {d['p.AB']} ({d['disc.AB']}); A vs C {d['p.AC']} "
            f"({d['disc.AC']}); B vs C {d['p.BC']} ({d['disc.BC']})."]  # fmt: skip
    tr = [
        f"LoRA rank {r['train']['rank']}, {d['lora_params']} trainable parameters, "
        f"{r['train']['n_train']} training rows, {r['train']['steps']} steps.",
        "",
        "| Measure | Value |", "|---|---|",
        f"| Training wall time (steps only) | {d['train_seconds']} s |",
        f"| Peak RSS of the training process | {d['peak_rss_mb']} MB |",
        f"| Training loss, first vs last 10% of steps | {d['loss_first']} to {d['loss_last']} |",
        "| Dev accuracy by epoch | "
        + ", ".join(f"{x['dev_accuracy']:.3f}" for x in r["train"]["dev_curve"]) + " |",
    ]  # fmt: skip
    eff = ["| Train fraction | Train rows | A. LoRA | B. Retrieval | A vs B McNemar p |",
           "|---|---|---|---|---|"]  # fmt: skip
    for p in FRACS:
        e = r["efficiency"][str(p)]
        eff.append(f"| {p}% | {e['n_train']} | {d[f'eff.A.{p}']} | {d[f'eff.B.{p}']} | "
                   f"{_p(e['p_AB'])[2:]} |")  # fmt: skip
    forget = [
        f"Held-out general text (wikitext-2 test, {r['forget']['n_chunks']} chunks of "
        f"{r['forget']['chunk_tokens']} tokens). Perplexity: base {d['ppl_base']}, "
        f"after LoRA {d['ppl_lora']}, ratio {d['ppl_ratio']}x.",
    ]  # fmt: skip
    cost = [
        f"ESTIMATE, not a bill: wall time x an assumed ${r['cost']['usd_per_hour_assumed']:.2f}/hour "
        "CPU instance (config `cost.assumed_usd_per_hour`, an assumption, not a vendor quote).",
        "",
        "| Item | Estimate |", "|---|---|",
        f"| One-time LoRA training | ${d['train_usd']} |",
        f"| Per 1k queries, A / B / C | ${r['cost']['per_1k_queries_usd']['A']:.5f} / "
        f"${r['cost']['per_1k_queries_usd']['B']:.5f} / ${r['cost']['per_1k_queries_usd']['C']:.5f} |",
        f"| Break-even queries (A recovers training cost vs B) | {d['breakeven']} |",
    ]  # fmt: skip
    dec = ["| Criterion | Fine-tune | Retrieve | Winner | Evidence |", "|---|---|---|---|---|"]
    for x in r["decision"]:
        dec.append(f"| {x['criterion']} | {x['fine_tune']} | {x['retrieve']} | **{x['winner']}** "
                   f"| {x['evidence']} |")  # fmt: skip
    ft = [x["criterion"] for x in r["decision"] if x["winner"] == "fine-tune"]
    rt = [x["criterion"] for x in r["decision"] if x["winner"] == "retrieve"]
    ti = [x["criterion"] for x in r["decision"] if x["winner"] == "tie"]
    dec += ["", f"Fine-tune wins: {'; '.join(ft) or 'none'}.", "",
            f"Retrieve wins: {'; '.join(rt) or 'none'}.", "",
            f"Statistical ties: {'; '.join(ti) or 'none'}."]  # fmt: skip
    _ = m
    return {"results": "\n".join(res), "training": "\n".join(tr), "efficiency": "\n".join(eff),
            "forgetting": "\n".join(forget), "cost": "\n".join(cost), "decision": "\n".join(dec)}  # fmt: skip


def _svg(tr: dict[int, dict[str, Any]]) -> str:
    w, h, pad = 640, 260, 40
    colors = {25: "#d95f02", 50: "#7570b3", 100: "#1b9e77"}
    ymax = max(c["loss"] for t in tr.values() for c in t["curve"]) * 1.05
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" '
             'aria-label="LoRA training loss by step for 25, 50 and 100 percent of train">',
             f'<rect width="{w}" height="{h}" fill="white"/>',
             f'<line x1="{pad}" y1="{h - pad}" x2="{w - 10}" y2="{h - pad}" stroke="#444"/>',
             f'<line x1="{pad}" y1="10" x2="{pad}" y2="{h - pad}" stroke="#444"/>',
             f'<text x="{pad}" y="{h - 8}" font-size="11" font-family="monospace">'
             "training progress (epochs 0 to 3)</text>",
             f'<text x="4" y="22" font-size="11" font-family="monospace">loss (max {ymax:.2f})</text>']  # fmt: skip
    for i, (p, t) in enumerate(sorted(tr.items())):
        cur = t["curve"]
        pts = " ".join(
            f"{pad + (j + 1) / len(cur) * (w - pad - 10):.1f},"
            f"{h - pad - c['loss'] / ymax * (h - pad - 10):.1f}"
            for j, c in enumerate(cur)
        )
        parts.append(f'<polyline fill="none" stroke="{colors[p]}" stroke-width="1.5" points="{pts}"/>')
        parts.append(f'<text x="{w - 110}" y="{24 + 14 * i}" font-size="11" fill="{colors[p]}" '
                     f'font-family="monospace">{p}% train ({t["n_train"]} rows)</text>')  # fmt: skip
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def replace_blocks(text: str, blocks: dict[str, str]) -> str:
    for name, body in blocks.items():
        pat = re.compile(rf"(<!-- BEGIN:{name} -->\n).*?(\n<!-- END:{name} -->)", re.S)
        found = pat.search(text)
        if found is None:
            raise RuntimeError(f"README missing block markers for '{name}'")
        text = text[: found.end(1)] + body + text[found.start(2) :]
    return text


def _stale(o: dict[str, Any]) -> str:
    """Reason a train receipt is stale, or ''. A receipt with a producer_files manifest must list the current set and match its own sha; one without predates the manifest and is checked against the legacy list."""
    manifest = o.get("producer_files")
    if manifest is not None and tuple(manifest) != PRODUCER_FILES:
        return "producer_files manifest differs from the current producer set"
    try:
        now = legacy_code_sha() if manifest is None else code_sha(tuple(manifest))
    except FileNotFoundError as e:
        return f"producer file missing: {str(e.filename).rsplit('/', 1)[-1]}"
    return "" if o.get("code_sha") == now else "code_sha differs from current producer source"


def check_receipts() -> int:
    files = sorted(REC.glob("*.json"))
    bad: list[str] = []
    for f in files:
        o = json.loads(f.read_text(encoding="utf-8"))
        if o.get("schema_version") != SCHEMA_VERSION:
            bad.append(f"{f.name}: schema_version")
            continue
        for key in REQUIRED.get(o.get("kind", ""), ["__unknown_kind__"]):
            if key not in o:
                bad.append(f"{f.name}: missing {key}")
        if o.get("kind") == "train" and (why := _stale(o)):
            bad.append(f"{f.name}: {why} (re-run `make run`)")
        if o.get("kind") == "eval":
            n = len(o["ids"])
            if not (n == len(o["gold"]) == len(o["preds"]) == len(o["correct"]) == len(o["latency_ms"])):
                bad.append(f"{f.name}: ragged vectors")
            if abs(sum(o["correct"]) / n - o["accuracy"]) > 1e-9:
                bad.append(f"{f.name}: accuracy != mean(correct)")
    if len(files) < EXPECTED_RECEIPTS_MIN:  # empty-input success is a lie
        bad.append(f"only {len(files)} receipts, need >= {EXPECTED_RECEIPTS_MIN}")
    for b in bad:
        print("RECEIPT RED:", b)
    print(f"RECEIPTS {len(files) - len({b.split(':')[0] for b in bad})}/{len(files)}")
    return 1 if bad else 0



def dispatch(cmd: str, cfg: LabConfig, arg: str | None, check: bool) -> int:
    if cmd == "analyze":
        r = analyze(cfg)
        (REC / "results.json").write_text(json.dumps(r, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print("analyze: results.json written;", r["display"]["acc.A"], r["display"]["acc.B"])
        return 0
    if cmd == "show":
        d = _load("results.json")["display"]
        if arg not in d:
            print(f"unknown key {arg}; known: {sorted(d)}", file=sys.stderr)
            return 2
        print(d[arg])
        return 0
    if cmd == "check-receipts":
        return check_receipts()
    r = _load("results.json")
    new = replace_blocks(README.read_text(encoding="utf-8"), _blocks(r))
    tr = {p: _load(f"train_f{p}.json") for p in FRACS}
    svg = _svg(tr)
    if check:
        ok = new == README.read_text(encoding="utf-8") and SVG.exists() and SVG.read_text(encoding="utf-8") == svg
        print("report --check:", "OK" if ok else "STALE (run make report)")
        return 0 if ok else 1
    README.write_text(new, encoding="utf-8")
    SVG.parent.mkdir(exist_ok=True)
    SVG.write_text(svg, encoding="utf-8")
    print("report: README blocks + docs/training_curve.svg written")
    return 0
