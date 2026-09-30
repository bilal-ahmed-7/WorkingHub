from django.urls import path

from integrations import views

urlpatterns = [
    path("", views.IntegrationListCreateView.as_view(), name="integration_list_create"),
    path("public/<uuid:public_id>/", views.PublicIntegrationFormView.as_view(), name="integration_public_form"),
    path("public/<uuid:public_id>/submit/", views.PublicIntegrationSubmissionView.as_view(), name="integration_public_submit"),
    path("<int:pk>/logs/", views.IntegrationSubmissionLogView.as_view(), name="integration_logs"),
    path("<int:pk>/", views.IntegrationDetailView.as_view(), name="integration_detail"),
]