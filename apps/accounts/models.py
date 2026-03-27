from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import BaseModel


class UserManager(BaseUserManager):
    """
    Custom manager that makes email the unique identifier
    instead of username.
    """

    use_in_migrations = True

    def _create_user(self, email: str, password: str, **extra_fields):
        if not email:
            raise ValueError("Email address is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)




class User(BaseModel, AbstractUser):
    """
    Platform user model.

    Replaces username-based auth with email-based auth.
    Role determines what the user can do across the system.
    """

    class Role(models.TextChoices):
        JOB_SEEKER = "job_seeker", _("Job Seeker")
        RECRUITER = "recruiter", _("Recruiter")
        ADMIN = "admin", _("Admin")

    # Remove username — email is the identifier
    username = None

    email = models.EmailField(
        _("email address"),
        unique=True,
        db_index=True,
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.JOB_SEEKER,
        db_index=True,
    )
    is_active = models.BooleanField(default=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # email + password only for createsuperuser

    objects = UserManager()

    class Meta:
        db_table = "accounts_user"
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    

    def __str__(self) -> str:
        return f"{self.email} ({self.role})"

    # ---------------------------------------------------------------------------
    # Role helpers — used throughout the codebase, not raw string checks
    # ---------------------------------------------------------------------------

    @property
    def is_job_seeker(self) -> bool:
        return self.role == self.Role.JOB_SEEKER

    @property
    def is_recruiter(self) -> bool:
        return self.role == self.Role.RECRUITER

    @property
    def is_platform_admin(self) -> bool:
        return self.role == self.Role.ADMIN
