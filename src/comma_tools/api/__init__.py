"""
CTS-Lite HTTP API Service

This package provides the HTTP API service layer for comma-tools,
enabling unified access to analysis and monitoring capabilities
through a RESTful API.

Architecture:
- server.py: FastAPI application setup
- models.py: Pydantic request/response models
- config.py: Service configuration management
- health.py: Health check endpoint
- capabilities.py: Tool discovery endpoint
- registry.py: Tool registration system
- execution.py: Tool execution engine
"""

__version__ = "0.1.0"