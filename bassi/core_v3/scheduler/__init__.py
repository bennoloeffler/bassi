"""
Task Scheduler for bassi

File-based task scheduling system that runs within the bassi web server.
Tasks are defined in ~/.bassi/tasks-scheduler/ as folders containing:
- schedule.yaml: When to run
- prompt.txt: What to run
- config.yaml: Optional configuration
- last_run.json: Execution metadata (auto-generated)
- results/: Output history (auto-generated)
"""

from .task_scheduler import TaskScheduler
from .models import Task

__all__ = ["TaskScheduler", "Task"]
