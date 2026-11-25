import json
from datetime import date, datetime
from pathlib import Path
from typing import Literal, NotRequired, TypedDict


TASK_FILE = Path(__file__).with_name("tasks.json")


class Task(TypedDict):
    id: int
    task: str
    completed: bool
    due_date: NotRequired[str | None]
    schedule_date: NotRequired[str | None]
    start_time: NotRequired[str | None]
    end_time: NotRequired[str | None]
    priority: NotRequired[Literal["low", "medium", "high"]]


PRIORITIES = {"low", "medium", "high"}


def _validate_optional_date(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must use YYYY-MM-DD format.")
    value = value.strip()
    if not value:
        return None
    try:
        parsed_date = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field_name} must use YYYY-MM-DD format.") from error
    if parsed_date.isoformat() != value:
        raise ValueError(f"{field_name} must use YYYY-MM-DD format.")
    return value


def _validate_optional_time(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must use 24-hour HH:MM format.")
    value = value.strip()
    if not value:
        return None
    try:
        parsed_time = datetime.strptime(value, "%H:%M")
    except ValueError as error:
        raise ValueError(f"{field_name} must use 24-hour HH:MM format.") from error
    if parsed_time.strftime("%H:%M") != value:
        raise ValueError(f"{field_name} must use 24-hour HH:MM format.")
    return value


def load_tasks() -> list[Task]:
    if not TASK_FILE.exists():
        return []

    content = TASK_FILE.read_text(encoding="utf-8").strip()
    if not content:
        return []

    tasks = json.loads(content)
    if not isinstance(tasks, list):
        raise ValueError("The task file must contain a JSON list.")

    for task in tasks:
        if (
            not isinstance(task, dict)
            or type(task.get("id")) is not int
            or not isinstance(task.get("task"), str)
            or not isinstance(task.get("completed"), bool)
        ):
            raise ValueError("A task entry has an invalid format.")
        for field_name in ("due_date", "schedule_date"):
            if field_name in task:
                task[field_name] = _validate_optional_date(task[field_name], field_name)
        for field_name in ("start_time", "end_time"):
            if field_name in task:
                task[field_name] = _validate_optional_time(task[field_name], field_name)
        if "priority" in task and (
            not isinstance(task["priority"], str) or task["priority"] not in PRIORITIES
        ):
            raise ValueError("priority must be low, medium, or high.")
        start_time = task.get("start_time")
        end_time = task.get("end_time")
        if bool(start_time) != bool(end_time):
            raise ValueError("Both start_time and end_time are required for a time range.")
        if start_time and end_time and start_time >= end_time:
            raise ValueError("end_time must be later than start_time.")

    return tasks


def save_tasks(tasks: list[Task]) -> None:
    TASK_FILE.write_text(
        json.dumps(tasks, indent=4) + "\n",
        encoding="utf-8",
    )


def add_task(
    task_name: str,
    due_date: str | None = None,
    schedule_date: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    priority: str = "medium",
) -> str:
    if not isinstance(task_name, str):
        raise ValueError("task_name must be a non-empty string.")
    task_name = task_name.strip()
    if not task_name:
        return "Please provide a task description."

    due_date = _validate_optional_date(due_date, "due_date")
    schedule_date = _validate_optional_date(schedule_date, "schedule_date")
    start_time = _validate_optional_time(start_time, "start_time")
    end_time = _validate_optional_time(end_time, "end_time")
    priority = _validate_priority(priority)
    if bool(start_time) != bool(end_time):
        raise ValueError("Both start_time and end_time are required for a time range.")
    if start_time and end_time and start_time >= end_time:
        raise ValueError("end_time must be later than start_time.")

    tasks = load_tasks()
    next_id = max((task["id"] for task in tasks), default=0) + 1
    new_task: Task = {
        "id": next_id,
        "task": task_name,
        "completed": False,
        "priority": priority,
    }
    for field_name, value in (
        ("due_date", due_date),
        ("schedule_date", schedule_date),
        ("start_time", start_time),
        ("end_time", end_time),
    ):
        if value is not None:
            new_task[field_name] = value
    tasks.append(new_task)
    save_tasks(tasks)
    details = []
    if schedule_date:
        details.append(f"scheduled {schedule_date}")
    if start_time and end_time:
        details.append(f"{start_time}-{end_time}")
    if due_date:
        details.append(f"due {due_date}")
    details_text = f" ({', '.join(details)})" if details else ""
    return f"Added task {next_id}: {task_name}{details_text}"


def _validate_priority(value: object) -> str:
    if not isinstance(value, str) or value not in PRIORITIES:
        raise ValueError("priority must be low, medium, or high.")
    return value


def update_task(task_id: int, **updates: object) -> str:
    allowed_fields = {
        "task_name",
        "due_date",
        "schedule_date",
        "start_time",
        "end_time",
        "priority",
    }
    if not updates or set(updates) - allowed_fields:
        raise ValueError("Provide supported task fields to update.")

    normalized: dict[str, object] = {}
    if "task_name" in updates:
        task_name = updates["task_name"]
        if not isinstance(task_name, str) or not task_name.strip():
            raise ValueError("task_name must be a non-empty string.")
        normalized["task"] = task_name.strip()
    for field_name in ("due_date", "schedule_date"):
        if field_name in updates:
            normalized[field_name] = _validate_optional_date(
                updates[field_name], field_name
            )
    for field_name in ("start_time", "end_time"):
        if field_name in updates:
            normalized[field_name] = _validate_optional_time(
                updates[field_name], field_name
            )
    if "priority" in updates:
        normalized["priority"] = _validate_priority(updates["priority"])

    tasks = load_tasks()
    for task in tasks:
        if task["id"] != task_id:
            continue
        updated = {**task, **normalized}
        start_time = updated.get("start_time")
        end_time = updated.get("end_time")
        if bool(start_time) != bool(end_time):
            raise ValueError("Both start_time and end_time are required for a time range.")
        if start_time and end_time and start_time >= end_time:
            raise ValueError("end_time must be later than start_time.")
        task.update(normalized)
        save_tasks(tasks)
        return f"Updated task {task_id}: {task['task']}"
    return f"Task with ID {task_id} was not found."


def view_tasks() -> str:
    tasks = load_tasks()
    if not tasks:
        return "Your task list is empty."

    output = ["===== MY TASK LIST ====="]
    for task in tasks:
        status = "Completed" if task["completed"] else "Pending"
        schedule_date = task.get("schedule_date")
        start_time = task.get("start_time")
        end_time = task.get("end_time")
        time_range = f"{start_time}-{end_time}" if start_time and end_time else ""
        schedule_parts = [value for value in (schedule_date, time_range) if value]
        schedule_text = f' | Scheduled: {" ".join(schedule_parts)}' if schedule_parts else ""
        due_text = f' | Due: {task["due_date"]}' if task.get("due_date") else ""
        priority = task.get("priority", "medium")
        output.append(
            f'ID: {task["id"]} | {status} | {priority.title()} priority | '
            f'{task["task"]}{schedule_text}{due_text}'
        )
    return "\n".join(output)


def complete_task(task_id: int) -> str:
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            if task["completed"]:
                return f"Task '{task['task']}' is already completed."
            task["completed"] = True
            save_tasks(tasks)
            return f"Task '{task['task']}' marked as completed!"
    return f"Task with ID {task_id} was not found."


def reopen_task(task_id: int) -> str:
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            if not task["completed"]:
                return f"Task '{task['task']}' is already in progress."
            task["completed"] = False
            save_tasks(tasks)
            return f"Task '{task['task']}' moved back to in progress."
    return f"Task with ID {task_id} was not found."


def delete_task(task_id: int) -> str:
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            tasks.remove(task)
            save_tasks(tasks)
            return f"Task '{task['task']}' deleted successfully!"
    return f"Task with ID {task_id} was not found."
