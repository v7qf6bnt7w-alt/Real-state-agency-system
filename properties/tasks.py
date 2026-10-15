from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

from .models import Lead


@shared_task
def notify_new_lead(lead_id):
    lead = Lead.objects.select_related("property").get(pk=lead_id)
    recipients = list(settings.ADMINS and [email for _, email in settings.ADMINS] or [])
    if recipients:
        send_mail(
            f"New inquiry: {lead.property.title}",
            f"{lead.first_name} {lead.last_name} ({lead.email}, {lead.phone})\n\n{lead.comments}",
            settings.DEFAULT_FROM_EMAIL,
            recipients,
            fail_silently=False,
        )
