import torch

from app.ranking import SegmentRanker, pairwise_accuracy, train_ranker
from app.retrieval import apply_scaler


def test_ranker_learns_a_separable_smoke_set():
    # Smoke test only: separable synthetic features, not a claim about video retrieval.
    positive = [1.0, 0.0, 0.0, 1.0, 0.2, 0.0, 0.0, 0.2, 0.0, 1.0, 1.0, 1.0]
    negative = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0]
    groups = [
        {"positives": [positive, positive], "negatives": [negative, negative]}
        for _ in range(6)
    ]
    result = train_ranker(groups[:4], groups[4:], seed=42, epochs=30, lr=0.05)
    assert result["seed"] == 42
    assert result["val_accuracy"] > 0.8
    model = SegmentRanker(result["in_dim"], result["hidden"])
    model.load_state_dict(result["state_dict"])
    accuracy = pairwise_accuracy(
        model(torch.tensor([apply_scaler(positive, result["mean"], result["std"])], dtype=torch.float32)),
        model(torch.tensor([apply_scaler(negative, result["mean"], result["std"])], dtype=torch.float32)),
    )
    assert accuracy == 1
