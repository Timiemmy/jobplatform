"""
tests/accounts/test_services.py

Unit tests for apps/accounts/services.py.

Tests exercise the service functions directly — no HTTP layer involved.
Each test is isolated, uses the test database, and tears down after itself.
"""

import pytest
from django.test import TestCase

from apps.accounts.models import User
from apps.accounts.services import register_user, deactivate_user, change_user_role
from tests.factories import make_user, make_admin, make_recruiter


class TestRegisterUser(TestCase):
    """Tests for the register_user() service function."""

    def test_registers_job_seeker_successfully(self):
        user = register_user(
            email="seeker@example.com",
            password="StrongPass123!",
            first_name="Jane",
            last_name="Doe",
            role=User.Role.JOB_SEEKER,
        )

        self.assertIsInstance(user, User)
        self.assertEqual(user.email, "seeker@example.com")
        self.assertEqual(user.role, User.Role.JOB_SEEKER)
        self.assertEqual(user.first_name, "Jane")
        self.assertEqual(user.last_name, "Doe")
        self.assertTrue(user.is_active)

    def test_registers_recruiter_successfully(self):
        user = register_user(
            email="recruiter@example.com",
            password="StrongPass123!",
            first_name="Bob",
            last_name="Smith",
            role=User.Role.RECRUITER,
        )

        self.assertEqual(user.role, User.Role.RECRUITER)

    def test_password_is_hashed_not_stored_plaintext(self):
        user = register_user(
            email="hashed@example.com",
            password="PlainPassword99!",
            first_name="A",
            last_name="B",
            role=User.Role.JOB_SEEKER,
        )

        # Password must never be stored as plain text
        self.assertNotEqual(user.password, "PlainPassword99!")
        self.assertTrue(user.check_password("PlainPassword99!"))

    def test_email_is_persisted_to_database(self):
        register_user(
            email="dbcheck@example.com",
            password="StrongPass123!",
            first_name="A",
            last_name="B",
            role=User.Role.JOB_SEEKER,
        )

        self.assertTrue(User.objects.filter(email="dbcheck@example.com").exists())

    def test_raises_value_error_for_invalid_role(self):
        with self.assertRaises(ValueError) as ctx:
            register_user(
                email="invalid@example.com",
                password="StrongPass123!",
                first_name="A",
                last_name="B",
                role="hacker",
            )
        self.assertIn("Invalid role", str(ctx.exception))

    def test_raises_value_error_when_admin_role_self_assigned(self):
        with self.assertRaises(ValueError) as ctx:
            register_user(
                email="admin@example.com",
                password="StrongPass123!",
                first_name="A",
                last_name="B",
                role=User.Role.ADMIN,
            )
        self.assertIn("admin role cannot be assigned", str(ctx.exception))

    def test_duplicate_email_raises_integrity_error(self):
        from django.db import IntegrityError

        register_user(
            email="duplicate@example.com",
            password="StrongPass123!",
            first_name="A",
            last_name="B",
            role=User.Role.JOB_SEEKER,
        )

        with self.assertRaises(IntegrityError):
            register_user(
                email="duplicate@example.com",
                password="AnotherPass123!",
                first_name="C",
                last_name="D",
                role=User.Role.JOB_SEEKER,
            )

    def test_uuid_primary_key_is_assigned(self):
        user = register_user(
            email="uuid@example.com",
            password="StrongPass123!",
            first_name="A",
            last_name="B",
            role=User.Role.JOB_SEEKER,
        )
        # UUID — not an integer, not None
        self.assertIsNotNone(user.id)
        self.assertNotIsInstance(user.id, int)

    def test_profile_auto_created_via_signal(self):
        """
        Registering a user must auto-create a Profile via the post_save signal.
        Tests the accounts → profiles signal integration.
        """
        from apps.profiles.models import Profile

        user = register_user(
            email="profile_signal@example.com",
            password="StrongPass123!",
            first_name="A",
            last_name="B",
            role=User.Role.JOB_SEEKER,
        )

        self.assertTrue(Profile.objects.filter(user=user).exists())


class TestDeactivateUser(TestCase):
    """Tests for the deactivate_user() service function."""

    def test_sets_is_active_false(self):
        user = make_user(email="active@example.com")
        self.assertTrue(user.is_active)

        deactivated = deactivate_user(user=user)

        self.assertFalse(deactivated.is_active)

    def test_deactivated_user_still_exists_in_database(self):
        user = make_user(email="softdelete@example.com")
        deactivate_user(user=user)

        # Record must still exist — this is a soft delete
        self.assertTrue(User.objects.filter(email="softdelete@example.com").exists())

    def test_returns_user_instance(self):
        user = make_user(email="return@example.com")
        result = deactivate_user(user=user)
        self.assertIsInstance(result, User)


class TestChangeUserRole(TestCase):
    """Tests for the change_user_role() service function."""

    def test_admin_can_change_role(self):
        admin = make_admin(email="admin@example.com")
        user = make_job_seeker(email="seeker@example.com")

        updated = change_user_role(user=user, new_role=User.Role.RECRUITER, performed_by=admin)

        self.assertEqual(updated.role, User.Role.RECRUITER)

    def test_non_admin_cannot_change_role(self):
        recruiter = make_recruiter(email="recruiter@example.com")
        seeker = make_job_seeker(email="seeker2@example.com")

        with self.assertRaises(PermissionError):
            change_user_role(user=seeker, new_role=User.Role.RECRUITER, performed_by=recruiter)

    def test_invalid_role_raises_value_error(self):
        admin = make_admin(email="admin2@example.com")
        user = make_job_seeker(email="seeker3@example.com")

        with self.assertRaises(ValueError):
            change_user_role(user=user, new_role="super_hacker", performed_by=admin)

    def test_role_change_is_persisted(self):
        admin = make_admin(email="admin3@example.com")
        user = make_job_seeker(email="seeker4@example.com")

        change_user_role(user=user, new_role=User.Role.RECRUITER, performed_by=admin)

        user.refresh_from_db()
        self.assertEqual(user.role, User.Role.RECRUITER)
