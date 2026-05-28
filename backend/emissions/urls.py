from django.urls import path
from .views import EmissionListView, EmissionDetailView, EmissionScopeBreakdownView

urlpatterns = [
    path("",                    EmissionListView.as_view(),          name="emission-list"),
    path("<uuid:pk>/",          EmissionDetailView.as_view(),        name="emission-detail"),
    path("scope-breakdown/",    EmissionScopeBreakdownView.as_view(), name="scope-breakdown"),
]
