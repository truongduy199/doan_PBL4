"""Main entry point for Smart Parking Edge Server (MySQL/InnoDB + FastAPI)."""
from __future__ import annotations

import logging
import os

from smart_parking.bootstrap import bootstrap_system


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("smart_parking")
    logger.info("Starting Smart Parking Edge Server (MySQL/InnoDB + FastAPI)...")
    app_context = bootstrap_system()
    logger.info("System initialized successfully.")

    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    try:
        import uvicorn  # type: ignore

        uvicorn.run(app_context["app"], host=host, port=port)
    except ImportError:
        logger.info("Uvicorn is not installed in this environment; app_context ready.")


if __name__ == "__main__":
    main()
