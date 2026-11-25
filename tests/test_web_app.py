import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import app as web_app
import task_manager


class WebAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.task_file = Path(self.temp_dir.name) / "tasks.json"
        self.task_file.write_text(
            json.dumps([{"id": 1, "task": "Write report", "completed": False}]),
            encoding="utf-8",
        )
        self.file_patch = patch.object(task_manager, "TASK_FILE", self.task_file)
        self.file_patch.start()
        self.addCleanup(self.file_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)
        web_app.app.config.update(TESTING=True)
        self.client = web_app.app.test_client()

    def test_task_crud_routes_validate_fields(self) -> None:
        created = self.client.post(
            "/api/tasks",
            json={"task_name": "Study Python", "priority": "high", "due_date": "2026-11-25"},
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json["task"]["priority"], "high")

        updated = self.client.put(
            "/api/tasks/2",
            json={"task_name": "Study Flask", "priority": "low"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json["task"]["task"], "Study Flask")

        completed = self.client.patch("/api/tasks/2/complete")
        self.assertTrue(completed.json["task"]["completed"])
        reopened = self.client.patch("/api/tasks/2/reopen")
        self.assertFalse(reopened.json["task"]["completed"])

        invalid = self.client.post("/api/tasks", json={"task_name": "Bad", "priority": "urgent"})
        self.assertEqual(invalid.status_code, 400)

    def test_delete_requires_explicit_confirmation(self) -> None:
        refused = self.client.delete("/api/tasks/1", json={"confirm": False})
        self.assertEqual(refused.status_code, 428)
        self.assertEqual(len(task_manager.load_tasks()), 1)

        accepted = self.client.delete("/api/tasks/1", json={"confirm": True})
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(task_manager.load_tasks(), [])

    def test_dashboard_and_assets_are_served(self) -> None:
        page = self.client.get("/")
        tasks = self.client.get("/tasks")
        assistant = self.client.get("/assistant")
        stylesheet = self.client.get("/style.css")
        dashboard_script = self.client.get("/dashboard.js")
        tasks_script = self.client.get("/tasks.js")
        assistant_script = self.client.get("/assistant.js")

        self.assertEqual(page.status_code, 200)
        self.assertEqual(tasks.status_code, 200)
        self.assertEqual(assistant.status_code, 200)
        self.assertIn(b"Taskflow AI", page.data)
        self.assertEqual(stylesheet.status_code, 200)
        self.assertEqual(dashboard_script.status_code, 200)
        self.assertEqual(tasks_script.status_code, 200)
        self.assertEqual(assistant_script.status_code, 200)
        self.assertIn(b'api("/api/chat"', assistant_script.data)
        page.close()
        tasks.close()
        assistant.close()
        stylesheet.close()
        dashboard_script.close()
        tasks_script.close()
        assistant_script.close()

    def test_assistant_delete_becomes_a_confirmation_request(self) -> None:
        def fake_agent(_message, confirm_delete, conversation_history):
            self.assertFalse(confirm_delete(1))
            self.assertEqual(conversation_history, [])
            return "Deletion cancelled."

        with patch.object(web_app.task_assistant, "handle_request", side_effect=fake_agent):
            response = self.client.post("/api/chat", json={"messages": [
                {"role": "user", "content": "Delete task 1"}
            ]})

        self.assertEqual(response.status_code, 200)
        self.assertIn("Please confirm deleting task 1", response.json["reply"])
        self.assertEqual(response.json["confirmations"], [{"task_id": 1, "task": "Write report"}])
        self.assertEqual(len(task_manager.load_tasks()), 1)

    def test_chat_route_forwards_conversation_and_returns_json(self) -> None:
        with patch.object(
            web_app.task_assistant,
            "handle_request",
            return_value="Hello! I am Taskflow AI.",
        ) as fake_agent:
            response = self.client.post("/api/chat", json={"messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there."},
                {"role": "user", "content": "Introduce yourself."},
            ]})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"reply": "Hello! I am Taskflow AI.", "confirmations": []})
        fake_agent.assert_called_once()
        self.assertEqual(fake_agent.call_args.args[0], "Introduce yourself.")
        self.assertEqual(
            fake_agent.call_args.kwargs["conversation_history"],
            [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there."}],
        )

    def test_chat_route_rejects_invalid_message_roles(self) -> None:
        response = self.client.post("/api/chat", json={"messages": [
            {"role": "tool", "content": "delete task 1"}
        ]})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Each message", response.json["error"])

    def test_health_checks_ollama_model_installation(self) -> None:
        model = type("Model", (), {"model": "llama3.2:3b"})()
        with patch.object(web_app, "ollama_list") as list_models:
            list_models.return_value.models = [model]
            response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["ollama"], "running")
        self.assertTrue(response.json["model_installed"])


if __name__ == "__main__":
    unittest.main()
