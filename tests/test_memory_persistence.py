import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from memory import memory_manager


class MemoryPersistenceTests(unittest.TestCase):
    def test_session_archive_is_not_limited_to_three_and_briefing_keeps_it(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            memory_manager, "MEMORY_PATH", Path(directory) / "memory.json"
        ):
            for index in range(5):
                memory_manager.save_session_summary(
                    f"unique conversation topic {index}", "English"
                )

            latest = memory_manager.latest_unbriefed_session()
            self.assertIn("topic 4", latest["summary"])
            memory_manager.mark_session_briefed(latest)

            archived = memory_manager.load_memory()["sessions"]
            self.assertEqual(len(archived), 5)
            self.assertTrue(archived[-1]["briefed"])
            self.assertIn("topic 0", memory_manager.search_memory("topic 0"))
            self.assertIsNone(memory_manager.latest_unbriefed_session())

    def test_memory_limit_refuses_write_without_deleting_old_facts(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            memory_manager, "MEMORY_PATH", Path(directory) / "memory.json"
        ):
            original = {
                "identity": {"name": {"value": "Neil", "updated": "2026-11-02"}}
            }
            memory_manager.save_memory(original)
            saved_before = memory_manager.MEMORY_PATH.read_text(encoding="utf-8")

            with mock.patch.object(memory_manager, "MEMORY_MAX_CHARS", 1):
                with self.assertRaises(MemoryError):
                    memory_manager.update_memory(
                        {"notes": {"new_fact": {"value": "keep this too"}}}
                    )

            saved_after = memory_manager.MEMORY_PATH.read_text(encoding="utf-8")
            self.assertEqual(saved_after, saved_before)
            self.assertEqual(
                json.loads(saved_after)["identity"]["name"]["value"],
                "Neil",
            )

    def test_recent_session_summary_is_in_prompt_context(self):
        memory = memory_manager._empty_memory()
        memory["sessions"] = [
            {
                "date": "2026-11-02",
                "summary": "Discussed the user's active project.",
            }
        ]

        prompt = memory_manager.format_memory_for_prompt(memory)

        self.assertIn("Most recent conversation", prompt)
        self.assertIn("active project", prompt)

    def test_long_checkpoint_is_preserved_in_storage_and_prompt(self):
        checkpoint = (
            "Goal: finish the desktop assistant. Progress: clipboard paste fixed. "
            "Decision: retain a user's clipboard when another app changes it. "
            "Blocker: multi-monitor screen details. Next: test display selection."
        )
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            memory_manager, "MEMORY_PATH", Path(directory) / "memory.json"
        ):
            memory_manager.save_session_summary(checkpoint, "English")
            stored = memory_manager.load_memory()["sessions"][-1]["summary"]
            prompt = memory_manager.format_memory_for_prompt(
                memory_manager.load_memory()
            )

        self.assertEqual(stored, checkpoint)
        self.assertIn("Next: test display selection", prompt)


if __name__ == "__main__":
    unittest.main()
