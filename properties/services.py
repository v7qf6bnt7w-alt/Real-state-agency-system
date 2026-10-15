import logging
import secrets
from datetime import timedelta

import requests
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import Throttled, ValidationError

from .models import LoginOTP

logger = logging.getLogger(__name__)


def send_login_code(user, code):
    subject = "Your Estate North sign-in code"
    message = f"Your verification code is {code}. It expires in 10 minutes."
    if user.email:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
    if user.phone:
        if settings.SMS_PROVIDER_URL:
            response = requests.post(
                settings.SMS_PROVIDER_URL,
                json={"to": user.phone, "message": message},
                headers={"Authorization": f"Bearer {settings.SMS_PROVIDER_TOKEN}"} if settings.SMS_PROVIDER_TOKEN else {},
                timeout=5,
            )
            response.raise_for_status()
        elif settings.DEBUG:
            logger.info("Development SMS mock for %s: %s", user.phone, message)
        else:
            raise RuntimeError("An SMS provider must be configured before sending phone OTPs.")


def issue_login_code(user):
    send_limit_key = f"otp-send-user:{user.pk}"
    if cache.get(send_limit_key, 0) >= 5:
        raise Throttled(detail="Too many verification codes requested. Try again later.", wait=3600)
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = timezone.now()
    LoginOTP.objects.filter(user=user, consumed_at__isnull=True).update(consumed_at=now)
    challenge = LoginOTP.objects.create(
        user=user,
        code_hash=make_password(code),
        expires_at=now + timedelta(minutes=10),
    )
    try:
        send_login_code(user, code)
    except Exception:
        challenge.delete()
        logger.exception("Could not deliver the staff sign-in code.")
        raise
    cache.add(send_limit_key, 0, timeout=3600)
    cache.incr(send_limit_key)


@transaction.atomic
def verify_login_code(user, code):
    attempt_key = f"otp-verify-user:{user.pk}"
    if cache.get(attempt_key, 0) >= 10:
        raise Throttled(detail="Too many verification attempts. Try again later.", wait=3600)
    now = timezone.now()
    challenge = LoginOTP.objects.filter(
        user=user, consumed_at__isnull=True, expires_at__gt=now
    ).select_for_update().order_by("-created_at").first()
    if challenge is None or challenge.attempts >= 5:
        cache.add(attempt_key, 0, timeout=3600)
        cache.incr(attempt_key)
        raise ValidationError({"detail": "Invalid or expired verification code."})
    challenge.attempts += 1
    if not check_password(code, challenge.code_hash):
        challenge.save(update_fields=["attempts"])
        cache.add(attempt_key, 0, timeout=3600)
        cache.incr(attempt_key)
        raise ValidationError({"detail": "Invalid or expired verification code."})
    challenge.consumed_at = now
    challenge.save(update_fields=["attempts", "consumed_at"])
    cache.delete(attempt_key)


def verify_recaptcha(token, remote_ip=None):
    if not settings.RECAPTCHA_REQUIRED:
        return
    if not settings.RECAPTCHA_SECRET_KEY:
        raise ValidationError({"recaptcha_token": "reCAPTCHA is not configured."})
    try:
        response = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": settings.RECAPTCHA_SECRET_KEY, "response": token, "remoteip": remote_ip},
            timeout=4,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException:
        logger.exception("reCAPTCHA verification service is unavailable.")
        raise ValidationError({"recaptcha_token": "Verification is temporarily unavailable."})
    if not result.get("success") or result.get("action") != "lead" or result.get("score", 0) < 0.5:
        raise ValidationError({"recaptcha_token": "Please complete the verification challenge."})
