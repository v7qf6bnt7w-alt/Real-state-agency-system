import hashlib

from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import redirect

ADMIN_OTP_SESSION_KEY = "admin_otp_verified"


class AdminLoginRateLimitMiddleware:
    max_attempts = 5
    timeout = 15 * 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path != "/admin/login/" or request.method != "POST":
            return self.get_response(request)

        identifier = request.POST.get("username", "").strip().lower()
        source = f"{request.META.get('REMOTE_ADDR', '')}:{identifier}"
        key = "admin-login:" + hashlib.sha256(source.encode()).hexdigest()
        if cache.get(key, 0) >= self.max_attempts:
            return HttpResponse("Too many sign-in attempts. Please wait and try again.", status=429)

        response = self.get_response(request)
        if 300 <= response.status_code < 400:
            cache.delete(key)
        else:
            cache.add(key, 0, timeout=self.timeout)
            cache.incr(key)
        return response


class AdminOTPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.path.startswith("/admin/")
            and request.path != "/admin/logout/"
            and request.user.is_authenticated
            and request.user.is_staff
            and not request.session.get(ADMIN_OTP_SESSION_KEY)
        ):
            return redirect("admin-otp")
        return self.get_response(request)
