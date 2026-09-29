from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from accounts import views

urlpatterns = [
    # Registration & Authentication
    path("register/", views.RegisterOwnerView.as_view(), name="register_owner"),
    path("login/", views.CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", views.LogoutView.as_view(), name="logout"),

    # Profile & Account Management
    path("me/", views.UserProfileView.as_view(), name="user_profile"),
    path("change-password/", views.ChangePasswordView.as_view(), name="change_password"),
]
