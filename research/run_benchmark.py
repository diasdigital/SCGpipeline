"""
run_benchmark.py
================
Scenario 1 benchmarking script: Validating the accuracy of the hallucination detection module
using the WikiBio GPT-3 dataset (238 biographies, 1,908 labeled sentences).

Workflow:
  1. Load dataset_v3.json and the DeBERTa model (once).
  2. For each entry: take gpt3_text as main_answer and
     gpt3_text_samples as offline stochastic samples (without Ollama).
  3. Run HallucinationEvaluator.evaluate() → sentence-level scores + avg_score.
  4. Log each entry as an MLflow run under the "WikiBio_Benchmark" experiment.
  5. After all 238 entries are complete, compute evaluation metrics:
       - Sentence-level AUC-PR (pred: NLI scores, true: major_inaccurate binary label)
       - Document-level Pearson & Spearman correlations
  6. Save the summary results to results/benchmark_results.csv and
     raw results to results/benchmark_raw.json.

How to run:
  From the project root directory:
    python run_benchmark.py

  To test with a subset of data first (e.g., 10 entries):
    python run_benchmark.py --limit 10

  To disable MLflow logging (faster):
    python run_benchmark.py --no-mlflow

Note:
  This script runs SYNCHRONOUSLY (without Celery) because its purpose is
  accuracy benchmarking—not simulating a production pipeline.
  It is highly recommended to use a GPU or run with --limit
  first to ensure the system runs correctly before a full run.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

import mlflow
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score
from scipy.stats import pearsonr, spearmanr

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.evaluator import HallucinationEvaluator


DATASET_PATH   = Path("data/dataset_v3.json")
RESULTS_DIR    = Path("results")
MLFLOW_URI     = "http://localhost:5000"
EXPERIMENT_NAME = "WikiBio_Benchmark"

# Convert annotation labels to numeric values for metric calculations:
#   accurate         → 0   (not hallucinated)
#   minor_inaccurate → 0.5 (mild hallucination)
#   major_inaccurate → 1   (severe hallucination)
#
# For AUC-PR (2-class), labels are binarized:
#   non-factual (major) = 1, others = 0
LABEL_TO_NUMERIC = {
    "accurate":         0.0,
    "minor_inaccurate": 0.5,
    "major_inaccurate": 1.0,
}

# Binarization threshold for AUC-PR (following the methodology of Manakul et al.)
# Sentences are considered "non-factual" only if annotated as major_inaccurate
NONFACTUAL_LABEL = "major_inaccurate"


def load_dataset(path: Path) -> list[dict]:
    """Load and validate the WikiBio GPT-3 dataset from a JSON file."""
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found at: {path}\n"
            "Ensure the dataset_v3.json file exists in the data/ folder."
        )
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    required_keys = {"gpt3_text", "gpt3_sentences", "annotation", "gpt3_text_samples", "wiki_bio_test_idx"}
    for i, entry in enumerate(data[:3]):
        missing = required_keys - set(entry.keys())
        if missing:
            raise ValueError(f"Entry {i} is missing fields: {missing}")

    print(f"[Benchmark] Dataset loaded: {len(data)} entries.")
    return data


def annotation_to_binary(annotations: list[str]) -> list[int]:
    """
    Convert annotation labels to binary for AUC-PR.
    major_inaccurate = 1 (non-factual), others = 0.
    """
    return [1 if a == NONFACTUAL_LABEL else 0 for a in annotations]


def compute_document_label(annotations: list[str]) -> float:
    """
    Compute document-level hallucination label as the mean of numeric values
    across all sentence annotations within a single biography.
    Used for document-level Pearson & Spearman correlations.
    """
    return float(np.mean([LABEL_TO_NUMERIC[a] for a in annotations]))


def format_duration(seconds: float) -> str:
    """Format duration in seconds into a readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.0f}s"

def evaluate_entry(
    entry: dict,
    evaluator: HallucinationEvaluator,
    entry_idx: int,
    use_mlflow: bool,
) -> dict:
    """
    Run hallucination evaluation for a single WikiBio dataset entry.

    Offline mode: gpt3_text_samples from the dataset are used directly as
    stochastic samples — no Ollama/LLM calls are made.

    Args:
        entry      : A single entry from dataset_v3.json.
        evaluator  : Loaded HallucinationEvaluator instance.
        entry_idx  : Entry sequence number (for logging).
        use_mlflow : Whether to log results to MLflow.

    Returns:
        Dict containing single entry evaluation results, ready for CSV/JSON storage.
    """
    wiki_idx    = entry["wiki_bio_test_idx"]
    main_answer = entry["gpt3_text"]
    samples     = entry["gpt3_text_samples"]
    annotations = entry["annotation"]
    sentences_gt = entry["gpt3_sentences"]      

    t_start = time.time()
    report  = evaluator.evaluate(main_answer, samples[:5]) 
    elapsed = time.time() - t_start

    avg_score      = float(report["avg_score"])
    sentence_scores = [float(s) for s in report["sentence_scores"]]
    sentences_pred  = report["sentences"] 

    doc_label = compute_document_label(annotations)

    if use_mlflow:
        with mlflow.start_run(run_name=f"WikiBio_{wiki_idx}"):
            mlflow.log_params({
                "wiki_bio_test_idx": wiki_idx,
                "num_sentences":     len(sentences_pred),
                "num_samples":       5,
                "entry_index":       entry_idx,
            })
            mlflow.log_metrics({
                "hallucination_score": avg_score,
                "doc_label_numeric":   doc_label,
                "eval_time_sec":       elapsed,
            })
            mlflow.log_dict({
                "wiki_bio_test_idx":  wiki_idx,
                "main_answer":        main_answer,
                "sentences_spacy":    sentences_pred,
                "sentence_scores":    sentence_scores,
                "annotations_human":  annotations,
                "sentences_gt":       sentences_gt,
            }, "entry_detail.json")

    return {
        "wiki_bio_test_idx":  wiki_idx,
        "entry_index":        entry_idx,
        "avg_score":          avg_score,
        "doc_label_numeric":  doc_label,
        "sentence_scores":    sentence_scores,
        "annotations":        annotations,
        "num_sentences_pred": len(sentences_pred),
        "num_sentences_gt":   len(sentences_gt),
        "eval_time_sec":      elapsed,
    }


def compute_metrics(results: list[dict]) -> dict:
    """
    Compute final evaluation metrics from all benchmarking results.

    Metrics computed (following Manakul et al. reference paper):
      1. Sentence-level AUC-PR:
           pred  = NLI score per sentence
           true  = binary major_inaccurate (1) vs others (0)
      2. Document-level Pearson correlation:
           between avg_score and doc_label_numeric
      3. Document-level Spearman correlation:
           same, but rank-based (more robust to outliers)

    Returns:
        Dict containing all metric values along with score distribution statistics.
    """
    all_sentence_scores = []
    all_sentence_labels = []

    for r in results:
        scores      = r["sentence_scores"]
        annotations = r["annotations"]

        n = min(len(scores), len(annotations))
        if n == 0:
            continue

        all_sentence_scores.extend(scores[:n])
        all_sentence_labels.extend(annotation_to_binary(annotations[:n]))

    doc_scores = [r["avg_score"]         for r in results]
    doc_labels = [r["doc_label_numeric"] for r in results]

    auc_pr = average_precision_score(all_sentence_labels, all_sentence_scores)

    pearson_r,  pearson_p  = pearsonr(doc_scores, doc_labels)
    spearman_r, spearman_p = spearmanr(doc_scores, doc_labels)

    scores_arr = np.array(doc_scores)

    return {
        "auc_pr":                round(float(auc_pr) * 100, 2), 
        "pearson_r":             round(float(pearson_r), 4),
        "pearson_p":             round(float(pearson_p), 6),
        "spearman_r":            round(float(spearman_r), 4),
        "spearman_p":            round(float(spearman_p), 6),

        "n_entries":             len(results),
        "n_sentences_total":     len(all_sentence_scores),
        "n_sentences_nonfactual": int(sum(all_sentence_labels)),
        "score_mean":            round(float(scores_arr.mean()), 4),
        "score_std":             round(float(scores_arr.std()), 4),
        "score_min":             round(float(scores_arr.min()), 4),
        "score_max":             round(float(scores_arr.max()), 4),
        "score_median":          round(float(np.median(scores_arr)), 4),
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Benchmarking SelfCheckNLI with the WikiBio GPT-3 dataset."
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Limit the number of processed entries (for testing). Default: all 238 entries."
    )
    parser.add_argument(
        "--no-mlflow", action="store_true",
        help="Disable MLflow logging (faster for testing)."
    )
    parser.add_argument(
        "--output-dir", type=str, default="results",
        help="Directory to save results. Default: results/"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    use_mlflow  = not args.no_mlflow
    output_dir  = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 60)
    print("  SCGpipeline — Scenario 1 Benchmarking")
    print("  Dataset : WikiBio GPT-3 (238 biographies)")
    print("  Method  : SelfCheckNLI (DeBERTa-v3-large)")
    print(f"  MLflow  : {'active' if use_mlflow else 'inactive'}")
    if args.limit:
        print(f"  Limit   : {args.limit} entries (test mode)")
    print("=" * 60)

    dataset = load_dataset(DATASET_PATH)
    if args.limit:
        dataset = dataset[:args.limit]
        print(f"[Benchmark] Test mode: processing only the first {len(dataset)} entries.")

    total = len(dataset)

    print("[Benchmark] Loading DeBERTa and SpaCy models...")
    evaluator = HallucinationEvaluator(method="nli")
    print("[Benchmark] Model loaded successfully. Starting evaluation...\n")

    if use_mlflow:
        mlflow.set_tracking_uri(MLFLOW_URI)
        mlflow.set_experiment(EXPERIMENT_NAME)
        print(f"[Benchmark] MLflow experiment: '{EXPERIMENT_NAME}' at {MLFLOW_URI}")

    results      = []
    total_start  = time.time()
    errors       = []

    for i, entry in enumerate(dataset):
        wiki_idx = entry["wiki_bio_test_idx"]

        try:
            print(f"[{i+1:>3}/{total}] WikiBio idx={wiki_idx} | "
                  f"{entry['gpt3_sentences'][0][:50]}...")

            result = evaluate_entry(entry, evaluator, i, use_mlflow)
            results.append(result)

            elapsed_total = time.time() - total_start
            avg_per_entry = elapsed_total / (i + 1)
            remaining     = avg_per_entry * (total - i - 1)

            print(f"         → score: {result['avg_score']:.4f} | "
                  f"label: {result['doc_label_numeric']:.2f} | "
                  f"time: {format_duration(result['eval_time_sec'])} | "
                  f"remaining: ~{format_duration(remaining)}")

        except Exception as e:
            print(f"         → ERROR: {e}")
            errors.append({"entry_index": i, "wiki_idx": wiki_idx, "error": str(e)})
            continue

    total_duration = time.time() - total_start
    print(f"\n[Benchmark] Evaluation completed in {format_duration(total_duration)}.")
    print(f"[Benchmark] Successful: {len(results)}/{total} | Errors: {len(errors)}")

    if not results:
        print("[Benchmark] No successful results. Aborting process.")
        return

    print("\n[Benchmark] Computing final evaluation metrics...")
    metrics = compute_metrics(results)

    print("\n" + "=" * 60)
    print("  BENCHMARKING RESULTS")
    print("=" * 60)
    print(f"  Processed entries     : {metrics['n_entries']}")
    print(f"  Total sentences       : {metrics['n_sentences_total']}")
    print(f"  Non-factual sentences : {metrics['n_sentences_nonfactual']}")
    print()
    print(f"  AUC-PR (sentence)     : {metrics['auc_pr']}%")
    print(f"    → Paper baseline     : 92.50%")
    print()
    print(f"  Pearson r (document)  : {metrics['pearson_r']}  (p={metrics['pearson_p']})")
    print(f"  Spearman r (document) : {metrics['spearman_r']}  (p={metrics['spearman_p']})")
    print()
    print(f"  Score distribution:")
    print(f"    Mean   : {metrics['score_mean']}")
    print(f"    Median : {metrics['score_median']}")
    print(f"    Std    : {metrics['score_std']}")
    print(f"    Min    : {metrics['score_min']}")
    print(f"    Max    : {metrics['score_max']}")
    print("=" * 60)

    if use_mlflow:
        with mlflow.start_run(run_name=f"SUMMARY_{timestamp}"):
            mlflow.log_params({
                "dataset":       "WikiBio_GPT-3",
                "method":        "SelfCheckNLI",
                "num_samples":   5,
                "total_entries": metrics["n_entries"],
            })
            mlflow.log_metrics({
                "auc_pr":          metrics["auc_pr"],
                "pearson_r":       metrics["pearson_r"],
                "spearman_r":      metrics["spearman_r"],
                "score_mean":      metrics["score_mean"],
                "total_time_sec":  total_duration,
            })
        print(f"\n[Benchmark] Metric summary logged to MLflow (run: SUMMARY_{timestamp}).")

    csv_path = output_dir / f"benchmark_results_{timestamp}.csv"
    df = pd.DataFrame([{
        "wiki_bio_test_idx":  r["wiki_bio_test_idx"],
        "avg_score":          r["avg_score"],
        "doc_label_numeric":  r["doc_label_numeric"],
        "num_sentences_pred": r["num_sentences_pred"],
        "num_sentences_gt":   r["num_sentences_gt"],
        "eval_time_sec":      r["eval_time_sec"],
    } for r in results])
    df.to_csv(csv_path, index=False)
    print(f"[Benchmark] Results CSV saved: {csv_path}")

    raw_path = output_dir / f"benchmark_raw_{timestamp}.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump({
            "metadata": {
                "timestamp":      timestamp,
                "total_entries":  len(results),
                "total_errors":   len(errors),
                "total_time_sec": round(total_duration, 2),
            },
            "metrics": metrics,
            "results": results,
            "errors":  errors,
        }, f, indent=2, ensure_ascii=False)
    print(f"[Benchmark] Raw JSON saved : {raw_path}")

    summary_path = output_dir / f"benchmark_summary_{timestamp}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp":       timestamp,
            "total_time_sec":  round(total_duration, 2),
            **metrics
        }, f, indent=2)
    print(f"[Benchmark] Summary saved  : {summary_path}")

    if errors:
        errors_path = output_dir / f"benchmark_errors_{timestamp}.json"
        with open(errors_path, "w", encoding="utf-8") as f:
            json.dump(errors, f, indent=2)
        print(f"[Benchmark] Error log saved  : {errors_path}")


if __name__ == "__main__":
    main()