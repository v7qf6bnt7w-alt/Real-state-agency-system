from rest_framework import serializers

from .models import FloorPlan, Lead, Media, Property
from .validators import validate_file_size, validate_hotspots, validate_property_media


class MediaSerializer(serializers.ModelSerializer):
    property = serializers.PrimaryKeyRelatedField(queryset=Property.objects.all())
    file = serializers.FileField(validators=[validate_property_media, validate_file_size], required=False)

    class Meta:
        model = Media
        fields = ["id", "property", "kind", "file", "external_url", "caption", "position"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        file_value = attrs.get("file", getattr(self.instance, "file", None))
        external_url = attrs.get("external_url", getattr(self.instance, "external_url", ""))
        if not file_value and not (kind == Media.Kind.VIDEO and external_url):
            raise serializers.ValidationError({"file": "Upload a file, or provide a video URL."})
        if external_url and kind != Media.Kind.VIDEO:
            raise serializers.ValidationError({"external_url": "External URLs are only supported for video media."})
        return attrs


class FloorPlanSerializer(serializers.ModelSerializer):
    property = serializers.PrimaryKeyRelatedField(queryset=Property.objects.all())
    image = serializers.FileField(validators=[validate_property_media, validate_file_size])
    hotspots = serializers.JSONField(validators=[validate_hotspots], required=False, default=list)

    class Meta:
        model = FloorPlan
        fields = ["id", "property", "title", "image", "hotspots", "created_at"]
        read_only_fields = ["id", "created_at"]


class PropertySerializer(serializers.ModelSerializer):
    media = MediaSerializer(many=True, read_only=True)
    floor_plans = FloorPlanSerializer(many=True, read_only=True)

    class Meta:
        model = Property
        fields = [
            "id", "title", "description", "property_type", "status", "price", "currency",
            "address", "city", "region", "country", "bedrooms", "bathrooms", "area_sqm",
            "year_built", "amenities", "is_published", "media", "floor_plans", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        return Property.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class LeadCreateSerializer(serializers.ModelSerializer):
    property_id = serializers.UUIDField(write_only=True)
    recaptcha_token = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Lead
        fields = ["id", "property_id", "first_name", "last_name", "email", "phone", "comments", "recaptcha_token"]
        read_only_fields = ["id"]

    def validate_property_id(self, value):
        if not Property.objects.filter(pk=value, is_published=True).exists():
            raise serializers.ValidationError("This listing is not available.")
        return value

    def create(self, validated_data):
        validated_data.pop("recaptcha_token", None)
        property_id = validated_data.pop("property_id")
        return Lead.objects.create(property_id=property_id, **validated_data)


class LeadAdminSerializer(serializers.ModelSerializer):
    property_title = serializers.CharField(source="property.title", read_only=True)

    class Meta:
        model = Lead
        fields = ["id", "property", "property_title", "first_name", "last_name", "email", "phone", "comments", "status", "created_at"]
        read_only_fields = ["id", "property", "property_title", "first_name", "last_name", "email", "phone", "comments", "created_at"]


class OTPStartSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class OTPVerifySerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254)
    code = serializers.RegexField(r"^\d{6}$")
