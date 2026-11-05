"""Client for SYKE's server-backed license activation and validation."""

from __future__ import annotations

from typing import Any

import requests

from memory.config_manager import get_or_create_license_device_id

SUPABASE_URL = "https://qipyzectzdupwvmosdek.supabase.co"
REDEEM_URL = f"{SUPABASE_URL}/functions/v1/redeem-license"
VALIDATE_URL = f"{SUPABASE_URL}/functions/v1/validate-license"
_CREDENTIAL_SERVICE = "SYKE"
_CREDENTIAL_ACCOUNT = "desktop-license"
_TIMEOUT = (5, 10)


class LicenseClientError(Exception):
    """A license request or local credential operation failed."""

    def __init__(self, message: str, status: str = "error"):
        super().__init__(message)
        self.status = status


def _credential_store():
    try:
        import keyring
    except ImportError as exc:
        raise LicenseClientError(
            "Secure credential storage is unavailable. Reinstall SYKE and try again."
        ) from exc
    return keyring


def load_license_key() -> str | None:
    try:
        return _credential_store().get_password(
            _CREDENTIAL_SERVICE, _CREDENTIAL_ACCOUNT
        )
    except LicenseClientError:
        raise
    except Exception as exc:
        raise LicenseClientError(
            "SYKE could not read its license from the system credential store."
        ) from exc


def _save_license_key(license_key: str) -> None:
    try:
        _credential_store().set_password(
            _CREDENTIAL_SERVICE, _CREDENTIAL_ACCOUNT, license_key
        )
    except LicenseClientError:
        raise
    except Exception as exc:
        raise LicenseClientError(
            "SYKE could not securely save the license on this device."
        ) from exc


def _response_status(response: requests.Response) -> tuple[str, dict[str, Any]]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise LicenseClientError(
            "The license server returned an unreadable response."
        ) from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("status"), str):
        raise LicenseClientError(
            "The license server returned an unexpected response."
        )
    status = payload["status"]
    if status == "rate_limited":
        if response.status_code != 429:
            raise LicenseClientError(
                "The license server returned an unexpected status code."
            )
        retry_after = response.headers.get(
            "Retry-After", str(payload.get("retry_after", "a short time"))
        )
        raise LicenseClientError(
            f"Too many license requests. Please try again in {retry_after} seconds.",
            status,
        )
    expected_http_status = 200 if status == "active" else 400
    if response.status_code != expected_http_status:
        raise LicenseClientError(
            "The license server returned an unexpected status code."
        )
    if status != "active":
        messages = {
            "already_used": "This license is already bound to another device.",
            "revoked": "This license has been revoked. Contact SYKE support.",
            "expired": "This license has expired. Contact SYKE support.",
            "invalid": "That license key is invalid.",
        }
        raise LicenseClientError(
            messages.get(status, "The license server rejected this request."),
            status,
        )
    return status, payload


def _request(url: str, license_key: str, device_id: str) -> dict[str, Any]:
    try:
        response = requests.post(
            url,
            json={"license_key": license_key, "device_id": device_id},
            timeout=_TIMEOUT,
        )
    except requests.Timeout as exc:
        raise LicenseClientError(
            "The license server took too long to respond. Check your connection and retry."
        ) from exc
    except requests.RequestException as exc:
        raise LicenseClientError(
            "Could not reach the license server. Check your internet connection and retry."
        ) from exc

    _, payload = _response_status(response)
    if payload.get("device_id") != device_id:
        raise LicenseClientError(
            "The license server response did not match this device."
        )
    return payload


def redeem_license(license_key: str) -> None:
    """Redeem a key on this device and securely save it after server approval."""
    normalized_key = license_key.strip()
    if not normalized_key:
        raise LicenseClientError("Enter your SYKE license key.", "invalid")

    device_id = get_or_create_license_device_id()
    _request(REDEEM_URL, normalized_key, device_id)
    _save_license_key(normalized_key)


def validate_license(license_key: str) -> None:
    """Require the stored license to be active and bound to this device."""
    normalized_key = license_key.strip()
    if not normalized_key:
        raise LicenseClientError("Enter your SYKE license key.", "invalid")

    device_id = get_or_create_license_device_id()
    _request(VALIDATE_URL, normalized_key, device_id)
