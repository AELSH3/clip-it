from __future__ import annotations

import json
from pathlib import Path

import torch

from app.ranking import SegmentRanker


class RankerRuntime:
    def __init__(self, directory: Path) -> None:
        self.available = False
        self.version = None
        self.mean: list[float] = []
        self.std: list[float] = []
        self.model = None
        self.note = "No trained ranker artifact is loaded. Results use reciprocal rank fusion only."
        config_path = directory / "preprocessor.json"
        weight_path = directory / "ranker.pt"
        if not config_path.is_file() or not weight_path.is_file():
            return
        config = json.loads(config_path.read_text())
        if not config.get("trained"):
            self.note = "A ranker file exists but is not marked trained, so it was not used."
            return
        model = SegmentRanker(int(config["in_dim"]), int(config.get("hidden", 32)))
        model.load_state_dict(torch.load(weight_path, map_location="cpu", weights_only=True))
        model.eval()
        self.model = model
        self.mean = [float(value) for value in config["mean"]]
        self.std = [float(value) for value in config["std"]]
        self.version = str(config.get("version") or "clipit-ranker")
        self.available = True
        self.note = str(config.get("note") or "")

    def score(self, rows: list[list[float]]) -> list[float]:
        if not self.available or self.model is None:
            raise RuntimeError("ranker is not available")
        with torch.no_grad():
            values = self.model(torch.tensor(rows, dtype=torch.float32))
        return [float(value) for value in values.detach().cpu().tolist()]
