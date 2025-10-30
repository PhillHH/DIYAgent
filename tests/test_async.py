"""Asyncio Sanity Checks für parallele Requests und ASGI-Stack."""

from __future__ import annotations

import asyncio
from typing import List

import httpx
from tenacity import AsyncRetrying, RetryError, stop_after_attempt, wait_fixed

from config import CONCURRENCY_SEMAPHORE, DEFAULT_TIMEOUT


async def _fetch_with_retry(
    client: httpx.AsyncClient, url: str, semaphore: asyncio.Semaphore
) -> httpx.Response:
    async with semaphore:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3), wait=wait_fixed(1), reraise=True
        ):
            with attempt:
                response = await client.get(url)
                response.raise_for_status()
                return response
    raise RetryError("Unreachable: AsyncRetrying sollte entweder zurückkehren oder werfen.")


def test_parallel_async_requests() -> None:
    async def _run() -> List[int]:
        urls = ["https://httpbin.org/get" for _ in range(3)]
        semaphore = asyncio.Semaphore(CONCURRENCY_SEMAPHORE)
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            responses = await asyncio.gather(
                *(_fetch_with_retry(client, url, semaphore) for url in urls)
            )
        return [resp.status_code for resp in responses]

    status_codes = asyncio.run(_run())
    assert all(code == 200 for code in status_codes)

