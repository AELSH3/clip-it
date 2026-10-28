from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env"),
        env_prefix="CLIPIT_",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://clipit:clipit@localhost:5432/clipit"
    redis_url: str = "redis://localhost:6379/0"
    storage_dir: Path = REPO_ROOT / "data"
    model_dir: Path = REPO_ROOT / "models"
    ranker_dir: Path = REPO_ROOT / "backend" / "artifacts" / "ranker"
    max_upload_bytes: int = 500 * 1024 * 1024
    max_duration_sec: float = 60 * 60
    window_sec: float = 8.0
    window_stride_sec: float = 4.0
    frame_sample_sec: float = 2.0
    whisper_model: str = "tiny"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    text_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    text_embedding_dim: int = 384
    clip_model_name: str = "ViT-B-32"
    clip_pretrained: str = "openai"
    visual_embedding_dim: int = 512
    torch_device: str = "auto"
    auth_mode: str = "local"
    api_token: str = ""
    public_deployment: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    inline_processing: bool = False
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    log_level: str = "INFO"
    rrf_k: int = 60
    channel_limit: int = 30

    @property
    def text_model_id(self) -> str:
        return self.text_model_name

    @property
    def visual_model_id(self) -> str:
        return f"open_clip:{self.clip_model_name}:{self.clip_pretrained}"

    @property
    def speech_model_id(self) -> str:
        return f"faster-whisper:{self.whisper_model}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_base_url and self.llm_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
