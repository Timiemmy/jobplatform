"""
tests/core/test_core.py

Tests for the core infrastructure layer:
  - StandardPageNumberPagination
  - custom_exception_handler response shape
  - Permission classes (role enforcement)
"""

from django.test import TestCase, RequestFactory
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from core.exceptions import (
    custom_exception_handler,
    ApplicationError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from core.pagination import StandardPageNumberPagination
from core.permissions import IsJobSeeker, IsRecruiter, IsOwnerOrAdmin
from tests.factories import make_job_seeker, make_recruiter, make_admin, make_user


# ---------------------------------------------------------------------------
# Exception handler tests
# ---------------------------------------------------------------------------

class TestCustomExceptionHandler(TestCase):

    def _get_response(self, exc):
        """Helper: run the exception through the custom handler."""
        context = {"view": None, "request": None}
        return custom_exception_handler(exc, context)

    def test_application_error_returns_correct_shape(self):
        exc = ApplicationError("Something broke.")
        response = self._get_response(exc)

        self.assertIsNotNone(response)
        self.assertIn("error", response.data)
        self.assertIn("message", response.data)
        self.assertIn("detail", response.data)
        self.assertIn("code", response.data)
        self.assertTrue(response.data["error"])

    def test_application_error_returns_400(self):
        exc = ApplicationError("Bad input.")
        response = self._get_response(exc)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_conflict_error_returns_409(self):
        exc = ConflictError("Already applied.")
        response = self._get_response(exc)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_forbidden_error_returns_403(self):
        exc = ForbiddenError("Not allowed.")
        response = self._get_response(exc)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_not_found_error_returns_404(self):
        exc = NotFoundError("Job not found.")
        response = self._get_response(exc)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_error_flag_is_always_true(self):
        for exc in [ApplicationError(), ConflictError(), ForbiddenError(), NotFoundError()]:
            response = self._get_response(exc)
            self.assertTrue(response.data["error"], f"Expected error=True for {type(exc)}")

    def test_validation_error_message_is_human_readable(self):
        from rest_framework.exceptions import ValidationError
        exc = ValidationError({"email": ["This field is required."]})
        response = self._get_response(exc)
        self.assertIn("Validation failed", response.data["message"])


# ---------------------------------------------------------------------------
# Pagination tests
# ---------------------------------------------------------------------------

class TestStandardPageNumberPagination(TestCase):

    def _make_paginator_response(self, items: list, page: int = 1, page_size: int = 10):
        """Helper: simulate a paginated response."""
        from rest_framework.request import Request
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/", {"page": page, "page_size": page_size})
        # Wrap in DRF Request
        drf_request = Request(request)

        paginator = StandardPageNumberPagination()
        paginator.request = drf_request
        paginator.page_size = page_size

        result = paginator.paginate_queryset(items, drf_request)
        return paginator.get_paginated_response(result)

    def test_response_has_required_envelope_fields(self):
        items = list(range(25))
        response = self._make_paginator_response(items)
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)

    def test_count_reflects_total_items(self):
        items = list(range(25))
        response = self._make_paginator_response(items)
        self.assertEqual(response.data["count"], 25)

    def test_results_length_matches_page_size(self):
        items = list(range(25))
        response = self._make_paginator_response(items, page=1, page_size=10)
        self.assertEqual(len(response.data["results"]), 10)

    def test_last_page_has_fewer_results(self):
        items = list(range(25))
        response = self._make_paginator_response(items, page=3, page_size=10)
        self.assertEqual(len(response.data["results"]), 5)

    def test_previous_is_none_on_first_page(self):
        items = list(range(25))
        response = self._make_paginator_response(items, page=1)
        self.assertIsNone(response.data["previous"])

    def test_next_is_none_on_last_page(self):
        items = list(range(10))
        response = self._make_paginator_response(items, page=1, page_size=10)
        self.assertIsNone(response.data["next"])


# ---------------------------------------------------------------------------
# Permission class tests
# ---------------------------------------------------------------------------

class TestIsJobSeekerPermission(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()

    def _make_request_with_user(self, user):
        request = self.factory.get("/")
        request.user = user
        return request

    def test_job_seeker_has_permission(self):
        user = make_job_seeker(email="seeker@perm.com")
        request = self._make_request_with_user(user)
        perm = IsJobSeeker()
        self.assertTrue(perm.has_permission(request, None))

    def test_recruiter_does_not_have_permission(self):
        user = make_recruiter(email="recruiter@perm.com")
        request = self._make_request_with_user(user)
        perm = IsJobSeeker()
        self.assertFalse(perm.has_permission(request, None))

    def test_unauthenticated_user_does_not_have_permission(self):
        from django.contrib.auth.models import AnonymousUser
        request = self.factory.get("/")
        request.user = AnonymousUser()
        perm = IsJobSeeker()
        self.assertFalse(perm.has_permission(request, None))


class TestIsRecruiterPermission(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()

    def _make_request_with_user(self, user):
        request = self.factory.get("/")
        request.user = user
        return request

    def test_recruiter_has_permission(self):
        user = make_recruiter(email="recruiter@perm.com")
        request = self._make_request_with_user(user)
        perm = IsRecruiter()
        self.assertTrue(perm.has_permission(request, None))

    def test_job_seeker_does_not_have_permission(self):
        user = make_job_seeker(email="seeker@perm.com")
        request = self._make_request_with_user(user)
        perm = IsRecruiter()
        self.assertFalse(perm.has_permission(request, None))


class TestIsOwnerOrAdminPermission(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.owner = make_job_seeker(email="owner@perm.com")
        self.other = make_job_seeker(email="other@perm.com")
        self.admin = make_admin(email="admin@perm.com")

    def _make_request_with_user(self, user, method="GET"):
        if method == "GET":
            request = self.factory.get("/")
        else:
            request = self.factory.patch("/")
        request.user = user
        return request

    def _make_obj_with_owner(self, owner):
        """Minimal object with an owner attribute."""
        class FakeObj:
            pass
        obj = FakeObj()
        obj.owner = owner
        return obj

    def test_owner_has_object_permission(self):
        obj = self._make_obj_with_owner(self.owner)
        request = self._make_request_with_user(self.owner)
        perm = IsOwnerOrAdmin()
        self.assertTrue(perm.has_object_permission(request, None, obj))

    def test_admin_has_object_permission(self):
        obj = self._make_obj_with_owner(self.owner)
        request = self._make_request_with_user(self.admin)
        perm = IsOwnerOrAdmin()
        self.assertTrue(perm.has_object_permission(request, None, obj))

    def test_non_owner_does_not_have_object_permission(self):
        obj = self._make_obj_with_owner(self.owner)
        request = self._make_request_with_user(self.other)
        perm = IsOwnerOrAdmin()
        self.assertFalse(perm.has_object_permission(request, None, obj))


# ---------------------------------------------------------------------------
# User model tests
# ---------------------------------------------------------------------------

class TestUserModel(TestCase):

    def test_str_includes_email_and_role(self):
        user = make_job_seeker(email="model@example.com")
        self.assertIn("model@example.com", str(user))
        self.assertIn("job_seeker", str(user))

    def test_is_job_seeker_property(self):
        user = make_job_seeker(email="seeker_prop@example.com")
        self.assertTrue(user.is_job_seeker)
        self.assertFalse(user.is_recruiter)

    def test_is_recruiter_property(self):
        user = make_recruiter(email="recruiter_prop@example.com")
        self.assertTrue(user.is_recruiter)
        self.assertFalse(user.is_job_seeker)

    def test_is_platform_admin_property(self):
        user = make_admin(email="admin_prop@example.com")
        self.assertTrue(user.is_platform_admin)

    def test_uuid_primary_key_is_not_integer(self):
        user = make_user(email="uuid_pk@example.com")
        self.assertNotIsInstance(user.id, int)

    def test_create_superuser_sets_admin_role(self):
        superuser = User.objects.create_superuser(
            email="super@example.com",
            password="StrongPass123!",
        )
        self.assertEqual(superuser.role, User.Role.ADMIN)
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)

    def test_email_is_unique_identifier_not_username(self):
        """User.USERNAME_FIELD must be 'email'."""
        self.assertEqual(User.USERNAME_FIELD, "email")

    def test_username_field_does_not_exist(self):
        user = make_user(email="nousername@example.com")
        self.assertFalse(hasattr(user, "username") and user.username is not None)
