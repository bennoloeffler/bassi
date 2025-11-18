# Task Scheduler Skill - Implementation Plan

**Status**: Planning Phase  
**Created**: 2025-11-16  
**Purpose**: Enable automated task scheduling on macOS that triggers bassi agent queries via API

---

## Executive Summary

This document outlines the complete plan for implementing a **task-scheduler skill** for macOS that allows users to schedule automated tasks that trigger bassi agent queries via HTTP API. The skill will:

1. Create and manage launchd jobs on macOS
2. Provide an HTTP API endpoint for triggering agent queries
3. Store scheduled task metadata
4. Enable recurring or one-time scheduled tasks
5. Support both interactive (WebSocket) and programmatic (HTTP) agent access

---

## Architecture Overview

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Scheduled Task Flow                       │
└─────────────────────────────────────────────────────────────┘

1. User: "Schedule a task to run every Monday at 9 AM"
   ↓
2. Skill creates:
   - launchd plist file
   - Task metadata (JSON)
   - Wrapper script that calls API
   ↓
3. launchd triggers at scheduled time
   ↓
4. Wrapper script executes:
   - HTTP POST to /api/tasks/execute
   - Includes prompt, session_id, task_id
   ↓
5. API endpoint:
   - Creates/uses agent session
   - Executes query
   - Streams response (or stores result)
   ↓
6. Results saved to:
   - _RESULTS_FROM_AGENT/tasks/{task_id}/
   - Task execution log
```

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Task Scheduler Skill                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  SKILL.md    │  │  scripts/    │  │ references/  │     │
│  │              │  │              │  │              │     │
│  │  Instructions│  │  - create.py │  │  - api.md    │     │
│  │  Workflows   │  │  - list.py   │  │  - launchd.md│     │
│  │  Examples    │  │  - delete.py │  │              │     │
│  └──────────────┘  │  - wrapper.sh│  └──────────────┘     │
│                    └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  API Endpoints (FastAPI)                             │  │
│  │  - POST /api/tasks/create                            │  │
│  │  - POST /api/tasks/execute                           │  │
│  │  - GET  /api/tasks/list                              │  │
│  │  - GET  /api/tasks/{task_id}                         │  │
│  │  - DELETE /api/tasks/{task_id}                       │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Task Storage                                        │  │
│  │  - tasks/ directory (JSON metadata)                 │  │
│  │  - launchd plist files                              │  │
│  │  - Execution logs                                    │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Agent Integration                                   │  │
│  │  - BassiAgentSession.query()                        │  │
│  │  - Background execution                              │  │
│  │  - Result storage                                    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    macOS launchd Layer                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  launchd Jobs                                        │  │
│  │  - ~/Library/LaunchAgents/com.bassi.task.*.plist     │  │
│  │  - Scheduled execution                              │  │
│  │  - Wrapper script calls API                         │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Part 1: Skill Structure

### Skill Location

```
.claude/skills/task-scheduler/
├── SKILL.md                    # Main skill documentation
├── scripts/
│   ├── create_task.py          # Create scheduled task
│   ├── list_tasks.py           # List all scheduled tasks
│   ├── delete_task.py          # Remove scheduled task
│   ├── test_task.py            # Test task execution
│   └── wrapper_template.sh     # Template for launchd wrapper
└── references/
    ├── api_reference.md        # API endpoint documentation
    ├── launchd_guide.md        # launchd scheduling guide
    └── examples.md             # Usage examples
```

### SKILL.md Structure

**Metadata**:
```yaml
---
name: task-scheduler
description: This skill should be used when the user wants to schedule automated tasks on macOS that trigger bassi agent queries. It handles creating launchd jobs, managing task metadata, and setting up API-triggered agent execution.
---
```

**Main Sections**:
1. **Overview** - What the skill does
2. **When to Use** - Specific scenarios
3. **Workflow Decision Tree** - Guide for task creation
4. **Creating Scheduled Tasks** - Step-by-step process
5. **Managing Tasks** - List, view, delete operations
6. **API Integration** - How tasks call the API
7. **Troubleshooting** - Common issues

---

## Part 2: API Changes

### New Endpoints Required

#### 1. POST /api/tasks/create

**Purpose**: Create a new scheduled task

**Request Body**:
```json
{
  "name": "weekly-metrics-report",
  "description": "Generate weekly metrics every Monday",
  "prompt": "Query the database and generate last week's metrics report",
  "schedule": {
    "type": "calendar_interval",  // or "interval" or "once"
    "weekday": 1,                 // 1=Monday, 7=Sunday (for calendar_interval)
    "hour": 9,
    "minute": 0
    // OR for interval:
    // "seconds": 3600  // every hour
    // OR for once:
    // "datetime": "2025-12-25T09:00:00"
  },
  "session_id": "optional-session-id",  // Use existing session or create new
  "options": {
    "store_results": true,
    "send_notifications": false,
    "timeout_seconds": 300
  }
}
```

**Response**:
```json
{
  "task_id": "uuid-123",
  "name": "weekly-metrics-report",
  "status": "scheduled",
  "launchd_label": "com.bassi.task.uuid-123",
  "next_run": "2025-11-23T09:00:00Z",
  "created_at": "2025-11-16T13:30:00Z"
}
```

**Implementation Location**: `bassi/core_v3/routes/task_routes.py`

**Dependencies**:
- Task storage service
- launchd plist generator
- Wrapper script generator

---

#### 2. POST /api/tasks/execute

**Purpose**: Execute a scheduled task (called by wrapper script)

**Request Body**:
```json
{
  "task_id": "uuid-123",
  "prompt": "Query the database and generate last week's metrics report",
  "session_id": "optional-session-id"
}
```

**Response**:
```json
{
  "task_id": "uuid-123",
  "execution_id": "exec-uuid-456",
  "status": "completed",
  "started_at": "2025-11-16T09:00:00Z",
  "completed_at": "2025-11-16T09:00:15Z",
  "duration_seconds": 15.2,
  "result_path": "_RESULTS_FROM_AGENT/tasks/uuid-123/exec-uuid-456.json",
  "usage": {
    "input_tokens": 150,
    "output_tokens": 500,
    "cost_usd": 0.0023
  }
}
```

**Implementation Notes**:
- Must execute agent query in background
- Stream response to file (not WebSocket)
- Handle timeouts gracefully
- Store execution metadata

**Implementation Location**: `bassi/core_v3/routes/task_routes.py`

---

#### 3. GET /api/tasks/list

**Purpose**: List all scheduled tasks

**Query Parameters**:
- `status`: Filter by status (scheduled, active, paused, deleted)
- `limit`: Max results (default: 100)
- `offset`: Pagination offset

**Response**:
```json
{
  "tasks": [
    {
      "task_id": "uuid-123",
      "name": "weekly-metrics-report",
      "description": "Generate weekly metrics every Monday",
      "status": "active",
      "schedule": {
        "type": "calendar_interval",
        "weekday": 1,
        "hour": 9,
        "minute": 0
      },
      "next_run": "2025-11-23T09:00:00Z",
      "last_run": "2025-11-16T09:00:00Z",
      "execution_count": 5,
      "created_at": "2025-11-09T10:00:00Z"
    }
  ],
  "total": 1
}
```

---

#### 4. GET /api/tasks/{task_id}

**Purpose**: Get detailed information about a specific task

**Response**:
```json
{
  "task_id": "uuid-123",
  "name": "weekly-metrics-report",
  "description": "Generate weekly metrics every Monday",
  "prompt": "Query the database and generate last week's metrics report",
  "status": "active",
  "schedule": {
    "type": "calendar_interval",
    "weekday": 1,
    "hour": 9,
    "minute": 0
  },
  "next_run": "2025-11-23T09:00:00Z",
  "last_run": "2025-11-16T09:00:00Z",
  "execution_count": 5,
  "executions": [
    {
      "execution_id": "exec-uuid-456",
      "started_at": "2025-11-16T09:00:00Z",
      "completed_at": "2025-11-16T09:00:15Z",
      "status": "completed",
      "result_path": "_RESULTS_FROM_AGENT/tasks/uuid-123/exec-uuid-456.json"
    }
  ],
  "created_at": "2025-11-09T10:00:00Z",
  "launchd_label": "com.bassi.task.uuid-123"
}
```

---

#### 5. DELETE /api/tasks/{task_id}

**Purpose**: Delete a scheduled task

**Response**:
```json
{
  "task_id": "uuid-123",
  "status": "deleted",
  "deleted_at": "2025-11-16T14:00:00Z"
}
```

**Side Effects**:
- Unloads launchd job
- Removes plist file
- Archives task metadata (soft delete)

---

#### 6. POST /api/tasks/{task_id}/pause

**Purpose**: Temporarily disable a task (keeps launchd job but pauses execution)

**Response**:
```json
{
  "task_id": "uuid-123",
  "status": "paused",
  "paused_at": "2025-11-16T14:00:00Z"
}
```

---

#### 7. POST /api/tasks/{task_id}/resume

**Purpose**: Resume a paused task

**Response**:
```json
{
  "task_id": "uuid-123",
  "status": "active",
  "resumed_at": "2025-11-16T14:05:00Z"
}
```

---

### API Implementation Details

#### File Structure

```
bassi/core_v3/
├── routes/
│   └── task_routes.py          # NEW: Task API endpoints
├── services/
│   ├── task_service.py         # NEW: Task business logic
│   └── task_storage.py         # NEW: Task metadata storage
└── tasks/
    ├── launchd_manager.py      # NEW: launchd job management
    └── wrapper_generator.py    # NEW: Generate wrapper scripts
```

#### Task Service Interface

```python
# bassi/core_v3/services/task_service.py

class TaskService:
    """Business logic for scheduled tasks."""
    
    async def create_task(
        self,
        name: str,
        description: str,
        prompt: str,
        schedule: dict,
        session_id: Optional[str] = None,
        options: Optional[dict] = None
    ) -> Task:
        """Create a new scheduled task."""
        # 1. Generate task_id
        # 2. Create task metadata
        # 3. Generate launchd plist
        # 4. Generate wrapper script
        # 5. Install launchd job
        # 6. Store metadata
        # 7. Return task object
    
    async def execute_task(
        self,
        task_id: str,
        prompt: str,
        session_id: Optional[str] = None
    ) -> TaskExecution:
        """Execute a scheduled task."""
        # 1. Load task metadata
        # 2. Create/use agent session
        # 3. Execute query (background)
        # 4. Stream results to file
        # 5. Store execution metadata
        # 6. Return execution result
    
    async def list_tasks(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Task]:
        """List all tasks with optional filtering."""
    
    async def get_task(self, task_id: str) -> Task:
        """Get task details."""
    
    async def delete_task(self, task_id: str) -> None:
        """Delete a task and unload launchd job."""
    
    async def pause_task(self, task_id: str) -> None:
        """Pause task execution."""
    
    async def resume_task(self, task_id: str) -> None:
        """Resume paused task."""
```

#### Task Storage Interface

```python
# bassi/core_v3/services/task_storage.py

class TaskStorage:
    """Storage for task metadata."""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.tasks_dir = base_path / "tasks"
        self.tasks_dir.mkdir(exist_ok=True)
    
    def save_task(self, task: Task) -> None:
        """Save task metadata to JSON file."""
        task_file = self.tasks_dir / f"{task.task_id}.json"
        task_file.write_text(json.dumps(task.to_dict(), indent=2))
    
    def load_task(self, task_id: str) -> Task:
        """Load task metadata from JSON file."""
        task_file = self.tasks_dir / f"{task_id}.json"
        if not task_file.exists():
            raise TaskNotFoundError(task_id)
        return Task.from_dict(json.loads(task_file.read_text()))
    
    def list_tasks(self) -> List[Task]:
        """List all tasks."""
        tasks = []
        for task_file in self.tasks_dir.glob("*.json"):
            tasks.append(Task.from_dict(json.loads(task_file.read_text())))
        return tasks
    
    def delete_task(self, task_id: str) -> None:
        """Delete task metadata (soft delete - move to archive)."""
        task_file = self.tasks_dir / f"{task_id}.json"
        if task_file.exists():
            archive_dir = self.tasks_dir / "archive"
            archive_dir.mkdir(exist_ok=True)
            task_file.rename(archive_dir / f"{task_id}.json")
```

#### launchd Manager Interface

```python
# bassi/core_v3/tasks/launchd_manager.py

class LaunchdManager:
    """Manage launchd jobs for scheduled tasks."""
    
    def __init__(self, plist_dir: Path = None):
        self.plist_dir = plist_dir or Path.home() / "Library" / "LaunchAgents"
        self.plist_dir.mkdir(parents=True, exist_ok=True)
    
    def create_plist(
        self,
        task_id: str,
        schedule: dict,
        wrapper_script_path: Path
    ) -> Path:
        """Generate launchd plist file."""
        # Generate plist XML based on schedule type
        # Save to ~/Library/LaunchAgents/com.bassi.task.{task_id}.plist
        # Return path to plist file
    
    def install_job(self, plist_path: Path) -> None:
        """Load launchd job."""
        subprocess.run(["launchctl", "load", str(plist_path)], check=True)
    
    def uninstall_job(self, plist_path: Path) -> None:
        """Unload launchd job."""
        subprocess.run(["launchctl", "unload", str(plist_path)], check=True)
    
    def job_exists(self, task_id: str) -> bool:
        """Check if launchd job exists."""
        plist_path = self.plist_dir / f"com.bassi.task.{task_id}.plist"
        return plist_path.exists()
```

#### Wrapper Script Generator

```python
# bassi/core_v3/tasks/wrapper_generator.py

class WrapperGenerator:
    """Generate wrapper scripts for launchd jobs."""
    
    def __init__(self, scripts_dir: Path, api_base_url: str = "http://localhost:8765"):
        self.scripts_dir = scripts_dir
        self.api_base_url = api_base_url
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_wrapper(
        self,
        task_id: str,
        prompt: str,
        session_id: Optional[str] = None
    ) -> Path:
        """Generate wrapper script that calls API."""
        script_path = self.scripts_dir / f"task_{task_id}.sh"
        
        script_content = f"""#!/bin/bash
# Auto-generated wrapper script for task {task_id}
# DO NOT EDIT - Regenerated when task is updated

set -e

TASK_ID="{task_id}"
PROMPT={shlex.quote(prompt)}
SESSION_ID={shlex.quote(session_id or "")}
API_URL="{self.api_base_url}/api/tasks/execute"

# Execute task via API
curl -X POST "$API_URL" \\
  -H "Content-Type: application/json" \\
  -d "{{\\"task_id\\": \\"$TASK_ID\\", \\"prompt\\": \\"$PROMPT\\", \\"session_id\\": \\"$SESSION_ID\\"}}" \\
  --fail --silent --show-error

exit $?
"""
        
        script_path.write_text(script_content)
        script_path.chmod(0o755)  # Make executable
        return script_path
```

---

## Part 3: Scripts

### 1. scripts/create_task.py

**Purpose**: Create a new scheduled task (used by skill)

**Usage**:
```python
# Called by skill when user requests task creation
from .claude.skills.task_scheduler.scripts.create_task import create_task

result = await create_task(
    name="weekly-metrics",
    description="Weekly metrics report",
    prompt="Generate weekly metrics",
    schedule={
        "type": "calendar_interval",
        "weekday": 1,
        "hour": 9,
        "minute": 0
    }
)
```

**Implementation**:
```python
# .claude/skills/task-scheduler/scripts/create_task.py

import asyncio
import httpx
from pathlib import Path

async def create_task(
    name: str,
    description: str,
    prompt: str,
    schedule: dict,
    session_id: str = None,
    api_url: str = "http://localhost:8765"
):
    """Create a scheduled task via API."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{api_url}/api/tasks/create",
            json={
                "name": name,
                "description": description,
                "prompt": prompt,
                "schedule": schedule,
                "session_id": session_id
            }
        )
        response.raise_for_status()
        return response.json()

if __name__ == "__main__":
    # CLI interface for testing
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: create_task.py <task_config.json>")
        sys.exit(1)
    
    config = json.loads(Path(sys.argv[1]).read_text())
    result = asyncio.run(create_task(**config))
    print(json.dumps(result, indent=2))
```

---

### 2. scripts/list_tasks.py

**Purpose**: List all scheduled tasks

**Usage**:
```python
from .claude.skills.task_scheduler.scripts.list_tasks import list_tasks

tasks = await list_tasks()
for task in tasks:
    print(f"{task['name']}: {task['next_run']}")
```

**Implementation**:
```python
# .claude/skills/task-scheduler/scripts/list_tasks.py

import asyncio
import httpx
from typing import List, Dict

async def list_tasks(
    status: str = None,
    api_url: str = "http://localhost:8765"
) -> List[Dict]:
    """List all scheduled tasks."""
    async with httpx.AsyncClient() as client:
        params = {}
        if status:
            params["status"] = status
        
        response = await client.get(
            f"{api_url}/api/tasks/list",
            params=params
        )
        response.raise_for_status()
        return response.json()["tasks"]

if __name__ == "__main__":
    tasks = asyncio.run(list_tasks())
    for task in tasks:
        print(f"{task['task_id']}: {task['name']} - Next: {task['next_run']}")
```

---

### 3. scripts/delete_task.py

**Purpose**: Delete a scheduled task

**Usage**:
```python
from .claude.skills.task_scheduler.scripts.delete_task import delete_task

await delete_task("uuid-123")
```

**Implementation**:
```python
# .claude/skills/task-scheduler/scripts/delete_task.py

import asyncio
import httpx

async def delete_task(
    task_id: str,
    api_url: str = "http://localhost:8765"
):
    """Delete a scheduled task."""
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{api_url}/api/tasks/{task_id}"
        )
        response.raise_for_status()
        return response.json()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: delete_task.py <task_id>")
        sys.exit(1)
    
    result = asyncio.run(delete_task(sys.argv[1]))
    print(f"Deleted task: {result['task_id']}")
```

---

### 4. scripts/test_task.py

**Purpose**: Test task execution without waiting for schedule

**Usage**:
```python
from .claude.skills.task_scheduler.scripts.test_task import test_task

result = await test_task("uuid-123")
print(f"Execution ID: {result['execution_id']}")
```

**Implementation**:
```python
# .claude/skills/task-scheduler/scripts/test_task.py

import asyncio
import httpx

async def test_task(
    task_id: str,
    api_url: str = "http://localhost:8765"
):
    """Test execute a task immediately."""
    # First get task details
    async with httpx.AsyncClient() as client:
        task_response = await client.get(f"{api_url}/api/tasks/{task_id}")
        task_response.raise_for_status()
        task = task_response.json()
    
    # Then execute it
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{api_url}/api/tasks/execute",
            json={
                "task_id": task_id,
                "prompt": task["prompt"],
                "session_id": task.get("session_id")
            }
        )
        response.raise_for_status()
        return response.json()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: test_task.py <task_id>")
        sys.exit(1)
    
    result = asyncio.run(test_task(sys.argv[1]))
    print(f"Execution completed: {result['execution_id']}")
    print(f"Result: {result['result_path']}")
```

---

### 5. scripts/wrapper_template.sh

**Purpose**: Template for launchd wrapper scripts

**Note**: This is a reference template. Actual wrappers are generated by `WrapperGenerator`.

```bash
#!/bin/bash
# Auto-generated wrapper script for task {TASK_ID}
# DO NOT EDIT - Regenerated when task is updated

set -e

TASK_ID="{TASK_ID}"
PROMPT="{PROMPT}"
SESSION_ID="{SESSION_ID}"
API_URL="http://localhost:8765/api/tasks/execute"

# Log execution start
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Task $TASK_ID execution started" >> /tmp/bassi-tasks.log

# Execute task via API
HTTP_CODE=$(curl -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"task_id\": \"$TASK_ID\", \"prompt\": \"$PROMPT\", \"session_id\": \"$SESSION_ID\"}" \
  --write-out "%{http_code}" \
  --silent \
  --show-error \
  --output /tmp/bassi-task-$TASK_ID-response.json)

# Check HTTP response code
if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Task $TASK_ID execution completed successfully" >> /tmp/bassi-tasks.log
    exit 0
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Task $TASK_ID execution failed (HTTP $HTTP_CODE)" >> /tmp/bassi-tasks.log
    cat /tmp/bassi-task-$TASK_ID-response.json >> /tmp/bassi-tasks.log
    exit 1
fi
```

---

## Part 4: Infrastructure

### Directory Structure

```
bassi/
├── tasks/                          # NEW: Task infrastructure
│   ├── metadata/                   # Task JSON files
│   │   ├── uuid-123.json
│   │   └── archive/                # Soft-deleted tasks
│   ├── scripts/                    # Wrapper scripts
│   │   └── task_uuid-123.sh
│   └── results/                    # Execution results
│       └── uuid-123/
│           ├── exec-uuid-456.json
│           └── exec-uuid-789.json
└── core_v3/
    ├── routes/
    │   └── task_routes.py          # NEW: API endpoints
    ├── services/
    │   ├── task_service.py         # NEW: Business logic
    │   └── task_storage.py         # NEW: Storage layer
    └── tasks/                      # NEW: Task utilities
        ├── launchd_manager.py      # launchd integration
        └── wrapper_generator.py    # Script generation

~/
└── Library/
    └── LaunchAgents/
        └── com.bassi.task.*.plist   # launchd job files
```

### Data Models

#### Task Model

```python
# bassi/core_v3/models/task.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum

class TaskStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    DELETED = "deleted"

class ScheduleType(str, Enum):
    CALENDAR_INTERVAL = "calendar_interval"  # Weekly, daily, etc.
    INTERVAL = "interval"                    # Every N seconds
    ONCE = "once"                            # One-time execution

@dataclass
class Schedule:
    type: ScheduleType
    weekday: Optional[int] = None      # 1=Monday, 7=Sunday
    hour: Optional[int] = None
    minute: Optional[int] = None
    seconds: Optional[int] = None       # For interval type
    datetime: Optional[datetime] = None  # For once type

@dataclass
class TaskOptions:
    store_results: bool = True
    send_notifications: bool = False
    timeout_seconds: int = 300

@dataclass
class Task:
    task_id: str
    name: str
    description: str
    prompt: str
    schedule: Schedule
    status: TaskStatus
    session_id: Optional[str] = None
    options: TaskOptions = None
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    execution_count: int = 0
    created_at: datetime = None
    launchd_label: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.launchd_label is None:
            self.launchd_label = f"com.bassi.task.{self.task_id}"
        if self.options is None:
            self.options = TaskOptions()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "prompt": self.prompt,
            "schedule": {
                "type": self.schedule.type.value,
                "weekday": self.schedule.weekday,
                "hour": self.schedule.hour,
                "minute": self.schedule.minute,
                "seconds": self.schedule.seconds,
                "datetime": self.schedule.datetime.isoformat() if self.schedule.datetime else None
            },
            "status": self.status.value,
            "session_id": self.session_id,
            "options": {
                "store_results": self.options.store_results,
                "send_notifications": self.options.send_notifications,
                "timeout_seconds": self.options.timeout_seconds
            },
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "execution_count": self.execution_count,
            "created_at": self.created_at.isoformat(),
            "launchd_label": self.launchd_label
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Task":
        """Create Task from dictionary."""
        schedule = Schedule(
            type=ScheduleType(data["schedule"]["type"]),
            weekday=data["schedule"].get("weekday"),
            hour=data["schedule"].get("hour"),
            minute=data["schedule"].get("minute"),
            seconds=data["schedule"].get("seconds"),
            datetime=datetime.fromisoformat(data["schedule"]["datetime"]) if data["schedule"].get("datetime") else None
        )
        
        options = TaskOptions(
            store_results=data.get("options", {}).get("store_results", True),
            send_notifications=data.get("options", {}).get("send_notifications", False),
            timeout_seconds=data.get("options", {}).get("timeout_seconds", 300)
        )
        
        return cls(
            task_id=data["task_id"],
            name=data["name"],
            description=data["description"],
            prompt=data["prompt"],
            schedule=schedule,
            status=TaskStatus(data["status"]),
            session_id=data.get("session_id"),
            options=options,
            next_run=datetime.fromisoformat(data["next_run"]) if data.get("next_run") else None,
            last_run=datetime.fromisoformat(data["last_run"]) if data.get("last_run") else None,
            execution_count=data.get("execution_count", 0),
            created_at=datetime.fromisoformat(data["created_at"]),
            launchd_label=data.get("launchd_label")
        )
```

#### TaskExecution Model

```python
# bassi/core_v3/models/task_execution.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict
from enum import Enum

class ExecutionStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"

@dataclass
class TaskExecution:
    execution_id: str
    task_id: str
    status: ExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    result_path: Optional[str] = None
    error_message: Optional[str] = None
    usage: Optional[Dict] = None  # Token usage, cost, etc.
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "execution_id": self.execution_id,
            "task_id": self.task_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result_path": self.result_path,
            "error_message": self.error_message,
            "usage": self.usage
        }
```

### Agent Integration

#### Background Query Execution

**Challenge**: Agent queries are designed for WebSocket streaming, but scheduled tasks need HTTP responses.

**Solution**: Execute query in background, stream to file, return execution metadata.

```python
# bassi/core_v3/services/task_service.py (excerpt)

async def execute_task(
    self,
    task_id: str,
    prompt: str,
    session_id: Optional[str] = None
) -> TaskExecution:
    """Execute a scheduled task."""
    execution_id = str(uuid.uuid4())
    execution = TaskExecution(
        execution_id=execution_id,
        task_id=task_id,
        status=ExecutionStatus.RUNNING,
        started_at=datetime.now()
    )
    
    # Create result directory
    result_dir = self.base_path / "tasks" / "results" / task_id
    result_dir.mkdir(parents=True, exist_ok=True)
    result_file = result_dir / f"{execution_id}.json"
    
    try:
        # Get or create agent session
        agent_session = await self._get_or_create_session(session_id)
        
        # Execute query and stream to file
        result_data = []
        async for message in agent_session.query(prompt, session_id=session_id or "default"):
            # Convert message to dict and accumulate
            result_data.append(self._message_to_dict(message))
            
            # Periodically flush to file (every 10 messages)
            if len(result_data) >= 10:
                self._append_to_file(result_file, result_data)
                result_data = []
        
        # Final flush
        if result_data:
            self._append_to_file(result_file, result_data)
        
        # Extract usage from final message
        usage = self._extract_usage(result_data)
        
        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = datetime.now()
        execution.result_path = str(result_file)
        execution.usage = usage
        
    except asyncio.TimeoutError:
        execution.status = ExecutionStatus.TIMEOUT
        execution.completed_at = datetime.now()
        execution.error_message = "Task execution timed out"
    
    except Exception as e:
        execution.status = ExecutionStatus.FAILED
        execution.completed_at = datetime.now()
        execution.error_message = str(e)
    
    # Save execution metadata
    execution_file = result_dir / f"{execution_id}_meta.json"
    execution_file.write_text(json.dumps(execution.to_dict(), indent=2))
    
    return execution
```

### Configuration

#### API Base URL Configuration

**Environment Variable**: `BASSI_API_URL` (default: `http://localhost:8765`)

**Usage in wrapper scripts**:
```bash
API_URL="${BASSI_API_URL:-http://localhost:8765}/api/tasks/execute"
```

#### Task Storage Path Configuration

**Environment Variable**: `BASSI_TASKS_DIR` (default: `tasks/` relative to workspace)

**Usage**:
```python
tasks_dir = Path(os.getenv("BASSI_TASKS_DIR", "tasks"))
```

---

## Part 5: Skill Workflow

### User Request Examples

#### Example 1: Weekly Report

**User**: "Schedule a task to generate weekly metrics every Monday at 9 AM"

**Skill Process**:
1. Parse request → Extract schedule (Monday 9 AM), prompt (generate weekly metrics)
2. Call `create_task.py` script
3. Script calls `POST /api/tasks/create`
4. API creates task, generates launchd plist, installs job
5. Return confirmation to user

#### Example 2: Daily Backup

**User**: "Run database backup every day at 2 AM"

**Skill Process**:
1. Parse request → Extract schedule (daily 2 AM), prompt (backup database)
2. Create task with `schedule.type = "calendar_interval"`, `hour = 2`, `minute = 0`
3. Install launchd job
4. Confirm creation

#### Example 3: One-Time Task

**User**: "Schedule a reminder to review PRs on December 25th at 10 AM"

**Skill Process**:
1. Parse request → Extract schedule (once, Dec 25 10 AM), prompt (review PRs)
2. Create task with `schedule.type = "once"`, `datetime = "2025-12-25T10:00:00"`
3. Install launchd job
4. Note: Job should auto-delete after execution

#### Example 4: List Tasks

**User**: "Show me all scheduled tasks"

**Skill Process**:
1. Call `list_tasks.py` script
2. Script calls `GET /api/tasks/list`
3. Format and display results

#### Example 5: Delete Task

**User**: "Delete the weekly metrics task"

**Skill Process**:
1. Find task by name → Get task_id
2. Call `delete_task.py` script with task_id
3. Script calls `DELETE /api/tasks/{task_id}`
4. API unloads launchd job, archives metadata
5. Confirm deletion

---

## Part 6: Security Considerations

### API Authentication

**Current State**: No authentication on API endpoints

**Recommendation**: Add API key authentication for `/api/tasks/*` endpoints

**Implementation**:
```python
# bassi/core_v3/middleware/auth.py

API_KEY_HEADER = "X-Bassi-API-Key"

async def verify_api_key(request: Request, call_next):
    """Verify API key for task endpoints."""
    if request.url.path.startswith("/api/tasks/"):
        api_key = request.headers.get(API_KEY_HEADER)
        expected_key = os.getenv("BASSI_API_KEY")
        
        if not expected_key or api_key != expected_key:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid API key"}
            )
    
    return await call_next(request)
```

**Wrapper Script Update**:
```bash
API_KEY="${BASSI_API_KEY:-}"
curl -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "X-Bassi-API-Key: $API_KEY" \
  -d "{...}"
```

### File Permissions

- Wrapper scripts: `755` (executable by owner, readable by all)
- Task metadata: `600` (readable/writable by owner only)
- Result files: `644` (readable by owner, readable by group)

### launchd Job Isolation

- Each task runs in its own launchd job
- Jobs run with user's permissions (not root)
- Wrapper scripts use `set -e` for error handling

---

## Part 7: Testing Strategy

### Unit Tests

1. **TaskService Tests**:
   - `test_create_task()`
   - `test_execute_task()`
   - `test_list_tasks()`
   - `test_delete_task()`

2. **TaskStorage Tests**:
   - `test_save_load_task()`
   - `test_list_tasks()`
   - `test_delete_task()`

3. **LaunchdManager Tests**:
   - `test_create_plist()`
   - `test_install_uninstall_job()`

4. **WrapperGenerator Tests**:
   - `test_generate_wrapper()`

### Integration Tests

1. **API Endpoint Tests**:
   - `test_create_task_endpoint()`
   - `test_execute_task_endpoint()`
   - `test_list_tasks_endpoint()`

2. **End-to-End Tests**:
   - `test_full_task_lifecycle()`:
     1. Create task via API
     2. Verify launchd job installed
     3. Manually trigger wrapper script
     4. Verify execution result
     5. Delete task
     6. Verify launchd job removed

### Manual Testing Checklist

- [ ] Create weekly task → Verify plist created → Verify job loaded
- [ ] List tasks → Verify all tasks shown
- [ ] Execute task manually → Verify result file created
- [ ] Wait for scheduled time → Verify task executes automatically
- [ ] Delete task → Verify job unloaded → Verify plist removed
- [ ] Test with API key authentication
- [ ] Test error handling (API server down, invalid task_id, etc.)

---

## Part 8: Implementation Phases

### Phase 1: Core Infrastructure (Week 1)

**Goal**: Basic API endpoints and storage

**Tasks**:
1. Create `Task` and `TaskExecution` models
2. Implement `TaskStorage` service
3. Implement `TaskService` (create, list, get, delete)
4. Create API routes (`task_routes.py`)
5. Wire routes into `web_server_v3.py`
6. Write unit tests

**Deliverables**:
- Task metadata can be created and stored
- API endpoints respond correctly
- Basic CRUD operations work

---

### Phase 2: launchd Integration (Week 2)

**Goal**: Generate and manage launchd jobs

**Tasks**:
1. Implement `LaunchdManager`
2. Implement `WrapperGenerator`
3. Integrate with `TaskService.create_task()`
4. Test launchd job creation and installation
5. Write integration tests

**Deliverables**:
- Tasks create launchd plist files
- Jobs can be installed/uninstalled
- Wrapper scripts call API correctly

---

### Phase 3: Agent Execution (Week 3)

**Goal**: Execute agent queries via API

**Tasks**:
1. Implement `TaskService.execute_task()`
2. Integrate with `BassiAgentSession`
3. Implement result streaming to file
4. Handle timeouts and errors
5. Test execution flow

**Deliverables**:
- Tasks can execute agent queries
- Results are stored correctly
- Error handling works

---

### Phase 4: Skill Implementation (Week 4)

**Goal**: Create the task-scheduler skill

**Tasks**:
1. Create skill directory structure
2. Write `SKILL.md` with workflows
3. Implement skill scripts (`create_task.py`, `list_tasks.py`, etc.)
4. Write reference documentation
5. Test skill with real user requests

**Deliverables**:
- Skill can be invoked
- User requests create tasks correctly
- Skill provides helpful guidance

---

### Phase 5: Polish & Documentation (Week 5)

**Goal**: Production-ready implementation

**Tasks**:
1. Add API authentication
2. Improve error messages
3. Add logging
4. Write user documentation
5. Performance testing
6. Security review

**Deliverables**:
- Secure, documented, production-ready system
- User guide available
- All tests passing

---

## Part 9: Open Questions & Decisions Needed

### 1. API Authentication

**Question**: Should we require API keys for task endpoints?

**Options**:
- A) Require API key (more secure, but requires key management)
- B) Allow localhost-only access (simpler, but less secure)
- C) No authentication (simplest, but insecure)

**Recommendation**: Option A with environment variable `BASSI_API_KEY`

---

### 2. Session Management

**Question**: How should scheduled tasks handle sessions?

**Options**:
- A) Each task uses its own session (isolated, but more sessions)
- B) All tasks share a default session (simpler, but context mixing)
- C) User specifies session_id per task (flexible, but complex)

**Recommendation**: Option C (user specifies, default to new session)

---

### 3. Result Storage Format

**Question**: How should execution results be stored?

**Options**:
- A) JSON with full message history
- B) Plain text summary only
- C) Both JSON and text

**Recommendation**: Option C (JSON for programmatic access, text for readability)

---

### 4. Error Notifications

**Question**: How should task failures be handled?

**Options**:
- A) Log to file only
- B) Send email notification
- C) Webhook callback
- D) User-configurable

**Recommendation**: Option A for MVP, Option D for future enhancement

---

### 5. One-Time Tasks

**Question**: Should one-time tasks auto-delete after execution?

**Options**:
- A) Auto-delete (cleaner, but lose history)
- B) Keep but mark as completed (preserves history)
- C) User-configurable

**Recommendation**: Option B (keep history, mark as completed)

---

## Part 10: Future Enhancements

### Short-Term (Post-MVP)

1. **Task Templates**: Pre-defined task templates (daily backup, weekly report, etc.)
2. **Task Dependencies**: Chain tasks (Task B runs after Task A completes)
3. **Conditional Execution**: Run task only if condition is met
4. **Result Notifications**: Email/webhook on completion
5. **Task History UI**: Web interface to view task execution history

### Medium-Term

1. **Cross-Platform Support**: Linux (systemd) and Windows (Task Scheduler)
2. **Task Monitoring**: Real-time status dashboard
3. **Retry Logic**: Automatic retry on failure
4. **Rate Limiting**: Prevent too many concurrent executions
5. **Task Variables**: Parameterized prompts (e.g., `{date}`, `{weekday}`)

### Long-Term

1. **Distributed Execution**: Run tasks on multiple machines
2. **Task Marketplace**: Share task definitions
3. **Visual Task Builder**: GUI for creating tasks
4. **Task Analytics**: Usage statistics and insights
5. **Integration with External Schedulers**: Cron, Airflow, etc.

---

## Summary

This plan outlines a comprehensive task-scheduler skill for macOS that enables automated agent queries via API. The implementation includes:

1. **Skill Package**: Modular skill with scripts and documentation
2. **API Layer**: 7 REST endpoints for task management
3. **Infrastructure**: Storage, launchd integration, wrapper generation
4. **Agent Integration**: Background query execution with result storage
5. **Security**: API key authentication, file permissions
6. **Testing**: Unit, integration, and end-to-end tests

The system is designed to be:
- **Secure**: API authentication, proper file permissions
- **Reliable**: Error handling, logging, retry logic
- **Extensible**: Easy to add new schedule types, features
- **User-Friendly**: Clear skill workflows, helpful error messages

**Estimated Implementation Time**: 5 weeks (1 developer, full-time)

**Next Steps**:
1. Review and approve this plan
2. Set up development environment
3. Begin Phase 1 implementation
4. Iterate based on feedback

---

**Document Status**: ✅ Complete - Ready for Review

