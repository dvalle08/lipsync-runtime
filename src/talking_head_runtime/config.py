from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    JOBS_ROOT: Path = Path("/var/lib/talking-head/gateway/jobs")
    MUSE_TALK_RESULTS_ROOT: Path = Path("/var/lib/talking-head/musetalk/results")
    SADTALKER_RESULTS_ROOT: Path = Path("/var/lib/talking-head/sadtalker/results")

    REDIS_URL: str = "redis://redis:6379/0"
    QUEUE_KEY: str = "thr:jobs:queue"
    PROCESSING_KEY: str = "thr:jobs:processing"

    COMPOSE_PROJECT_NAME: str = "talking-head-local"
    COMPOSE_FILE: Path = Path("/srv/talking-head-runtime/deploy/compose.runtime.yaml")
    MUSE_TALK_INTERNAL_URL: str = "http://musetalk-api:8000"
    SADTALKER_INTERNAL_URL: str = "http://sadtalker-api:8000"

    BACKEND_START_TIMEOUT_SECONDS: int = 300
    BACKEND_IDLE_TIMEOUT_SECONDS: int = 900
    QUEUE_POP_TIMEOUT_SECONDS: int = 2

    MUSE_TALK_DEFAULT_FPS: int = 25
    MUSE_TALK_DEFAULT_USE_CACHE: bool = True
    SADTALKER_DEFAULT_SIZE: int = 256
    SADTALKER_DEFAULT_PREPROCESS: str = "crop"
    SADTALKER_DEFAULT_ENHANCER: str = "gfpgan"
    SADTALKER_DEFAULT_STILL: bool = True
