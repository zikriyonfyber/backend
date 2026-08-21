from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import IdentityChip
from apps.voip.services import provision_sip_number_for_chip


@receiver(post_save, sender=IdentityChip)
def ensure_sip_number(sender, instance: IdentityChip, **kwargs):
    if instance.status == IdentityChip.STATUS_ACTIVE and instance.subscriber_id:
        provision_sip_number_for_chip(instance)
