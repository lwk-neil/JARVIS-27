import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from actions import reminder as reminder_action


class ReminderListingTests(unittest.TestCase):
    def test_scheduling_persists_reminder_for_startup_briefing(self):
        with tempfile.TemporaryDirectory() as directory:
            scripts_dir = Path(directory)
            script_path = scripts_dir / "reminder.py"
            script_path.write_text("", encoding="utf-8")
            with (
                mock.patch.object(reminder_action, "_scripts_dir", return_value=scripts_dir),
                mock.patch.object(reminder_action, "_get_os", return_value="windows"),
                mock.patch.object(reminder_action, "_write_notify_script", return_value=script_path),
                mock.patch.object(reminder_action, "_schedule_windows", return_value="task"),
            ):
                result = reminder_action.reminder({
                    "date": "2099-12-31",
                    "time": "23:59",
                    "message": "Review project",
                })

                self.assertIn("Reminder set", result)
                self.assertEqual(
                    reminder_action.list_upcoming_reminders(datetime(2099, 12, 31, 23, 58)),
                    [{
                        "datetime": "2099-12-31T23:59:00",
                        "message": "Review project",
                    }],
                )

    def test_listing_excludes_past_reminders_and_sorts_upcoming(self):
        with tempfile.TemporaryDirectory() as directory:
            scripts_dir = Path(directory)
            index = scripts_dir / reminder_action._REMINDER_INDEX_FILENAME
            index.write_text(
                '[{"datetime":"2099-12-31T13:00:00","message":"Later"},'
                '{"datetime":"2099-12-30T13:00:00","message":"Past"},'
                '{"datetime":"2099-12-31T12:00:00","message":"Sooner"}]',
                encoding="utf-8",
            )
            with mock.patch.object(reminder_action, "_scripts_dir", return_value=scripts_dir):
                reminders = reminder_action.list_upcoming_reminders(
                    datetime(2099, 12, 31, 11, 0)
                )

            self.assertEqual(
                [entry["message"] for entry in reminders],
                ["Sooner", "Later"],
            )

    def test_corrupt_reminder_index_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            scripts_dir = Path(directory)
            (scripts_dir / reminder_action._REMINDER_INDEX_FILENAME).write_text(
                "{invalid json", encoding="utf-8"
            )
            with mock.patch.object(reminder_action, "_scripts_dir", return_value=scripts_dir):
                with self.assertRaisesRegex(ValueError, "not valid JSON"):
                    reminder_action.list_upcoming_reminders()


if __name__ == "__main__":
    unittest.main()
