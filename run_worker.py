#!/usr/bin/env python
"""Run the Arq worker with proper event loop handling for Python 3.12+."""

import asyncio
import logging

from arq.worker import Worker

from app.workers.tasks import WorkerSettings

logging.basicConfig(level=logging.INFO)


async def main():
    """Run the worker."""
    worker = Worker(
        functions=WorkerSettings.functions,
        on_startup=WorkerSettings.on_startup,
        on_shutdown=WorkerSettings.on_shutdown,
        redis_settings=WorkerSettings.redis_settings,
        max_jobs=WorkerSettings.max_jobs,
        job_timeout=WorkerSettings.job_timeout,
        keep_result=WorkerSettings.keep_result,
    )
    await worker.main()


if __name__ == "__main__":
    asyncio.run(main())
