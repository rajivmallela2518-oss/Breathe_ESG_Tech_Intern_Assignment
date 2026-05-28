from django.urls import path
from .views import ReviewQueueView, ApproveView, RejectView

urlpatterns = [
    path("",                          ReviewQueueView.as_view(), name="review-queue"),
    path("<uuid:pk>/approve/",        ApproveView.as_view(),     name="review-approve"),
    path("<uuid:pk>/reject/",         RejectView.as_view(),      name="review-reject"),
]
