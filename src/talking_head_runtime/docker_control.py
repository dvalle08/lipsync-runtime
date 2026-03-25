from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from .config import RuntimeSettings
from .models import BackendStatus, Engine


@dataclass(frozen=True, slots=True)
class BackendSpec:
    engine: Engine
    service_name: str
    base_url: str


class ComposeController:
    def __init__(self, settings: RuntimeSettings) -> None:
        self.settings = settings

    def _compose_command(self, *args: str) -> list[str]:
        return [
            "docker",
            "compose",
            "-p",
            self.settings.COMPOSE_PROJECT_NAME,
            "-f",
            str(self.settings.COMPOSE_FILE),
            *args,
        ]

    def up(self, service_name: str) -> None:
        self._run(*self._compose_command("up", "-d", service_name))

    def stop(self, *service_names: str) -> None:
        if not service_names:
            return
        self._run(*self._compose_command("stop", *service_names))

    def _run(self, *command: str) -> None:
        result = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Docker compose command failed with exit code {result.returncode}: {' '.join(command)}\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )


class BackendManager:
    def __init__(self, settings: RuntimeSettings, controller: ComposeController) -> None:
        self.settings = settings
        self.controller = controller
        self.specs = {
            Engine.MUSE_TALK: BackendSpec(
                engine=Engine.MUSE_TALK,
                service_name="musetalk-api",
                base_url=settings.MUSE_TALK_INTERNAL_URL,
            ),
            Engine.SADTALKER: BackendSpec(
                engine=Engine.SADTALKER,
                service_name="sadtalker-api",
                base_url=settings.SADTALKER_INTERNAL_URL,
            ),
        }
        self.active_engine: Engine | None = None
        self.last_used_at: datetime | None = None

    async def reset(self) -> None:
        self.controller.stop("musetalk-api", "sadtalker-api")
        self.active_engine = None
        self.last_used_at = None

    async def ensure_backend(self, engine: Engine) -> BackendSpec:
        spec = self.specs[engine]
        if self.active_engine is not None and self.active_engine != engine:
            old_spec = self.specs[self.active_engine]
            self.controller.stop(old_spec.service_name)
            self.active_engine = None
        self.controller.up(spec.service_name)
        await self._wait_until_ready(spec.base_url)
        self.active_engine = engine
        self.last_used_at = datetime.now(UTC)
        return spec

    async def maybe_stop_idle_backend(self) -> None:
        if self.active_engine is None or self.last_used_at is None:
            return
        idle_seconds = (datetime.now(UTC) - self.last_used_at).total_seconds()
        if idle_seconds < self.settings.BACKEND_IDLE_TIMEOUT_SECONDS:
            return
        spec = self.specs[self.active_engine]
        self.controller.stop(spec.service_name)
        self.active_engine = None
        self.last_used_at = None

    def snapshot(self, queue_depth: int) -> BackendStatus:
        return BackendStatus(
            active_engine=self.active_engine,
            last_used_at=self.last_used_at,
            queue_depth=queue_depth,
        )

    async def _wait_until_ready(self, base_url: str) -> None:
        timeout = self.settings.BACKEND_START_TIMEOUT_SECONDS
        deadline = datetime.now(UTC).timestamp() + timeout
        async with httpx.AsyncClient(timeout=10.0) as client:
            while datetime.now(UTC).timestamp() < deadline:
                try:
                    response = await client.get(f"{base_url}/health/ready")
                    if response.is_success:
                        return
                except httpx.HTTPError:
                    pass
                await self._sleep()
        raise RuntimeError(f"Backend did not become ready before timeout: {base_url}")

    async def _sleep(self) -> None:
        import asyncio

        await asyncio.sleep(2)
