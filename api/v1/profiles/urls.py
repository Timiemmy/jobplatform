"""
api/v1/profiles/urls.py

URL routes for the profiles domain under /api/v1/profiles/.
"""

from django.urls import path
from api.v1.profiles.views import MyProfileView

app_name = "profiles"

urlpatterns = [
    # Own profile — retrieve and update
    path("me/", MyProfileView.as_view(), name="my-profile"),
]
