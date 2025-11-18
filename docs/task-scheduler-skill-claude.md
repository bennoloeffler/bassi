# Task Scheduler for bassi - Fresh Thinking

**Created**: 2025-01-16
**Status**: Planning / Architecture Exploration
**Purpose**: Rethink task scheduling from first principles

---

## The Core Question

**How should users schedule bassi to do things automatically?**

Two fundamental approaches:
1. **External**: Schedule when bassi is NOT running (spawn on-demand)
2. **Internal**: Schedule when bassi IS running (daemon mode)

Let's think through both honestly.

---

## Option 1: External Scheduling (On-Demand bassi)

### How It Works

```
OS Scheduler (launchd/cron/systemd)
    ↓
Executes: bassi execute "do the weekly report"
    ↓
bassi starts, runs task, exits
```

### What Users Do

```bash
# Register a task
bassi schedule add "weekly-report" \
  --when "monday 09:00" \
  --prompt "Query the metrics database and generate last week's report"

# This creates:
# 1. Task definition in ~/.bassi/tasks/weekly-report.json
# 2. OS scheduler entry (launchd plist / cron entry)

# Manage tasks
bassi schedule list
bassi schedule pause weekly-report
bassi schedule delete weekly-report
```

### Pros
- **Simple**: No new daemon, uses proven OS schedulers
- **Reliable**: OS handles scheduling, restarts, logging
- **Low resource**: bassi only runs when needed
- **Familiar**: Works like cron/launchd users expect
- **Clean**: Each run is isolated, fresh state

### Cons
- **Startup overhead**: 2-3 seconds to launch bassi each time
- **No shared context**: Each run is independent
- **Can't cancel running task**: Once started, runs to completion
- **Limited frequency**: Not suitable for "every 30 seconds" tasks

### Best For
- Daily/weekly/monthly tasks
- Tasks that complete in minutes (reports, backups, summaries)
- Independent tasks (no inter-task dependencies)
- **This covers 90% of automation needs**

---

## Option 2: Internal Scheduling (Daemon Mode)

### How It Works

```
bassi daemon start
    ↓
Runs in background 24/7
    ↓
Internal scheduler checks tasks every minute
    ↓
Executes tasks in-process (no startup overhead)
```

### What Users Do

```bash
# Start daemon
bassi daemon start

# Register tasks (stored in daemon's memory/database)
bassi task add "check-emails" \
  --interval "5m" \
  --prompt "Check for new high-priority emails and notify me"

# Manage tasks
bassi task list
bassi task cancel <running-task-id>
bassi task history check-emails

# Stop daemon
bassi daemon stop
```

### Pros
- **Fast execution**: No startup overhead
- **High frequency**: Can run every minute/30 seconds
- **Shared context**: Tasks can share state/memory
- **Real-time control**: Cancel, pause, modify running tasks
- **Advanced features**: Task dependencies, chaining, conditions

### Cons
- **Complexity**: New daemon process, lifecycle management, state persistence
- **Resource usage**: bassi runs 24/7 (memory, CPU)
- **Failure handling**: What if daemon crashes? Auto-restart?
- **Upgrade path**: How to update daemon while running?
- **Overkill**: Most users don't need always-on scheduling

### Best For
- High-frequency tasks (every few minutes)
- Tasks that need shared context
- Complex workflows with dependencies
- **This is needed for <10% of users**

---

## Hybrid Option 3: Lightweight Scheduler Daemon

### The Middle Ground

What if we have a tiny scheduler daemon that ONLY checks schedules and spawns bassi?

```
bassi-scheduler (tiny Python daemon, <10MB)
    ↓
Reads ~/.bassi/tasks/*.json every minute
    ↓
When task is due: spawns `bassi execute <task>`
    ↓
bassi runs task and exits
```

### What Users Do

```bash
# Start scheduler (one-time setup)
bassi scheduler install  # Creates launchd entry for scheduler itself

# Add tasks (scheduler reads these files)
bassi schedule add "weekly-report" \
  --when "monday 09:00" \
  --prompt "Generate weekly report"

# Scheduler automatically picks up changes
# No need to reload/restart scheduler
```

### Pros
- **Lightweight**: Scheduler is 50 lines of Python, minimal resources
- **Cross-platform**: Works same on Mac/Linux/Windows
- **No OS-specific code**: Pure Python, no plist/cron manipulation
- **Task management**: Can pause, delete, view history
- **Reliable**: If scheduler crashes, auto-restarts (via launchd/systemd)

### Cons
- **Another process**: Scheduler daemon must run 24/7
- **Not native**: Doesn't use OS scheduler directly
- **Debugging**: Two layers (scheduler + bassi)

### Best For
- **Users who want task management UI**
- Cross-platform consistency
- Future web UI for task management

---

## Recommendation: Start with Option 1 (External)

### Why?

1. **Simplicity wins**: 90% of users need daily/weekly tasks
2. **Leverage existing tools**: launchd/cron are rock-solid
3. **Minimal code**: ~200 lines vs 2000+ lines for daemon
4. **Familiar mental model**: Users understand cron
5. **Easy to debug**: Standard OS logging
6. **Future-proof**: Can add Option 2 later if needed

### Implementation Scope

**Phase 1: Core Commands** (Week 1)
```bash
bassi schedule add <name> --when <schedule> --prompt <prompt>
bassi schedule list
bassi schedule delete <name>
```

**Phase 2: Management** (Week 2)
```bash
bassi schedule pause <name>
bassi schedule resume <name>
bassi schedule show <name>
bassi schedule logs <name>
```

**Phase 3: Execution** (Week 3)
```bash
bassi execute <task-name>  # Run task manually
bassi execute --task-id <id>  # Run from scheduler
```

---

## Architecture: External Scheduling

### Task Storage

```
~/.bassi/tasks/
├── weekly-report.json
├── daily-backup.json
└── monthly-summary.json
```

**Task File Format**:
```json
{
  "task_id": "weekly-report",
  "name": "Weekly Metrics Report",
  "prompt": "Query metrics database for last 7 days and generate summary report",
  "schedule": {
    "type": "weekly",
    "day": "monday",
    "time": "09:00",
    "timezone": "America/Los_Angeles"
  },
  "enabled": true,
  "created_at": "2025-01-16T10:00:00Z",
  "last_run": "2025-01-13T09:00:00Z",
  "next_run": "2025-01-20T09:00:00Z",
  "run_count": 42,
  "options": {
    "timeout": 600,
    "retry_on_error": true,
    "notify_on_failure": true
  }
}
```

### OS Scheduler Integration

**macOS (launchd)**:
```xml
<!-- ~/Library/LaunchAgents/com.bassi.task.weekly-report.plist -->
<plist>
  <dict>
    <key>Label</key>
    <string>com.bassi.task.weekly-report</string>

    <key>ProgramArguments</key>
    <array>
      <string>/usr/local/bin/bassi</string>
      <string>execute</string>
      <string>--task-id</string>
      <string>weekly-report</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
      <key>Weekday</key>
      <integer>1</integer>
      <key>Hour</key>
      <integer>9</integer>
      <key>Minute</key>
      <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/benno/.bassi/logs/weekly-report.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/benno/.bassi/logs/weekly-report.error.log</string>
  </dict>
</plist>
```

**Linux (systemd timer)**:
```ini
# ~/.config/systemd/user/bassi-weekly-report.timer
[Unit]
Description=bassi Task: Weekly Report

[Timer]
OnCalendar=Mon *-*-* 09:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# ~/.config/systemd/user/bassi-weekly-report.service
[Unit]
Description=bassi Execute: weekly-report

[Service]
Type=oneshot
ExecStart=/usr/local/bin/bassi execute --task-id weekly-report
```

### Execution Flow

```
1. User: bassi schedule add "weekly-report" --when "monday 09:00" --prompt "..."
   ↓
2. bassi:
   - Creates ~/.bassi/tasks/weekly-report.json
   - Generates OS scheduler config (plist/timer)
   - Installs scheduler entry
   - Calculates next_run time
   ↓
3. OS Scheduler: Monday 09:00
   ↓
4. Executes: bassi execute --task-id weekly-report
   ↓
5. bassi:
   - Reads ~/.bassi/tasks/weekly-report.json
   - Starts agent session
   - Executes prompt
   - Logs output
   - Updates task.json (last_run, run_count)
   - Exits
```

---

## User Experience

### Creating a Task

```bash
$ bassi schedule add "weekly-metrics" \
    --when "monday 09:00" \
    --prompt "Query the CRM database and generate a weekly sales report"

✅ Task created: weekly-metrics
📅 Next run: Monday, Jan 20, 2025 at 09:00
📝 Task saved to: ~/.bassi/tasks/weekly-metrics.json
⚙️  Scheduler configured: ~/Library/LaunchAgents/com.bassi.task.weekly-metrics.plist

To test immediately:
  bassi execute weekly-metrics
```

### Listing Tasks

```bash
$ bassi schedule list

📋 Scheduled Tasks (3)

┌────────────────────┬──────────┬─────────────────┬──────────────────┬───────┐
│ Name               │ Schedule │ Next Run        │ Last Run         │ Count │
├────────────────────┼──────────┼─────────────────┼──────────────────┼───────┤
│ weekly-metrics     │ Mon 9:00 │ Jan 20, 09:00   │ Jan 13, 09:00    │ 42    │
│ daily-backup       │ Daily    │ Today, 22:00    │ Yesterday, 22:00 │ 156   │
│ monthly-summary    │ 1st 8:00 │ Feb 1, 08:00    │ Jan 1, 08:00     │ 3     │
└────────────────────┴──────────┴─────────────────┴──────────────────┴───────┘

Commands:
  bassi schedule show <name>   - View task details
  bassi schedule logs <name>   - View execution logs
  bassi execute <name>         - Run task immediately
```

### Viewing Task Details

```bash
$ bassi schedule show weekly-metrics

📊 Task: weekly-metrics

Name:        Weekly Metrics Report
Created:     Jan 1, 2025
Status:      ✅ Enabled
Schedule:    Every Monday at 09:00 (America/Los_Angeles)

📝 Prompt:
  Query the CRM database and generate a weekly sales report

📅 Execution History:
  Next run:    Monday, Jan 20, 2025 at 09:00
  Last run:    Monday, Jan 13, 2025 at 09:00 (success)
  Run count:   42
  Success:     40 (95%)
  Failed:      2 (5%)

⚙️  Options:
  Timeout:     600 seconds
  Retry:       Yes
  Notify:      On failure only

📂 Files:
  Config:      ~/.bassi/tasks/weekly-metrics.json
  Scheduler:   ~/Library/LaunchAgents/com.bassi.task.weekly-metrics.plist
  Logs:        ~/.bassi/logs/weekly-metrics.log

Commands:
  bassi execute weekly-metrics        - Run now
  bassi schedule pause weekly-metrics - Pause scheduling
  bassi schedule logs weekly-metrics  - View logs
```

### Execution Logs

```bash
$ bassi schedule logs weekly-metrics

📜 Execution logs: weekly-metrics (last 10 runs)

[2025-01-13 09:00:00] ✅ SUCCESS (47s)
  Generated report: _RESULTS_FROM_AGENT/weekly_metrics_20250113.txt

[2025-01-06 09:00:00] ✅ SUCCESS (52s)
  Generated report: _RESULTS_FROM_AGENT/weekly_metrics_20250106.txt

[2025-12-30 09:00:00] ❌ FAILED (5s)
  Error: Database connection timeout

[2024-12-23 09:00:00] ✅ SUCCESS (44s)
  Generated report: _RESULTS_FROM_AGENT/weekly_metrics_20241223.txt

View full log:
  tail -f ~/.bassi/logs/weekly-metrics.log
```

---

## Implementation: File Structure

```
bassi/
├── cli.py
│   └── schedule_commands.py    # NEW: schedule add/list/delete commands
│
├── core_v3/
│   ├── scheduler/              # NEW: Scheduling logic
│   │   ├── __init__.py
│   │   ├── task_manager.py     # Task CRUD operations
│   │   ├── schedule_parser.py  # Parse "monday 09:00" → cron/plist
│   │   ├── os_integration.py   # Platform-specific scheduler creation
│   │   └── executor.py         # Execute task (called by scheduler)
│   │
│   └── models/
│       └── task.py             # Task dataclass
│
└── skills/
    └── task-scheduler/         # Skill bundle
        ├── SKILL.md
        └── scripts/
            ├── add_task.py
            ├── list_tasks.py
            └── show_task.py
```

---

## Implementation: Core Components

### 1. Task Model

```python
# bassi/core_v3/models/task.py

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

class ScheduleType(Enum):
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    INTERVAL = "interval"  # Every N seconds

@dataclass
class Schedule:
    type: ScheduleType
    day: Optional[int] = None  # 0-6 for weekly, 1-31 for monthly
    time: str = "09:00"  # HH:MM
    timezone: str = "UTC"
    interval_seconds: Optional[int] = None  # For interval type

@dataclass
class Task:
    task_id: str
    name: str
    prompt: str
    schedule: Schedule
    enabled: bool = True
    created_at: datetime = None
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    options: dict = None

    def to_dict(self) -> dict:
        """Serialize to JSON"""
        pass

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Deserialize from JSON"""
        pass

    def calculate_next_run(self) -> datetime:
        """Calculate next scheduled run time"""
        pass
```

### 2. Task Manager

```python
# bassi/core_v3/scheduler/task_manager.py

from pathlib import Path
import json
from typing import List, Optional
from ..models.task import Task

class TaskManager:
    def __init__(self, tasks_dir: Path = None):
        self.tasks_dir = tasks_dir or Path.home() / ".bassi" / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def create_task(self, task: Task) -> Task:
        """Create new scheduled task"""
        task_file = self.tasks_dir / f"{task.task_id}.json"
        if task_file.exists():
            raise ValueError(f"Task '{task.task_id}' already exists")

        # Calculate first run
        task.next_run = task.calculate_next_run()

        # Save to file
        task_file.write_text(json.dumps(task.to_dict(), indent=2))

        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Load task by ID"""
        task_file = self.tasks_dir / f"{task_id}.json"
        if not task_file.exists():
            return None

        data = json.loads(task_file.read_text())
        return Task.from_dict(data)

    def list_tasks(self, enabled_only: bool = False) -> List[Task]:
        """List all tasks"""
        tasks = []
        for task_file in self.tasks_dir.glob("*.json"):
            task = Task.from_dict(json.loads(task_file.read_text()))
            if enabled_only and not task.enabled:
                continue
            tasks.append(task)

        return sorted(tasks, key=lambda t: t.next_run or datetime.max)

    def update_task(self, task: Task) -> Task:
        """Update existing task"""
        task_file = self.tasks_dir / f"{task.task_id}.json"
        task_file.write_text(json.dumps(task.to_dict(), indent=2))
        return task

    def delete_task(self, task_id: str) -> bool:
        """Delete task"""
        task_file = self.tasks_dir / f"{task_id}.json"
        if task_file.exists():
            task_file.unlink()
            return True
        return False

    def mark_executed(self, task_id: str, success: bool) -> Task:
        """Update task after execution"""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found")

        task.last_run = datetime.now()
        task.run_count += 1
        if success:
            task.success_count += 1
        else:
            task.failure_count += 1

        task.next_run = task.calculate_next_run()

        return self.update_task(task)
```

### 3. Schedule Parser

```python
# bassi/core_v3/scheduler/schedule_parser.py

from ..models.task import Schedule, ScheduleType
import re

def parse_schedule(schedule_str: str) -> Schedule:
    """
    Parse human-readable schedule strings:

    Examples:
    - "monday 09:00"
    - "daily 14:30"
    - "monthly 1st 08:00"
    - "every 2h"
    - "once tomorrow 10:00"
    """

    schedule_str = schedule_str.lower().strip()

    # Daily: "daily 14:30"
    if schedule_str.startswith("daily"):
        time = schedule_str.split()[1]
        return Schedule(type=ScheduleType.DAILY, time=time)

    # Weekly: "monday 09:00"
    days = {
        "monday": 1, "tuesday": 2, "wednesday": 3,
        "thursday": 4, "friday": 5, "saturday": 6, "sunday": 0
    }
    for day_name, day_num in days.items():
        if schedule_str.startswith(day_name):
            time = schedule_str.split()[1]
            return Schedule(
                type=ScheduleType.WEEKLY,
                day=day_num,
                time=time
            )

    # Monthly: "monthly 1st 08:00" or "monthly 15 08:00"
    if schedule_str.startswith("monthly"):
        parts = schedule_str.split()
        day = int(re.sub(r'\D', '', parts[1]))  # Extract number
        time = parts[2]
        return Schedule(
            type=ScheduleType.MONTHLY,
            day=day,
            time=time
        )

    # Interval: "every 2h" or "every 30m"
    if schedule_str.startswith("every"):
        interval_str = schedule_str.split()[1]
        if interval_str.endswith("h"):
            hours = int(interval_str[:-1])
            seconds = hours * 3600
        elif interval_str.endswith("m"):
            minutes = int(interval_str[:-1])
            seconds = minutes * 60
        else:
            seconds = int(interval_str)

        return Schedule(
            type=ScheduleType.INTERVAL,
            interval_seconds=seconds
        )

    raise ValueError(f"Could not parse schedule: {schedule_str}")
```

### 4. OS Integration

```python
# bassi/core_v3/scheduler/os_integration.py

import platform
from pathlib import Path
from ..models.task import Task

class OSScheduler:
    @staticmethod
    def install_task(task: Task) -> str:
        """Install task in OS scheduler, return config file path"""
        system = platform.system()

        if system == "Darwin":
            return OSScheduler._install_launchd(task)
        elif system == "Linux":
            return OSScheduler._install_systemd(task)
        else:
            raise NotImplementedError(f"OS not supported: {system}")

    @staticmethod
    def uninstall_task(task: Task) -> bool:
        """Remove task from OS scheduler"""
        system = platform.system()

        if system == "Darwin":
            return OSScheduler._uninstall_launchd(task)
        elif system == "Linux":
            return OSScheduler._uninstall_systemd(task)
        else:
            raise NotImplementedError(f"OS not supported: {system}")

    @staticmethod
    def _install_launchd(task: Task) -> str:
        """Create launchd plist for macOS"""
        plist_dir = Path.home() / "Library" / "LaunchAgents"
        plist_dir.mkdir(parents=True, exist_ok=True)

        plist_file = plist_dir / f"com.bassi.task.{task.task_id}.plist"

        # Generate plist content based on schedule type
        if task.schedule.type == "weekly":
            calendar_interval = f"""
        <key>StartCalendarInterval</key>
        <dict>
            <key>Weekday</key>
            <integer>{task.schedule.day}</integer>
            <key>Hour</key>
            <integer>{int(task.schedule.time.split(':')[0])}</integer>
            <key>Minute</key>
            <integer>{int(task.schedule.time.split(':')[1])}</integer>
        </dict>
            """
        elif task.schedule.type == "daily":
            hour, minute = task.schedule.time.split(":")
            calendar_interval = f"""
        <key>StartCalendarInterval</key>
        <dict>
            <key>Hour</key>
            <integer>{int(hour)}</integer>
            <key>Minute</key>
            <integer>{int(minute)}</integer>
        </dict>
            """
        elif task.schedule.type == "interval":
            calendar_interval = f"""
        <key>StartInterval</key>
        <integer>{task.schedule.interval_seconds}</integer>
            """

        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.bassi.task.{task.task_id}</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/bassi</string>
        <string>execute</string>
        <string>--task-id</string>
        <string>{task.task_id}</string>
    </array>

    {calendar_interval}

    <key>StandardOutPath</key>
    <string>{Path.home()}/.bassi/logs/{task.task_id}.log</string>

    <key>StandardErrorPath</key>
    <string>{Path.home()}/.bassi/logs/{task.task_id}.error.log</string>

    <key>WorkingDirectory</key>
    <string>{Path.home()}</string>
</dict>
</plist>
"""

        plist_file.write_text(plist_content)

        # Load with launchctl
        import subprocess
        subprocess.run(["launchctl", "load", str(plist_file)], check=True)

        return str(plist_file)

    @staticmethod
    def _uninstall_launchd(task: Task) -> bool:
        """Remove launchd plist"""
        import subprocess

        plist_file = (
            Path.home() / "Library" / "LaunchAgents"
            / f"com.bassi.task.{task.task_id}.plist"
        )

        if not plist_file.exists():
            return False

        # Unload from launchctl
        subprocess.run(
            ["launchctl", "unload", str(plist_file)],
            stderr=subprocess.DEVNULL
        )

        # Delete file
        plist_file.unlink()
        return True
```

### 5. Task Executor

```python
# bassi/core_v3/scheduler/executor.py

import sys
from pathlib import Path
from datetime import datetime
from .task_manager import TaskManager
from ..agent_session import BassiAgentSession

def execute_task(task_id: str) -> int:
    """
    Execute a scheduled task.
    Called by OS scheduler: bassi execute --task-id <id>

    Returns exit code: 0 = success, 1 = failure
    """

    # Setup logging
    log_dir = Path.home() / ".bassi" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{task_id}.log"

    # Load task
    task_manager = TaskManager()
    task = task_manager.get_task(task_id)

    if not task:
        print(f"❌ Task not found: {task_id}", file=sys.stderr)
        return 1

    if not task.enabled:
        print(f"⏸️  Task is paused: {task_id}", file=sys.stderr)
        return 0

    # Log execution start
    print(f"\n{'='*60}")
    print(f"🚀 Task: {task.name}")
    print(f"📅 Started: {datetime.now()}")
    print(f"📝 Prompt: {task.prompt}")
    print(f"{'='*60}\n")

    try:
        # Create agent session
        session = BassiAgentSession(
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            session_id=f"task-{task_id}-{int(datetime.now().timestamp())}"
        )

        # Execute prompt
        print("🤖 Executing with Claude...\n")

        # Stream output to console
        for event in session.query(task.prompt):
            if event.type == "text":
                print(event.text, end="", flush=True)
            elif event.type == "tool_use":
                print(f"\n🔧 Using tool: {event.tool_name}")

        print("\n")

        # Mark success
        task_manager.mark_executed(task_id, success=True)

        print(f"\n{'='*60}")
        print(f"✅ Task completed successfully")
        print(f"⏱️  Duration: {datetime.now() - task.last_run}")
        print(f"📊 Run count: {task.run_count}")
        print(f"{'='*60}\n")

        return 0

    except Exception as e:
        # Mark failure
        task_manager.mark_executed(task_id, success=False)

        print(f"\n{'='*60}")
        print(f"❌ Task failed: {str(e)}")
        print(f"{'='*60}\n")

        return 1
```

### 6. CLI Commands

```python
# bassi/cli.py (add these commands)

import click
from bassi.core_v3.scheduler.task_manager import TaskManager
from bassi.core_v3.scheduler.schedule_parser import parse_schedule
from bassi.core_v3.scheduler.os_integration import OSScheduler
from bassi.core_v3.scheduler.executor import execute_task
from bassi.core_v3.models.task import Task

@click.group()
def schedule():
    """Manage scheduled tasks"""
    pass

@schedule.command(name="add")
@click.argument("name")
@click.option("--when", required=True, help="Schedule: 'monday 09:00', 'daily 14:30'")
@click.option("--prompt", required=True, help="Prompt to execute")
def schedule_add(name: str, when: str, prompt: str):
    """Create a new scheduled task"""

    # Generate task ID from name
    task_id = name.lower().replace(" ", "-")

    # Parse schedule
    schedule = parse_schedule(when)

    # Create task
    task_manager = TaskManager()
    task = Task(
        task_id=task_id,
        name=name,
        prompt=prompt,
        schedule=schedule
    )

    task = task_manager.create_task(task)

    # Install in OS scheduler
    config_file = OSScheduler.install_task(task)

    click.echo(f"\n✅ Task created: {task_id}")
    click.echo(f"📅 Next run: {task.next_run.strftime('%A, %b %d, %Y at %H:%M')}")
    click.echo(f"📝 Task saved to: ~/.bassi/tasks/{task_id}.json")
    click.echo(f"⚙️  Scheduler configured: {config_file}")
    click.echo(f"\nTo test immediately:\n  bassi execute {task_id}")

@schedule.command(name="list")
def schedule_list():
    """List all scheduled tasks"""

    task_manager = TaskManager()
    tasks = task_manager.list_tasks()

    if not tasks:
        click.echo("No scheduled tasks found")
        return

    click.echo(f"\n📋 Scheduled Tasks ({len(tasks)})\n")

    # Table header
    click.echo("┌" + "─"*20 + "┬" + "─"*15 + "┬" + "─"*20 + "┬" + "─"*7 + "┐")
    click.echo(f"│ {'Name':<18} │ {'Schedule':<13} │ {'Next Run':<18} │ {'Count':<5} │")
    click.echo("├" + "─"*20 + "┼" + "─"*15 + "┼" + "─"*20 + "┼" + "─"*7 + "┤")

    # Table rows
    for task in tasks:
        schedule_str = f"{task.schedule.type.value}"
        next_run_str = task.next_run.strftime("%b %d, %H:%M") if task.next_run else "N/A"

        click.echo(
            f"│ {task.name[:18]:<18} │ "
            f"{schedule_str:<13} │ "
            f"{next_run_str:<18} │ "
            f"{task.run_count:<5} │"
        )

    click.echo("└" + "─"*20 + "┴" + "─"*15 + "┴" + "─"*20 + "┴" + "─"*7 + "┘")

@schedule.command(name="delete")
@click.argument("name")
def schedule_delete(name: str):
    """Delete a scheduled task"""

    task_id = name.lower().replace(" ", "-")

    task_manager = TaskManager()
    task = task_manager.get_task(task_id)

    if not task:
        click.echo(f"❌ Task not found: {name}")
        return

    # Uninstall from OS scheduler
    OSScheduler.uninstall_task(task)

    # Delete task file
    task_manager.delete_task(task_id)

    click.echo(f"✅ Task deleted: {name}")

@click.command()
@click.option("--task-id", required=True)
def execute(task_id: str):
    """Execute a task immediately"""

    exit_code = execute_task(task_id)
    sys.exit(exit_code)
```

---

## What We're NOT Building (Scope Boundaries)

To keep this simple, we explicitly exclude:

1. **Web UI**: CLI only (web UI can come later)
2. **Task dependencies**: No "run task B after task A completes"
3. **Conditional execution**: No "only run if condition X is true"
4. **Distributed execution**: Single machine only
5. **Task parameters**: Prompt is fixed (no runtime variables)
6. **Output parsing**: bassi generates files, we don't parse/validate them
7. **Notifications**: No email/SMS alerts (use bassi's built-in notifications)
8. **Task history database**: Just update task.json, no separate history DB
9. **Concurrent execution**: Tasks run sequentially (one at a time)
10. **Priority queues**: All tasks are equal priority

These features can be added later if needed, but they're not in v1.

---

## Testing Strategy

### Unit Tests

```python
# bassi/core_v3/tests/test_task_manager.py

def test_create_task():
    task_manager = TaskManager(tmp_path / "tasks")
    task = Task(
        task_id="test-task",
        name="Test Task",
        prompt="Test prompt",
        schedule=Schedule(type=ScheduleType.DAILY, time="09:00")
    )

    created = task_manager.create_task(task)
    assert created.task_id == "test-task"
    assert (tmp_path / "tasks" / "test-task.json").exists()

def test_parse_schedule_weekly():
    schedule = parse_schedule("monday 09:00")
    assert schedule.type == ScheduleType.WEEKLY
    assert schedule.day == 1
    assert schedule.time == "09:00"

def test_calculate_next_run():
    task = Task(
        task_id="test",
        name="Test",
        prompt="Test",
        schedule=Schedule(type=ScheduleType.WEEKLY, day=1, time="09:00")
    )

    next_run = task.calculate_next_run()
    assert next_run.weekday() == 1  # Monday
    assert next_run.hour == 9
    assert next_run.minute == 0
```

### Integration Tests

```python
# bassi/core_v3/tests/test_scheduler_integration.py

@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
def test_install_launchd_task():
    task = Task(
        task_id="integration-test",
        name="Integration Test",
        prompt="Test",
        schedule=Schedule(type=ScheduleType.DAILY, time="09:00")
    )

    config_file = OSScheduler.install_task(task)
    assert Path(config_file).exists()

    # Cleanup
    OSScheduler.uninstall_task(task)
    assert not Path(config_file).exists()
```

### End-to-End Tests

```bash
# tests/e2e/test_scheduler.sh

#!/bin/bash
set -e

echo "Creating test task..."
bassi schedule add "e2e-test" \
  --when "daily 09:00" \
  --prompt "Echo 'test successful'"

echo "Verifying task exists..."
bassi schedule list | grep "e2e-test"

echo "Executing task immediately..."
bassi execute e2e-test

echo "Checking logs..."
cat ~/.bassi/logs/e2e-test.log | grep "test successful"

echo "Deleting task..."
bassi schedule delete "e2e-test"

echo "✅ E2E test passed"
```

---

## Migration Path (If Coming from Previous Design)

If you implemented the Option 1/2 designs from other docs:

1. **Keep existing tasks working**: Read old format, convert to new format
2. **Migrate command**: `bassi schedule migrate` to convert old tasks
3. **Deprecation warning**: Show warning for 3 months before removing old format
4. **Backward compatibility**: Accept both old and new CLI syntax

But if starting fresh, ignore this section.

---

## Future Enhancements (Post-v1)

### Short term (v1.1 - Next 2 months)
- **Task edit**: `bassi schedule edit <name>` to modify prompt/schedule
- **Execution history**: Separate history file per task
- **Retry logic**: Auto-retry failed tasks with backoff
- **Notifications**: Optional email/webhook on success/failure

### Medium term (v1.2 - 3-6 months)
- **Web UI**: View/manage tasks via browser
- **Task dependencies**: Chain tasks (run B after A)
- **Conditional execution**: "Only run if file exists" type conditions
- **Template prompts**: Variables in prompts: `{today}`, `{last_run}`

### Long term (v2.0 - 6-12 months)
- **Distributed execution**: Run tasks across multiple machines
- **Priority queues**: High-priority tasks run first
- **Resource limits**: Max concurrent tasks, memory limits
- **Cloud integration**: Sync tasks across devices

---

## Open Questions & Decisions Needed

1. **Task ID generation**: Auto-generate or user-provided?
   - **Recommendation**: Auto-generate from name (safer, no conflicts)

2. **Timezone handling**: Store times in UTC or local?
   - **Recommendation**: Store UTC, display local (standard practice)

3. **Failed task retry**: Auto-retry or manual?
   - **Recommendation**: Manual for v1 (simpler), auto-retry in v1.1

4. **Concurrent tasks**: Allow or block?
   - **Recommendation**: Block for v1 (simpler), queue in v1.1

5. **Task output**: Where to store results?
   - **Recommendation**: Use existing `_RESULTS_FROM_AGENT/` directory

6. **Long-running tasks**: What if task takes 2 hours?
   - **Recommendation**: Let it run, no timeout for v1

7. **Task naming**: Enforce unique names?
   - **Recommendation**: Yes, task_id must be unique

---

## Summary: Why This Design?

### Core Philosophy
**"Do one thing well, then add features"**

### Key Decisions
1. **External scheduling (Option 1)**: Simplest, covers 90% of use cases
2. **OS-native schedulers**: Proven, reliable, well-understood
3. **JSON file storage**: No database dependency, easy to inspect/edit
4. **CLI-first**: Web UI later, CLI validates UX first
5. **Minimal code**: <1000 lines total, vs 3000+ for daemon approach

### What Makes This Different
- **Not over-engineered**: Previous designs had 7 API endpoints, complex state management
- **User-focused**: CLI designed for actual user workflows, not API completeness
- **Testable**: Each component is small, focused, easy to test
- **Maintainable**: Future developer can understand in 30 minutes

### Expected Development Time
- Week 1: Core models, task manager, schedule parser (40 hours)
- Week 2: OS integration, CLI commands (30 hours)
- Week 3: Testing, documentation, polish (30 hours)

**Total: ~100 hours / 2.5 weeks for one developer**

Compare to daemon approach: ~250 hours / 6 weeks

---

## Conclusion

This design prioritizes **simplicity and reliability** over features.

It's built on the principle: **Let bassi be bassi, let the OS handle scheduling.**

We're not building a competitor to Kubernetes CronJobs or Apache Airflow. We're building a way for users to say "run this bassi prompt every Monday" without thinking about it.

That's it. That's the whole feature.

Everything else is details.

---

# APPENDIX: Real-World Claude Code Scheduling

**Research Date**: 2025-01-16
**What People Are Actually Doing**

After researching existing Claude Code scheduling implementations, here's what the community has built:

---

## Approach 1: Cron + Shell Wrapper (blle.co)

### Architecture
```
Cron (every 10 min)
    ↓
Shell script (claude-worker.sh)
    ↓
Sources environment (NVM, PATH)
    ↓
Executes: claude -p "/process-next-task"
    ↓
MCP Server handles task queue
```

### Key Technical Insights

**Environment Loading is Critical**
```bash
source_user_environment() {
    [[ -f "$HOME/.zshrc" ]] && source "$HOME/.zshrc"
    if [[ -s "$HOME/.nvm/nvm.sh" ]]; then
        source "$HOME/.nvm/nvm.sh"
        nvm use default || nvm use node
    fi
}
```
Cron runs with minimal environment—must explicitly load Node, PATH, and user configs.

**Strict Error Handling**
```bash
set -euo pipefail  # Exit on error, undefined vars, pipeline failures
```
Prevents silent failures in automated context.

**Emergency Cleanup**
```bash
cleanup() {
    if [[ -n "${TASK_ID:-}" ]]; then
        log "Emergency cleanup for task $TASK_ID"
        # Mark task as failed in queue
    fi
}
trap cleanup EXIT
```
Ensures tasks get marked failed even if script crashes.

**Master Prompt Pattern**
Instead of calling `claude` with different prompts, uses a single `/process-next-task` prompt that:
1. Fetches next task from MCP queue
2. Routes to appropriate handler based on task type
3. Updates task status
4. Handles errors

### What Works Well
- ✅ Simple: Just bash + cron (no new daemons)
- ✅ MCP integration gives Claude access to task queue
- ✅ Robust error handling
- ✅ Standard logging

### What's Challenging
- ❌ Environment loading is finicky (NVM, PATH issues)
- ❌ Cron timing limitations (minimum 1 minute intervals)
- ❌ No real-time task visibility (must check logs)

---

## Approach 2: MCP Scheduler (tonybentley/claude-mcp-scheduler)

### Architecture
```
Custom Scheduler Process
    ↓
Reads config.json (tasks + cron schedules)
    ↓
Starts MCP servers as child processes
    ↓
When cron triggers: Execute prompt via Claude API
    ↓
MCP servers provide tools (filesystem, etc.)
```

### Key Technical Insights

**Configuration-Driven**
```json
{
  "tasks": [
    {
      "name": "daily-report",
      "cron": "0 9 * * *",
      "prompt": "Generate daily report using data from ~/reports/",
      "output": "reports/daily_{date}.md",
      "enabled": true
    }
  ],
  "mcpServers": [
    {
      "type": "filesystem",
      "allowedDirectories": ["/Users/me/reports"]
    }
  ]
}
```

**Output Templating**
Supports dynamic output paths: `reports/daily_{date}.md` expands to `reports/daily_2025-01-16.md`

**Security via MCP Constraints**
MCP servers have explicit `allowedDirectories`—Claude can't access files outside these paths.

**Batch Processing Model**
Designed for **server/CI environments** where Claude Desktop GUI isn't available. Uses Claude API directly.

### What Works Well
- ✅ Declarative configuration (no coding needed)
- ✅ MCP security model (constrained file access)
- ✅ Output templating
- ✅ Runs headless (perfect for servers)

### What's Challenging
- ❌ Another custom daemon to maintain
- ❌ Configuration gets complex with many tasks
- ❌ No built-in task history/logging

---

## Approach 3: GitHub Actions (Medium/SmartScope)

### Architecture
```
GitHub Actions Workflow
    ↓
Scheduled trigger (cron syntax)
    ↓
Checkout code
    ↓
Install Claude CLI
    ↓
Execute claude with prompt
    ↓
Commit results back to repo
```

### Key Technical Insights

**Workflow Configuration**
```yaml
name: Claude Documentation Update

on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9 AM
  workflow_dispatch:  # Manual trigger

jobs:
  update-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run Claude
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          claude -p "Update documentation based on recent code changes"

      - name: Commit changes
        run: |
          git config user.name "Claude Bot"
          git config user.email "claude@example.com"
          git add .
          git commit -m "docs: Claude automated update"
          git push
```

**Two Trigger Types**
1. **Scheduled**: Runs on cron schedule
2. **workflow_dispatch**: Manual "Run workflow" button in GitHub UI

**PR-Based Workflow**
Alternative approach: Trigger on pull requests, Claude reviews code and suggests doc updates in the same PR.

### What Works Well
- ✅ Zero infrastructure (GitHub runs it)
- ✅ Visual UI for monitoring
- ✅ Built-in secrets management
- ✅ Logs and history in GitHub UI
- ✅ Git-integrated (results auto-committed)

### What's Challenging
- ❌ Requires GitHub repo
- ❌ Limited to public repo actions (or paid plan)
- ❌ Cold start (installs dependencies every run)
- ❌ Not suitable for frequent tasks (<1 hour intervals)

---

## Lessons for bassi Design

### 1. Environment Loading is HARD
All implementations struggle with PATH, Node versions, and environment variables. Cron's minimal environment is a major pain point.

**Implication for bassi**: We should:
- Document environment requirements clearly
- Provide debugging command: `bassi schedule debug <task>` that shows environment
- Consider embedding Node path in plist/systemd config (not relying on $PATH)

### 2. Master Prompt Pattern is Elegant
Instead of different commands for different task types, one `/process-next-task` prompt that routes internally.

**Implication for bassi**: We could add:
```bash
bassi execute --task-id <id>  # Current design
bassi execute --next           # NEW: Process next queued task
```
This enables a queue model where tasks get added but not scheduled—then a single cron job processes the queue.

### 3. MCP Integration is Key
Both production systems use MCP servers to:
- Manage task queues
- Provide constrained filesystem access
- Handle state management

**Implication for bassi**: We already have MCP! We should:
- Create a **task-queue MCP server** for queue-based scheduling
- Use MCP security model for file access
- Let users add MCP servers to scheduled tasks

### 4. Output Templating Matters
Users need dynamic filenames: `report_{date}.txt`, not hardcoded `report.txt`.

**Implication for bassi**: Add template variables:
```bash
bassi schedule add "daily-report" \
  --when "daily 09:00" \
  --prompt "Generate report and save to _RESULTS_FROM_AGENT/report_{date}.txt"
```
Bassi should expand `{date}`, `{time}`, `{timestamp}` before executing.

### 5. GitHub Actions is Popular
Despite limitations, developers love it because:
- Zero setup
- Visual monitoring
- Free (for public repos)

**Implication for bassi**: We should provide:
- GitHub Actions template for bassi
- Document how to use bassi in CI/CD
- Consider `bassi execute --ci` mode (exits with error codes, no interactive prompts)

---

## Updated Architecture: Hybrid Model

Based on real-world usage, here's an enhanced architecture:

### Core: OS Scheduler (Same as before)
```bash
bassi schedule add "weekly-report" --when "monday 09:00" --prompt "..."
```

Creates launchd/cron entry that calls: `bassi execute --task-id weekly-report`

### Enhancement 1: Task Queue Mode
```bash
bassi queue add "analyze-data" --prompt "..."
bassi queue add "generate-report" --prompt "..."
bassi queue add "send-email" --prompt "..."
```

Then single scheduled job:
```bash
bassi schedule add "process-queue" \
  --when "every 10m" \
  --prompt "/process-next-task"
```

This polls the queue every 10 minutes.

### Enhancement 2: MCP Task Server
```bash
# Create built-in MCP server: task-queue
bassi/mcp_servers/task_queue/
    ├── server.py
    ├── tools/
    │   ├── get_next_task()
    │   ├── complete_task(id, result)
    │   └── fail_task(id, error)
    └── storage/
        └── queue.json
```

Then scheduled prompts can use MCP tools:
```
"Use get_next_task() to fetch the next pending task.
Execute the task.
Call complete_task() with results."
```

### Enhancement 3: Template Variables
Expand variables in prompts before execution:
- `{date}` → "2025-01-16"
- `{time}` → "09:00"
- `{timestamp}` → "1705392000"
- `{weekday}` → "monday"
- `{task_id}` → "weekly-report"

### Enhancement 4: CI Mode
```bash
bassi execute --task-id <id> --ci
```
- No interactive prompts (fail if question asked)
- Exit code 0 = success, 1 = failure
- JSON output to stdout
- Errors to stderr

Perfect for GitHub Actions, GitLab CI, Jenkins, etc.

---

## Revised Implementation Priority

### Phase 1: Core (Same as before)
- Task storage (JSON files)
- Schedule parser
- OS integration (launchd/systemd)
- Basic CLI: add, list, delete, execute

### Phase 2: Real-World Enhancements
- **Template variables** in prompts
- **CI mode** (--ci flag)
- **Environment debugging** (`bassi schedule debug <task>`)
- **GitHub Actions template** in docs

### Phase 3: Queue Model (If needed)
- Task queue MCP server
- `bassi queue` commands
- Queue processing mode

### Phase 4: Advanced (Future)
- Task dependencies
- Conditional execution
- Web UI
- Distributed execution

---

## Final Thoughts

The real-world research validates our **Option 1 (External Scheduling)** approach:
- Everyone uses OS schedulers (cron/launchd/GitHub Actions)
- No one built a custom daemon
- MCP integration is the key differentiator
- Environment issues are universal pain point

Our design is **exactly right**, we just need to:
1. Add template variables
2. Add CI mode
3. Document environment setup clearly
4. Consider queue model as Phase 3 (not Phase 1)

The path forward is clear: **Build the simple version first, add queue/MCP enhancements in v1.1.**
