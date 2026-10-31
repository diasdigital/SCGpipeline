"""
research/sample_size_sweep.py
=============================
Sample-size sweep for SelfCheck-NLI on WikiBio GPT-3 (APSEC camera-ready, R2).

Scores every (sentence, sample) pair ONCE for all 20 pre-generated samples,
then derives metrics for N = 1, 2, 3, 5, 10, 20 by averaging the first N
columns. Protocol is identical to Table I (gpt3_sentences, no re-sampling):
  NonFact  : minor + major inaccurate = positive
  NonFact* : major inaccurate = positive, passages with human score < 1.0 only
  Factual  : accurate = positive, score = 1 - S
  Pearson / Spearman : passage mean score vs mean label (0 / 0.5 / 1)
N = 20 must reproduce Table I exactly (sanity check).

Run from the repository root:
    uv run python research/sample_size_sweep.py            # all 238 passages
    uv run python research/sample_size_sweep.py --limit 5  # quick test
"""
import argparse, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root

import numpy as np
import torch
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import average_precision_score as ap

from selfcheckgpt.selfcheckgpt.modeling_selfcheck import SelfCheckNLI

DATASET = Path("research/data/dataset_v3.json")
OUT     = Path("research/scripts/results/sample_size_sweep.json")
N_LIST  = [1, 2, 3, 5, 10, 20]
V       = {"accurate": 0.0, "minor_inaccurate": 0.5, "major_inaccurate": 1.0}


def metrics(mats, labels, n):
    s, y, ss, ys, pm, ph = [], [], [], [], [], []
    for m, lb in zip(mats, labels):
        sc = m[:, :n].mean(axis=1)
        hv = [V[l] for l in lb]
        h  = float(np.mean(hv))
        s += list(sc); y += [int(v > 0) for v in hv]
        if h < 1.0:
            ss += list(sc); ys += [int(v == 1.0) for v in hv]
        pm.append(float(sc.mean())); ph.append(h)
    s, y = np.array(s), np.array(y)
    return {
        "NonFact":     round(100 * ap(y, s), 2),
        "NonFactStar": round(100 * ap(ys, ss), 2),
        "Factual":     round(100 * ap(1 - y, 1 - s), 2),
        "Pearson":     round(100 * pearsonr(pm, ph)[0], 2),
        "Spearman":    round(100 * spearmanr(pm, ph)[0], 2),
    }


def main():
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--limit", type=int, default=None)
    args = ap_.parse_args()

    data = json.load(open(DATASET, encoding="utf-8"))
    if args.limit:
        data = data[: args.limit]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    nli = SelfCheckNLI(device=device)

    mats, labels, n_pairs, t_nli = [], [], 0, 0.0
    t0 = time.time()
    for i, e in enumerate(data, 1):
        sents, samples = e["gpt3_sentences"], e["gpt3_text_samples"][:20]
        m = np.zeros((len(sents), len(samples)))
        for j, smp in enumerate(samples):
            t = time.time()
            m[:, j] = nli.predict(sentences=sents, sampled_passages=[smp])
            t_nli += time.time() - t
        n_pairs += m.size
        mats.append(m); labels.append(e["annotation"])
        if i % 10 == 0 or i == len(data):
            print(f"[{i}/{len(data)}] pairs={n_pairs} elapsed={time.time()-t0:.0f}s")

    sec_per_pair = t_nli / n_pairs
    n_sent = sum(m.shape[0] for m in mats)
    rows = []
    for n in N_LIST:
        r = {"N": n, **metrics(mats, labels, n),
             "est_nli_sec_per_passage": round(sec_per_pair * n * n_sent / len(mats), 2)}
        rows.append(r); print(r)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"device": str(device), "n_passages": len(mats), "n_sentences": n_sent,
               "sec_per_pair": sec_per_pair, "results": rows,
               "table1_reference_N20": {"NonFact": 92.50, "NonFactStar": 45.35, "Factual": 66.15,
                                        "Pearson": 74.13, "Spearman": 73.77}},
              open(OUT, "w", encoding="utf-8"), indent=2)
    print(f"Saved to {OUT}")


if __name__ == "__main__":
    main()
