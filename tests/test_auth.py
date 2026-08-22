import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from huilianyi.auth import AuthSession, login
from huilianyi.exceptions import ErrorCode, HuilianyiError


class Response:
    status = 200

    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.value).encode()


class AuthTests(unittest.TestCase):
    def test_login_returns_validated_auth_without_logging_secret(self):
        captured = {}

        def opener(request, timeout):
            captured["request"] = request
            return Response([{"access_token": "test-token", "realm_base_service_url": "https://tenant"}])

        with patch("huilianyi.auth._rsa_encrypt", return_value="encrypted"):
            value = login("user", "password", opener=opener)
        self.assertEqual(AuthSession.from_response(value).api_base_url, "https://tenant")
        self.assertNotIn(b"password=password", captured["request"].data)
        self.assertIn(b"password=encrypted", captured["request"].data)

    def test_blank_credentials_have_stable_error_code(self):
        with self.assertRaises(HuilianyiError) as caught:
            login("", "")
        self.assertEqual(caught.exception.code, ErrorCode.AUTH_REQUIRED)

    def test_missing_token_is_auth_failed(self):
        with self.assertRaises(HuilianyiError) as caught:
            AuthSession.from_response({})
        self.assertEqual(caught.exception.code, ErrorCode.AUTH_FAILED)


if __name__ == "__main__":
    unittest.main()
