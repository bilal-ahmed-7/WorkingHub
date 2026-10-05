from django.urls import path

from audience import views

urlpatterns = [
    path("", views.AudienceListView.as_view(), name="audience_list"),
    path("<int:pk>/", views.AudienceDetailView.as_view(), name="audience_detail"),
]
