import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from actions import open_app
from core import appidentity, windows_app_launcher


class WindowsAppLauncherTests(unittest.TestCase):
    def test_edge_aliases_normalize_to_edge_executable(self):
        with mock.patch.object(appidentity, "_OS", "Windows"):
            self.assertEqual(appidentity.launcher_name("Edge"), "msedge")
            self.assertEqual(appidentity.launcher_name("Microsoft Edge"), "msedge")
            self.assertEqual(appidentity.launcher_name("browser"), "msedge")

    def test_registered_app_is_preferred(self):
        with mock.patch.object(
            windows_app_launcher, "_registered_app",
            return_value=("Microsoft Edge", "MSEdge"),
        ), mock.patch.object(
            windows_app_launcher, "_start_registered_app",
            return_value=mock.Mock(poll=mock.Mock(return_value=None)),
        ) as start_registered, mock.patch.object(
            windows_app_launcher, "_known_executables",
        ) as find_executable:
            result = windows_app_launcher.launch("Edge", "msedge")

        self.assertTrue(result.accepted)
        self.assertIn("registered app", result.method)
        start_registered.assert_called_once_with("MSEdge")
        find_executable.assert_not_called()

    def test_missing_application_returns_actionable_error(self):
        with mock.patch.object(windows_app_launcher, "_registered_app", return_value=None), \
                mock.patch.object(windows_app_launcher, "_known_executables",
                                  return_value=(None, "")), \
                mock.patch.object(windows_app_launcher, "_start_menu_shortcut",
                                  return_value=None):
            result = windows_app_launcher.launch("No Such App", "No Such App")

        self.assertFalse(result.accepted)
        self.assertIn("no matching registered app", result.error)

    def test_invalid_executable_path_is_reported(self):
        missing_path = r"C:\not-a-real-install\missing.exe"
        with mock.patch.object(windows_app_launcher, "_registered_app", return_value=None), \
                mock.patch.object(windows_app_launcher, "_known_executables",
                                  return_value=(None, "")), \
                mock.patch.object(windows_app_launcher, "_start_menu_shortcut",
                                  return_value=None):
            result = windows_app_launcher.launch(missing_path, missing_path)

        self.assertFalse(result.accepted)
        self.assertIn("requested executable path does not exist", result.error)

    def test_launch_exception_is_reported_instead_of_success(self):
        with mock.patch.object(
            windows_app_launcher, "_registered_app",
            return_value=("Sample App", "Sample.App!App"),
        ), mock.patch.object(
            windows_app_launcher, "_start_registered_app",
            side_effect=PermissionError("access denied"),
        ), mock.patch.object(
            windows_app_launcher, "_known_executables",
            return_value=(None, ""),
        ), mock.patch.object(
            windows_app_launcher, "_start_menu_shortcut",
            return_value=None,
        ):
            result = windows_app_launcher.launch("Sample App", "Sample App")

        self.assertFalse(result.accepted)
        self.assertIn("PermissionError: access denied", result.error)

    def test_nonzero_launcher_exit_status_is_reported(self):
        with mock.patch.object(
            windows_app_launcher, "_registered_app",
            return_value=("Sample App", "Sample.App!App"),
        ), mock.patch.object(
            windows_app_launcher, "_start_registered_app",
            return_value=mock.Mock(poll=mock.Mock(return_value=7)),
        ), mock.patch.object(
            windows_app_launcher, "_known_executables",
            return_value=(None, ""),
        ), mock.patch.object(
            windows_app_launcher, "_start_menu_shortcut",
            return_value=None,
        ):
            result = windows_app_launcher.launch("Sample App", "Sample App")

        self.assertFalse(result.accepted)
        self.assertIn("status 7", result.error)

    def test_executable_arguments_are_passed_without_a_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "app with spaces.exe"
            executable.touch()
            with mock.patch.object(windows_app_launcher.subprocess, "Popen") as popen:
                windows_app_launcher._start_executable(executable)

        args, kwargs = popen.call_args
        self.assertEqual(args[0], [str(executable)])
        self.assertEqual(kwargs["cwd"], str(executable.parent))
        self.assertNotIn("shell", kwargs)

    def test_repeated_open_requests_are_suppressed_while_pending(self):
        pending_key = appidentity.fold("Unique Test Application")
        self.addCleanup(open_app._PENDING_APPS.discard, pending_key)
        with mock.patch.object(appidentity, "running", return_value=[]), \
                mock.patch.object(appidentity, "snapshot", return_value=set()), \
                mock.patch.object(open_app.threading, "Thread") as thread:
            first = open_app.open_app({"app_name": "Unique Test Application"})
            second = open_app.open_app({"app_name": "Unique Test Application"})

        self.assertIn("status=started", first)
        self.assertIn("duplicate_request=true", second)
        thread.assert_called_once()
        self.assertIs(thread.call_args.kwargs["target"], open_app._launch_and_verify)
        self.assertTrue(thread.call_args.kwargs["daemon"])


if __name__ == "__main__":
    unittest.main()
