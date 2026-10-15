from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrPhoneBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, email=None, **kwargs):
        identifier = email or username
        if not identifier or password is None:
            return None
        User = get_user_model()
        try:
            user = User.objects.get(Q(email__iexact=identifier) | Q(phone=identifier))
        except User.DoesNotExist:
            User().set_password(password)
            return None
        except User.MultipleObjectsReturned:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
