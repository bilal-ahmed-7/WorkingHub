from django.urls import path

from companies import views

urlpatterns = [
    # Company Profile
    path("me/", views.CompanyDetailView.as_view(), name="company_detail"),
    # Dashboard Analytics
    path("dashboard-stats/", views.CompanyStatsView.as_view(), name="company_dashboard_stats"),
    # Worker Management
    path("workers/", views.CompanyWorkersListView.as_view(), name="company_workers_list"),
    path("workers/<int:pk>/", views.CompanyWorkerDeleteView.as_view(), name="company_worker_delete"),
]
