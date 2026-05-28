from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("ingestion/", include("ingestion.urls")),
    path("emissions/", include("emissions.urls")),
    path("reviews/", include("reviews.urls")),
    path("audit/", include("audit.urls")),
]
