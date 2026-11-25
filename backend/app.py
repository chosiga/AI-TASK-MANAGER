"""Local Flask API and static-file server for Taskflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory
from ollama import RequestError, ResponseError, list as ollama_list

from backend import assistant as task_assistant
from backend import task_manager


ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/tasks")
def tasks_page():
    return send_from_directory(FRONTEND_DIR, "tasks.html")


@app.get("/assistant")
def assistant_page():
    return send_from_directory(FRONTEND_DIR, "assistant.html")


@app.get("/<path:asset_path>")
def frontend_asset(asset_path: str):
    if asset_path.startswith("api/"):
        return jsonify(error="Not found."), 404
    return send_from_directory(FRONTEND_DIR, asset_path)


def _json_body() -> dict[str, Any]:
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object.")
    return body


def _visible_task(task: task_manager.Task) -> dict[str, Any]:
    return {**task, "priority": task.get("priority", "medium")}


@app.get("/api/health")
def health():
    try:
        models = ollama_list().models
    except (RequestError, ResponseError, ConnectionError) as error:
        return jsonify(
            status="error",
            ollama="unavailable",
            model=task_assistant.MODEL,
            model_installed=False,
            error=f"Could not reach local Ollama: {error}",
        ), 503

    model_installed = any(model.model == task_assistant.MODEL for model in models)
    if not model_installed:
        return jsonify(
            status="error",
            ollama="running",
            model=task_assistant.MODEL,
            model_installed=False,
            error=f"Model {task_assistant.MODEL} is not installed.",
        ), 503
    return jsonify(
        status="ok",
        ollama="running",
        model=task_assistant.MODEL,
        model_installed=True,
    )


@app.get("/api/tasks")
def get_tasks():
    status = request.args.get("status", "all").lower()
    priority = request.args.get("priority", "all").lower()
    query = request.args.get("q", "").strip().casefold()
    if status not in {"all", "pending", "completed"}:
        return jsonify(error="status must be all, pending, or completed."), 400
    if priority not in {"all", *task_manager.PRIORITIES}:
        return jsonify(error="priority must be all, low, medium, or high."), 400
    try:
        tasks = [_visible_task(task) for task in task_manager.load_tasks()]
    except json.JSONDecodeError as error:
        return jsonify(error=f"Could not read the task file: {error}"), 500
    except ValueError as error:
        return jsonify(error=f"Invalid task data: {error}"), 500
    if status != "all":
        is_completed = status == "completed"
        tasks = [task for task in tasks if task["completed"] is is_completed]
    if priority != "all":
        tasks = [task for task in tasks if task["priority"] == priority]
    if query:
        tasks = [task for task in tasks if query in task["task"].casefold()]
    return jsonify(tasks=tasks)


@app.post("/api/tasks")
def create_task():
    try:
        body = _json_body()
        allowed = {
            "task_name",
            "due_date",
            "schedule_date",
            "start_time",
            "end_time",
            "priority",
        }
        if set(body) - allowed:
            return jsonify(error="Unsupported task fields were provided."), 400
        if not isinstance(body.get("task_name"), str):
            return jsonify(error="task_name must be a string."), 400
        for field in allowed - {"task_name"}:
            if field in body and not isinstance(body[field], str):
                return jsonify(error=f"{field} must be a string."), 400
        message = task_manager.add_task(**body)
        tasks = task_manager.load_tasks()
        created = _visible_task(tasks[-1])
        return jsonify(task=created, message=message), 201
    except json.JSONDecodeError as error:
        return jsonify(error=f"Could not read the task file: {error}"), 500
    except ValueError as error:
        return jsonify(error=str(error)), 400


@app.put("/api/tasks/<int:task_id>")
def edit_task(task_id: int):
    try:
        body = _json_body()
        allowed = {
            "task_name",
            "due_date",
            "schedule_date",
            "start_time",
            "end_time",
            "priority",
        }
        if not body or set(body) - allowed:
            return jsonify(error="Provide supported task fields to update."), 400
        if any(not isinstance(value, str) for value in body.values()):
            return jsonify(error="Task update fields must be strings."), 400
        message = task_manager.update_task(task_id, **body)
        if message.startswith("Task with ID"):
            return jsonify(error=message), 404
        task = next(item for item in task_manager.load_tasks() if item["id"] == task_id)
        return jsonify(task=_visible_task(task), message=message)
    except json.JSONDecodeError as error:
        return jsonify(error=f"Could not read the task file: {error}"), 500
    except ValueError as error:
        return jsonify(error=str(error)), 400


@app.patch("/api/tasks/<int:task_id>/complete")
def finish_task(task_id: int):
    try:
        message = task_manager.complete_task(task_id)
    except json.JSONDecodeError as error:
        return jsonify(error=f"Could not read the task file: {error}"), 500
    except ValueError as error:
        return jsonify(error=f"Invalid task data: {error}"), 500
    if message.startswith("Task with ID"):
        return jsonify(error=message), 404
    task = next(item for item in task_manager.load_tasks() if item["id"] == task_id)
    return jsonify(task=_visible_task(task), message=message)


@app.patch("/api/tasks/<int:task_id>/reopen")
def reopen_task(task_id: int):
    try:
        message = task_manager.reopen_task(task_id)
    except json.JSONDecodeError as error:
        return jsonify(error=f"Could not read the task file: {error}"), 500
    except ValueError as error:
        return jsonify(error=f"Invalid task data: {error}"), 500
    if message.startswith("Task with ID"):
        return jsonify(error=message), 404
    task = next(item for item in task_manager.load_tasks() if item["id"] == task_id)
    return jsonify(task=_visible_task(task), message=message)


@app.delete("/api/tasks/<int:task_id>")
def remove_task(task_id: int):
    try:
        body = _json_body()
    except (ValueError, json.JSONDecodeError):
        return jsonify(error="Explicit confirmation is required to delete a task."), 428
    if body.get("confirm") is not True:
        return jsonify(error="Explicit confirmation is required to delete a task."), 428
    try:
        message = task_manager.delete_task(task_id)
    except json.JSONDecodeError as error:
        return jsonify(error=f"Could not read the task file: {error}"), 500
    except ValueError as error:
        return jsonify(error=f"Invalid task data: {error}"), 500
    if message.startswith("Task with ID"):
        return jsonify(error=message), 404
    return jsonify(message=message)


@app.post("/api/chat")
@app.post("/api/assistant")
def assistant_message():
    try:
        body = _json_body()
        if "messages" in body:
            messages = body["messages"]
            if not isinstance(messages, list) or not messages:
                return jsonify(error="messages must be a non-empty list."), 400
            normalized_messages: list[dict[str, str]] = []
            for item in messages:
                if (
                    not isinstance(item, dict)
                    or set(item) != {"role", "content"}
                    or not isinstance(item["role"], str)
                    or item["role"] not in {"user", "assistant"}
                    or not isinstance(item["content"], str)
                    or not item["content"].strip()
                ):
                    return jsonify(
                        error="Each message must have a user or assistant role and non-empty content."
                    ), 400
                normalized_messages.append(
                    {"role": item["role"], "content": item["content"].strip()}
                )
            if normalized_messages[-1]["role"] != "user":
                return jsonify(error="The latest message must be from the user."), 400
            message = normalized_messages[-1]["content"]
            conversation_history = normalized_messages[:-1][-20:]
        else:
            message = body.get("message")
            if not isinstance(message, str) or not message.strip():
                return jsonify(error="message must be a non-empty string."), 400
            message = message.strip()
            conversation_history = []

        pending_deletions: list[int] = []

        def request_delete_confirmation(task_id: int) -> bool:
            pending_deletions.append(task_id)
            return False

        reply = task_assistant.handle_request(
            message,
            confirm_delete=request_delete_confirmation,
            conversation_history=conversation_history,
        )
        tasks_by_id = {task["id"]: task for task in task_manager.load_tasks()}
        confirmations = [
            {"task_id": task_id, "task": tasks_by_id[task_id]["task"]}
            for task_id in dict.fromkeys(pending_deletions)
            if task_id in tasks_by_id
        ]
        if confirmations:
            reply = "\n".join(
                f"Please confirm deleting task {item['task_id']}: {item['task']}."
                for item in confirmations
            )
        return jsonify(reply=reply, confirmations=confirmations)
    except (RequestError, ResponseError, ConnectionError) as error:
        return jsonify(
            error=f"Could not reach the local Ollama model ({task_assistant.MODEL}): {error}"
        ), 503
    except task_assistant.ToolCallError as error:
        return jsonify(error=str(error)), 422
    except json.JSONDecodeError as error:
        return jsonify(error=f"Could not read the task file: {error}"), 500
    except ValueError as error:
        return jsonify(error=str(error)), 400


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
