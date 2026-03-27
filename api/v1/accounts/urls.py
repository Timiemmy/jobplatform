"""
api/v1/accounts/urls.py

URL routes for the accounts domain under /api/v1/auth/.
"""

from django.urls import path

from api.v1.accounts.views import (
    RegisterView,
    LoginView,
    LogoutView,
    UserDetailView,
    CustomTokenRefreshView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("token/refresh/", CustomTokenRefreshView.as_view(), name="token-refresh"),
    path("user/", UserDetailView.as_view(), name="user-detail"),
]
