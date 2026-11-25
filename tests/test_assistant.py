import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import assistant
import task_manager


def tool_call(name: str, arguments: dict[str, object]):
    return SimpleNamespace(
        function=SimpleNamespace(name=name, arguments=arguments)
    )


def model_message(content: str | None = None, tool_calls: list[object] | None = None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


class AssistantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.task_file = Path(self.temp_dir.name) / "tasks.json"
        self.task_file.write_text(
            '[{"id": 1, "task": "Buy groceries", "completed": false}]',
            encoding="utf-8",
        )
        self.task_file_patch = patch.object(task_manager, "TASK_FILE", self.task_file)
        self.task_file_patch.start()
        self.addCleanup(self.task_file_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def test_model_selects_tool_and_receives_its_result(self) -> None:
        responses = [
            SimpleNamespace(message=model_message(tool_calls=[tool_call("list_tasks", {})])),
            SimpleNamespace(
                message=model_message(tool_calls=[tool_call("complete_task", {"task_id": 1})])
            ),
            SimpleNamespace(message=model_message("Done, I marked Buy groceries complete.")),
        ]
        with patch.object(assistant, "chat", side_effect=responses) as mock_chat:
            answer = assistant.handle_request("Mark Buy groceries as done")

        self.assertEqual(answer, "Task 'Buy groceries' marked as completed!")
        self.assertTrue(task_manager.load_tasks()[0]["completed"])
        self.assertEqual(mock_chat.call_count, 3)
        final_messages = mock_chat.call_args.kwargs["messages"]
        self.assertEqual(final_messages[-1]["tool_name"], "complete_task")
        self.assertIn("Buy groceries", final_messages[-1]["content"])

    def test_conversation_history_is_sent_to_the_model(self) -> None:
        with patch.object(
            assistant,
            "chat",
            return_value=SimpleNamespace(message=model_message("I can help with that.")),
        ) as mock_chat:
            assistant.handle_request(
                "Can you do that?",
                conversation_history=[
                    {"role": "user", "content": "Add a task to study Python."},
                    {"role": "assistant", "content": "Added task 2: Study Python"},
                ],
            )

        messages = mock_chat.call_args.kwargs["messages"]
        self.assertEqual(messages[1:3], [
            {"role": "user", "content": "Add a task to study Python."},
            {"role": "assistant", "content": "Added task 2: Study Python"},
        ])
        self.assertEqual(messages[-1], {"role": "user", "content": "Can you do that?"})

    def test_model_can_add_task_using_the_exposed_tool(self) -> None:
        responses = [
            SimpleNamespace(
                message=model_message(
                    tool_calls=[tool_call("add_task", {"task_name": "Call the dentist"})]
                )
            ),
            SimpleNamespace(message=model_message("Added: Call the dentist.")),
        ]
        with patch.object(assistant, "chat", side_effect=responses) as mock_chat:
            answer = assistant.handle_request("Remind me to call the dentist")

        self.assertEqual(answer, "Added task 2: Call the dentist")
        self.assertEqual(task_manager.load_tasks()[-1]["task"], "Call the dentist")
        self.assertEqual(mock_chat.call_args.kwargs["tools"], assistant.TOOLS)

    def test_update_task_tool_changes_priority(self) -> None:
        result = assistant.execute_tool(
            "update_task",
            {"task_id": 1, "priority": "high"},
        )

        self.assertIn("Updated task 1", result)
        self.assertEqual(task_manager.load_tasks()[0]["priority"], "high")

    def test_task_listing_returns_matching_names_and_ids(self) -> None:
        responses = [
            SimpleNamespace(message=model_message(tool_calls=[tool_call("view_tasks", {})])),
            SimpleNamespace(message=model_message("There is one pending task.")),
        ]
        with patch.object(assistant, "chat", side_effect=responses):
            answer = assistant.handle_request("Show all pending tasks")

        self.assertIn("ID 1 · Buy groceries", answer)
        self.assertIn("Pending · Medium priority", answer)

    def test_today_listing_includes_only_pending_tasks_due_today(self) -> None:
        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        self.task_file.write_text(
            json.dumps(
                [
                    {"id": 1, "task": "Due today", "completed": False, "due_date": today},
                    {"id": 2, "task": "Due tomorrow", "completed": False, "due_date": tomorrow},
                    {"id": 3, "task": "Already done", "completed": True, "due_date": today},
                ]
            ),
            encoding="utf-8",
        )

        answer = assistant._format_task_listing("What tasks should I complete today?")

        self.assertIn("Due today", answer)
        self.assertNotIn("Due tomorrow", answer)
        self.assertNotIn("Already done", answer)

    def test_model_can_add_a_scheduled_task_with_a_separate_deadline(self) -> None:
        responses = [
            SimpleNamespace(
                message=model_message(
                    tool_calls=[
                        tool_call(
                            "add_task",
                            {
                                "task_name": "Study Python",
                                "schedule_date": "2026-11-21",
                                "start_time": "14:00",
                                "end_time": "16:00",
                                "due_date": "2026-11-25",
                            },
                        )
                    ]
                )
            ),
            SimpleNamespace(message=model_message("Added your task for November 21.")),
        ]
        with patch.object(assistant, "chat", side_effect=responses):
            assistant.handle_request("Study Python tomorrow from 2 to 4, due by Wednesday")

        scheduled_task = task_manager.load_tasks()[-1]
        self.assertEqual(scheduled_task["schedule_date"], "2026-11-21")
        self.assertEqual(scheduled_task["start_time"], "14:00")
        self.assertEqual(scheduled_task["end_time"], "16:00")
        self.assertEqual(scheduled_task["due_date"], "2026-11-25")

    def test_delete_requires_and_obeys_confirmation(self) -> None:
        responses = [
            SimpleNamespace(
                message=model_message(
                    tool_calls=[tool_call("delete_task", {"task_id": 1})]
                )
            ),
            SimpleNamespace(message=model_message("Deletion cancelled.")),
        ]
        with patch.object(assistant, "chat", side_effect=responses):
            answer = assistant.handle_request(
                "Delete task 1",
                confirm_delete=lambda _task_id: False,
            )

        self.assertEqual(answer, "Deletion of task 1 was cancelled.")
        self.assertEqual(len(task_manager.load_tasks()), 1)

    def test_confirmed_delete_removes_the_task(self) -> None:
        responses = [
            SimpleNamespace(
                message=model_message(
                    tool_calls=[tool_call("delete_task", {"task_id": 1})]
                )
            ),
            SimpleNamespace(message=model_message("Task deleted.")),
        ]
        with patch.object(assistant, "chat", side_effect=responses):
            answer = assistant.handle_request(
                "Delete task 1",
                confirm_delete=lambda _task_id: True,
            )

        self.assertEqual(answer, "Task 'Buy groceries' deleted successfully!")
        self.assertEqual(task_manager.load_tasks(), [])

    def test_unavailable_tool_is_rejected(self) -> None:
        responses = [
            SimpleNamespace(
                message=model_message(tool_calls=[tool_call("run_shell", {})])
            )
        ]
        with patch.object(assistant, "chat", side_effect=responses):
            with self.assertRaisesRegex(assistant.ToolCallError, "unavailable tool"):
                assistant.handle_request("Run some command")

        self.assertEqual(len(task_manager.load_tasks()), 1)


if __name__ == "__main__":
    unittest.main()
