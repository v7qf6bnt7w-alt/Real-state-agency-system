import re
from decimal import Decimal
from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import authenticate, get_user_model
from django.core.cache import cache
from django.core import mail
from django.utils import timezone
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import Throttled
from rest_framework.test import APIClient

from .models import Lead, Property
from .services import issue_login_code

User = get_user_model()


def make_property(**overrides):
    values = {
        "title": "Garden House",
        "description": "A quiet home with a leafy garden.",
        "property_type": Property.PropertyType.HOUSE,
        "status": Property.Status.FOR_SALE,
        "price": Decimal("425000"),
        "currency": "USD",
        "address": "12 Garden Lane",
        "city": "Northport",
        "region": "Coast",
        "bedrooms": 3,
        "bathrooms": 2,
        "area_sqm": Decimal("148"),
        "amenities": ["garden", "parking"],
        "is_published": True,
    }
    values.update(overrides)
    return Property.objects.create(**values)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RealEstateAPITests(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox.clear()
        self.client = APIClient()
        self.property = make_property()

    def test_public_catalog_only_returns_published_properties_and_filters(self):
        make_property(title="Private Draft", is_published=False, city="Northport")
        make_property(title="Town Apartment", property_type=Property.PropertyType.APARTMENT, city="Southport", price=300000)

        response = self.client.get("/api/properties/", {"min_price": "400000", "min_bedrooms": "2", "search": "Garden"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Garden House")

    def test_public_catalog_filters_by_bathrooms(self):
        make_property(title="One Bath Flat", bathrooms=1)

        response = self.client.get("/api/properties/", {
            "min_bathrooms": "2",
            "min_price": "400000",
            "max_price": "500000",
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Garden House")

    def test_catalog_exposes_selectable_price_bedroom_and_bathroom_filters(self):
        response = self.client.get("/")
        self.assertContains(response, 'name="min_price"')
        self.assertContains(response, 'name="max_price"')
        self.assertContains(response, 'name="min_bedrooms"')
        self.assertContains(response, 'name="min_bathrooms"')
        self.assertContains(response, '$1.5m max')
        self.assertContains(response, '5+ baths')

    def test_invalid_price_filter_returns_validation_error(self):
        response = self.client.get("/api/properties/", {"min_price": "not-a-price"})
        self.assertEqual(response.status_code, 400)

    def test_public_lead_submission_creates_new_inquiry(self):
        response = self.client.post("/api/leads/public/", {
            "property_id": str(self.property.pk),
            "first_name": "Sam",
            "last_name": "Rivera",
            "email": "sam@example.com",
            "phone": "+15551234567",
            "comments": "Could I arrange a viewing?",
        }, format="json")

        self.assertEqual(response.status_code, 201)
        lead = Lead.objects.get(pk=response.data["id"])
        self.assertEqual(lead.status, Lead.Status.NEW)
        self.assertEqual(lead.property, self.property)

    def test_staff_property_create_requires_token_and_staff_role(self):
        response = self.client.post("/api/properties/", {"title": "Unauthorized"}, format="json")
        self.assertEqual(response.status_code, 401)

        agent = User.objects.create_user("agent@example.com", "A-long-password-123", is_staff=True)
        token = Token.objects.create(user=agent)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.post("/api/properties/", {
            "title": "New Apartment",
            "description": "A bright apartment.",
            "property_type": "apartment",
            "status": "for_sale",
            "price": "320000",
            "currency": "USD",
            "address": "8 River Road",
            "city": "Northport",
            "bedrooms": 2,
            "bathrooms": 1,
            "area_sqm": "90",
            "is_published": True,
        }, format="json")
        self.assertEqual(response.status_code, 201)

    def test_otp_password_then_code_returns_staff_token_and_is_single_use(self):
        staff = User.objects.create_user("staff@example.com", "A-long-password-123", is_staff=True)

        response = self.client.post("/api/auth/otp/start/", {
            "identifier": staff.email,
            "password": "A-long-password-123",
        }, format="json")

        self.assertEqual(response.status_code, 200)
        code = re.search(r"\b\d{6}\b", mail.outbox[-1].body).group()
        verify = self.client.post("/api/auth/otp/verify/", {"identifier": staff.email, "code": code}, format="json")
        self.assertEqual(verify.status_code, 200)
        self.assertTrue(Token.objects.filter(user=staff, key=verify.data["token"]).exists())
        self.assertIn("expires_at", verify.data)
        replay = self.client.post("/api/auth/otp/verify/", {"identifier": staff.email, "code": code}, format="json")
        self.assertEqual(replay.status_code, 400)

    def test_api_token_expiry_and_logout(self):
        staff = User.objects.create_user("token-staff@example.com", "A-long-password-123", is_staff=True)
        token = Token.objects.create(user=staff)
        Token.objects.filter(pk=token.pk).update(created=timezone.now() - timedelta(hours=13))
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        expired = self.client.get("/api/properties/")
        self.assertEqual(expired.status_code, 401)
        self.assertFalse(Token.objects.filter(pk=token.pk).exists())

        new_token = Token.objects.create(user=staff)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {new_token.key}")
        logged_out = self.client.post("/api/auth/logout/")
        self.assertEqual(logged_out.status_code, 204)
        self.assertFalse(Token.objects.filter(pk=new_token.pk).exists())

    def test_staff_can_begin_otp_sign_in_with_phone_number(self):
        staff = User.objects.create_user("phone-staff@example.com", "A-long-password-123", phone="+15550001111", is_staff=True)
        self.assertEqual(authenticate(username=staff.phone, password="A-long-password-123"), staff)

        sms_response = Mock()
        with (
            override_settings(SMS_PROVIDER_URL="https://sms.example.test/send"),
            patch("properties.services.requests.post", return_value=sms_response) as send_sms,
        ):
            response = self.client.post("/api/auth/otp/start/", {
                "identifier": staff.phone,
                "password": "A-long-password-123",
            }, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(mail.outbox)
        self.assertEqual(send_sms.call_args.kwargs["json"]["to"], staff.phone)

    def test_staff_otp_delivery_is_rate_limited_per_account(self):
        staff = User.objects.create_user("rate-staff@example.com", "A-long-password-123", is_staff=True)

        with patch("properties.services.send_login_code"):
            for _ in range(5):
                issue_login_code(staff)
            with self.assertRaises(Throttled):
                issue_login_code(staff)

    def test_staff_can_upload_and_delete_listing_media(self):
        agent = User.objects.create_user("agent@example.com", "A-long-password-123", is_staff=True)
        token = Token.objects.create(user=agent)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        upload = SimpleUploadedFile("front.jpg", b"not-empty", content_type="image/jpeg")

        response = self.client.post("/api/media/", {
            "property": str(self.property.pk),
            "kind": "image",
            "file": upload,
            "caption": "Front elevation",
        }, format="multipart")

        self.assertEqual(response.status_code, 201)
        deleted = self.client.delete(f"/api/media/{response.data['id']}/")
        self.assertEqual(deleted.status_code, 204)

    def test_admin_requires_otp_after_password_authentication(self):
        admin = User.objects.create_superuser("admin@example.com", "A-long-password-123")
        self.client.force_login(admin)

        response = self.client.get("/admin/")
        self.assertRedirects(response, "/admin-otp/", fetch_redirect_response=False)
        challenge = self.client.get("/admin-otp/")
        self.assertEqual(challenge.status_code, 200)
        code = re.search(r"\b\d{6}\b", mail.outbox[-1].body).group()
        verified = self.client.post("/admin-otp/", {"code": code})
        self.assertRedirects(verified, "/admin/", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        admin_page = self.client.get("/admin/")
        self.assertContains(admin_page, "estate-admin-card")
        self.assertContains(admin_page, "PROPERTY STUDIO")
        self.assertNotContains(admin_page, "Django administration")

    def test_admin_password_login_is_rate_limited(self):
        for _ in range(5):
            response = self.client.post("/admin/login/", {"username": "unknown@example.com", "password": "wrong"})
            self.assertEqual(response.status_code, 200)
        limited = self.client.post("/admin/login/", {"username": "unknown@example.com", "password": "wrong"})
        self.assertEqual(limited.status_code, 429)
