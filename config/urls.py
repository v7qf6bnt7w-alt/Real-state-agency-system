from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from properties.views import admin_otp

urlpatterns = [
    path("admin-otp/", admin_otp, name="admin-otp"),
    path("admin/", admin.site.urls),
    path("api/", include("properties.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="openapi-schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="openapi-schema"), name="swagger-ui"),
    path("", include("properties.web_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
