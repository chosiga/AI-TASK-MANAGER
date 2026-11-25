import argparse
import json
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, Callable

from ollama import RequestError, ResponseError, chat

import task_manager


MODEL = "llama3.2:3b"
MAX_TOOL_ROUNDS = 5

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": "Create a task when the user asks to add or remember something.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_name": {
                        "type": "string",
                        "description": "A concise description of the task to add.",
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Optional task deadline in YYYY-MM-DD format.",
                    },
                    "schedule_date": {
                        "type": "string",
                        "description": "Optional date to work on the task, in YYYY-MM-DD format.",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Optional scheduled start time in 24-hour HH:MM format.",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "Optional scheduled end time in 24-hour HH:MM format.",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Task priority; defaults to medium.",
                    },
                },
                "required": ["task_name"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "view_tasks",
            "description": "Show the user's tasks or find a task by its description.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update an existing task's description, priority, or dates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "task_name": {"type": "string"},
                    "due_date": {"type": "string"},
                    "schedule_date": {"type": "string"},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Mark a task as completed using its numeric task ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "The ID of an existing task.",
                    }
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Delete a task using its numeric task ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "The ID of an existing task.",
                    }
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
    },
]


class ToolCallError(ValueError):
    pass


def _is_task_listing_request(request: str) -> bool:
    text = request.casefold()
    asks_to_list = any(word in text for word in ("show", "list", "view", "display"))
    asks_about_today = "today" in text and "task" in text
    return "task" in text and (asks_to_list or asks_about_today)


def _format_task_listing(request: str) -> str:
    text = request.casefold()
    tasks = task_manager.load_tasks()
    today_request = "today" in text
    if today_request:
        today = date.today().isoformat()
        tasks = [
            task
            for task in tasks
            if not task["completed"]
            and (task.get("schedule_date") == today or task.get("due_date") == today)
        ]
        heading = "Tasks to complete today:"
        empty_message = "There are no pending tasks scheduled or due today."
    else:
        if any(word in text for word in ("pending", "unfinished", "in progress")):
            tasks = [task for task in tasks if not task["completed"]]
            heading = "Pending tasks:"
            empty_message = "There are no pending tasks."
        elif any(word in text for word in ("completed", "finished", "done")):
            tasks = [task for task in tasks if task["completed"]]
            heading = "Completed tasks:"
            empty_message = "There are no completed tasks."
        else:
            heading = "Your tasks:"
            empty_message = "Your task list is empty."

    if not tasks:
        return empty_message
    lines = [heading]
    for task in tasks:
        status = "Completed" if task["completed"] else "Pending"
        priority = task.get("priority", "medium").title()
        details = [f'ID {task["id"]}', task["task"], f"{status} · {priority} priority"]
        if task.get("due_date"):
            details.append(f'Due {task["due_date"]}')
        if task.get("schedule_date"):
            details.append(f'Scheduled {task["schedule_date"]}')
        lines.append(" · ".join(details))
    return "\n".join(lines)


def execute_tool(
    tool_name: str,
    arguments: Mapping[str, Any],
    confirm_delete: Callable[[int], bool] | None = None,
) -> str:
    if tool_name == "add_task":
        if (
            set(arguments)
            - {"task_name", "due_date", "schedule_date", "start_time", "end_time", "priority"}
            or "task_name" not in arguments
            or not isinstance(arguments.get("task_name"), str)
        ):
            raise ToolCallError("add_task requires a string task_name and supported schedule fields.")
        schedule_fields = ("due_date", "schedule_date", "start_time", "end_time", "priority")
        for field_name in schedule_fields:
            value = arguments.get(field_name)
            if value is not None and not isinstance(value, str):
                raise ToolCallError(f"add_task {field_name} must be a string.")
        return task_manager.add_task(
            arguments["task_name"],
            due_date=arguments.get("due_date"),
            schedule_date=arguments.get("schedule_date"),
            start_time=arguments.get("start_time"),
            end_time=arguments.get("end_time"),
            priority=arguments.get("priority", "medium"),
        )

    if tool_name in {"list_tasks", "view_tasks"}:
        if arguments:
            raise ToolCallError(f"{tool_name} does not accept arguments.")
        return task_manager.view_tasks()

    if tool_name == "update_task":
        task_id = arguments.get("task_id")
        if type(task_id) is not int or set(arguments) - {
            "task_id",
            "task_name",
            "due_date",
            "schedule_date",
            "start_time",
            "end_time",
            "priority",
        }:
            raise ToolCallError("update_task requires an integer task_id and supported fields.")
        updates = {key: value for key, value in arguments.items() if key != "task_id"}
        if not updates:
            raise ToolCallError("update_task requires at least one field to update.")
        if any(not isinstance(value, str) for value in updates.values()):
            raise ToolCallError("update_task fields must be strings.")
        return task_manager.update_task(task_id, **updates)

    if tool_name in {"complete_task", "delete_task"}:
        task_id = arguments.get("task_id")
        if set(arguments) != {"task_id"} or type(task_id) is not int:
            raise ToolCallError(f"{tool_name} requires only an integer task_id.")
        if tool_name == "complete_task":
            return task_manager.complete_task(task_id)
        if confirm_delete is None:
            raise ToolCallError("Deleting a task requires user confirmation.")
        if not confirm_delete(task_id):
            return f"Deletion of task {task_id} was cancelled."
        return task_manager.delete_task(task_id)

    raise ToolCallError(f"The model requested an unavailable tool: {tool_name}.")


def handle_request(
    request: str,
    confirm_delete: Callable[[int], bool] | None = None,
    conversation_history: Sequence[Mapping[str, str]] | None = None,
) -> str:
    messages: list[Any] = [
        {
            "role": "system",
            "content": (
                "You are a helpful AI task manager. Use the supplied tools to manage tasks. "
                "Use add_task only when asked to add a task, view_tasks to show or find tasks, "
                "update_task when asked to edit a task, "
                "complete_task to mark a task done, and delete_task only when asked to delete. "
                "When a task is identified by its name or description rather than ID, call "
                "view_tasks first, then use the matching ID. If the task is missing or "
                "ambiguous, ask a clarifying question instead of guessing. Never invent IDs. "
                "When asked to show or list tasks, use view_tasks and list each matching task's "
                "exact ID and name; do not answer only with a count or ask which task to show. "
                "For a request about what to complete today, use view_tasks and list pending "
                "tasks whose schedule date or due date is today, and say clearly if there are none. "
                f"Today's date is {date.today().isoformat()}. For planned work times, use "
                "schedule_date in YYYY-MM-DD format and start_time/end_time in 24-hour HH:MM "
                "format. Interpret relative dates like 'tomorrow' as schedule_date when the user "
                "says when they will work. Use due_date only for a separate deadline (for example "
                "'due by Friday'). Include both start_time and end_time or ask the user to clarify. "
                "For unrelated requests, respond briefly that you can help manage tasks."
            ),
        }
    ]
    messages.extend(dict(message) for message in (conversation_history or ()))
    messages.append({"role": "user", "content": request})
    last_tool_result = ""
    last_action_result = ""
    view_tool_used = False

    for round_number in range(MAX_TOOL_ROUNDS + 1):
        response = chat(model=MODEL, messages=messages, tools=TOOLS)
        message = response.message
        tool_calls = message.tool_calls or []

        if not tool_calls:
            answer = (message.content or "").strip()
            if view_tool_used and _is_task_listing_request(request):
                return _format_task_listing(request)
            if last_action_result:
                return last_action_result
            return answer or last_tool_result or "I couldn't determine a response. Please try again."

        if round_number == MAX_TOOL_ROUNDS:
            raise ToolCallError("The model exceeded the tool-call limit for one request.")

        messages.append(message)
        for tool_call in tool_calls:
            name = tool_call.function.name
            arguments = tool_call.function.arguments
            if not isinstance(arguments, Mapping):
                raise ToolCallError(f"{name} must be called with a JSON object.")

            last_tool_result = execute_tool(name, arguments, confirm_delete)
            if name in {"add_task", "update_task", "complete_task", "delete_task"}:
                last_action_result = last_tool_result
            if name in {"view_tasks", "list_tasks"}:
                view_tool_used = True
            messages.append(
                {
                    "role": "tool",
                    "tool_name": name,
                    "content": last_tool_result,
                }
            )

    raise ToolCallError("The model did not finish the request.")


def run_cli() -> None:
    print(f"AI Task Manager (model: {MODEL})")
    print("Tell me what you'd like to do, or type 'quit' to exit.")

    while True:
        try:
            request = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            return

        if not request:
            continue
        if request.lower() in {"quit", "exit"}:
            print("Goodbye!")
            return

        try:
            answer = handle_request(request, confirm_delete=_confirm_delete_cli)
        except (ConnectionError, RequestError, ResponseError) as error:
            print(f"AI service error: {error}")
            print(f"Check that Ollama is running and that {MODEL} is available.")
            continue
        except ToolCallError as error:
            print(f"Couldn't process that request: {error}")
            continue
        except json.JSONDecodeError as error:
            print(f"Couldn't read the task file: {error}")
            continue

        print(f"\nAssistant: {answer}")


def _confirm_delete_cli(task_id: int) -> bool:
    try:
        confirmation = input(f"Delete task {task_id}? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return confirmation in {"y", "yes"}


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-powered task manager")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="use the original command-line interface",
    )
    args = parser.parse_args()

    if args.cli:
        run_cli()
        return

    from gui import main as gui_main

    gui_main()


if __name__ == "__main__":
    main()
