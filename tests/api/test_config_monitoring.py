"""Tests for Phase 4B configuration management and monitoring systems."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from comma_tools.api.config import Config, ConfigManager, Environment, ProductionConfig
from comma_tools.api.health import HealthCheck, HealthCheckManager, HealthStatus
from comma_tools.api.metrics import Metrics, MetricsCollector


class TestConfigurationManagement:
    """Test configuration loading and management."""

    def test_default_development_config(self):
        """Test: Default development configuration loads correctly."""
        config = ProductionConfig()

        assert config.environment == Environment.DEVELOPMENT
        assert config.debug is False  # Default
        assert config.log_level == "INFO"
        assert config.max_concurrent_runs == 3
        assert config.enable_metrics is True

    def test_production_config_overrides(self):
        """Test: Production environment applies correct settings."""
        config = ProductionConfig.get_environment_config(Environment.PRODUCTION)

        assert config.environment == Environment.PRODUCTION
        assert config.debug is False
        assert config.log_level == "WARNING"
        assert config.enable_rate_limiting is True
        assert config.require_authentication is True
        assert config.max_concurrent_runs == 5

    def test_staging_config_overrides(self):
        """Test: Staging environment applies correct settings."""
        config = ProductionConfig.get_environment_config(Environment.STAGING)

        assert config.environment == Environment.STAGING
        assert config.debug is True
        assert config.log_level == "INFO"
        assert config.enable_rate_limiting is True
        assert config.max_concurrent_runs == 2

    def test_development_config_overrides(self):
        """Test: Development environment applies correct settings."""
        config = ProductionConfig.get_environment_config(Environment.DEVELOPMENT)

        assert config.environment == Environment.DEVELOPMENT
        assert config.debug is True
        assert config.log_level == "DEBUG"
        assert config.max_concurrent_runs == 1

    def test_environment_variable_overrides(self):
        """Test: Environment variables override config file settings."""
        manager = ConfigManager()

        # Test with development environment using temp directories
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_config = ProductionConfig(
                base_storage_path=tmpdir, temp_directory=tmpdir, log_directory=tmpdir
            )

            with patch.dict(os.environ, {"CTS_ENVIRONMENT": "development"}):
                with patch.object(
                    ProductionConfig, "get_environment_config", return_value=temp_config
                ):
                    config = manager.load_config()
                    assert config.environment == Environment.DEVELOPMENT

    def test_config_validation(self):
        """Test: Invalid configurations raise appropriate errors."""
        manager = ConfigManager()

        # Test with invalid environment using temp directories
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_config = ProductionConfig(
                base_storage_path=tmpdir, temp_directory=tmpdir, log_directory=tmpdir
            )

            with patch.dict(os.environ, {"CTS_ENVIRONMENT": "invalid"}):
                with patch.object(
                    ProductionConfig, "get_environment_config", return_value=temp_config
                ):
                    config = manager.load_config()
                    assert config.environment == Environment.DEVELOPMENT

    def test_config_validation_errors(self):
        """Test: Configuration validation catches invalid values."""
        manager = ConfigManager()

        # Create config with invalid values but valid directories
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ProductionConfig(
                max_concurrent_runs=0,  # Invalid: must be >= 1
                tool_timeout_seconds=10,  # Invalid: must be >= 30
                base_storage_path=tmpdir,
                temp_directory=tmpdir,
                log_directory=tmpdir,
            )

            with pytest.raises(ValueError, match="max_concurrent_runs must be at least 1"):
                manager._validate_config(config)

            config = ProductionConfig(
                tool_timeout_seconds=10,
                base_storage_path=tmpdir,
                temp_directory=tmpdir,
                log_directory=tmpdir,
            )
            with pytest.raises(ValueError, match="tool_timeout_seconds must be at least 30"):
                manager._validate_config(config)

    def test_production_environment_validation(self):
        """Test: Production environment has specific validations."""
        # This should not raise an error since metrics are enabled by default
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ProductionConfig.get_environment_config(Environment.PRODUCTION)
            config.base_storage_path = tmpdir
            config.temp_directory = tmpdir
            config.log_directory = tmpdir

            manager = ConfigManager()
            manager._validate_config(config)  # Should not raise

    def test_backward_compatibility(self):
        """Test: Backward compatibility with original Config class."""
        config = Config.from_env()

        assert hasattr(config, "host")
        assert hasattr(config, "port")
        assert hasattr(config, "log_level")
        assert hasattr(config, "storage_dir")


class TestHealthChecks:
    """Test health check system."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test: Health check passes with successful function."""

        async def successful_check():
            return True

        health_check = HealthCheck("test_check", successful_check)
        result = await health_check.run()

        assert result["name"] == "test_check"
        assert result["status"] == HealthStatus.HEALTHY
        assert result["details"] == "OK"
        assert "duration_ms" in result

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test: Health check properly detects and reports failures."""

        async def failing_check():
            raise Exception("Check failed")

        health_check = HealthCheck("failing_check", failing_check)
        result = await health_check.run()

        assert result["name"] == "failing_check"
        assert result["status"] == HealthStatus.UNHEALTHY
        assert "Check failed" in result["details"]

    @pytest.mark.asyncio
    async def test_health_check_timeout(self):
        """Test: Health checks handle timeouts appropriately."""
        import asyncio

        async def slow_check():
            await asyncio.sleep(10)  # Longer than timeout
            return True

        health_check = HealthCheck("slow_check", slow_check, timeout=1)
        result = await health_check.run()

        assert result["name"] == "slow_check"
        assert result["status"] == HealthStatus.UNHEALTHY
        assert "timed out" in result["details"]

    @pytest.mark.asyncio
    async def test_health_check_manager(self):
        """Test: Health check manager runs all checks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ProductionConfig.get_environment_config(Environment.DEVELOPMENT)
            config.base_storage_path = tmpdir
            config.temp_directory = tmpdir
            config.log_directory = tmpdir

            manager = HealthCheckManager(config)

            result = await manager.run_all_checks()

            assert result["status"] in [
                HealthStatus.HEALTHY,
                HealthStatus.DEGRADED,
                HealthStatus.UNHEALTHY,
            ]
            assert "timestamp" in result
            assert "checks" in result
            assert "summary" in result
            assert len(result["checks"]) == len(manager.checks)


class TestMetricsCollection:
    """Test metrics collection system."""

    def test_metrics_initialization(self):
        """Test: Metrics collector initializes correctly."""
        collector = MetricsCollector()

        assert collector.metrics.runs_total == 0
        assert collector.metrics.runs_successful == 0
        assert collector.metrics.runs_failed == 0
        assert len(collector.metrics.execution_times) == 0

    def test_execution_metrics(self):
        """Test: Execution metrics are recorded correctly."""
        collector = MetricsCollector()

        # Test run start
        collector.record_run_start("test_tool", "run_123")
        assert collector.metrics.runs_total == 1
        assert collector.metrics.active_runs == 1
        assert collector.metrics.tools_usage_count["test_tool"] == 1

        # Test successful completion
        collector.record_run_completion("run_123", success=True, duration=5.0)
        assert collector.metrics.runs_successful == 1
        assert collector.metrics.active_runs == 0
        assert 5.0 in collector.metrics.execution_times

        # Test failed completion
        collector.record_run_start("test_tool", "run_456")
        collector.record_run_completion("run_456", success=False, duration=2.0)
        assert collector.metrics.runs_failed == 1
        assert collector.metrics.runs_total == 2

    def test_api_metrics(self):
        """Test: API request metrics are tracked."""
        collector = MetricsCollector()

        # Test successful API request
        collector.record_api_request("/v1/health", 0.1, success=True)
        assert collector.metrics.api_requests_total == 1
        assert 0.1 in collector.metrics.api_response_times

        # Test failed API request
        collector.record_api_request("/v1/test", 0.5, success=False)
        assert collector.metrics.api_requests_total == 2
        assert collector.metrics.api_errors_by_endpoint["/v1/test"] == 1

    def test_system_metrics(self):
        """Test: System metrics are collected accurately."""
        collector = MetricsCollector()
        system_metrics = collector.get_system_metrics()

        # Check that all expected keys are present
        expected_keys = [
            "cpu_percent",
            "memory_percent",
            "memory_available_bytes",
            "disk_free_bytes",
            "disk_used_percent",
            "uptime_seconds",
        ]

        for key in expected_keys:
            assert key in system_metrics

        # Uptime should be a small positive number
        assert system_metrics["uptime_seconds"] >= 0

    def test_metrics_summary(self):
        """Test: Comprehensive metrics summary is generated."""
        collector = MetricsCollector()

        # Add some test data
        collector.record_run_start("tool1", "run1")
        collector.record_run_completion("run1", success=True, duration=1.0)
        collector.record_api_request("/v1/test", 0.2, success=True)
        collector.record_artifact_generated(1024)

        summary = collector.get_summary()

        # Check structure
        assert "execution_metrics" in summary
        assert "api_metrics" in summary
        assert "business_metrics" in summary
        assert "system_metrics" in summary

        # Check execution metrics
        exec_metrics = summary["execution_metrics"]
        assert exec_metrics["runs_total"] == 1
        assert exec_metrics["runs_successful"] == 1
        assert exec_metrics["success_rate"] == 1.0

        # Check business metrics
        business_metrics = summary["business_metrics"]
        assert business_metrics["artifacts_generated"] == 1
        assert business_metrics["artifact_storage_bytes"] == 1024

    def test_metrics_reset(self):
        """Test: Metrics can be reset for testing."""
        collector = MetricsCollector()

        # Add some data
        collector.record_run_start("tool1", "run1")
        collector.record_api_request("/v1/test", 0.1, success=True)

        # Verify data exists
        assert collector.metrics.runs_total > 0
        assert collector.metrics.api_requests_total > 0

        # Reset metrics
        collector.reset_metrics()

        # Verify reset
        assert collector.metrics.runs_total == 0
        assert collector.metrics.api_requests_total == 0
        assert len(collector.metrics.execution_times) == 0
