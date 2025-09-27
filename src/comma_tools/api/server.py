"""FastAPI application setup and routing for CTS-Lite API."""

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import artifacts, capabilities, health, logs, runs
from . import monitors
from .config import Config


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="CTS-Lite API",
        description="Analysis and monitoring API for comma-tools",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/v1", tags=["health"])
    app.include_router(capabilities.router, prefix="/v1", tags=["capabilities"])
    app.include_router(runs.router, prefix="/v1", tags=["runs"])
    app.include_router(artifacts.router, prefix="/v1", tags=["artifacts"])
    app.include_router(logs.router, prefix="/v1", tags=["logs"])
    app.include_router(monitors.router, prefix="/v1", tags=["monitors"])

    return app


app = create_app()


def main():
    """Entry point for cts-lite command."""
    import uvicorn

    config = Config.from_env()

    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Starting CTS-Lite API server on {config.host}:{config.port}")

    try:
        uvicorn.run(
            "comma_tools.api.server:app",
            host=config.host,
            port=config.port,
            log_level=config.log_level.lower(),
            reload=False,
        )
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
