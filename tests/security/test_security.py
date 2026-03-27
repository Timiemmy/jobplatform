"""
tests/security/test_security.py

Tests for core/security.py and core/middleware.py.
"""

from django.test import TestCase, RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from core.security import sanitize_string, mask_email, assert_no_sensitive_fields
from core.middleware import RequestIDMiddleware, SecurityHeadersMiddleware


# ---------------------------------------------------------------------------
# sanitize_string
# ---------------------------------------------------------------------------

class TestSanitizeString(SimpleTestCase):

    def test_normal_string_unchanged(self):
        self.assertEqual(sanitize_string("Hello, world!"), "Hello, world!")

    def test_null_byte_removed(self):
        self.assertEqual(sanitize_string("resume\x00.pdf"), "resume.pdf")

    def test_multiple_null_bytes_removed(self):
        result = sanitize_string("bad\x00bad\x00string")
        self.assertNotIn("\x00", result)

    def test_control_chars_removed(self):
        # \x01 to \x08 should be stripped
        self.assertEqual(sanitize_string("clean\x01dirty"), "cleandirty")

    def test_tab_preserved(self):
        """Tab (\x09) is a legitimate whitespace character — must be kept."""
        self.assertEqual(sanitize_string("col1\tcol2"), "col1\tcol2")

    def test_newline_preserved(self):
        """Newline (\x0a) is legitimate in multi-line text — must be kept."""
        self.assertIn("\n", sanitize_string("line1\nline2"))

    def test_carriage_return_preserved(self):
        self.assertIn("\r", sanitize_string("line1\r\nline2"))

    def test_unicode_string_unchanged(self):
        self.assertEqual(sanitize_string("héllo wörld 🎉"), "héllo wörld 🎉")

    def test_empty_string_unchanged(self):
        self.assertEqual(sanitize_string(""), "")

    def test_non_string_returned_as_is(self):
        self.assertEqual(sanitize_string(42), 42)
        self.assertIsNone(sanitize_string(None))


# ---------------------------------------------------------------------------
# mask_email
# ---------------------------------------------------------------------------

class TestMaskEmail(SimpleTestCase):

    def test_masks_local_part(self):
        masked = mask_email("alice@example.com")
        self.assertNotEqual(masked, "alice@example.com")
        self.assertIn("@example.com", masked)

    def test_keeps_domain_visible(self):
        masked = mask_email("bob@company.io")
        self.assertIn("@company.io", masked)

    def test_shows_first_two_chars_only(self):
        masked = mask_email("charlie@test.com")
        self.assertTrue(masked.startswith("ch"))

    def test_short_local_part_handled(self):
        masked = mask_email("x@test.com")
        self.assertIn("@test.com", masked)
        self.assertNotIn("None", masked)

    def test_invalid_email_returns_mask(self):
        self.assertEqual(mask_email("notanemail"), "***")

    def test_empty_string_returns_mask(self):
        self.assertEqual(mask_email(""), "***")

    def test_none_returns_mask(self):
        self.assertEqual(mask_email(None), "***")

    def test_raw_email_not_in_output(self):
        self.assertNotIn("alice", mask_email("alice@example.com"))


# ---------------------------------------------------------------------------
# assert_no_sensitive_fields
# ---------------------------------------------------------------------------

class TestAssertNoSensitiveFields(SimpleTestCase):

    def test_clean_fields_do_not_raise(self):
        try:
            assert_no_sensitive_fields(["id", "email", "title"], "TestSerializer")
        except AssertionError:
            self.fail("assert_no_sensitive_fields raised for clean fields")

    def test_password_field_raises(self):
        with self.assertRaises(AssertionError) as ctx:
            assert_no_sensitive_fields(["id", "password", "email"], "TestSerializer")
        self.assertIn("password", str(ctx.exception))
        self.assertIn("TestSerializer", str(ctx.exception))

    def test_resume_path_raises(self):
        with self.assertRaises(AssertionError):
            assert_no_sensitive_fields(["id", "resume_path"], "ApplicationSerializer")

    def test_recruiter_notes_raises(self):
        with self.assertRaises(AssertionError):
            assert_no_sensitive_fields(["id", "recruiter_notes"], "RecruiterSerializer")

    def test_multiple_sensitive_fields_all_named_in_error(self):
        with self.assertRaises(AssertionError) as ctx:
            assert_no_sensitive_fields(
                ["password", "resume_path", "id"], "LeakySerializer"
            )
        msg = str(ctx.exception)
        self.assertIn("password",    msg)
        self.assertIn("resume_path", msg)


# ---------------------------------------------------------------------------
# RequestIDMiddleware
# ---------------------------------------------------------------------------

class TestRequestIDMiddleware(TestCase):

    def _make_request(self, path="/", request_id_header=None):
        factory = RequestFactory()
        request = factory.get(path)
        if request_id_header:
            request.META["HTTP_X_REQUEST_ID"] = request_id_header
        return request

    def _wrap(self, request):
        """Run request through middleware and return (request, response)."""
        responses = []

        def get_response(req):
            from django.http import HttpResponse
            resp = HttpResponse("ok")
            responses.append(resp)
            return resp

        middleware = RequestIDMiddleware(get_response)
        response   = middleware(request)
        return request, response

    def test_request_id_set_on_request_object(self):
        request, _ = self._wrap(self._make_request())
        self.assertTrue(hasattr(request, "request_id"))
        self.assertIsNotNone(request.request_id)

    def test_request_id_in_response_header(self):
        _, response = self._wrap(self._make_request())
        self.assertIn("X-Request-ID", response)

    def test_client_supplied_uuid_is_honoured(self):
        client_id = "550e8400-e29b-41d4-a716-446655440000"
        request, response = self._wrap(self._make_request(request_id_header=client_id))
        self.assertEqual(request.request_id, client_id)
        self.assertEqual(response["X-Request-ID"], client_id)

    def test_invalid_client_id_replaced_with_new_uuid(self):
        request, response = self._wrap(self._make_request(request_id_header="not-a-uuid"))
        # Must be a valid UUID (not the garbage value)
        import uuid
        try:
            uuid.UUID(request.request_id)
        except ValueError:
            self.fail("request_id is not a valid UUID")
        self.assertNotEqual(request.request_id, "not-a-uuid")

    def test_different_requests_get_different_ids(self):
        req_a, _ = self._wrap(self._make_request())
        req_b, _ = self._wrap(self._make_request())
        self.assertNotEqual(req_a.request_id, req_b.request_id)


# ---------------------------------------------------------------------------
# SecurityHeadersMiddleware
# ---------------------------------------------------------------------------

class TestSecurityHeadersMiddleware(TestCase):

    def _run(self, extra_headers=None):
        from django.http import HttpResponse

        def get_response(req):
            resp = HttpResponse("ok")
            if extra_headers:
                for k, v in extra_headers.items():
                    resp[k] = v
            return resp

        factory    = RequestFactory()
        request    = factory.get("/")
        middleware = SecurityHeadersMiddleware(get_response)
        return middleware(request)

    def test_permissions_policy_header_added(self):
        response = self._run()
        self.assertIn("Permissions-Policy", response)

    def test_cross_origin_opener_policy_added(self):
        response = self._run()
        self.assertIn("Cross-Origin-Opener-Policy", response)

    def test_x_content_type_options_added(self):
        response = self._run()
        self.assertEqual(response.get("X-Content-Type-Options"), "nosniff")

    def test_server_header_stripped(self):
        response = self._run(extra_headers={"Server": "Apache/2.4.1"})
        self.assertNotIn("Server", response)

    def test_x_powered_by_stripped(self):
        response = self._run(extra_headers={"X-Powered-By": "Django"})
        self.assertNotIn("X-Powered-By", response)


# ---------------------------------------------------------------------------
# Health check endpoint
# ---------------------------------------------------------------------------

class TestHealthCheckEndpoint(TestCase):

    def test_health_endpoint_is_accessible(self):
        from unittest.mock import patch
        client = APIClient()
        with patch("core.health.HealthCheckView.get") as mock_get:
            from rest_framework.response import Response
            mock_get.return_value = Response({"status": "healthy", "checks": {}})
            response = client.get("/health/")
            # endpoint exists (not 404)
            self.assertNotEqual(response.status_code, 404)

    def test_health_endpoint_requires_no_auth(self):
        """Health check must be reachable by load balancers without any token."""
        from unittest.mock import patch
        from rest_framework.response import Response as DRFResponse
        client = APIClient()  # no credentials
        with patch("django.db.connection.ensure_connection"), \
             patch("django.core.cache.cache.set"), \
             patch("django.core.cache.cache.get", return_value="pong"), \
             patch("infrastructure.tasks.celery.app.control.ping"):
            response = client.get("/health/")
        self.assertNotEqual(response.status_code, 401)
        self.assertNotEqual(response.status_code, 403)
