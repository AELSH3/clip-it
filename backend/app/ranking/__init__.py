from __future__ import annotations

import random

import torch
from torch import nn


class SegmentRanker(nn.Module):
    def __init__(self, in_dim: int = 12, hidden: int = 32) -> None:
        super().__init__()
        self.net = nn.Sequential(nn.Linear(in_dim, hidden), nn.ReLU(), nn.Dropout(0.1), nn.Linear(hidden, 1))

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.net(features).squeeze(-1)


def pairwise_logistic_loss(positive: torch.Tensor, negative: torch.Tensor) -> torch.Tensor:
    return torch.nn.functional.softplus(-(positive - negative)).mean()


def pairwise_accuracy(positive: torch.Tensor, negative: torch.Tensor) -> float:
    if positive.numel() == 0:
        return 0.0
    return float((positive > negative).float().mean().item())


def train_ranker(
    train_groups: list[dict],
    val_groups: list[dict] | None = None,
    *,
    seed: int = 42,
    epochs: int = 20,
    lr: float = 1e-3,
    hidden: int = 32,
) -> dict:
    """Train on query-grouped positives and negatives. Scaler statistics come from train groups only."""
    from app.retrieval import apply_scaler, fit_scaler

    random.seed(seed)
    torch.manual_seed(seed)
    train_rows = [row for group in train_groups for row in group["positives"] + group["negatives"]]
    if not train_rows:
        raise ValueError("training groups are empty")
    mean, std = fit_scaler(train_rows)
    model = SegmentRanker(len(train_rows[0]), hidden)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    history = []
    best_state = None
    best_val = -1.0
    for epoch in range(epochs):
        model.train()
        losses = []
        for group in train_groups:
            if not group["positives"] or not group["negatives"]:
                continue
            positives = torch.tensor([apply_scaler(row, mean, std) for row in group["positives"]], dtype=torch.float32)
            negatives = torch.tensor([apply_scaler(row, mean, std) for row in group["negatives"]], dtype=torch.float32)
            # Pair every positive with a sampled negative, including the hardest (first) negative.
            pairs_pos = []
            pairs_neg = []
            for index in range(positives.shape[0]):
                neg_index = 0 if index == 0 else random.randrange(negatives.shape[0])
                pairs_pos.append(positives[index])
                pairs_neg.append(negatives[neg_index])
            loss = pairwise_logistic_loss(model(torch.stack(pairs_pos)), model(torch.stack(pairs_neg)))
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            losses.append(float(loss.item()))
        val_accuracy = evaluate_groups(model, val_groups or [], mean, std)
        history.append({"epoch": epoch, "loss": sum(losses) / len(losses) if losses else 0.0, "val_accuracy": val_accuracy})
        if val_groups and val_accuracy >= best_val:
            best_val = val_accuracy
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    return {
        "state_dict": model.state_dict(),
        "mean": mean,
        "std": std,
        "hidden": hidden,
        "in_dim": len(train_rows[0]),
        "history": history,
        "val_accuracy": best_val if val_groups else None,
        "seed": seed,
    }


def evaluate_groups(model: SegmentRanker, groups: list[dict], mean: list[float], std: list[float]) -> float:
    from app.retrieval import apply_scaler

    if not groups:
        return 0.0
    model.eval()
    correct = 0
    total = 0
    with torch.no_grad():
        for group in groups:
            if not group["positives"] or not group["negatives"]:
                continue
            positives = model(
                torch.tensor([apply_scaler(row, mean, std) for row in group["positives"]], dtype=torch.float32)
            )
            negatives = model(
                torch.tensor([apply_scaler(row, mean, std) for row in group["negatives"]], dtype=torch.float32)
            )
            total += positives.numel() * negatives.numel()
            correct += int((positives.unsqueeze(1) > negatives.unsqueeze(0)).sum().item())
    return correct / total if total else 0.0
