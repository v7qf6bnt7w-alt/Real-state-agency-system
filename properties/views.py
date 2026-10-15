import csv
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from rest_framework import generics, permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.exceptions import Throttled, ValidationError
from django_filters import rest_framework as filters
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework import serializers as drf_serializers
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer

from .models import FloorPlan, Lead, Media, Property
from .serializers import (
    LeadAdminSerializer,
    LeadCreateSerializer,
    OTPStartSerializer,
    OTPVerifySerializer,
    FloorPlanSerializer,
    MediaSerializer,
    PropertySerializer,
)
from .services import issue_login_code, verify_login_code, verify_recaptcha
from .tasks import notify_new_lead
from .forms import OTPCodeForm
from .middleware import ADMIN_OTP_SESSION_KEY

logger = logging.getLogger(__name__)
User = get_user_model()


def _csv_cell(value):
    text = str(value or "")
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


class PropertyFilter(filters.FilterSet):
    min_price = filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = filters.NumberFilter(field_name="price", lookup_expr="lte")
    min_bedrooms = filters.NumberFilter(field_name="bedrooms", lookup_expr="gte")
    min_bathrooms = filters.NumberFilter(field_name="bathrooms", lookup_expr="gte")

    class Meta:
        model = Property
        fields = ["property_type", "status", "city", "bedrooms", "bathrooms", "currency"]


class OTPThrottle(AnonRateThrottle):
    scope = "otp"


class LeadThrottle(AnonRateThrottle):
    scope = "lead"


@extend_schema(
    request=OTPStartSerializer,
    responses={
        200: inline_serializer(name="OTPStartResponse", fields={"detail": drf_serializers.CharField()}),
        401: inline_serializer(name="OTPStartError", fields={"detail": drf_serializers.CharField()}),
    },
    summary="Start staff OTP sign-in",
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
@throttle_classes([OTPThrottle])
def otp_start(request):
    serializer = OTPStartSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    identifier = serializer.validated_data["identifier"].strip()
    user = User.objects.filter(Q(email__iexact=identifier) | Q(phone=identifier), is_active=True, is_staff=True).first()
    authenticated = authenticate(request, email=user.email if user else identifier, password=serializer.validated_data["password"])
    if not user or authenticated is None or authenticated.pk != user.pk:
        return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)
    issue_login_code(user)
    return Response({"detail": "If the credentials are valid, a verification code was sent to your registered contact."})


@extend_schema(
    request=OTPVerifySerializer,
    responses={
        200: inline_serializer(
            name="OTPVerifyResponse",
            fields={
                "token": drf_serializers.CharField(),
                "expires_at": drf_serializers.DateTimeField(),
                "user": inline_serializer(
                    name="OTPVerifyUser",
                    fields={"email": drf_serializers.EmailField(), "first_name": drf_serializers.CharField()},
                ),
            },
        ),
        400: inline_serializer(name="OTPVerifyError", fields={"detail": drf_serializers.CharField()}),
    },
    summary="Verify staff OTP",
)
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
@throttle_classes([OTPThrottle])
def otp_verify(request):
    serializer = OTPVerifySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    identifier = serializer.validated_data["identifier"].strip()
    user = User.objects.filter(Q(email__iexact=identifier) | Q(phone=identifier), is_active=True, is_staff=True).first()
    if not user:
        return Response({"detail": "Invalid or expired verification code."}, status=status.HTTP_400_BAD_REQUEST)
    verify_login_code(user, serializer.validated_data["code"])
    Token.objects.filter(user=user).delete()
    token = Token.objects.create(user=user)
    expires_at = token.created + timedelta(hours=settings.API_TOKEN_TTL_HOURS)
    return Response({
        "token": token.key,
        "expires_at": expires_at,
        "user": {"email": user.email, "first_name": user.first_name},
    })


@extend_schema(request=None, responses={204: None}, summary="Revoke the current staff API token")
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def logout(request):
    request.auth.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


class PropertyViewSet(viewsets.ModelViewSet):
    serializer_class = PropertySerializer
    lookup_field = "pk"
    ordering_fields = ["created_at", "price", "area_sqm"]
    filterset_class = PropertyFilter
    search_fields = ["title", "description", "city", "region", "address"]

    def get_queryset(self):
        queryset = Property.objects.prefetch_related("media", "floor_plans")
        if self.request.user and self.request.user.is_staff:
            return queryset
        queryset = queryset.filter(is_published=True)
        return queryset

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def perform_create(self, serializer):
        serializer.save()


class LeadCreateView(generics.CreateAPIView):
    serializer_class = LeadCreateSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LeadThrottle]

    def perform_create(self, serializer):
        verify_recaptcha(
            serializer.validated_data.get("recaptcha_token", ""),
            self.request.META.get("REMOTE_ADDR"),
        )
        lead = serializer.save()
        try:
            notify_new_lead.delay(lead.pk)
        except Exception:
            logger.exception("The lead was saved, but its notification could not be queued (lead=%s).", lead.pk)


class LeadAdminViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LeadAdminSerializer
    permission_classes = [permissions.IsAdminUser]
    filterset_fields = ["status", "property"]
    search_fields = ["first_name", "last_name", "email", "phone", "property__title"]
    ordering_fields = ["created_at", "status"]

    def get_queryset(self):
        return Lead.objects.select_related("property")

    @action(detail=True, methods=["patch"])
    def status(self, request, pk=None):
        lead = self.get_object()
        new_status = request.data.get("status")
        if new_status not in Lead.Status.values:
            return Response({"status": "Choose a valid lead status."}, status=status.HTTP_400_BAD_REQUEST)
        lead.status = new_status
        lead.save(update_fields=["status"])
        return Response(self.get_serializer(lead).data)


@extend_schema(
    responses={(200, "text/csv"): OpenApiTypes.BINARY},
    summary="Export filtered leads as CSV",
)
@api_view(["GET"])
@permission_classes([permissions.IsAdminUser])
def export_leads(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="leads.csv"'
    writer = csv.writer(response)
    writer.writerow(["ID", "Property", "First name", "Last name", "Email", "Phone", "Comments", "Status", "Created"])
    queryset = Lead.objects.select_related("property").order_by("-created_at")
    status_filter = request.query_params.get("status")
    if status_filter:
        if status_filter not in Lead.Status.values:
            return Response({"status": "Choose a valid lead status."}, status=status.HTTP_400_BAD_REQUEST)
        queryset = queryset.filter(status=status_filter)
    for lead in queryset.iterator():
        writer.writerow([
            lead.pk,
            *(_csv_cell(value) for value in (
                lead.property.title, lead.first_name, lead.last_name, lead.email,
                lead.phone, lead.comments, lead.status,
            )),
            lead.created_at.isoformat(),
        ])
    return response


@extend_schema(
    responses=inline_serializer(
        name="PlatformConfigResponse",
        fields={
            "whatsapp_number": drf_serializers.CharField(allow_blank=True),
            "recaptcha_required": drf_serializers.BooleanField(),
            "recaptcha_site_key": drf_serializers.CharField(allow_blank=True),
        },
    ),
    summary="Public site configuration",
)
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def platform_config(request):
    return Response({
        "whatsapp_number": settings.WHATSAPP_NUMBER,
        "recaptcha_required": settings.RECAPTCHA_REQUIRED,
        "recaptcha_site_key": settings.RECAPTCHA_SITE_KEY,
    })


def admin_otp(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return HttpResponse(status=403)
    if not request.session.get("admin_otp_started"):
        try:
            issue_login_code(request.user)
        except Throttled as exc:
            return HttpResponse(str(exc.detail), status=429)
        request.session["admin_otp_started"] = True
    form = OTPCodeForm(request.POST or None)
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            verify_login_code(request.user, form.cleaned_data["code"])
        except ValidationError:
            error = "That code is invalid or expired. Please try again."
        except Throttled as exc:
            return HttpResponse(str(exc.detail), status=429)
        else:
            request.session[ADMIN_OTP_SESSION_KEY] = True
            request.session.pop("admin_otp_started", None)
            return redirect("/admin/")

    return render(request, "admin_otp.html", {"form": form, "error": error})


class MediaUploadView(viewsets.ModelViewSet):
    serializer_class = MediaSerializer
    permission_classes = [permissions.IsAdminUser]

    queryset = Media.objects.select_related("property").all()
    filterset_fields = ["property", "kind"]
    ordering_fields = ["position", "created_at"]


class FloorPlanUploadView(viewsets.ModelViewSet):
    serializer_class = FloorPlanSerializer
    permission_classes = [permissions.IsAdminUser]

    queryset = FloorPlan.objects.select_related("property").all()
    filterset_fields = ["property"]
