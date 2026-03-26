from __future__ import annotations

from typing import cast

from redis import asyncio as redis

from .config import RuntimeSettings
from .models import JobRecord


class RedisJobStore:
    def __init__(self, settings: RuntimeSettings) -> None:
        self.settings = settings
        self._redis: redis.Redis | None = None

    async def connect(self) -> None:
        self._redis = redis.from_url(self.settings.REDIS_URL, decode_responses=True)
        await self._redis.ping()

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.close()

    @property
    def client(self) -> redis.Redis:
        if self._redis is None:
            raise RuntimeError("RedisJobStore is not connected")
        return self._redis

    def job_key(self, job_id: str) -> str:
        return f"thr:job:{job_id}"

    async def save_job(self, job: JobRecord) -> None:
        await self.client.set(self.job_key(job.job_id), job.model_dump_json())

    async def load_job(self, job_id: str) -> JobRecord | None:
        payload = await self.client.get(self.job_key(job_id))
        if payload is None:
            return None
        return JobRecord.model_validate_json(payload)

    async def enqueue(self, job: JobRecord) -> int:
        await self.save_job(job)
        await self.client.lpush(self.settings.QUEUE_KEY, job.job_id)
        return await self.queue_depth()

    async def queue_depth(self) -> int:
        return cast(int, await self.client.llen(self.settings.QUEUE_KEY))

    async def pop_next_job(self) -> str | None:
        return await self.client.brpoplpush(
            self.settings.QUEUE_KEY,
            self.settings.PROCESSING_KEY,
            timeout=self.settings.QUEUE_POP_TIMEOUT_SECONDS,
        )

    async def ack(self, job_id: str) -> None:
        await self.client.lrem(self.settings.PROCESSING_KEY, 1, job_id)

    async def requeue_processing_job(self, job_id: str) -> None:
        await self.client.lrem(self.settings.PROCESSING_KEY, 1, job_id)
        await self.client.lpush(self.settings.QUEUE_KEY, job_id)

    async def recover_processing_jobs(self) -> None:
        while True:
            recovered = await self.client.rpoplpush(
                self.settings.PROCESSING_KEY,
                self.settings.QUEUE_KEY,
            )
            if recovered is None:
                break
