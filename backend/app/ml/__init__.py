from __future__ import annotations

import threading
from pathlib import Path

from app.config import Settings, get_settings

_lock = threading.Lock()
_speech = None
_text = None
_vision = None


def _device(settings: Settings) -> str:
    if settings.torch_device != "auto":
        return settings.torch_device
    import torch

    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _cache(settings: Settings) -> Path:
    path = settings.model_dir / "huggingface"
    path.mkdir(parents=True, exist_ok=True)
    return path


class SpeechModel:
    def __init__(self) -> None:
        self._model = None
        self.model_id = get_settings().speech_model_id

    def transcribe(self, audio_path: Path) -> list[dict]:
        settings = get_settings()
        with _lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                root = settings.model_dir / "whisper"
                root.mkdir(parents=True, exist_ok=True)
                self._model = WhisperModel(
                    settings.whisper_model,
                    device=settings.whisper_device,
                    compute_type=settings.whisper_compute_type,
                    download_root=str(root),
                )
        segments, _info = self._model.transcribe(str(audio_path), word_timestamps=True, vad_filter=True)
        rows = []
        for segment in segments:
            words = []
            for word in segment.words or []:
                words.append({"word": word.word, "start": word.start, "end": word.end})
            text = (segment.text or "").strip()
            if text:
                rows.append(
                    {
                        "start": float(segment.start),
                        "end": float(segment.end),
                        "text": text,
                        "words": words,
                    }
                )
        return rows


class TextEmbedder:
    def __init__(self) -> None:
        self._model = None
        self.model_id = get_settings().text_model_id

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            settings = get_settings()
            self._model = SentenceTransformer(
                settings.text_model_name,
                device=_device(settings),
                cache_folder=str(_cache(settings)),
            )
        return self._model

    def embed(self, texts: list[str]):
        if not texts:
            return []
        import numpy as np

        with _lock:
            model = self._load()
            vectors = model.encode(texts, normalize_embeddings=True)
        return [vector.astype("float32") for vector in np.atleast_2d(vectors)]


class VisionEmbedder:
    def __init__(self) -> None:
        self._bundle = None
        self.model_id = get_settings().visual_model_id

    def _load(self):
        if self._bundle is None:
            import open_clip
            import torch

            settings = get_settings()
            device = _device(settings)
            model, _, preprocess = open_clip.create_model_and_transforms(
                settings.clip_model_name,
                pretrained=settings.clip_pretrained,
                device=device,
                cache_dir=str(_cache(settings)),
            )
            model.eval()
            tokenizer = open_clip.get_tokenizer(settings.clip_model_name)
            self._bundle = (model, preprocess, tokenizer, device)
        return self._bundle

    def embed_text(self, text: str):
        import torch

        with _lock:
            model, _preprocess, tokenizer, device = self._load()
            tokens = tokenizer([text]).to(device)
            with torch.no_grad():
                feature = model.encode_text(tokens)
                feature = feature / feature.norm(dim=-1, keepdim=True)
        return feature[0].detach().cpu().numpy().astype("float32")

    def embed_images(self, paths: list):
        import torch
        from PIL import Image

        if not paths:
            return []
        with _lock:
            model, preprocess, _tokenizer, device = self._load()
            batch = torch.stack([preprocess(Image.open(path).convert("RGB")) for path in paths]).to(device)
            with torch.no_grad():
                feature = model.encode_image(batch)
                feature = feature / feature.norm(dim=-1, keepdim=True)
        return [row.detach().cpu().numpy().astype("float32") for row in feature]


def speech_model() -> SpeechModel:
    global _speech
    if _speech is None:
        _speech = SpeechModel()
    return _speech


def text_embedder() -> TextEmbedder:
    global _text
    if _text is None:
        _text = TextEmbedder()
    return _text


def vision_embedder() -> VisionEmbedder:
    global _vision
    if _vision is None:
        _vision = VisionEmbedder()
    return _vision


def read_screen_text(path) -> str:
    import pytesseract
    from PIL import Image

    text = pytesseract.image_to_string(Image.open(path))
    return " ".join(text.split())
