from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .forms import StaffChangeForm, StaffCreationForm
from .models import FloorPlan, Lead, LoginOTP, Media, Property, User

admin.site.site_header = "Estate North"
admin.site.site_title = "Estate North Staff"
admin.site.index_title = "Agency workspace"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = StaffChangeForm
    add_form = StaffCreationForm
    ordering = ["email"]
    list_display = ["email", "phone", "is_staff", "is_active"]
    search_fields = ["email", "phone", "first_name", "last_name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "phone")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "phone", "password1", "password2", "is_staff", "is_active")}),)
    filter_horizontal = ["groups", "user_permissions"]


class MediaInline(admin.TabularInline):
    model = Media
    extra = 0


class FloorPlanInline(admin.TabularInline):
    model = FloorPlan
    extra = 0


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ["title", "property_type", "status", "price", "city", "is_published"]
    list_filter = ["property_type", "status", "is_published", "city"]
    search_fields = ["title", "address", "city", "description"]
    inlines = [MediaInline, FloorPlanInline]


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ["first_name", "last_name", "email", "property", "status", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["first_name", "last_name", "email", "phone", "property__title"]
    list_editable = ["status"]
    readonly_fields = ["created_at"]


@admin.register(LoginOTP)
class LoginOTPAdmin(admin.ModelAdmin):
    list_display = ["user", "created_at", "expires_at", "attempts", "consumed_at"]
    readonly_fields = ["user", "code_hash", "created_at", "expires_at", "attempts", "consumed_at"]
