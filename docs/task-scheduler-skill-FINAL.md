# Task Scheduler for bassi - FINAL Design

**Created**: 2025-01-16
**Status**: Final Architecture
**Approach**: File-Based Internal Scheduling

---

## Core Concept

**Tasks live in files. bassi server watches files. Simple.**

```
~/.bassi/tasks-scheduler/
├── weekly-report/
│   ├── schedule.yaml          # When to run
│   ├── prompt.txt             # What to run
│   ├── last_run.json          # Execution metadata
│   └── results/               # Output history
│       ├── 2025-01-13.txt
│       └── 2025-01-06.txt
├── daily-backup/
│   ├── schedule.yaml
│   ├── prompt.txt
│   ├── last_run.json
│   └── results/
└── monthly-summary/
    ├── schedule.yaml
    ├── prompt.txt
    ├── last_run.json
    └── results/
```

**When bassi web server starts:**
1. Reads all task folders
2. Parses schedule.yaml files
3. Sets up internal triggers
4. Watches for file changes

**When files change:**
1. Re-reads affected task folder
2. Updates triggers
3. Logs the change

**When trigger fires:**
1. Reads prompt.txt
2. Executes with bassi agent
3. Saves result to results/
4. Updates last_run.json

---

## Why This Design?

### Compared to External Scheduling (claude.md)
- ❌ NO CLI commands needed (`bassi schedule add` → just create folder)
- ❌ NO OS scheduler integration (launchd/cron)
- ✅ Works when bassi server is running (assumption: almost always)
- ✅ File-based = easy to backup, version control, sync
- ✅ Hot-reload on file changes

### Compared to API-Driven (cursor.md)
- ❌ NO API endpoints needed
- ❌ NO HTTP calls
- ✅ Simpler: fewer moving parts
- ✅ Configuration as code (YAML files)

### Key Benefits
1. **Declarative**: Tasks are configuration, not commands
2. **Version Controllable**: Git-track your tasks
3. **Discoverable**: `ls ~/.bassi/tasks-scheduler/` shows all tasks
4. **Self-Documenting**: Each task is a folder with all its files
5. **Portable**: Copy folder = copy all tasks
6. **No Database**: Everything is files

---

## Task Folder Structure

### Minimal Task
```
my-task/
├── schedule.yaml    # REQUIRED
└── prompt.txt       # REQUIRED
```

### Complete Task
```
my-task/
├── schedule.yaml           # Schedule configuration
├── prompt.txt              # Prompt to execute
├── config.yaml             # Optional: timeout, retry, etc.
├── last_run.json           # Auto-generated: execution metadata
├── results/                # Auto-generated: execution outputs
│   ├── 2025-01-13_09-00.txt
│   ├── 2025-01-13_09-00.json   # Structured metadata
│   └── 2025-01-06_09-00.txt
└── scripts/                # Optional: helper scripts
    └── preprocess.py
```

---

## File Formats

### schedule.yaml

**Weekly task:**
```yaml
# Run every Monday at 9:00 AM
type: weekly
day: monday
time: "09:00"
timezone: America/Los_Angeles
enabled: true
```

**Daily task:**
```yaml
# Run every day at 14:30
type: daily
time: "14:30"
enabled: true
```

**Monthly task:**
```yaml
# Run on the 1st of every month at 8:00
type: monthly
day: 1
time: "08:00"
enabled: true
```

**Interval task:**
```yaml
# Run every 2 hours
type: interval
minutes: 120
enabled: true
```

**Cron expression (advanced):**
```yaml
# Custom cron expression
type: cron
cron: "0 9 * * 1"  # Every Monday at 9:00
enabled: true
```

**One-time task:**
```yaml
# Run once at specific time
type: once
datetime: "2025-01-20 09:00:00"
enabled: true
```

### prompt.txt

Plain text file with the prompt:

```
Query the CRM database for all sales from last week.
Generate a summary report and save it to _RESULTS_FROM_AGENT/weekly_sales.txt

Include:
- Total revenue
- Number of orders
- Top 3 products
- Year-over-year comparison
```

**Template variables** (expanded before execution):
```
Generate report for week ending {date}.
Save to _RESULTS_FROM_AGENT/weekly_report_{timestamp}.txt
Last run was {last_run_date}.
```

Available variables:
- `{date}` → "2025-01-16"
- `{time}` → "09:00"
- `{timestamp}` → "1705392000"
- `{weekday}` → "monday"
- `{task_name}` → "weekly-report"
- `{last_run_date}` → "2025-01-13"
- `{last_run_success}` → "true" or "false"

### config.yaml (optional)

```yaml
# Task execution configuration

timeout: 600              # Seconds (10 minutes)
retry_on_failure: true
max_retries: 3
retry_delay: 60           # Seconds between retries

notify:
  on_success: false
  on_failure: true
  channels:
    - log
    # Future: email, webhook, etc.

output:
  format: text            # text, json, markdown
  keep_history: 30        # Days of results to keep
  auto_cleanup: true

environment:
  # Environment variables for this task
  DATABASE_URL: "postgresql://localhost/crm"
  REPORT_FORMAT: "detailed"
```

### last_run.json (auto-generated)

```json
{
  "task_name": "weekly-report",
  "last_run": "2025-01-13T09:00:00Z",
  "next_run": "2025-01-20T09:00:00Z",
  "run_count": 42,
  "success_count": 40,
  "failure_count": 2,
  "last_status": "success",
  "last_duration_seconds": 47,
  "last_result_file": "results/2025-01-13_09-00.txt",
  "history": [
    {
      "timestamp": "2025-01-13T09:00:00Z",
      "status": "success",
      "duration": 47,
      "result_file": "results/2025-01-13_09-00.txt"
    },
    {
      "timestamp": "2025-01-06T09:00:00Z",
      "status": "success",
      "duration": 52,
      "result_file": "results/2025-01-06_09-00.txt"
    },
    {
      "timestamp": "2024-12-30T09:00:00Z",
      "status": "failed",
      "duration": 5,
      "error": "Database connection timeout"
    }
  ]
}
```

---

## User Experience

### Creating a Task

**Step 1: Create folder**
```bash
mkdir -p ~/.bassi/tasks-scheduler/weekly-report
```

**Step 2: Create schedule.yaml**
```bash
cat > ~/.bassi/tasks-scheduler/weekly-report/schedule.yaml << 'EOF'
type: weekly
day: monday
time: "09:00"
enabled: true
EOF
```

**Step 3: Create prompt.txt**
```bash
cat > ~/.bassi/tasks-scheduler/weekly-report/prompt.txt << 'EOF'
Query the metrics database and generate last week's sales report.
Save to _RESULTS_FROM_AGENT/weekly_report_{date}.txt
EOF
```

**Done!** bassi will:
- Detect the new folder (within 5 seconds)
- Parse schedule.yaml
- Set up trigger
- Show in logs: "✅ Loaded task: weekly-report (runs Monday 09:00)"

### Viewing All Tasks

```bash
ls -la ~/.bassi/tasks-scheduler/
```

```
drwxr-xr-x  weekly-report/
drwxr-xr-x  daily-backup/
drwxr-xr-x  monthly-summary/
```

### Checking Task Status

```bash
cat ~/.bassi/tasks-scheduler/weekly-report/last_run.json
```

```json
{
  "last_run": "2025-01-13T09:00:00Z",
  "next_run": "2025-01-20T09:00:00Z",
  "run_count": 42,
  "last_status": "success"
}
```

### Viewing Results

```bash
ls -la ~/.bassi/tasks-scheduler/weekly-report/results/
```

```
-rw-r--r--  2.1K  2025-01-13_09-00.txt
-rw-r--r--  2.3K  2025-01-06_09-00.txt
-rw-r--r--  2.0K  2024-12-30_09-00.txt
```

```bash
cat ~/.bassi/tasks-scheduler/weekly-report/results/2025-01-13_09-00.txt
```

### Pausing a Task

```bash
# Option 1: Edit schedule.yaml
sed -i '' 's/enabled: true/enabled: false/' \
  ~/.bassi/tasks-scheduler/weekly-report/schedule.yaml
```

```bash
# Option 2: Rename folder (simpler)
mv ~/.bassi/tasks-scheduler/weekly-report \
   ~/.bassi/tasks-scheduler/.weekly-report  # Dot prefix = ignored
```

bassi logs: "⏸️  Task disabled: weekly-report"

### Deleting a Task

```bash
rm -rf ~/.bassi/tasks-scheduler/weekly-report
```

bassi logs: "🗑️  Task removed: weekly-report"

### Testing a Task Immediately

**Web UI**: Visit `http://localhost:8765/tasks`
- Click "Run Now" button next to task

**Or** create a temporary one-time task:
```bash
cp -r ~/.bassi/tasks-scheduler/weekly-report \
      ~/.bassi/tasks-scheduler/.test-weekly-report

cat > ~/.bassi/tasks-scheduler/.test-weekly-report/schedule.yaml << 'EOF'
type: once
datetime: "$(date -u +%Y-%m-%d) $(date -u +%H:%M:%S)"
enabled: true
EOF
```

This runs immediately, then auto-cleans up.

---

## Implementation Architecture

### Core Components

```python
bassi/
├── core_v3/
│   ├── scheduler/
│   │   ├── __init__.py
│   │   ├── task_loader.py         # Load tasks from filesystem
│   │   ├── task_watcher.py        # Watch for file changes
│   │   ├── task_scheduler.py      # Internal APScheduler
│   │   ├── task_executor.py       # Execute prompts
│   │   └── models.py              # Task, Schedule dataclasses
│   │
│   ├── web_server_v3.py           # Add scheduler startup
│   └── routes/
│       └── task_routes.py         # NEW: /tasks web UI
│
└── config.py                       # Add TASKS_DIR config
```

### Integration with bassi Web Server

**In `web_server_v3.py`:**

```python
from bassi.core_v3.scheduler import TaskScheduler

class WebServerV3:
    def __init__(self):
        # ... existing code ...
        self.task_scheduler = None

    async def startup(self):
        """Server startup - initialize scheduler"""
        logger.info("Starting bassi web server...")

        # Start task scheduler
        self.task_scheduler = TaskScheduler(
            tasks_dir=Path.home() / ".bassi" / "tasks-scheduler"
        )
        await self.task_scheduler.start()

        logger.info("Task scheduler started")

    async def shutdown(self):
        """Server shutdown - cleanup"""
        if self.task_scheduler:
            await self.task_scheduler.stop()

        logger.info("Shutdown complete")
```

### Task Scheduler Component

```python
# bassi/core_v3/scheduler/task_scheduler.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import yaml
import json
from datetime import datetime
from typing import Dict

class TaskScheduler:
    def __init__(self, tasks_dir: Path):
        self.tasks_dir = tasks_dir
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

        # APScheduler for internal scheduling
        self.scheduler = AsyncIOScheduler()

        # File watcher for hot-reload
        self.observer = Observer()

        # Track loaded tasks
        self.tasks: Dict[str, Task] = {}

    async def start(self):
        """Start the scheduler"""
        logger.info(f"Loading tasks from {self.tasks_dir}")

        # Load all existing tasks
        self._load_all_tasks()

        # Start scheduler
        self.scheduler.start()

        # Start file watcher
        event_handler = TaskFileHandler(self)
        self.observer.schedule(
            event_handler,
            str(self.tasks_dir),
            recursive=True
        )
        self.observer.start()

        logger.info(f"✅ Scheduler started with {len(self.tasks)} tasks")

    async def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        self.observer.stop()
        self.observer.join()

    def _load_all_tasks(self):
        """Load all task folders"""
        for task_dir in self.tasks_dir.iterdir():
            if task_dir.is_dir() and not task_dir.name.startswith('.'):
                self._load_task(task_dir)

    def _load_task(self, task_dir: Path):
        """Load a single task from folder"""
        task_name = task_dir.name

        # Check required files
        schedule_file = task_dir / "schedule.yaml"
        prompt_file = task_dir / "prompt.txt"

        if not schedule_file.exists():
            logger.warning(f"⚠️  Task {task_name}: missing schedule.yaml")
            return

        if not prompt_file.exists():
            logger.warning(f"⚠️  Task {task_name}: missing prompt.txt")
            return

        try:
            # Parse schedule
            with open(schedule_file) as f:
                schedule_data = yaml.safe_load(f)

            if not schedule_data.get('enabled', True):
                logger.info(f"⏸️  Task {task_name}: disabled")
                return

            # Read prompt
            prompt = prompt_file.read_text()

            # Load config (optional)
            config_file = task_dir / "config.yaml"
            config = {}
            if config_file.exists():
                with open(config_file) as f:
                    config = yaml.safe_load(f)

            # Create Task object
            task = Task(
                name=task_name,
                directory=task_dir,
                schedule=schedule_data,
                prompt=prompt,
                config=config
            )

            # Add to scheduler
            self._schedule_task(task)

            # Store in memory
            self.tasks[task_name] = task

            logger.info(
                f"✅ Loaded task: {task_name} "
                f"({self._format_schedule(schedule_data)})"
            )

        except Exception as e:
            logger.error(f"❌ Failed to load task {task_name}: {e}")

    def _schedule_task(self, task: Task):
        """Add task to APScheduler"""
        schedule = task.schedule

        if schedule['type'] == 'daily':
            hour, minute = schedule['time'].split(':')
            self.scheduler.add_job(
                self._execute_task,
                'cron',
                args=[task],
                hour=int(hour),
                minute=int(minute),
                id=task.name,
                replace_existing=True
            )

        elif schedule['type'] == 'weekly':
            day_map = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2,
                'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
            }
            hour, minute = schedule['time'].split(':')
            self.scheduler.add_job(
                self._execute_task,
                'cron',
                args=[task],
                day_of_week=day_map[schedule['day']],
                hour=int(hour),
                minute=int(minute),
                id=task.name,
                replace_existing=True
            )

        elif schedule['type'] == 'monthly':
            hour, minute = schedule['time'].split(':')
            self.scheduler.add_job(
                self._execute_task,
                'cron',
                args=[task],
                day=schedule['day'],
                hour=int(hour),
                minute=int(minute),
                id=task.name,
                replace_existing=True
            )

        elif schedule['type'] == 'interval':
            self.scheduler.add_job(
                self._execute_task,
                'interval',
                args=[task],
                minutes=schedule['minutes'],
                id=task.name,
                replace_existing=True
            )

        elif schedule['type'] == 'cron':
            # Parse cron expression
            # Format: "minute hour day month day_of_week"
            parts = schedule['cron'].split()
            self.scheduler.add_job(
                self._execute_task,
                'cron',
                args=[task],
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
                id=task.name,
                replace_existing=True
            )

        elif schedule['type'] == 'once':
            # Parse datetime and schedule once
            run_date = datetime.fromisoformat(schedule['datetime'])
            self.scheduler.add_job(
                self._execute_task,
                'date',
                args=[task],
                run_date=run_date,
                id=task.name,
                replace_existing=True
            )

    async def _execute_task(self, task: Task):
        """Execute a task"""
        logger.info(f"🚀 Executing task: {task.name}")

        start_time = datetime.now()

        try:
            # Expand template variables in prompt
            prompt = self._expand_template(task)

            # Create results directory
            results_dir = task.directory / "results"
            results_dir.mkdir(exist_ok=True)

            # Generate result filename
            timestamp = start_time.strftime("%Y-%m-%d_%H-%M")
            result_file = results_dir / f"{timestamp}.txt"

            # Execute with bassi agent
            from bassi.core_v3.agent_session import BassiAgentSession

            session = BassiAgentSession(
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                session_id=f"task-{task.name}-{int(start_time.timestamp())}"
            )

            # Stream output to file
            with open(result_file, 'w') as f:
                for event in session.query(prompt):
                    if event.type == "text":
                        f.write(event.text)
                        f.flush()

            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()

            # Update last_run.json
            self._update_last_run(
                task,
                status="success",
                duration=duration,
                result_file=f"results/{timestamp}.txt"
            )

            logger.info(
                f"✅ Task completed: {task.name} "
                f"({duration:.1f}s)"
            )

            # Cleanup old results
            self._cleanup_old_results(task)

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()

            logger.error(f"❌ Task failed: {task.name}: {e}")

            # Update last_run.json with failure
            self._update_last_run(
                task,
                status="failed",
                duration=duration,
                error=str(e)
            )

    def _expand_template(self, task: Task) -> str:
        """Expand template variables in prompt"""
        prompt = task.prompt

        # Load last_run data
        last_run_file = task.directory / "last_run.json"
        last_run_data = {}
        if last_run_file.exists():
            with open(last_run_file) as f:
                last_run_data = json.load(f)

        # Template variables
        now = datetime.now()
        replacements = {
            '{date}': now.strftime('%Y-%m-%d'),
            '{time}': now.strftime('%H:%M'),
            '{timestamp}': str(int(now.timestamp())),
            '{weekday}': now.strftime('%A').lower(),
            '{task_name}': task.name,
            '{last_run_date}': last_run_data.get('last_run', '')[:10],
            '{last_run_success}': str(
                last_run_data.get('last_status') == 'success'
            ).lower()
        }

        for var, value in replacements.items():
            prompt = prompt.replace(var, value)

        return prompt

    def _update_last_run(
        self,
        task: Task,
        status: str,
        duration: float,
        result_file: str = None,
        error: str = None
    ):
        """Update last_run.json"""
        last_run_file = task.directory / "last_run.json"

        # Load existing data
        if last_run_file.exists():
            with open(last_run_file) as f:
                data = json.load(f)
        else:
            data = {
                'task_name': task.name,
                'run_count': 0,
                'success_count': 0,
                'failure_count': 0,
                'history': []
            }

        # Update counts
        data['run_count'] += 1
        if status == 'success':
            data['success_count'] += 1
        else:
            data['failure_count'] += 1

        # Update last run info
        now = datetime.now()
        data['last_run'] = now.isoformat()
        data['last_status'] = status
        data['last_duration_seconds'] = duration

        if result_file:
            data['last_result_file'] = result_file

        # Calculate next run
        data['next_run'] = self._calculate_next_run(task)

        # Add to history (keep last 20)
        history_entry = {
            'timestamp': now.isoformat(),
            'status': status,
            'duration': duration
        }
        if result_file:
            history_entry['result_file'] = result_file
        if error:
            history_entry['error'] = error

        data['history'].insert(0, history_entry)
        data['history'] = data['history'][:20]  # Keep last 20

        # Save
        with open(last_run_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _cleanup_old_results(self, task: Task):
        """Cleanup old result files"""
        config = task.config
        keep_days = config.get('output', {}).get('keep_history', 30)

        if not config.get('output', {}).get('auto_cleanup', True):
            return

        results_dir = task.directory / "results"
        if not results_dir.exists():
            return

        cutoff = datetime.now().timestamp() - (keep_days * 86400)

        for result_file in results_dir.iterdir():
            if result_file.stat().st_mtime < cutoff:
                result_file.unlink()
                logger.debug(
                    f"🗑️  Cleaned up old result: {result_file.name}"
                )

    def _calculate_next_run(self, task: Task) -> str:
        """Calculate next scheduled run time"""
        # Get next run from APScheduler
        job = self.scheduler.get_job(task.name)
        if job and job.next_run_time:
            return job.next_run_time.isoformat()
        return ""

    def _format_schedule(self, schedule: dict) -> str:
        """Format schedule for logging"""
        if schedule['type'] == 'daily':
            return f"daily at {schedule['time']}"
        elif schedule['type'] == 'weekly':
            return f"{schedule['day']} at {schedule['time']}"
        elif schedule['type'] == 'monthly':
            return f"day {schedule['day']} at {schedule['time']}"
        elif schedule['type'] == 'interval':
            return f"every {schedule['minutes']} minutes"
        elif schedule['type'] == 'cron':
            return f"cron: {schedule['cron']}"
        elif schedule['type'] == 'once':
            return f"once at {schedule['datetime']}"
        return "unknown schedule"


class TaskFileHandler(FileSystemEventHandler):
    """Watch for file changes in tasks directory"""

    def __init__(self, scheduler: TaskScheduler):
        self.scheduler = scheduler

    def on_created(self, event):
        """Handle file/folder creation"""
        if event.is_directory:
            # New task folder
            task_dir = Path(event.src_path)
            if not task_dir.name.startswith('.'):
                logger.info(f"📁 New task detected: {task_dir.name}")
                self.scheduler._load_task(task_dir)

    def on_modified(self, event):
        """Handle file modification"""
        if not event.is_directory:
            # File changed - reload parent task
            file_path = Path(event.src_path)
            task_dir = file_path.parent

            if file_path.name in ['schedule.yaml', 'prompt.txt', 'config.yaml']:
                logger.info(
                    f"📝 Task updated: {task_dir.name} "
                    f"({file_path.name} changed)"
                )
                self.scheduler._load_task(task_dir)

    def on_deleted(self, event):
        """Handle file/folder deletion"""
        if event.is_directory:
            task_name = Path(event.src_path).name
            if task_name in self.scheduler.tasks:
                # Remove from scheduler
                try:
                    self.scheduler.scheduler.remove_job(task_name)
                except:
                    pass

                # Remove from memory
                del self.scheduler.tasks[task_name]

                logger.info(f"🗑️  Task removed: {task_name}")


@dataclass
class Task:
    """Task model"""
    name: str
    directory: Path
    schedule: dict
    prompt: str
    config: dict
```

---

## Web UI Routes

Add `/tasks` page to view and manage tasks:

```python
# bassi/core_v3/routes/task_routes.py

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
import json

router = APIRouter()

@router.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request):
    """Render tasks dashboard"""
    return templates.TemplateResponse("tasks.html", {
        "request": request
    })

@router.get("/api/tasks/list")
async def list_tasks(request: Request):
    """API: List all tasks"""
    scheduler = request.app.state.task_scheduler

    tasks_data = []
    for task in scheduler.tasks.values():
        # Load last_run.json
        last_run_file = task.directory / "last_run.json"
        last_run_data = {}
        if last_run_file.exists():
            with open(last_run_file) as f:
                last_run_data = json.load(f)

        tasks_data.append({
            'name': task.name,
            'schedule': scheduler._format_schedule(task.schedule),
            'last_run': last_run_data.get('last_run'),
            'next_run': last_run_data.get('next_run'),
            'status': last_run_data.get('last_status'),
            'run_count': last_run_data.get('run_count', 0),
            'success_rate': (
                last_run_data.get('success_count', 0) /
                max(last_run_data.get('run_count', 1), 1) * 100
            )
        })

    return JSONResponse(tasks_data)

@router.post("/api/tasks/{task_name}/run")
async def run_task_now(task_name: str, request: Request):
    """API: Trigger task immediately"""
    scheduler = request.app.state.task_scheduler

    if task_name not in scheduler.tasks:
        return JSONResponse(
            {'error': 'Task not found'},
            status_code=404
        )

    task = scheduler.tasks[task_name]

    # Execute asynchronously
    import asyncio
    asyncio.create_task(scheduler._execute_task(task))

    return JSONResponse({
        'status': 'started',
        'task': task_name
    })
```

### Web UI Template

```html
<!-- bassi/core_v3/static/tasks.html -->

<!DOCTYPE html>
<html>
<head>
    <title>Scheduled Tasks - bassi</title>
    <style>
        body {
            font-family: system-ui;
            max-width: 1200px;
            margin: 40px auto;
            padding: 20px;
        }
        .task-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            background: #fff;
        }
        .task-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .task-name {
            font-size: 1.5em;
            font-weight: bold;
        }
        .status-success { color: #28a745; }
        .status-failed { color: #dc3545; }
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        .btn-primary {
            background: #007bff;
            color: white;
        }
        .btn-primary:hover {
            background: #0056b3;
        }
    </style>
</head>
<body>
    <h1>📅 Scheduled Tasks</h1>

    <div id="tasks-container"></div>

    <script>
        async function loadTasks() {
            const response = await fetch('/api/tasks/list');
            const tasks = await response.json();

            const container = document.getElementById('tasks-container');
            container.innerHTML = '';

            tasks.forEach(task => {
                const statusClass = task.status === 'success'
                    ? 'status-success'
                    : 'status-failed';

                const card = document.createElement('div');
                card.className = 'task-card';
                card.innerHTML = `
                    <div class="task-header">
                        <div class="task-name">${task.name}</div>
                        <button class="btn btn-primary"
                                onclick="runTask('${task.name}')">
                            ▶️ Run Now
                        </button>
                    </div>
                    <div style="margin-top: 10px;">
                        <div>📅 Schedule: ${task.schedule}</div>
                        <div>⏰ Next run: ${task.next_run || 'N/A'}</div>
                        <div>✓ Last run: ${task.last_run || 'Never'}</div>
                        <div class="${statusClass}">
                            ● Status: ${task.status || 'pending'}
                        </div>
                        <div>📊 Runs: ${task.run_count}
                            (${task.success_rate.toFixed(0)}% success)
                        </div>
                    </div>
                `;
                container.appendChild(card);
            });
        }

        async function runTask(taskName) {
            const response = await fetch(`/api/tasks/${taskName}/run`, {
                method: 'POST'
            });

            if (response.ok) {
                alert(`Task "${taskName}" started!`);
                setTimeout(loadTasks, 2000);
            }
        }

        // Load tasks on page load
        loadTasks();

        // Refresh every 30 seconds
        setInterval(loadTasks, 30000);
    </script>
</body>
</html>
```

---

## Missed Tasks Handling

**When bassi server is not running:**
- Tasks are NOT executed (no background daemon)
- Next run time is NOT adjusted

**When server starts after downtime:**
- Reads all tasks
- Checks `next_run` in last_run.json
- If `next_run` is in the past:
  - **Option 1** (default): Skip and wait for next scheduled time
  - **Option 2** (if configured): Execute immediately ("catch-up mode")

**Configuration in config.yaml:**
```yaml
missed_task_policy: skip  # or "catchup" or "notify"
```

**Policy behaviors:**
- `skip`: Do nothing, wait for next scheduled time
- `catchup`: Execute immediately on startup if missed
- `notify`: Log warning but don't execute

---

## Testing Strategy

### Unit Tests

```python
# bassi/core_v3/tests/test_task_scheduler.py

def test_load_task_from_folder(tmp_path):
    """Test loading task from filesystem"""
    task_dir = tmp_path / "test-task"
    task_dir.mkdir()

    # Create schedule.yaml
    (task_dir / "schedule.yaml").write_text("""
type: daily
time: "09:00"
enabled: true
""")

    # Create prompt.txt
    (task_dir / "prompt.txt").write_text("Test prompt")

    # Load task
    scheduler = TaskScheduler(tmp_path)
    scheduler._load_task(task_dir)

    assert "test-task" in scheduler.tasks

def test_template_expansion():
    """Test template variable expansion"""
    task = Task(
        name="test",
        directory=Path("/tmp"),
        schedule={'type': 'daily', 'time': '09:00'},
        prompt="Today is {date}, task is {task_name}",
        config={}
    )

    scheduler = TaskScheduler(Path("/tmp"))
    expanded = scheduler._expand_template(task)

    assert "{date}" not in expanded
    assert "{task_name}" not in expanded
    assert "test" in expanded
```

### Integration Tests

```python
@pytest.mark.integration
async def test_task_execution(tmp_path):
    """Test full task execution flow"""
    # Create task
    task_dir = tmp_path / "integration-test"
    task_dir.mkdir()

    (task_dir / "schedule.yaml").write_text("""
type: once
datetime: "2025-01-16 10:00:00"
enabled: true
""")

    (task_dir / "prompt.txt").write_text(
        "Echo test successful"
    )

    # Start scheduler
    scheduler = TaskScheduler(tmp_path)
    await scheduler.start()

    # Manually trigger task
    task = scheduler.tasks["integration-test"]
    await scheduler._execute_task(task)

    # Check results
    results_dir = task_dir / "results"
    assert results_dir.exists()
    assert len(list(results_dir.glob("*.txt"))) > 0

    # Check last_run.json
    last_run_file = task_dir / "last_run.json"
    assert last_run_file.exists()

    with open(last_run_file) as f:
        data = json.load(f)

    assert data['run_count'] == 1
    assert data['last_status'] == 'success'

    await scheduler.stop()
```

### E2E Tests

```python
@pytest.mark.e2e
async def test_file_watch_and_reload():
    """Test hot-reload when files change"""
    # Start scheduler with empty dir
    tmp_path = Path("/tmp/test-scheduler")
    tmp_path.mkdir(exist_ok=True)

    scheduler = TaskScheduler(tmp_path)
    await scheduler.start()

    assert len(scheduler.tasks) == 0

    # Create new task folder
    task_dir = tmp_path / "new-task"
    task_dir.mkdir()

    (task_dir / "schedule.yaml").write_text("""
type: daily
time: "10:00"
enabled: true
""")

    (task_dir / "prompt.txt").write_text("Test")

    # Wait for file watcher to detect
    await asyncio.sleep(2)

    # Verify task loaded
    assert "new-task" in scheduler.tasks

    # Modify schedule
    (task_dir / "schedule.yaml").write_text("""
type: daily
time: "11:00"
enabled: true
""")

    # Wait for reload
    await asyncio.sleep(2)

    # Verify schedule updated
    task = scheduler.tasks["new-task"]
    assert task.schedule['time'] == "11:00"

    await scheduler.stop()
```

---

## Migration from Existing Approaches

### From External Scheduling (claude.md approach)

If you have tasks managed by launchd/cron:

**Migration script:**
```python
# migrate_external_to_internal.py

import json
from pathlib import Path
import yaml

old_tasks_dir = Path.home() / ".bassi" / "tasks"
new_tasks_dir = Path.home() / ".bassi" / "tasks-scheduler"

for task_file in old_tasks_dir.glob("*.json"):
    # Load old task
    with open(task_file) as f:
        old_task = json.load(f)

    # Create new task folder
    task_name = task_file.stem
    task_dir = new_tasks_dir / task_name
    task_dir.mkdir(exist_ok=True)

    # Convert schedule
    schedule_data = {
        'type': old_task['schedule']['type'],
        'enabled': old_task.get('enabled', True)
    }

    if old_task['schedule']['type'] == 'weekly':
        schedule_data['day'] = ['monday', 'tuesday', ...][
            old_task['schedule']['day']
        ]
        schedule_data['time'] = old_task['schedule']['time']

    # Write new files
    with open(task_dir / "schedule.yaml", 'w') as f:
        yaml.dump(schedule_data, f)

    with open(task_dir / "prompt.txt", 'w') as f:
        f.write(old_task['prompt'])

    # Preserve history
    if 'last_run' in old_task:
        with open(task_dir / "last_run.json", 'w') as f:
            json.dump({
                'last_run': old_task['last_run'],
                'run_count': old_task.get('run_count', 0)
            }, f, indent=2)

    print(f"✅ Migrated: {task_name}")

print("\n🎉 Migration complete!")
print(f"Old tasks preserved in: {old_tasks_dir}")
print(f"New tasks created in: {new_tasks_dir}")
```

### From API-Driven (cursor.md approach)

If you have API-based tasks:

**Same migration approach** - API metadata → file structure

---

## Advantages of This Design

### vs External Scheduling
- ✅ No OS-specific code (launchd/cron/systemd)
- ✅ Hot-reload when files change
- ✅ Integrated with bassi (no separate processes)
- ✅ Web UI for monitoring
- ❌ Requires bassi server running

### vs CLI-Based
- ✅ No CLI commands needed
- ✅ Files = version control
- ✅ Easy to backup/sync
- ✅ Self-documenting (each task is a folder)
- ❌ Less discoverability for beginners

### vs API-Driven
- ✅ Simpler (no HTTP layer)
- ✅ No authentication needed
- ✅ Lower latency
- ❌ Less suitable for external triggers

---

## Future Enhancements

### Phase 2 (v1.1)
- **Task templates**: Reusable task definitions
- **Conditional execution**: `if file_exists: run_task`
- **Task dependencies**: "Run B after A completes"
- **Email notifications**: On success/failure

### Phase 3 (v1.2)
- **Remote tasks**: Tasks on networked machines
- **Task marketplace**: Share tasks with community
- **Advanced scheduling**: Business days, holidays, etc.
- **Resource limits**: Max concurrent tasks

### Phase 4 (v2.0)
- **Visual task builder**: Drag-drop UI
- **Task analytics**: Success rates, trends
- **A/B testing**: Compare task variations
- **ML-powered scheduling**: Optimize run times

---

## Documentation for Users

### Quick Start Guide

**Create your first scheduled task in 3 steps:**

1. **Create folder:**
   ```bash
   mkdir -p ~/.bassi/tasks-scheduler/my-first-task
   ```

2. **Add schedule:**
   ```bash
   cat > ~/.bassi/tasks-scheduler/my-first-task/schedule.yaml << 'EOF'
   type: daily
   time: "09:00"
   enabled: true
   EOF
   ```

3. **Add prompt:**
   ```bash
   cat > ~/.bassi/tasks-scheduler/my-first-task/prompt.txt << 'EOF'
   Good morning! What's the weather forecast for today?
   Save the answer to _RESULTS_FROM_AGENT/daily_weather_{date}.txt
   EOF
   ```

**Done!** Check logs:
```bash
tail -f server.log | grep "my-first-task"
```

You'll see:
```
✅ Loaded task: my-first-task (daily at 09:00)
```

### Common Recipes

**Weekly team standup reminder:**
```yaml
# schedule.yaml
type: weekly
day: monday
time: "09:00"
enabled: true
```

```
# prompt.txt
Create this week's standup agenda:
1. Check calendar for this week's events
2. List any blockers from last week
3. Highlight upcoming deadlines
4. Generate meeting notes template

Save to _RESULTS_FROM_AGENT/standup_{date}.md
```

**Daily backup:**
```yaml
# schedule.yaml
type: daily
time: "22:00"
enabled: true
```

```
# prompt.txt
Backup important project files:
1. Zip _DATA_FROM_USER/ folder
2. Upload to cloud storage
3. Email confirmation to admin@example.com
```

**Monthly report:**
```yaml
# schedule.yaml
type: monthly
day: 1
time: "08:00"
enabled: true
```

```
# prompt.txt
Generate monthly summary for {last_run_date} to {date}:
1. Query CRM database for sales data
2. Calculate metrics (revenue, orders, customers)
3. Create charts and visualizations
4. Save report to _RESULTS_FROM_AGENT/monthly_report_{date}.pdf
```

---

## Summary

This design is:

- **Simple**: Just folders and YAML files
- **Integrated**: Part of bassi web server
- **File-based**: Everything is version-controllable
- **Hot-reload**: Changes take effect immediately
- **Tolerant**: Missed tasks are OK
- **Precise enough**: Minute-level scheduling

**No CLI. No database. No external schedulers. Just files.**

**Estimated implementation time**: 2 weeks (1 developer)

**Dependencies**:
- APScheduler (async scheduling)
- watchdog (file watching)
- PyYAML (config parsing)

**Total code**: ~500 lines (vs 1000+ for other approaches)

---

**Ready to implement? Start with Phase 1: Core scheduler.**
