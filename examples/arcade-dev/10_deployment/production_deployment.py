#!/usr/bin/env python3
"""
Production Deployment Example for Arcade.dev Integration

This example demonstrates production-ready deployment of Arcade.dev integration including:
- Initialization and bootstrapping
- Configuration management
- Health checks and readiness probes
- Graceful shutdown
- Resource management and cleanup
"""

import os
import sys
import asyncio
import signal
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
import time
import json
import yaml
from contextlib import asynccontextmanager
import threading
from concurrent.futures import ThreadPoolExecutor
import subprocess

try:
    import psutil
except ImportError:
    psutil = None

# Setup FACT imports using the import helper
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.import_helper import setup_fact_imports

# Setup FACT module path
setup_fact_imports()

from src.core.driver import FACTDriver
from src.core.config import Config
from src.cache.manager import CacheManager
from src.monitoring.metrics import MetricsCollector
from src.security.auth import AuthorizationManager
from src.core.errors import ConfigurationError, ToolExecutionError


# Mock classes for demonstration (in production, these would be real implementations)
class ArcadeClient:
    """Mock Arcade.dev API client for deployment example."""

    def __init__(
        self,
        api_key: str,
        api_url: str,
        timeout: int,
        max_retries: int,
        cache_manager=None,
    ):
        self.api_key = api_key
        self.api_url = api_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache_manager = cache_manager
        self.connected = False

    async def connect(self):
        """Connect to Arcade.dev API."""
        # Mock connection
        self.connected = True

    async def disconnect(self):
        """Disconnect from Arcade.dev API."""
        self.connected = False

    async def health_check(self):
        """Perform health check."""
        if not self.connected:
            raise Exception("Not connected to Arcade.dev API")
        return {"status": "healthy", "timestamp": time.time()}


class ArcadeGateway:
    """Mock Arcade.dev gateway for deployment example."""

    def __init__(self, arcade_client, cache_manager, metrics, authorization_manager):
        self.arcade_client = arcade_client
        self.cache_manager = cache_manager
        self.metrics = metrics
        self.authorization_manager = authorization_manager
        self.initialized = False

    async def initialize(self):
        """Initialize the gateway."""
        self.initialized = True

    async def cleanup(self):
        """Clean up gateway resources."""
        self.initialized = False


class ServiceStartupError(Exception):
    """Custom exception for service startup errors."""

    pass


@dataclass
class ServiceHealthStatus:
    """Health status of a service component."""

    service_name: str
    healthy: bool
    last_check: float
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


@dataclass
class DeploymentConfig:
    """Production deployment configuration."""

    # Service configuration
    service_name: str = "fact-arcade-integration"
    service_version: str = "1.0.0"
    environment: str = "production"

    # Network configuration
    host: str = "0.0.0.0"
    port: int = 8080
    health_check_port: int = 8081

    # Arcade.dev configuration
    arcade_api_key: str = ""
    arcade_api_url: str = "https://api.arcade.dev"
    arcade_timeout: int = 30
    arcade_max_retries: int = 3

    # Cache configuration
    cache_backend: str = "redis"
    cache_host: str = "localhost"
    cache_port: int = 6379
    cache_db: int = 0

    # Monitoring configuration
    metrics_enabled: bool = True
    metrics_port: int = 9090
    log_level: str = "INFO"

    # Performance configuration
    worker_threads: int = 4
    max_concurrent_requests: int = 100
    request_timeout: int = 60

    # Security configuration
    enable_auth: bool = False  # Disabled for demo
    jwt_secret: str = ""
    cors_origins: List[str] = field(default_factory=list)


class ProductionArcadeService:
    """Production-ready Arcade.dev integration service."""

    def __init__(self, config: DeploymentConfig):
        self.config = config
        self.logger = self._setup_logging()

        # Core components
        self.driver: Optional[FACTDriver] = None
        self.cache_manager: Optional[CacheManager] = None
        self.arcade_client: Optional[ArcadeClient] = None
        self.arcade_gateway: Optional[ArcadeGateway] = None
        self.metrics: Optional[MetricsCollector] = None
        self.authorization_manager: Optional[AuthorizationManager] = None

        # Service state
        self.is_running = False
        self.is_ready = False
        self.startup_time: Optional[float] = None
        self.shutdown_event = asyncio.Event()
        self.health_status: Dict[str, ServiceHealthStatus] = {}

        # Background tasks
        self.background_tasks: List[asyncio.Task] = []
        self.thread_pool = ThreadPoolExecutor(max_workers=config.worker_threads)

        # Signal handlers
        self._setup_signal_handlers()

    def _setup_logging(self) -> logging.Logger:
        """Set up production logging configuration."""
        # Create log handlers
        handlers = [logging.StreamHandler()]

        # Try to add file handler, but don't fail if directory doesn't exist
        try:
            log_file = f"/var/log/{self.config.service_name}.log"
            handlers.append(logging.FileHandler(log_file))
        except (PermissionError, FileNotFoundError):
            # Fallback to local log file
            try:
                log_file = f"./{self.config.service_name}.log"
                handlers.append(logging.FileHandler(log_file))
            except Exception:
                # If all file logging fails, just use console
                pass

        logging.basicConfig(
            level=getattr(logging, self.config.log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(pathname)s:%(lineno)d",
            handlers=handlers,
        )

        logger = logging.getLogger(self.config.service_name)
        logger.info(
            f"Initializing {self.config.service_name} v{self.config.service_version}"
        )
        return logger

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown")
            asyncio.create_task(self.shutdown())

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    async def initialize(self):
        """Initialize all service components."""
        self.logger.info("Starting service initialization")
        initialization_start = time.time()

        try:
            # Load and validate configuration
            await self._load_configuration()

            # Initialize core components
            await self._initialize_cache()
            await self._initialize_arcade_client()
            await self._initialize_monitoring()
            await self._initialize_authorization()
            await self._initialize_gateway()

            # Start background tasks
            await self._start_background_tasks()

            # Perform initial health checks
            await self._perform_initial_health_checks()

            self.startup_time = time.time() - initialization_start
            self.is_running = True
            self.is_ready = True

            self.logger.info(
                f"Service initialization completed in {self.startup_time:.2f}s"
            )

        except Exception as e:
            self.logger.error(f"Service initialization failed: {e}")
            await self.cleanup()
            raise ServiceStartupError(f"Failed to initialize service: {e}")

    async def _load_configuration(self):
        """Load and validate configuration from environment and files."""
        self.logger.info("Loading configuration")

        # Load from environment variables
        self.config.arcade_api_key = os.getenv(
            "ARCADE_API_KEY", self.config.arcade_api_key
        )
        self.config.arcade_api_url = os.getenv(
            "ARCADE_API_URL", self.config.arcade_api_url
        )
        self.config.cache_host = os.getenv("CACHE_HOST", self.config.cache_host)
        self.config.jwt_secret = os.getenv("JWT_SECRET", self.config.jwt_secret)

        # Load from configuration file if exists
        config_file = os.getenv("CONFIG_FILE", "/etc/fact-arcade/config.yaml")
        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                file_config = yaml.safe_load(f)
                self._merge_config(file_config)

        # Validate required configuration
        if not self.config.arcade_api_key:
            raise ConfigurationError("ARCADE_API_KEY is required")

        if self.config.enable_auth and not self.config.jwt_secret:
            raise ConfigurationError(
                "JWT_SECRET is required when authentication is enabled"
            )

        self.logger.info("Configuration loaded and validated")

    def _merge_config(self, file_config: Dict[str, Any]):
        """Merge file configuration with current config."""
        for key, value in file_config.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

    async def _initialize_cache(self):
        """Initialize cache manager."""
        self.logger.info("Initializing cache manager")

        cache_config = {
            "prefix": "fact_arcade_cache",
            "min_tokens": 1,  # Reduced for demo purposes
            "max_size": "100MB",
            "ttl_seconds": 3600,
            "backend": self.config.cache_backend,
            "host": self.config.cache_host,
            "port": self.config.cache_port,
            "db": self.config.cache_db,
        }

        self.cache_manager = CacheManager(cache_config)
        # CacheManager doesn't require async initialization

        # Test cache connectivity
        test_key = "health_check_cache"
        test_content = '{"status": "ok"}'
        self.cache_manager.store(test_key, test_content)
        result = self.cache_manager.get(test_key)

        if not result:
            raise ServiceStartupError("Cache connectivity test failed")

        self.cache_manager.invalidate_by_prefix(test_key)
        self.logger.info("Cache manager initialized successfully")

    async def _initialize_arcade_client(self):
        """Initialize Arcade.dev client."""
        self.logger.info("Initializing Arcade.dev client")

        self.arcade_client = ArcadeClient(
            api_key=self.config.arcade_api_key,
            api_url=self.config.arcade_api_url,
            timeout=self.config.arcade_timeout,
            max_retries=self.config.arcade_max_retries,
            cache_manager=self.cache_manager,
        )

        await self.arcade_client.connect()

        # Test API connectivity
        try:
            health_result = await self.arcade_client.health_check()
            self.logger.info(
                f"Arcade.dev API health: {health_result.get('status', 'unknown')}"
            )
        except Exception as e:
            self.logger.warning(f"Arcade.dev API health check failed: {e}")

        self.logger.info("Arcade.dev client initialized successfully")

    async def _initialize_monitoring(self):
        """Initialize monitoring and metrics collection."""
        if not self.config.metrics_enabled:
            self.logger.info("Metrics collection disabled")
            return

        self.logger.info("Initializing metrics collection")

        self.metrics = MetricsCollector(max_history=10000)

        # MetricsCollector doesn't require async initialization

        # Register custom metrics
        await self._register_custom_metrics()

        self.logger.info("Metrics collection initialized successfully")

    async def _register_custom_metrics(self):
        """Register custom application metrics."""
        if not self.metrics:
            return

        # MetricsCollector from monitoring doesn't require metric registration
        # It automatically tracks tool execution metrics
        self.logger.info("Metrics collection ready")

    async def _initialize_authorization(self):
        """Initialize security manager."""
        if not self.config.enable_auth:
            self.logger.info("Authorization disabled")
            return

        self.logger.info("Initializing authorization manager")

        self.authorization_manager = AuthorizationManager()

        # Authorization manager doesn't need async initialization
        self.logger.info("Authorization manager initialized successfully")

    async def _initialize_gateway(self):
        """Initialize Arcade.dev gateway."""
        self.logger.info("Initializing Arcade.dev gateway")

        self.arcade_gateway = ArcadeGateway(
            arcade_client=self.arcade_client,
            cache_manager=self.cache_manager,
            metrics=self.metrics,
            authorization_manager=self.authorization_manager,
        )

        await self.arcade_gateway.initialize()
        self.logger.info("Arcade.dev gateway initialized successfully")

    async def _start_background_tasks(self):
        """Start background maintenance tasks."""
        self.logger.info("Starting background tasks")

        # Health check task
        health_task = asyncio.create_task(self._health_check_loop())
        self.background_tasks.append(health_task)

        # Metrics collection task
        if self.metrics:
            metrics_task = asyncio.create_task(self._metrics_collection_loop())
            self.background_tasks.append(metrics_task)

        # Cache cleanup task
        if self.cache_manager:
            cleanup_task = asyncio.create_task(self._cache_cleanup_loop())
            self.background_tasks.append(cleanup_task)

        self.logger.info(f"Started {len(self.background_tasks)} background tasks")

    async def _perform_initial_health_checks(self):
        """Perform initial health checks on all components."""
        self.logger.info("Performing initial health checks")

        # Check all components
        await self._check_cache_health()
        await self._check_arcade_health()
        await self._check_system_health()

        # Verify all components are healthy
        unhealthy_services = [
            name for name, status in self.health_status.items() if not status.healthy
        ]

        if unhealthy_services:
            raise ServiceStartupError(f"Unhealthy services: {unhealthy_services}")

        self.logger.info("All initial health checks passed")

    async def _health_check_loop(self):
        """Background task for periodic health checks."""
        while not self.shutdown_event.is_set():
            try:
                await self._check_cache_health()
                await self._check_arcade_health()
                await self._check_system_health()

                # Wait for next check
                await asyncio.wait_for(
                    self.shutdown_event.wait(), timeout=30.0  # Check every 30 seconds
                )

            except asyncio.TimeoutError:
                continue  # Continue health checks
            except Exception as e:
                self.logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(30)

    async def _check_cache_health(self):
        """Check cache health."""
        try:
            start_time = time.time()
            test_key = f"health_check_{int(time.time())}"

            self.cache_manager.store(test_key, "ok")
            result = self.cache_manager.get(test_key)
            self.cache_manager.invalidate_by_prefix(test_key)

            response_time = time.time() - start_time

            self.health_status["cache"] = ServiceHealthStatus(
                service_name="cache",
                healthy=result is not None and result.content == "ok",
                last_check=time.time(),
                details={"response_time": response_time},
            )

        except Exception as e:
            self.health_status["cache"] = ServiceHealthStatus(
                service_name="cache",
                healthy=False,
                last_check=time.time(),
                error_message=str(e),
            )

    async def _check_arcade_health(self):
        """Check Arcade.dev API health."""
        try:
            start_time = time.time()
            result = await self.arcade_client.health_check()
            response_time = time.time() - start_time

            self.health_status["arcade"] = ServiceHealthStatus(
                service_name="arcade",
                healthy=result.get("status") == "healthy",
                last_check=time.time(),
                details={"response_time": response_time, "api_status": result},
            )

        except Exception as e:
            self.health_status["arcade"] = ServiceHealthStatus(
                service_name="arcade",
                healthy=False,
                last_check=time.time(),
                error_message=str(e),
            )

    async def _check_system_health(self):
        """Check system resource health."""
        try:
            if psutil is None:
                # Fallback when psutil is not available
                healthy = True
                memory_mb = 0
                cpu_percent = 0
            else:
                # Check memory usage
                process = psutil.Process()
                memory_info = process.memory_info()
                cpu_percent = process.cpu_percent()

                # Check if we're using too much memory (> 1GB as example)
                memory_mb = memory_info.rss / 1024 / 1024
                healthy = memory_mb < 1024 and cpu_percent < 80

            self.health_status["system"] = ServiceHealthStatus(
                service_name="system",
                healthy=healthy,
                last_check=time.time(),
                details={
                    "memory_mb": memory_mb,
                    "cpu_percent": cpu_percent,
                    "uptime": (
                        time.time() - self.startup_time if self.startup_time else 0
                    ),
                },
            )

        except Exception as e:
            self.health_status["system"] = ServiceHealthStatus(
                service_name="system",
                healthy=False,
                last_check=time.time(),
                error_message=str(e),
            )

    async def _metrics_collection_loop(self):
        """Background task for metrics collection."""
        while not self.shutdown_event.is_set():
            try:
                if self.metrics and self.startup_time:
                    uptime = time.time() - self.startup_time
                    # MetricsCollector from monitoring doesn't have record_gauge method
                    # It automatically tracks metrics during tool execution
                    self.logger.debug(f"Service uptime: {uptime:.2f} seconds")

                # Wait for next collection
                await asyncio.wait_for(
                    self.shutdown_event.wait(), timeout=60.0  # Collect every minute
                )

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Metrics collection error: {e}")
                await asyncio.sleep(60)

    async def _cache_cleanup_loop(self):
        """Background task for cache cleanup."""
        while not self.shutdown_event.is_set():
            try:
                if self.cache_manager:
                    # Use private method for cleanup (sync, not async)
                    self.cache_manager._cleanup_expired()

                # Wait for next cleanup
                await asyncio.wait_for(
                    self.shutdown_event.wait(), timeout=300.0  # Cleanup every 5 minutes
                )

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Cache cleanup error: {e}")
                await asyncio.sleep(300)

    async def get_health_status(self) -> Dict[str, Any]:
        """Get current health status of all components."""
        overall_healthy = all(status.healthy for status in self.health_status.values())

        return {
            "service": self.config.service_name,
            "version": self.config.service_version,
            "environment": self.config.environment,
            "status": "healthy" if overall_healthy else "unhealthy",
            "uptime": time.time() - self.startup_time if self.startup_time else 0,
            "components": {
                name: {
                    "healthy": status.healthy,
                    "last_check": status.last_check,
                    "details": status.details,
                    "error": status.error_message,
                }
                for name, status in self.health_status.items()
            },
        }

    async def get_readiness_status(self) -> Dict[str, Any]:
        """Get readiness status for load balancer probes."""
        return {
            "ready": self.is_ready,
            "startup_time": self.startup_time,
            "components_ready": len(self.health_status) > 0,
        }

    async def shutdown(self):
        """Gracefully shutdown the service."""
        if not self.is_running:
            return

        self.logger.info("Starting graceful shutdown")
        shutdown_start = time.time()

        # Set shutdown event
        self.shutdown_event.set()
        self.is_ready = False

        try:
            # Cancel background tasks
            self.logger.info("Cancelling background tasks")
            for task in self.background_tasks:
                task.cancel()

            # Wait for tasks to complete
            if self.background_tasks:
                await asyncio.gather(*self.background_tasks, return_exceptions=True)

            # Cleanup components
            await self.cleanup()

            shutdown_time = time.time() - shutdown_start
            self.logger.info(f"Graceful shutdown completed in {shutdown_time:.2f}s")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
        finally:
            self.is_running = False

    async def cleanup(self):
        """Clean up all resources."""
        self.logger.info("Cleaning up resources")

        # Close gateway
        if self.arcade_gateway:
            await self.arcade_gateway.cleanup()

        # Close arcade client
        if self.arcade_client:
            await self.arcade_client.disconnect()

        # Close cache manager
        if self.cache_manager:
            # CacheManager doesn't have a close method - cleanup is automatic
            pass

        # Close metrics collector
        if self.metrics:
            # MetricsCollector from monitoring doesn't require cleanup
            pass

        # Shutdown thread pool
        self.thread_pool.shutdown(wait=True)

        self.logger.info("Resource cleanup completed")


async def create_health_check_server(service: ProductionArcadeService):
    """Create HTTP server for health checks."""
    try:
        from aiohttp import web, web_response
    except ImportError:
        # Fallback for demonstration if aiohttp is not installed
        web = None
        web_response = None

    if web is None or web_response is None:
        # Return a mock app if aiohttp is not available
        class MockApp:
            pass

        return MockApp()

    async def health_handler(request):
        """Health check endpoint."""
        status = await service.get_health_status()
        status_code = 200 if status["status"] == "healthy" else 503
        return web_response.json_response(status, status=status_code)

    async def readiness_handler(request):
        """Readiness check endpoint."""
        status = await service.get_readiness_status()
        status_code = 200 if status["ready"] else 503
        return web_response.json_response(status, status=status_code)

    app = web.Application()
    app.router.add_get("/health", health_handler)
    app.router.add_get("/ready", readiness_handler)

    return app


async def main():
    """Main service entry point."""
    # Load configuration
    config = DeploymentConfig()

    # Override from environment
    config.environment = os.getenv("ENVIRONMENT", config.environment)
    config.log_level = os.getenv("LOG_LEVEL", config.log_level)
    config.port = int(os.getenv("PORT", str(config.port)))

    # Create and start service
    service = ProductionArcadeService(config)

    try:
        # Initialize service
        await service.initialize()

        # Create health check server
        health_app = await create_health_check_server(service)

        # Start health check server
        try:
            from aiohttp import web
        except ImportError:
            web = None
        if web is not None and hasattr(health_app, "router"):
            health_runner = web.AppRunner(health_app)
            await health_runner.setup()
            health_site = web.TCPSite(
                health_runner, service.config.host, service.config.health_check_port
            )
            await health_site.start()

            service.logger.info(
                f"Health check server started on port {service.config.health_check_port}"
            )
        else:
            service.logger.info("Health check server skipped (aiohttp not available)")
            health_runner = None

        service.logger.info(f"Service ready and accepting requests")

        # Wait for shutdown signal
        await service.shutdown_event.wait()

        # Cleanup health server
        if health_runner:
            await health_runner.cleanup()

        service.logger.info("Service shutdown completed")
        return 0

    except Exception as e:
        if service:
            service.logger.error(f"Service failed: {e}")
        else:
            print(f"Service startup failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
