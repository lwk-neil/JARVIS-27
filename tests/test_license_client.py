import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import license_client
from memory import config_manager


def response(status, device_id=None, http_status=200, headers=None):
    payload = {"status": status}
    if device_id is not None:
        payload["device_id"] = device_id
    return SimpleNamespace(
        status_code=http_status,
        headers=headers or {},
        json=lambda: payload,
    )


class LicenseClientTests(unittest.TestCase):
    def test_key_is_saved_and_read_through_system_keyring(self):
        store = mock.Mock()
        store.get_password.return_value = "SYKE-KEY"
        with mock.patch.object(
            license_client, "_credential_store", return_value=store
        ):
            license_client._save_license_key("SYKE-KEY")
            loaded = license_client.load_license_key()

        store.set_password.assert_called_once_with(
            "SYKE", "desktop-license", "SYKE-KEY"
        )
        store.get_password.assert_called_once_with("SYKE", "desktop-license")
        self.assertEqual(loaded, "SYKE-KEY")

    def test_redeem_posts_device_binding_and_saves_only_after_approval(self):
        device_id = "37d71e0a-755f-4f7f-b721-bdffb9751903"
        with mock.patch.object(
            license_client, "get_or_create_license_device_id",
            return_value=device_id,
        ), mock.patch.object(
            license_client.requests, "post",
            return_value=response("active", device_id),
        ) as post, mock.patch.object(
            license_client, "_save_license_key",
        ) as save:
            license_client.redeem_license("  SYKE-TEST-KEY  ")

        post.assert_called_once_with(
            license_client.REDEEM_URL,
            json={"license_key": "SYKE-TEST-KEY", "device_id": device_id},
            timeout=(5, 10),
        )
        save.assert_called_once_with("SYKE-TEST-KEY")

    def test_rejected_redemption_does_not_save_key(self):
        with mock.patch.object(
            license_client, "get_or_create_license_device_id",
            return_value="device",
        ), mock.patch.object(
            license_client.requests, "post",
            return_value=response("already_used", http_status=400),
        ), mock.patch.object(
            license_client, "_save_license_key",
        ) as save:
            with self.assertRaisesRegex(
                license_client.LicenseClientError, "another device"
            ):
                license_client.redeem_license("SYKE-USED-KEY")

        save.assert_not_called()

    def test_validation_checks_server_and_exact_device(self):
        device_id = "device"
        with mock.patch.object(
            license_client, "get_or_create_license_device_id",
            return_value=device_id,
        ), mock.patch.object(
            license_client.requests, "post",
            return_value=response("active", device_id),
        ) as post:
            license_client.validate_license("SYKE-ACTIVE-KEY")

        post.assert_called_once_with(
            license_client.VALIDATE_URL,
            json={"license_key": "SYKE-ACTIVE-KEY", "device_id": device_id},
            timeout=(5, 10),
        )

    def test_active_response_for_another_device_fails_closed(self):
        with mock.patch.object(
            license_client, "get_or_create_license_device_id",
            return_value="expected-device",
        ), mock.patch.object(
            license_client.requests, "post",
            return_value=response("active", "other-device"),
        ):
            with self.assertRaisesRegex(
                license_client.LicenseClientError, "did not match"
            ):
                license_client.validate_license("SYKE-ACTIVE-KEY")

    def test_rate_limit_uses_retry_after_header(self):
        with mock.patch.object(
            license_client, "get_or_create_license_device_id",
            return_value="device",
        ), mock.patch.object(
            license_client.requests, "post",
            return_value=response(
                "rate_limited", http_status=429, headers={"Retry-After": "17"}
            ),
        ):
            with self.assertRaisesRegex(
                license_client.LicenseClientError, "17 seconds"
            ):
                license_client.validate_license("SYKE-ACTIVE-KEY")

    def test_http_status_must_match_response_body(self):
        with mock.patch.object(
            license_client, "get_or_create_license_device_id",
            return_value="device",
        ), mock.patch.object(
            license_client.requests, "post",
            return_value=response("active", "device", http_status=500),
        ):
            with self.assertRaisesRegex(
                license_client.LicenseClientError, "unexpected status code"
            ):
                license_client.validate_license("SYKE-ACTIVE-KEY")

    def test_network_timeout_is_actionable(self):
        with mock.patch.object(
            license_client, "get_or_create_license_device_id",
            return_value="device",
        ), mock.patch.object(
            license_client.requests, "post",
            side_effect=license_client.requests.Timeout,
        ):
            with self.assertRaisesRegex(
                license_client.LicenseClientError, "too long to respond"
            ):
                license_client.validate_license("SYKE-ACTIVE-KEY")

    def test_blank_key_is_rejected_without_network_request(self):
        with mock.patch.object(license_client.requests, "post") as post:
            with self.assertRaises(license_client.LicenseClientError):
                license_client.validate_license(" ")
        post.assert_not_called()


class LicenseDeviceIdTests(unittest.TestCase):
    def test_device_id_is_valid_uuid_and_persists_across_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            config_dir = Path(directory)
            config_file = config_dir / "api_keys.json"
            with mock.patch.object(config_manager, "CONFIG_DIR", config_dir), \
                    mock.patch.object(config_manager, "CONFIG_FILE", config_file):
                first = config_manager.get_or_create_license_device_id()
                config_manager.save_api_keys("gemini-test-key", "Windows")
                second = config_manager.get_or_create_license_device_id()
                saved = json.loads(config_file.read_text(encoding="utf-8"))

        self.assertEqual(first, second)
        self.assertEqual(first, saved["license_device_id"])
        self.assertEqual(saved["gemini_api_key"], "gemini-test-key")
        self.assertEqual(saved["os_system"], "Windows")
        self.assertEqual(len(first), 36)
