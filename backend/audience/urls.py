from django.urls import path

from audience import views

urlpatterns = [
    path("", views.AudienceListCreateView.as_view(), name="audience_list_create"),
    path("<int:pk>/", views.AudienceDetailView.as_view(), name="audience_detail"),
]
