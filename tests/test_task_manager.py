import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import task_manager


class TaskManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.task_file = Path(self.temp_dir.name) / "tasks.json"
        self.task_file.write_text(
            json.dumps(
                [
                    {"id": 1, "task": "First task", "completed": True},
                    {"id": 3, "task": "Third task", "completed": False},
                ]
            ),
            encoding="utf-8",
        )
        self.task_file_patch = patch.object(task_manager, "TASK_FILE", self.task_file)
        self.task_file_patch.start()
        self.addCleanup(self.task_file_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def test_add_uses_an_id_after_the_highest_existing_id(self) -> None:
        result = task_manager.add_task("  New task  ")

        self.assertEqual(result, "Added task 4: New task")
        self.assertEqual(task_manager.load_tasks()[-1], {
            "id": 4,
            "task": "New task",
            "completed": False,
            "priority": "medium",
        })

    def test_add_does_not_collide_with_existing_ids_after_a_gap(self) -> None:
        task_manager.add_task("Another task")

        self.assertEqual(task_manager.load_tasks()[-1]["id"], 4)

    def test_add_stores_an_optional_due_date(self) -> None:
        task_manager.add_task("Study Python", "2026-11-21")

        self.assertEqual(task_manager.load_tasks()[-1]["due_date"], "2026-11-21")

    def test_add_rejects_non_iso_due_dates(self) -> None:
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            task_manager.add_task("Study Python", "tomorrow")

    def test_add_stores_schedule_and_deadline_separately(self) -> None:
        task_manager.add_task(
            "Study Python",
            due_date="2026-11-25",
            schedule_date="2026-11-21",
            start_time="14:00",
            end_time="16:00",
        )

        task = task_manager.load_tasks()[-1]
        self.assertEqual(task["schedule_date"], "2026-11-21")
        self.assertEqual(task["start_time"], "14:00")
        self.assertEqual(task["end_time"], "16:00")
        self.assertEqual(task["due_date"], "2026-11-25")

    def test_time_range_requires_both_times_and_end_after_start(self) -> None:
        with self.assertRaisesRegex(ValueError, "Both start_time and end_time"):
            task_manager.add_task("Study Python", start_time="14:00")
        with self.assertRaisesRegex(ValueError, "later than start_time"):
            task_manager.add_task("Study Python", start_time="16:00", end_time="14:00")

    def test_load_rejects_invalid_task_entries(self) -> None:
        self.task_file.write_text('[{"id": "1", "task": "Bad", "completed": false}]')

        with self.assertRaisesRegex(ValueError, "invalid format"):
            task_manager.load_tasks()

    def test_update_changes_task_fields_and_clears_optional_dates(self) -> None:
        task_manager.update_task(
            3,
            task_name="Updated task",
            priority="high",
            due_date="2026-11-25",
        )
        task = task_manager.load_tasks()[1]
        self.assertEqual(task["task"], "Updated task")
        self.assertEqual(task["priority"], "high")
        self.assertEqual(task["due_date"], "2026-11-25")

        task_manager.update_task(3, due_date="")
        self.assertIsNone(task_manager.load_tasks()[1]["due_date"])

    def test_update_rejects_invalid_priority_and_time_ranges(self) -> None:
        with self.assertRaisesRegex(ValueError, "priority must be"):
            task_manager.update_task(3, priority="urgent")
        with self.assertRaisesRegex(ValueError, "Both start_time and end_time"):
            task_manager.update_task(3, start_time="14:00")

    def test_reopen_moves_completed_task_back_to_pending(self) -> None:
        task_manager.reopen_task(1)

        self.assertFalse(task_manager.load_tasks()[0]["completed"])


if __name__ == "__main__":
    unittest.main()
