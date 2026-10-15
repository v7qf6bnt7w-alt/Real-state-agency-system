import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from .validators import validate_file_size, validate_hotspots, validate_property_media


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("A superuser must have staff and superuser privileges.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=32, blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)
    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["phone"], condition=~models.Q(phone=""), name="unique_nonempty_user_phone"),
        ]

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


class Property(models.Model):
    class PropertyType(models.TextChoices):
        APARTMENT = "apartment", "Apartment"
        HOUSE = "house", "House"
        COMMERCIAL = "commercial", "Commercial"

    class Status(models.TextChoices):
        FOR_SALE = "for_sale", "For Sale"
        FOR_RENT = "for_rent", "For Rent"
        SOLD = "sold", "Sold"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=180)
    description = models.TextField()
    property_type = models.CharField(max_length=20, choices=PropertyType.choices, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, db_index=True)
    price = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default="USD")
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=120, db_index=True)
    region = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)
    bedrooms = models.PositiveSmallIntegerField(default=0)
    bathrooms = models.PositiveSmallIntegerField(default=0)
    area_sqm = models.DecimalField(max_digits=9, decimal_places=2, validators=[MinValueValidator(0)])
    year_built = models.PositiveSmallIntegerField(null=True, blank=True)
    amenities = models.JSONField(default=list, blank=True)
    is_published = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "is_published", "price"]),
            models.Index(fields=["city", "bedrooms"]),
        ]

    def __str__(self):
        return self.title


class Media(models.Model):
    class Kind(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"
        BROCHURE = "brochure", "Brochure"

    property = models.ForeignKey(Property, related_name="media", on_delete=models.CASCADE)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    file = models.FileField(upload_to="properties/%Y/%m/", blank=True, validators=[validate_property_media, validate_file_size])
    external_url = models.URLField(blank=True)
    caption = models.CharField(max_length=180, blank=True)
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]


class FloorPlan(models.Model):
    property = models.ForeignKey(Property, related_name="floor_plans", on_delete=models.CASCADE)
    title = models.CharField(max_length=120, default="Floor plan")
    image = models.FileField(upload_to="floor-plans/%Y/%m/", validators=[validate_property_media, validate_file_size])
    hotspots = models.JSONField(default=list, blank=True, validators=[validate_hotspots])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]


class Lead(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        IN_PROGRESS = "in_progress", "In Progress"
        CLOSED = "closed", "Closed"

    property = models.ForeignKey(Property, related_name="leads", on_delete=models.PROTECT)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=32)
    comments = models.TextField(max_length=3000, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} — {self.property.title}"


class LoginOTP(models.Model):
    user = models.ForeignKey(User, related_name="login_otps", on_delete=models.CASCADE)
    code_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "expires_at", "consumed_at"])]
