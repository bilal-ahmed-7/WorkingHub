from django.urls import path

from integrations import views

urlpatterns = [
    path("", views.IntegrationListCreateView.as_view(), name="integration_list_create"),
    path("public/<uuid:public_id>/", views.PublicIntegrationFormView.as_view(), name="integration_public_form"),
    path("<int:pk>/", views.IntegrationDetailView.as_view(), name="integration_detail"),
]