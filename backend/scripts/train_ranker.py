"""Train the segment ranker.

Synthetic mode checks that the training loop runs. It does not measure video retrieval.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import torch

from app.config import get_settings
from app.ranking import train_ranker
from app.retrieval import FEATURE_NAMES


def synthetic_groups(count: int, seed: int) -> list[dict]:
    random.seed(seed)
    groups = []
    for _ in range(count):
        positives = []
        negatives = []
        for _ in range(2):
            row = [0.0] * len(FEATURE_NAMES)
            row[0] = random.uniform(0.7, 1.0)
            row[3] = random.uniform(0.5, 1.0)
            row[4] = random.uniform(0.05, 0.2)
            positives.append(row)
        for _ in range(3):
            row = [0.0] * len(FEATURE_NAMES)
            row[0] = random.uniform(0.0, 0.3)
            row[8] = 1.0
            negatives.append(row)
        groups.append({"positives": positives, "negatives": negatives})
    return groups


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=15)
    args = parser.parse_args()
    if not args.synthetic:
        raise SystemExit("Pass --synthetic. A real retrieval export is not wired to automatic clicks.")
    groups = synthetic_groups(12, args.seed)
    trained = train_ranker(groups[:8], groups[8:], seed=args.seed, epochs=args.epochs)
    out = get_settings().ranker_dir
    out.mkdir(parents=True, exist_ok=True)
    torch.save(trained["state_dict"], out / "ranker.pt")
    config = {
        "trained": True,
        "version": "clipit-ranker-synthetic-v1",
        "note": "Trained on separable synthetic features only. This checks the training loop. It does not establish generalization to video search.",
        "seed": args.seed,
        "feature_names": FEATURE_NAMES,
        "mean": trained["mean"],
        "std": trained["std"],
        "hidden": trained["hidden"],
        "in_dim": trained["in_dim"],
        "val_accuracy": trained["val_accuracy"],
        "history": trained["history"],
    }
    (out / "preprocessor.json").write_text(json.dumps(config, indent=2))
    print(json.dumps({"version": config["version"], "val_accuracy": config["val_accuracy"], "path": str(out)}))


if __name__ == "__main__":
    main()
