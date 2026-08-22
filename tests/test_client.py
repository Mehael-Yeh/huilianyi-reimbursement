import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from huilianyi.auth import AuthSession
from huilianyi.client import HuilianyiClient
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


class ClientTests(unittest.TestCase):
    def client(self, opener):
        return HuilianyiClient(AuthSession("token", "https://tenant", {}), opener=opener)

    def test_typed_list_normalizes_rows_and_pagination_path(self):
        seen = []

        def opener(request, timeout):
            seen.append((request.method, request.full_url))
            return Response({"rows": [{"applicationOID": "a1"}]})

        rows = self.client(opener).list_travel_applications(page=2, size=25)
        self.assertEqual(rows, [{"applicationOID": "a1"}])
        self.assertEqual(seen[0][0], "POST")
        self.assertIn("page=2&size=25", seen[0][1])

    def test_http_auth_error_is_standardized_and_redacted(self):
        def opener(request, timeout):
            body = io.BytesIO(json.dumps({"access_token": "secret", "message": "expired"}).encode())
            raise urllib.error.HTTPError(request.full_url, 401, "no", {}, body)

        with self.assertRaises(HuilianyiError) as caught:
            self.client(opener).get_current_user()
        self.assertEqual(caught.exception.code, ErrorCode.AUTH_EXPIRED)
        self.assertEqual(caught.exception.details["access_token"], "<redacted>")

    def test_draft_guard_rejects_non_draft_state(self):
        client = self.client(lambda request, timeout: Response({}))
        with self.assertRaises(HuilianyiError) as caught:
            client.create_reimbursement_draft({"status": 1003})
        self.assertEqual(caught.exception.code, ErrorCode.UNSAFE_OPERATION)

    def test_draft_write_forces_status_1001(self):
        seen = []

        def opener(request, timeout):
            seen.append((request.method, request.full_url, json.loads(request.data)))
            return Response({"status": 1001, "expenseReportOID": "draft-1"})

        result = self.client(opener).create_reimbursement_draft({"title": "test draft"})
        self.assertEqual(result["status"], 1001)
        self.assertEqual(seen[0][0], "POST")
        self.assertEqual(seen[0][2]["status"], 1001)

    def test_approval_history_uses_verified_read_endpoint(self):
        seen = []

        def opener(request, timeout):
            seen.append(request.full_url)
            return Response({"rows": [{"operation": "created"}]})

        rows = self.client(opener).get_reimbursement_approval_history("report 1")
        self.assertEqual(rows, [{"operation": "created"}])
        self.assertIn("expenseReportOID=report%201", seen[0])


if __name__ == "__main__":
    unittest.main()
