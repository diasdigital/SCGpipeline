# Modifications to Upstream SelfCheckGPT

This folder is a local (vendored) copy of the [`selfcheckgpt`](https://pypi.org/project/selfcheckgpt/)
package, **not** a dependency pulled directly from PyPI. This is intentional:
the code here has been modified for the needs of this thesis project, and
those modifications don't exist in the upstream version.

In `pyproject.toml`, this package is installed in editable mode from a local path:

```toml
sources = { selfcheckgpt = { path = "./selfcheckgpt", editable = true } }
```

Because of this, **do not** replace this dependency with the regular PyPI
`selfcheckgpt` package — doing so would remove the modifications below and
change the evaluation behavior/results.

## Summary of Changes

### 1. Tokenizer compatibility fix for `transformers` v5 (main fix)

-   **File:** `selfcheckgpt/modeling_selfcheck.py`
-   **Class/method:** `SelfCheckNLI.predict()` (around line 380)

**Problem:** The upstream version calls the tokenizer in a way that relies on
the `batch_text_or_text_pairs` parameter to form the premise–hypothesis pairs
(main answer sentence vs. stochastic sample sentence) required by the NLI
model. In `transformers` v4.x this parameter was still processed correctly,
but in v5.x it is **silently ignored** (no error, but no pairing either) —
as a result, the tokenizer treats both sentences as a single unpaired input.
The NLI model then receives malformed input, causing contradiction scores to
come out near-random, far from the results reported by Manakul et al.

**Fix:** The tokenizer call was changed to explicitly pass `text=sentence`
and `text_pair=sample` as separate arguments to `self.tokenizer(...)`. This
API is fully supported in `transformers` v5 and ensures the tokenizer
correctly forms the premise–hypothesis pair as intended.

**Impact:** After this fix, replicating the WikiBio GPT-3 benchmark
(Scenario 1) produces AUC-PR/Pearson/Spearman values matching the original
paper (max deviation 0.18 pp) — see `research/run_benchmark.py` and
`research/scripts/results/`.

### 2. Progress bar no longer prints per sentence pair

-   **File:** `selfcheckgpt/modeling_selfcheck.py`
-   **Class/method:** `SelfCheckNLI.predict()`

A previously modified version of upstream printed one log line for **every
sentence × sample pair** (potentially hundreds of times per evaluation).
This was replaced with a single optional `tqdm` progress bar (`verbose`
parameter, default `False`), matching the pattern already used by other
`predict()` methods in the same file.
