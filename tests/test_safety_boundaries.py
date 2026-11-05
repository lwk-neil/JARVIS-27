import contextlib
import inspect
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from actions import (
    browser_control, code_helper, computer_control, computer_settings,
    file_controller, file_processor,
)
from actions import preferences
from actions import screen_processor
from core.action_loader import ActionRecord, ActionRegistry
from core import confirm as confirm_gate
from core.permission_modes import evaluate_tool
from memory import config_manager


class SafetyBoundaryTests(unittest.TestCase):
    def test_hud_center_styles_include_legacy_core_mapping(self):
        self.assertEqual(
            config_manager.HUD_STYLES,
            (
                "dna", "pulse", "matrix", "prism", "atom", "solar",
                "vortex", "quantum", "singularity", "halo", "lattice",
                "face",
            ),
        )
        with mock.patch.object(
            config_manager, "load_api_keys", return_value={"hud_style": "core"}
        ):
            self.assertEqual(config_manager.get_hud_style(), "dna")
        with mock.patch.object(config_manager, "_save_flag") as save_flag:
            config_manager.save_hud_style("core")

        save_flag.assert_called_once_with("hud_style", "dna")

    def test_restricted_mode_allows_read_only_file_actions_only(self):
        read = evaluate_tool(
            "file_controller", {"action": "read"}, mode="restricted")
        write = evaluate_tool(
            "file_controller", {"action": "write"}, mode="restricted")
        unknown = evaluate_tool(
            "unknown_plugin", {}, mode="restricted")

        self.assertEqual(read.kind, "allow")
        self.assertEqual(write.kind, "deny")
        self.assertEqual(unknown.kind, "deny")

    def test_restricted_mode_allows_reading_preferences_but_not_changes(self):
        self.assertEqual(
            evaluate_tool(
                "manage_preferences", {"action": "list"}, mode="restricted"
            ).kind,
            "allow",
        )
        self.assertEqual(
            evaluate_tool(
                "manage_preferences", {"action": "set"}, mode="restricted"
            ).kind,
            "deny",
        )
        self.assertEqual(
            evaluate_tool(
                "manage_preferences", {"action": "remove"}, mode="normal"
            ).kind,
            "allow",
        )

    def test_preferences_can_be_listed_set_and_removed(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            preferences.memory_manager,
            "MEMORY_PATH",
            Path(directory) / "memory.json",
        ), mock.patch("builtins.print"):
            saved = preferences.manage_preferences(
                {"action": "set", "key": "response_style", "value": "concise"}
            )
            listed = preferences.manage_preferences({"action": "list"})
            removed = preferences.manage_preferences(
                {"action": "remove", "key": "response_style"}
            )

        self.assertIn("Saved preference", saved)
        self.assertIn("response_style: concise", listed)
        self.assertIn("Forgotten", removed)

    def test_restricted_mode_blocks_screen_and_browser_capture(self):
        capture = evaluate_tool("screen_process", {}, mode="restricted")
        computer_capture = evaluate_tool(
            "computer_control", {"action": "screenshot"},
            mode="restricted",
        )
        browser_capture = evaluate_tool(
            "browser_control", {"action": "screenshot"}, mode="restricted")

        self.assertEqual(capture.kind, "deny")
        self.assertEqual(computer_capture.kind, "deny")
        self.assertEqual(browser_capture.kind, "deny")

    def test_file_changes_run_without_confirmation(self):
        normal_create = evaluate_tool(
            "file_controller", {"action": "create_file"}, mode="normal")
        trusted_create = evaluate_tool(
            "file_controller", {"action": "create_file"}, mode="trusted")
        self.assertEqual(normal_create.kind, "allow")
        self.assertEqual(trusted_create.kind, "allow")

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "notes.txt"
            new_target = Path(directory) / "new.txt"
            target.write_text("existing", encoding="utf-8")
            with mock.patch(
                "actions.file_controller._resolve_path",
                return_value=Path(directory),
            ):
                overwrite = evaluate_tool(
                    "file_controller",
                    {"action": "write", "name": target.name},
                    mode="normal",
                )
                append = evaluate_tool(
                    "file_controller",
                    {"action": "write", "name": target.name, "append": True},
                    mode="normal",
                )
                delete = evaluate_tool(
                    "file_controller",
                    {"action": "delete", "name": target.name},
                    mode="trusted",
                )
                create = evaluate_tool(
                    "file_controller",
                    {"action": "write", "name": new_target.name},
                    mode="normal",
                )

        self.assertEqual(overwrite.kind, "allow")
        self.assertEqual(append.kind, "allow")
        self.assertEqual(delete.kind, "allow")
        self.assertEqual(create.kind, "allow")

    def test_external_and_browser_actions_run_without_confirmation(self):
        message = evaluate_tool(
            "send_message",
            {"receiver": "Alex", "message_text": "Hello", "platform": "Signal"},
            mode="trusted",
        )
        browser = evaluate_tool(
            "browser_control", {"action": "go_to", "url": "https://example.com"},
            mode="trusted",
        )

        self.assertEqual(message.kind, "allow")
        self.assertEqual(browser.kind, "allow")

    def test_browser_form_fields_are_available_without_confirmation(self):
        fields = browser_control.TOOL["parameters"]["properties"]["fields"]
        self.assertEqual(fields["type"], "OBJECT")

        decision = evaluate_tool(
            "browser_control",
            {
                "action": "fill_form",
                "fields": {"#recipient": "Alex", "#message": "Hello"},
            },
            mode="trusted",
        )

        self.assertEqual(decision.kind, "allow")

    def test_explicit_current_tab_does_not_fall_back_to_another_browser(self):
        decision = evaluate_tool(
            "browser_control",
            {"action": "click", "browser": "current", "text": "Send"},
            mode="normal",
        )
        self.assertEqual(decision.kind, "deny")
        self.assertIn("No current browser tab is paired", decision.reason)

        with mock.patch.object(
            browser_control.browser_bridge, "submit", return_value=None
        ), mock.patch.object(browser_control._registry, "get") as get_session:
            result = browser_control.browser_control(
                {"action": "get_url", "browser": "current"}
            )

        self.assertIn("No current tab is paired", result)
        get_session.assert_not_called()

    def test_unlimited_mode_runs_actions_without_confirmation(self):
        create = evaluate_tool(
            "file_controller",
            {"action": "create_file"},
            mode="unlimited",
        )
        message = evaluate_tool(
            "send_message",
            {"receiver": "Alex", "message_text": "Hello", "platform": "Signal"},
            mode="unlimited",
        )
        browser = evaluate_tool(
            "browser_control",
            {"action": "go_to", "url": "https://example.com"},
            mode="unlimited",
        )
        scroll = evaluate_tool(
            "browser_control",
            {"action": "scroll"},
            mode="unlimited",
        )
        click = evaluate_tool(
            "browser_control",
            {"action": "click", "text": "Submit"},
            mode="unlimited",
        )
        run = evaluate_tool(
            "file_processor",
            {"action": "run", "file_path": "sample.py"},
            mode="unlimited",
        )

        self.assertEqual(create.kind, "allow")
        self.assertEqual(message.kind, "allow")
        self.assertEqual(browser.kind, "allow")
        self.assertEqual(scroll.kind, "allow")
        self.assertEqual(click.kind, "allow")
        self.assertEqual(run.kind, "allow")

    def test_desktop_input_does_not_require_confirmation(self):
        decision = evaluate_tool(
            "computer_control",
            {"action": "screen_click", "description": "Save button"},
            mode="trusted",
        )

        self.assertEqual(decision.kind, "allow")

    def test_restart_and_shutdown_run_without_confirmation(self):
        for action in ("restart", "shutdown"):
            handler = mock.Mock()
            with self.subTest(action=action), mock.patch.dict(
                computer_settings.ACTION_MAP, {action: handler}
            ):
                result = computer_settings.computer_settings(
                    {"action": action}
                )

            self.assertIn(f"wanted={action}", result)
            handler.assert_called_once_with()

    def test_file_processing_actions_run_without_confirmation(self):
        run = evaluate_tool(
            "file_processor", {"action": "run", "file_path": "sample.py"},
            mode="normal",
        )
        resize = evaluate_tool(
            "file_processor", {"action": "resize", "file_path": "photo.png"},
            mode="normal",
        )

        self.assertEqual(run.kind, "allow")
        self.assertEqual(resize.kind, "allow")

    def test_extracting_into_existing_archive_folder_runs_without_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "bundle.zip"
            destination = Path(directory) / "bundle"
            destination.mkdir()
            decision = evaluate_tool(
                "file_processor",
                {
                    "action": "extract",
                    "file_path": str(archive),
                    "destination": str(destination),
                },
                mode="normal",
            )

        self.assertEqual(decision.kind, "allow")

    def test_generated_file_outputs_do_not_overwrite_existing_results(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "report.pdf"
            first = file_processor._output_path(source, "text", ".txt")
            first.touch()

            next_path = file_processor._output_path(source, "text", ".txt")

        self.assertEqual(next_path.name, "report_text_2.txt")

    def test_code_helper_overwrites_without_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "existing.py"
            new_target = Path(directory) / "new.py"
            target.write_text("print('old')", encoding="utf-8")
            with mock.patch(
                "actions.code_helper._resolve_save_path",
                return_value=target,
            ):
                overwrite = evaluate_tool(
                    "code_helper", {"action": "write", "language": "python"},
                    mode="normal",
                )
            with mock.patch(
                "actions.code_helper._resolve_save_path",
                return_value=new_target,
            ):
                create = evaluate_tool(
                    "code_helper",
                    {"action": "write", "language": "python", "output_path": "new.py"},
                    mode="normal",
                )

        self.assertEqual(overwrite.kind, "allow")
        self.assertEqual(create.kind, "allow")

    def test_empty_action_result_is_not_reported_as_success(self):
        registry = ActionRegistry(
            {
                "empty_action": ActionRecord(
                    name="empty_action",
                    handler=lambda parameters: None,
                    valid=True,
                )
            },
            logger=lambda _message: None,
        )

        result = registry.run("empty_action", {})

        self.assertIn("returned no result", result)
        self.assertNotEqual(result, "Done.")

    def test_close_app_confirmation_cannot_be_supplied_by_tool_parameters(self):
        self.assertNotIn("confirmed", inspect.signature(computer_control._close_app).parameters)
        self.assertNotIn("confirmed", computer_control.TOOL["parameters"]["properties"])

    def test_create_file_does_not_overwrite_existing_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "existing.txt"
            target.write_text("keep this", encoding="utf-8")
            with mock.patch.object(file_controller, "_resolve_path", return_value=root), \
                    mock.patch.object(file_controller, "_is_safe_path", return_value=True):
                result = file_controller.create_file("root", target.name, "replace it")

            self.assertIn("already exists", result)
            self.assertEqual(target.read_text(encoding="utf-8"), "keep this")

    def test_move_does_not_replace_an_existing_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.txt"
            destination = root / "destination.txt"
            source.write_text("source", encoding="utf-8")
            destination.write_text("destination", encoding="utf-8")
            with mock.patch.object(file_controller, "_resolve_path", return_value=root), \
                    mock.patch.object(file_controller, "_is_safe_path", return_value=True):
                result = file_controller.move_file("root", source.name, destination.name)

            self.assertIn("already exists", result)
            self.assertEqual(source.read_text(encoding="utf-8"), "source")
            self.assertEqual(destination.read_text(encoding="utf-8"), "destination")

    def test_copy_does_not_replace_an_existing_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.txt"
            destination = root / "destination.txt"
            source.write_text("source", encoding="utf-8")
            destination.write_text("destination", encoding="utf-8")
            with mock.patch.object(file_controller, "_resolve_path", return_value=root), \
                    mock.patch.object(file_controller, "_is_safe_path", return_value=True):
                result = file_controller.copy_file("root", source.name, destination.name)

            self.assertIn("already exists", result)
            self.assertEqual(source.read_text(encoding="utf-8"), "source")
            self.assertEqual(destination.read_text(encoding="utf-8"), "destination")

    def test_running_code_does_not_wait_for_ui_confirmation(self):
        with mock.patch.object(
            code_helper, "_run_action", return_value="ran"
        ) as run_action:
            result = code_helper.code_helper(
                {"action": "run", "file_path": "sample.py"},
                player=None,
            )

        self.assertEqual(result, "ran")
        run_action.assert_called_once_with("sample.py", [], 30, None)

    def test_generated_build_does_not_wait_for_ui_confirmation(self):
        with mock.patch.object(
            code_helper, "_build", return_value="built"
        ) as build:
            result = code_helper.code_helper(
                {"action": "build", "description": "make a simple program"},
                player=None,
            )

        self.assertEqual(result, "built")
        build.assert_called_once_with(
            "make a simple program", "python", "", [], 30, None, None
        )

    def test_confirmation_gate_does_not_replace_an_existing_request(self):
        show = mock.Mock()
        with mock.patch.object(confirm_gate, "_pending", None), \
                mock.patch.object(confirm_gate, "_show_cb", show), \
                mock.patch.object(confirm_gate, "_hide_cb", None):
            first = confirm_gate.request("first", "First action", "detail", lambda: "done")
            second = confirm_gate.request("second", "Second action", "detail", lambda: "done")
            pending = confirm_gate.pending_title()
            confirm_gate.resolve(False)

        self.assertIn("[CONFIRMATION_PENDING]", first)
        self.assertIn("[CONFIRMATION_PENDING]", second)
        self.assertEqual(pending, "First action")
        show.assert_called_once_with("First action", "detail")

    def test_voice_confirmation_accepts_short_explicit_phrases_only(self):
        run = mock.Mock(return_value="sent")
        pending = confirm_gate._Pending(
            key="send_message",
            title="Send message",
            detail="Send to Alex",
            run=run,
            at=confirm_gate.time.monotonic(),
        )
        with mock.patch.object(confirm_gate, "_pending", pending), \
                mock.patch.object(confirm_gate, "_hide_cb", None), \
                mock.patch.object(
                    confirm_gate.threading,
                    "Thread",
                    side_effect=lambda **kwargs: mock.Mock(
                        start=lambda: kwargs["target"]()
                    ),
                ):
            self.assertFalse(confirm_gate.resolve_voice("yes, send the message"))
            self.assertTrue(confirm_gate.resolve_voice("Yes!"))

        run.assert_called_once_with()
        self.assertIsNone(confirm_gate._pending)

    def test_voice_cancellation_never_runs_confirmed_action(self):
        run = mock.Mock(return_value="sent")
        pending = confirm_gate._Pending(
            key="send_message",
            title="Send message",
            detail="Send to Alex",
            run=run,
            at=confirm_gate.time.monotonic(),
        )
        with mock.patch.object(confirm_gate, "_pending", pending), \
                mock.patch.object(confirm_gate, "_hide_cb", None):
            self.assertTrue(confirm_gate.resolve_voice("cancel"))

        run.assert_not_called()
        self.assertIsNone(confirm_gate._pending)

    def test_voice_confirmation_accepts_short_common_localized_responses(self):
        for phrase in ("sí", "oui", "evet", "はい", "да"):
            pending = confirm_gate._Pending(
                key="test",
                title="Test",
                detail="",
                run=mock.Mock(return_value="done"),
                at=confirm_gate.time.monotonic(),
            )
            with self.subTest(phrase=phrase), \
                    mock.patch.object(confirm_gate, "_pending", pending), \
                    mock.patch.object(confirm_gate, "_hide_cb", None), \
                    mock.patch.object(
                        confirm_gate.threading,
                        "Thread",
                        side_effect=lambda **kwargs: mock.Mock(
                            start=lambda: kwargs["target"]()
                        ),
                    ):
                self.assertTrue(confirm_gate.resolve_voice(phrase))

    def test_failed_code_process_is_not_classified_as_success(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "sample.py"
            script.write_text("pass", encoding="utf-8")
            completed = mock.Mock(returncode=7, stdout="", stderr="")
            with mock.patch.object(code_helper.subprocess, "run", return_value=completed):
                result = code_helper._run_file(script, [], timeout=5)

        self.assertIn("exit code 7", result)
        self.assertTrue(code_helper._has_error(result))

    def test_window_title_is_passed_as_data_not_script(self):
        title = 'window "name"'
        completed = mock.Mock(returncode=0)
        with mock.patch.object(computer_control, "_get_os", return_value="windows"), \
                mock.patch.object(computer_control.subprocess, "run", return_value=completed) as run, \
                mock.patch.object(computer_control.time, "sleep"):
            result = computer_control._focus_window(title)

        self.assertEqual(result, f"Focused window: {title}")
        args, kwargs = run.call_args
        self.assertNotIn(title, args[0][-1])
        self.assertEqual(kwargs["env"]["SYKE_WINDOW_TITLE"], title)

    def test_computer_control_types_unicode_and_restores_clipboard(self):
        clipboard = mock.Mock()
        keyboard = mock.Mock()
        text = "Hello, café!"
        clipboard.paste.side_effect = ["previous clipboard", text]
        with mock.patch.object(computer_control, "_require_pyautogui"), \
                mock.patch.object(computer_control, "_require_pyperclip",
                                  return_value=True), \
                mock.patch.object(computer_control, "_get_os",
                                  return_value="windows"), \
                mock.patch.object(computer_control, "pyperclip", clipboard), \
                mock.patch.object(computer_control, "pyautogui", keyboard), \
                mock.patch.object(computer_control.time, "sleep"):
            result = computer_control._type(text)

        self.assertIn("status=unverified", result)
        self.assertIn("method=clipboard", result)
        self.assertEqual(
            clipboard.copy.call_args_list,
            [mock.call(text), mock.call("previous clipboard")],
        )
        keyboard.hotkey.assert_called_once_with("ctrl", "v")
        keyboard.typewrite.assert_not_called()

    def test_computer_control_does_not_restore_over_a_new_clipboard_value(self):
        clipboard = mock.Mock()
        clipboard.paste.side_effect = ["previous clipboard", "copied by another app"]
        keyboard = mock.Mock()
        with mock.patch.object(computer_control, "_require_pyautogui"), \
                mock.patch.object(computer_control, "_get_os",
                                  return_value="windows"), \
                mock.patch.object(computer_control, "pyperclip", clipboard), \
                mock.patch.object(computer_control, "pyautogui", keyboard), \
                mock.patch.object(computer_control.time, "sleep"):
            computer_control._type_via_clipboard("message")

        clipboard.copy.assert_called_once_with("message")
        keyboard.hotkey.assert_called_once_with("ctrl", "v")

    def test_computer_control_waits_for_chat_app_to_process_clipboard_paste(self):
        clipboard = mock.Mock()
        clipboard.paste.side_effect = ["old", "new message"]
        keyboard = mock.Mock()
        with mock.patch.object(computer_control, "_get_os",
                               return_value="windows"), \
                mock.patch.object(computer_control, "pyperclip", clipboard), \
                mock.patch.object(computer_control, "pyautogui", keyboard), \
                mock.patch.object(computer_control.time, "sleep") as sleep:
            computer_control._type_via_clipboard("new message")

        self.assertEqual(
            sleep.call_args_list,
            [mock.call(0.1), mock.call(computer_control._PASTE_SETTLE_SECONDS)],
        )

    def test_screen_capture_can_select_all_displays_or_a_specific_display(self):
        displays = [
            {"left": -1920, "top": 0, "width": 3840, "height": 1080},
            {"left": 0, "top": 0, "width": 1920, "height": 1080},
            {"left": -1920, "top": 0, "width": 1920, "height": 1080},
        ]
        capture = mock.MagicMock(monitors=displays)
        fake_mss = mock.MagicMock()
        fake_mss.mss.return_value.__enter__.return_value = capture
        fake_mss.tools.to_png.return_value = b"png"
        with mock.patch.object(screen_processor, "_MSS", True), \
                mock.patch.object(screen_processor, "mss", fake_mss, create=True), \
                mock.patch.object(
                    screen_processor, "_compress",
                    return_value=(b"jpeg", "image/jpeg"),
                ):
            screen_processor._capture_screen()
            screen_processor._capture_screen(2)

        self.assertEqual(
            [call.args[0] for call in capture.grab.call_args_list],
            [displays[0], displays[2]],
        )

    def test_screen_capture_rejects_an_unavailable_display(self):
        capture = mock.MagicMock(monitors=[{}, {"left": 0}])
        fake_mss = mock.MagicMock()
        fake_mss.mss.return_value.__enter__.return_value = capture
        with mock.patch.object(screen_processor, "_MSS", True), \
                mock.patch.object(screen_processor, "mss", fake_mss, create=True):
            with self.assertRaisesRegex(ValueError, "Display 2 is unavailable"):
                screen_processor._capture_screen(2)

    def test_computer_control_falls_back_to_keypress_without_clipboard(self):
        keyboard = mock.Mock()
        with mock.patch.object(computer_control, "_require_pyautogui"), \
                mock.patch.object(computer_control, "_require_pyperclip",
                                  return_value=False), \
                mock.patch.object(computer_control, "pyautogui", keyboard), \
                mock.patch.object(computer_control.time, "sleep"):
            result = computer_control._type("hello")

        self.assertIn("status=unverified", result)
        self.assertIn('method="key events"', result)
        keyboard.typewrite.assert_called_once_with("hello", interval=0.03)
        keyboard.hotkey.assert_not_called()

    def test_computer_control_does_not_log_typed_content(self):
        secret = "private text that should not enter logs"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            computer_control.computer_control(
                {"action": "unknown", "text": secret},
                player=None,
            )

        self.assertNotIn(secret, output.getvalue())


if __name__ == "__main__":
    unittest.main()
