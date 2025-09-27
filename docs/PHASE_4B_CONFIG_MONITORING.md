# Phase 4B Implementation Guide: Configuration & Monitoring Systems

**Assigned to**: AI Coding Agent  
**Estimated Time**: 2-3 hours  
**Priority**: IMPORTANT - Production configuration and observability  
**Architecture Review Required**: Yes  
**Previous Phase**: Phase 4A (Enhanced Error Handling) - Must be completed first

## Objective

Implement production-grade configuration management and basic monitoring capabilities. This phase establishes the foundation for operational visibility and environment-specific configuration needed for production deployment.

**Goal**: Enable CTS-Lite to operate reliably in different environments (development, staging, production) with proper observability and configuration management.

## Phase 4B Scope: Configuration & Monitoring Foundation

### **1. Enhanced Configuration Management (REQUIRED)**

#### Update `src/comma_tools/api/config.py`
**Requirements**:
- Environment-specific configuration support
- Production-ready defaults
- Resource limits and timeout configurations
- Security and operational settings

**Configuration Schema**:
```python
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseSettings, validator

class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

class ProductionConfig(BaseSettings):
    """Production-grade configuration with environment support."""
    
    # Environment Settings
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    log_level: str = "INFO"
    
    # Resource Management
    max_concurrent_runs: int = 3
    tool_timeout_seconds: int = 300  # 5 minutes default
    max_artifact_size_mb: int = 100
    artifact_retention_days: int = 7
    max_log_buffer_size: int = 1000
    
    # Performance Tuning  
    artifact_scan_interval_seconds: int = 5
    cleanup_interval_minutes: int = 60
    health_check_interval_seconds: int = 30
    
    # Security Settings
    enable_rate_limiting: bool = False  # Start disabled
    max_requests_per_minute: int = 60
    require_authentication: bool = False
    cors_allowed_origins: List[str] = ["*"]  # Restrictive in production
    
    # Monitoring & Observability
    enable_metrics: bool = True
    enable_health_checks: bool = True
    metrics_export_interval_seconds: int = 60
    
    # File System Settings
    base_storage_path: str = "/var/lib/cts"
    temp_directory: str = "/tmp/cts"
    log_directory: str = "/var/log/cts"
    
    class Config:
        env_file = ".env"
        env_prefix = "CTS_"
        
    @validator('environment')
    def validate_environment(cls, v):
        """Apply environment-specific defaults."""
        if v == Environment.PRODUCTION:
            # Production-specific validations
            if not cls.enable_metrics:
                raise ValueError("Metrics must be enabled in production")
        return v
        
    @classmethod
    def get_environment_config(cls, env: Environment) -> "ProductionConfig":
        """Get environment-specific configuration."""
        if env == Environment.PRODUCTION:
            return cls(
                environment=env,
                debug=False,
                log_level="WARNING",
                enable_rate_limiting=True,
                require_authentication=True,
                cors_allowed_origins=["https://yourdomain.com"],
                max_concurrent_runs=5
            )
        elif env == Environment.STAGING:
            return cls(
                environment=env,
                debug=True,
                log_level="INFO",
                enable_rate_limiting=True,
                max_concurrent_runs=2
            )
        else:  # Development
            return cls(
                environment=env,
                debug=True,
                log_level="DEBUG",
                max_concurrent_runs=1
            )
```

#### Configuration Loader Implementation:
```python
class ConfigManager:
    """Manages configuration loading and environment detection."""
    
    def __init__(self):
        self._config: Optional[ProductionConfig] = None
        self._config_file_path: Optional[str] = None
        
    def load_config(self, config_file: Optional[str] = None) -> ProductionConfig:
        """
        Load configuration from environment and/or config file.
        
        Args:
            config_file: Optional path to configuration file
            
        Returns:
            Loaded configuration instance
        """
        # Detect environment
        env_name = os.getenv("CTS_ENVIRONMENT", "development")
        environment = Environment(env_name)
        
        # Load base config for environment
        config = ProductionConfig.get_environment_config(environment)
        
        # Override with config file if provided
        if config_file and Path(config_file).exists():
            file_config = self._load_from_file(config_file)
            config = self._merge_configs(config, file_config)
            
        # Override with environment variables (highest priority)
        env_overrides = self._load_from_environment()
        config = self._merge_configs(config, env_overrides)
        
        self._config = config
        self._validate_config(config)
        return config
        
    def _validate_config(self, config: ProductionConfig):
        """Validate configuration for consistency and requirements."""
        # Ensure directories exist
        for dir_path in [config.base_storage_path, config.temp_directory, config.log_directory]:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            
        # Validate resource limits
        if config.max_concurrent_runs < 1:
            raise ValueError("max_concurrent_runs must be at least 1")
            
        if config.tool_timeout_seconds < 30:
            raise ValueError("tool_timeout_seconds must be at least 30")
```

### **2. Basic Monitoring & Metrics (REQUIRED)**

#### Create `src/comma_tools/api/metrics.py`
**Purpose**: Application metrics collection and health monitoring
**Requirements**:
- Tool execution metrics
- API performance tracking
- System health indicators
- Business metrics collection

```python
from dataclasses import dataclass, field
from typing import Dict, Any, Counter as CounterType
import time
from threading import Lock
import psutil

@dataclass
class Metrics:
    """Application metrics collection."""
    
    # Execution Metrics
    runs_total: int = 0
    runs_successful: int = 0
    runs_failed: int = 0
    execution_times: List[float] = field(default_factory=list)
    
    # API Metrics  
    api_requests_total: int = 0
    api_response_times: List[float] = field(default_factory=list)
    api_errors_by_endpoint: Dict[str, int] = field(default_factory=dict)
    
    # System Metrics
    active_runs: int = 0
    peak_concurrent_runs: int = 0
    artifact_storage_bytes: int = 0
    log_storage_bytes: int = 0
    
    # Business Metrics
    tools_usage_count: CounterType[str] = field(default_factory=CounterType)
    artifacts_generated: int = 0
    
    _lock: Lock = field(default_factory=Lock, init=False)

class MetricsCollector:
    """Collects and manages application metrics."""
    
    def __init__(self):
        self.metrics = Metrics()
        self.start_time = time.time()
        
    def record_run_start(self, tool_id: str, run_id: str):
        """Record the start of a tool execution."""
        with self.metrics._lock:
            self.metrics.runs_total += 1
            self.metrics.active_runs += 1
            self.metrics.peak_concurrent_runs = max(
                self.metrics.peak_concurrent_runs, 
                self.metrics.active_runs
            )
            self.metrics.tools_usage_count[tool_id] += 1
            
    def record_run_completion(self, run_id: str, success: bool, duration: float):
        """Record the completion of a tool execution."""
        with self.metrics._lock:
            self.metrics.active_runs -= 1
            self.metrics.execution_times.append(duration)
            
            if success:
                self.metrics.runs_successful += 1
            else:
                self.metrics.runs_failed += 1
                
    def record_api_request(self, endpoint: str, response_time: float, success: bool):
        """Record API request metrics."""
        with self.metrics._lock:
            self.metrics.api_requests_total += 1
            self.metrics.api_response_times.append(response_time)
            
            if not success:
                self.metrics.api_errors_by_endpoint[endpoint] = \
                    self.metrics.api_errors_by_endpoint.get(endpoint, 0) + 1
                    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics."""
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": memory.percent,
            "memory_available_bytes": memory.available,
            "disk_free_bytes": disk.free,
            "disk_used_percent": (disk.used / disk.total) * 100,
            "uptime_seconds": time.time() - self.start_time
        }
        
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        with self.metrics._lock:
            success_rate = (
                self.metrics.runs_successful / self.metrics.runs_total 
                if self.metrics.runs_total > 0 else 0
            )
            
            avg_execution_time = (
                sum(self.metrics.execution_times) / len(self.metrics.execution_times)
                if self.metrics.execution_times else 0
            )
            
            avg_response_time = (
                sum(self.metrics.api_response_times) / len(self.metrics.api_response_times)
                if self.metrics.api_response_times else 0
            )
            
            return {
                "execution_metrics": {
                    "runs_total": self.metrics.runs_total,
                    "runs_successful": self.metrics.runs_successful,
                    "runs_failed": self.metrics.runs_failed,
                    "success_rate": success_rate,
                    "average_execution_time_seconds": avg_execution_time,
                    "active_runs": self.metrics.active_runs,
                    "peak_concurrent_runs": self.metrics.peak_concurrent_runs
                },
                "api_metrics": {
                    "requests_total": self.metrics.api_requests_total,
                    "average_response_time_ms": avg_response_time * 1000,
                    "errors_by_endpoint": dict(self.metrics.api_errors_by_endpoint)
                },
                "business_metrics": {
                    "tools_usage": dict(self.metrics.tools_usage_count),
                    "artifacts_generated": self.metrics.artifacts_generated
                },
                "system_metrics": self.get_system_metrics()
            }
```

### **3. Health Check System (REQUIRED)**

#### Create `src/comma_tools/api/health.py`
**Purpose**: Service health monitoring and readiness checks
**Requirements**:
- Application health status
- Dependency health checks
- Resource availability validation
- Detailed health reporting

```python
from enum import Enum
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio

class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

class HealthCheck:
    """Individual health check implementation."""
    
    def __init__(self, name: str, check_func, timeout: int = 5):
        self.name = name
        self.check_func = check_func
        self.timeout = timeout
        self.last_check: Optional[datetime] = None
        self.last_status: HealthStatus = HealthStatus.UNHEALTHY
        self.last_error: Optional[str] = None
        
    async def run(self) -> Dict[str, Any]:
        """Execute the health check."""
        start_time = datetime.utcnow()
        
        try:
            result = await asyncio.wait_for(
                self.check_func(), 
                timeout=self.timeout
            )
            
            self.last_status = HealthStatus.HEALTHY
            self.last_error = None
            status_detail = "OK"
            
        except asyncio.TimeoutError:
            self.last_status = HealthStatus.UNHEALTHY
            self.last_error = f"Health check timed out after {self.timeout}s"
            status_detail = self.last_error
            
        except Exception as e:
            self.last_status = HealthStatus.UNHEALTHY  
            self.last_error = str(e)
            status_detail = f"Check failed: {e}"
            
        self.last_check = start_time
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            "name": self.name,
            "status": self.last_status,
            "last_check": start_time.isoformat(),
            "duration_ms": duration_ms,
            "details": status_detail
        }

class HealthCheckManager:
    """Manages all health checks for the application."""
    
    def __init__(self, config: ProductionConfig):
        self.config = config
        self.checks: List[HealthCheck] = []
        self._setup_default_checks()
        
    def _setup_default_checks(self):
        """Set up standard health checks."""
        self.checks.extend([
            HealthCheck("database_connection", self._check_database),
            HealthCheck("file_system", self._check_file_system),
            HealthCheck("tool_registry", self._check_tool_registry),
            HealthCheck("resource_usage", self._check_resource_usage),
        ])
        
    async def _check_database(self) -> bool:
        """Check database connectivity (if applicable)."""
        # For now, just a placeholder since we're file-based
        return True
        
    async def _check_file_system(self) -> bool:
        """Check file system availability and space."""
        storage_path = Path(self.config.base_storage_path)
        if not storage_path.exists():
            raise Exception(f"Storage path {storage_path} does not exist")
            
        # Check available space
        disk_usage = psutil.disk_usage(str(storage_path))
        free_percent = (disk_usage.free / disk_usage.total) * 100
        
        if free_percent < 10:  # Less than 10% free
            raise Exception(f"Low disk space: {free_percent:.1f}% free")
            
        return True
        
    async def _check_tool_registry(self) -> bool:
        """Check that tool registry is functioning."""
        from .registry import ToolRegistry
        registry = ToolRegistry()
        tools = await registry.get_available_tools()
        
        if len(tools) == 0:
            raise Exception("No tools registered")
            
        return True
        
    async def _check_resource_usage(self) -> bool:
        """Check system resource usage."""
        memory = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=1)
        
        if memory.percent > 90:
            raise Exception(f"High memory usage: {memory.percent:.1f}%")
            
        if cpu > 95:
            raise Exception(f"High CPU usage: {cpu:.1f}%")
            
        return True
        
    async def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks and return comprehensive status."""
        check_results = []
        
        # Run all checks concurrently
        check_tasks = [check.run() for check in self.checks]
        check_results = await asyncio.gather(*check_tasks, return_exceptions=True)
        
        # Determine overall status
        healthy_count = sum(1 for result in check_results 
                          if isinstance(result, dict) and result.get("status") == HealthStatus.HEALTHY)
        total_checks = len(self.checks)
        
        if healthy_count == total_checks:
            overall_status = HealthStatus.HEALTHY
        elif healthy_count > total_checks // 2:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.UNHEALTHY
            
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": check_results,
            "summary": {
                "total_checks": total_checks,
                "healthy_checks": healthy_count,
                "failed_checks": total_checks - healthy_count
            }
        }
```

### **4. Configuration & Health API Endpoints (REQUIRED)**

#### Update FastAPI application with new endpoints
**Requirements**:
- Health check endpoint
- Metrics endpoint  
- Configuration status endpoint
- Operational visibility

```python
# Add to main FastAPI application
@app.get("/health", response_model=Dict[str, Any])
async def health_check():
    """Get comprehensive health status of the service."""
    health_manager = HealthCheckManager(app.config)
    return await health_manager.run_all_checks()

@app.get("/health/simple")
async def simple_health_check():
    """Simple health check for load balancers."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/metrics", response_model=Dict[str, Any])
async def get_metrics():
    """Get comprehensive application metrics."""
    return app.metrics_collector.get_summary()

@app.get("/config/status")
async def config_status():
    """Get configuration status (non-sensitive information only)."""
    return {
        "environment": app.config.environment,
        "debug": app.config.debug,
        "max_concurrent_runs": app.config.max_concurrent_runs,
        "metrics_enabled": app.config.enable_metrics,
        "health_checks_enabled": app.config.enable_health_checks
    }
```

### **5. Testing Requirements (IMPORTANT)**

#### Create `tests/api/test_config_monitoring.py`
**Purpose**: Test configuration and monitoring systems
**Requirements**:
- Configuration loading tests
- Health check validation
- Metrics collection tests
- API endpoint tests

```python
class TestConfigurationManagement:
    """Test configuration loading and management."""
    
    def test_default_development_config(self):
        """Test: Default development configuration loads correctly."""
        
    def test_production_config_overrides(self):
        """Test: Production environment applies correct settings."""
        
    def test_environment_variable_overrides(self):
        """Test: Environment variables override config file settings."""
        
    def test_config_validation(self):
        """Test: Invalid configurations raise appropriate errors."""

class TestHealthChecks:
    """Test health check system."""
    
    async def test_all_health_checks_pass(self):
        """Test: All health checks pass in normal conditions."""
        
    async def test_health_check_failures(self):
        """Test: Health checks properly detect and report failures."""
        
    async def test_health_check_timeouts(self):
        """Test: Health checks handle timeouts appropriately."""

class TestMetricsCollection:
    """Test metrics collection system."""
    
    def test_execution_metrics(self):
        """Test: Execution metrics are recorded correctly."""
        
    def test_api_metrics(self):
        """Test: API request metrics are tracked."""
        
    def test_system_metrics(self):
        """Test: System metrics are collected accurately."""
```

## Implementation Priority

### **🔥 CRITICAL (Must Complete)**
1. **Configuration System**: Environment-based configuration loading
2. **Health Checks**: Basic health monitoring for service reliability
3. **API Integration**: Health and metrics endpoints
4. **Basic Testing**: Validate configuration and health systems

### **📋 IMPORTANT (Should Complete)**  
1. **Metrics Collection**: Comprehensive application metrics
2. **Advanced Health Checks**: Resource usage and dependency checks
3. **Configuration Validation**: Proper error handling for invalid configs
4. **Comprehensive Testing**: Edge cases and error conditions

## Success Criteria

### **Configuration Management**
- [ ] Service loads environment-specific configuration
- [ ] Configuration can be overridden via environment variables
- [ ] Invalid configurations are detected and reported
- [ ] Production settings are appropriately restrictive

### **Health & Monitoring**
- [ ] Health checks pass in normal operation
- [ ] Health endpoint provides detailed status information
- [ ] Metrics are collected and reported accurately
- [ ] Monitoring data helps identify operational issues

### **API Integration**
```bash
# Test new endpoints work correctly:
curl http://localhost:8000/health          # Detailed health status
curl http://localhost:8000/health/simple   # Simple OK response
curl http://localhost:8000/metrics         # Application metrics
curl http://localhost:8000/config/status   # Configuration info
```

## Architecture Compliance

### **Integration with Phase 4A**
- **Build on Error Handling**: Use error categorization for health checks
- **Leverage Cleanup**: Integrate with resource management systems  
- **Extend Monitoring**: Add metrics to error handling flows
- **Maintain Consistency**: Follow established patterns and styles

### **Configuration Philosophy**
- **Environment Aware**: Different settings for dev/staging/production
- **Override Hierarchy**: Environment variables > config file > defaults
- **Validation First**: Catch configuration errors at startup
- **Security Conscious**: Sensitive settings not exposed in status endpoints

---

**Next Phase**: Phase 4C (Testing & Quality Assurance) builds comprehensive test suites to validate production readiness and ensure service reliability.