"""
infrastructure/storage/s3.py

Custom S3 storage backend for resume files.

Extends django-storages S3Boto3Storage with:
  - Private ACL enforcement (resumes are never public)
  - Short-lived pre-signed URL generation (5-minute TTL)
  - Namespaced storage location under resumes/

Used only in production. Development uses Django's default
FileSystemStorage via DEFAULT_FILE_STORAGE in dev settings.
"""

from storages.backends.s3boto3 import S3Boto3Storage


class ResumeStorage(S3Boto3Storage):
    """
    Private S3 storage for applicant resume files.

    - location:             All files stored under resumes/ prefix.
    - file_overwrite:       Disabled — UUID filenames prevent collisions.
    - default_acl:          private — objects never publicly accessible.
    - querystring_auth:     True — all URLs are pre-signed with TTL.
    - querystring_expire:   300s (5 minutes) — URLs expire quickly.
    - object_parameters:    No public cache headers on private files.
    """

    location           = "resumes"
    file_overwrite     = False
    default_acl        = "private"
    querystring_auth   = True
    querystring_expire = 300        # seconds — match AWS_QUERYSTRING_EXPIRE

    def get_object_parameters(self, name: str) -> dict:
        params = super().get_object_parameters(name)
        # Private files must not be cached by browsers or CDNs
        params["CacheControl"] = "no-cache, no-store, must-revalidate"
        return params
