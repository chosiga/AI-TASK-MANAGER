"""Web-facing access to the shared task operations."""

from task_manager import (
    PRIORITIES,
    TASK_FILE,
    Task,
    add_task,
    complete_task,
    delete_task,
    load_tasks,
    reopen_task,
    save_tasks,
    update_task,
    view_tasks,
)

__all__ = [
    "PRIORITIES",
    "TASK_FILE",
    "Task",
    "add_task",
    "complete_task",
    "delete_task",
    "load_tasks",
    "reopen_task",
    "save_tasks",
    "update_task",
    "view_tasks",
]
