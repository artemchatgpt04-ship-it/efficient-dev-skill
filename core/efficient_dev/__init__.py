"""Deterministic repository mapping and read-scope recommendations."""

from .change_tracker import ChangeResult, ChangeTracker
from .fingerprint import fingerprint_file
from .project_map import ProjectMap, ProjectMapBuilder
from .read_cache import CacheEntry, CacheLookup, CacheStatus, ReadCache
from .smart_reader import ReadPlan, SmartReader
from .task_router import RouteResult, TaskRouter

__all__ = [
    "CacheEntry",
    "CacheLookup",
    "CacheStatus",
    "ChangeResult",
    "ChangeTracker",
    "ProjectMap",
    "ProjectMapBuilder",
    "ReadPlan",
    "ReadCache",
    "RouteResult",
    "SmartReader",
    "TaskRouter",
    "fingerprint_file",
]
