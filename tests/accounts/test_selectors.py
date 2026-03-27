"""
tests/accounts/test_selectors.py

Unit tests for apps/accounts/selectors.py.
Tests query functions directly — no HTTP involved.
"""

from django.test import TestCase

from apps.accounts.models import User
from apps.accounts.selectors import (
    get_user_by_id,
    get_user_by_email,
    get_all_users,
    get_users_by_role,
    user_exists_by_email,
)
from tests.factories import make_user, make_job_seeker, make_recruiter


class TestGetUserById(TestCase):

    def test_returns_user_when_found(self):
        user = make_user(email="byid@example.com")
        result = get_user_by_id(user_id=str(user.id))
        self.assertEqual(result, user)

    def test_raises_does_not_exist_for_unknown_id(self):
        import uuid
        with self.assertRaises(User.DoesNotExist):
            get_user_by_id(user_id=str(uuid.uuid4()))


class TestGetUserByEmail(TestCase):

    def test_returns_active_user(self):
        user = make_user(email="byemail@example.com")
        result = get_user_by_email(email="byemail@example.com")
        self.assertEqual(result, user)

    def test_raises_does_not_exist_for_inactive_user(self):
        make_user(email="inactive@example.com", is_active=False)
        with self.assertRaises(User.DoesNotExist):
            get_user_by_email(email="inactive@example.com")

    def test_raises_does_not_exist_for_unknown_email(self):
        with self.assertRaises(User.DoesNotExist):
            get_user_by_email(email="ghost@example.com")


class TestGetAllUsers(TestCase):

    def test_returns_only_active_users(self):
        make_user(email="active1@example.com", is_active=True)
        make_user(email="active2@example.com", is_active=True)
        make_user(email="inactive@example.com", is_active=False)

        users = get_all_users()
        emails = list(users.values_list("email", flat=True))

        self.assertIn("active1@example.com", emails)
        self.assertIn("active2@example.com", emails)
        self.assertNotIn("inactive@example.com", emails)

    def test_returns_queryset_not_list(self):
        from django.db.models import QuerySet
        result = get_all_users()
        self.assertIsInstance(result, QuerySet)


class TestGetUsersByRole(TestCase):

    def test_returns_only_users_with_given_role(self):
        make_job_seeker(email="seeker1@example.com")
        make_job_seeker(email="seeker2@example.com")
        make_recruiter(email="recruiter1@example.com")

        seekers = get_users_by_role(role=User.Role.JOB_SEEKER)
        seeker_emails = list(seekers.values_list("email", flat=True))

        self.assertIn("seeker1@example.com", seeker_emails)
        self.assertIn("seeker2@example.com", seeker_emails)
        self.assertNotIn("recruiter1@example.com", seeker_emails)

    def test_excludes_inactive_users(self):
        make_job_seeker(email="inactive_seeker@example.com", is_active=False)
        seekers = get_users_by_role(role=User.Role.JOB_SEEKER)
        emails = list(seekers.values_list("email", flat=True))
        self.assertNotIn("inactive_seeker@example.com", emails)


class TestUserExistsByEmail(TestCase):

    def test_returns_true_when_email_registered(self):
        make_user(email="exists@example.com")
        self.assertTrue(user_exists_by_email(email="exists@example.com"))

    def test_returns_false_for_unknown_email(self):
        self.assertFalse(user_exists_by_email(email="ghost@example.com"))

    def test_returns_true_even_for_inactive_user(self):
        # email uniqueness check must catch inactive users too
        make_user(email="inactive_exists@example.com", is_active=False)
        self.assertTrue(user_exists_by_email(email="inactive_exists@example.com"))
