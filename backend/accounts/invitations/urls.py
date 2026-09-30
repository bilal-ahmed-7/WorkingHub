from django.urls import path

from accounts.invitations import views

urlpatterns = [
    # Company Owner Invitation Management
    path("", views.InvitationListView.as_view(), name="invitation_list"),
    path("send/", views.SendInvitationView.as_view(), name="send_invitation"),
    path("revoke/<str:token>/", views.RevokeInvitationView.as_view(), name="revoke_invitation"),

    # Worker Acceptance Flow
    path("validate/<str:token>/", views.ValidateInvitationView.as_view(), name="validate_invitation"),
    path("accept/", views.AcceptInvitationView.as_view(), name="accept_invitation"),
]
