"""FastAPI application setup and routing for CTS-Lite API."""

import logging
import sys
from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from . import artifacts, capabilities, health, logs, runs
from .config import Config, ConfigManager, ProductionConfig
from .health import HealthCheckManager
from .metrics import MetricsCollector


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="CTS-Lite API",
        description="Analysis and monitoring API for comma-tools",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Initialize configuration management
    config_manager = ConfigManager()
    try:
        production_config = config_manager.load_config()
        app.state.config = production_config
        app.state.config_manager = config_manager
    except Exception as e:
        # Fallback to basic config for backward compatibility
        app.state.config = Config.from_env()
        app.state.config_manager = None
        logging.warning(f"Failed to load production config, using basic config: {e}")

    # Initialize metrics collector
    app.state.metrics_collector = MetricsCollector()

    # Initialize health check manager (only if production config is available)
    if hasattr(app.state.config, "environment") and isinstance(app.state.config, ProductionConfig):
        app.state.health_manager = HealthCheckManager(app.state.config)
    else:
        app.state.health_manager = None

    # Configure CORS based on config
    allowed_origins = ["*"]  # Default
    if hasattr(app.state.config, "cors_allowed_origins"):
        allowed_origins = app.state.config.cors_allowed_origins

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Middleware for metrics collection
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        start_time = datetime.utcnow()
        response = await call_next(request)

        # Record API metrics
        duration = (datetime.utcnow() - start_time).total_seconds()
        endpoint = f"{request.method} {request.url.path}"
        success = 200 <= response.status_code < 400

        app.state.metrics_collector.record_api_request(endpoint, duration, success)

        return response

    # Include routers
    app.include_router(health.router, prefix="/v1", tags=["health"])
    app.include_router(capabilities.router, prefix="/v1", tags=["capabilities"])
    app.include_router(runs.router, prefix="/v1", tags=["runs"])
    app.include_router(artifacts.router, prefix="/v1", tags=["artifacts"])
    app.include_router(logs.router, prefix="/v1", tags=["logs"])

    # Add new monitoring endpoints
    @app.get("/v1/metrics", tags=["monitoring"])
    async def get_metrics() -> Dict[str, Any]:
        """Get comprehensive application metrics."""
        return app.state.metrics_collector.get_summary()

    @app.get("/v1/config/status", tags=["monitoring"])
    async def config_status() -> Dict[str, Any]:
        """Get configuration status (non-sensitive information only)."""
        config = app.state.config

        # Basic information available in all config types
        status = {
            "log_level": getattr(config, "log_level", "INFO"),
            "host": getattr(config, "host", "127.0.0.1"),
            "port": getattr(config, "port", 8080),
        }

        # Additional information if using ProductionConfig
        if hasattr(config, "environment"):
            status.update(
                {
                    "environment": config.environment,
                    "debug": config.debug,
                    "max_concurrent_runs": config.max_concurrent_runs,
                    "metrics_enabled": config.enable_metrics,
                    "health_checks_enabled": config.enable_health_checks,
                }
            )

        return status

    @app.get("/v1/health/comprehensive", tags=["health"])
    async def comprehensive_health_check() -> Dict[str, Any]:
        """Get comprehensive health status of the service."""
        if app.state.health_manager:
            return await app.state.health_manager.run_all_checks()
        else:
            # Fallback for basic health status
            return {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "checks": [],
                "summary": {"total_checks": 0, "healthy_checks": 0, "failed_checks": 0},
            }

    return app


app = create_app()


def main():
    """Entry point for cts-lite command."""
    import uvicorn

    # Use the appropriate config from the app state
    config = app.state.config

    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Starting CTS-Lite API server on {config.host}:{config.port}")

    # Log configuration details
    if hasattr(config, "environment"):
        logger.info(f"Environment: {config.environment}")
        logger.info(f"Debug mode: {config.debug}")
        logger.info(f"Metrics enabled: {config.enable_metrics}")

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
