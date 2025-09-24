"""Adapters for wrapping comma-tools as service components."""

from .batch import BatchAdapter
from .realtime import RealtimeAdapter

__all__ = ["BatchAdapter", "RealtimeAdapter"]
