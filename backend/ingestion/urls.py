from django.urls import path
from .views import (
    UploadView,
    BatchListView,
    BatchDetailView,
    BatchRowsView,
    DashboardSummaryView,
)

urlpatterns = [
    path("upload/",                       UploadView.as_view(),          name="upload"),
    path("batches/",                      BatchListView.as_view(),        name="batch-list"),
    path("batches/<uuid:pk>/",            BatchDetailView.as_view(),      name="batch-detail"),
    path("batches/<uuid:pk>/rows/",       BatchRowsView.as_view(),        name="batch-rows"),
    path("summary/",                      DashboardSummaryView.as_view(), name="dashboard-summary"),
]
