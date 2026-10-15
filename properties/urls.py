from rest_framework.routers import DefaultRouter
from django.urls import path

from .views import FloorPlanUploadView, LeadAdminViewSet, LeadCreateView, MediaUploadView, PropertyViewSet, export_leads, logout, otp_start, otp_verify, platform_config

router = DefaultRouter()
router.register("properties", PropertyViewSet, basename="property")
router.register("media", MediaUploadView, basename="media")
router.register("floor-plans", FloorPlanUploadView, basename="floor-plan")
router.register("leads", LeadAdminViewSet, basename="lead-admin")

urlpatterns = [
    path("auth/otp/start/", otp_start, name="otp-start"),
    path("auth/otp/verify/", otp_verify, name="otp-verify"),
    path("auth/logout/", logout, name="auth-logout"),
    path("leads/public/", LeadCreateView.as_view(), name="lead-create"),
    path("leads/export/", export_leads, name="lead-export"),
    path("config/", platform_config, name="platform-config"),
] + router.urls
