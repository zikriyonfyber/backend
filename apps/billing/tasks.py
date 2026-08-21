from celery import shared_task


@shared_task(name="billing.expire_stale_subscriptions")
def expire_stale_subscriptions_task():
    """Runs periodically (see config/celery.py beat schedule) to flip any
    Subscription whose expires_at has passed into STATUS_EXPIRED, so
    ChipAuthView's `data_authorized` reflects reality without relying on
    a check happening at request time alone."""
    from django.utils import timezone
    from apps.billing.models import Subscription

    Subscription.objects.filter(
        status=Subscription.STATUS_ACTIVE, expires_at__lt=timezone.now()
    ).update(status=Subscription.STATUS_EXPIRED)


@shared_task(name="billing.roll_up_daily_usage")
def roll_up_daily_usage_task():
    """Aggregates yesterday's AAASession rows into DailyUsageSummary for
    fast dashboard queries."""
    from datetime import timedelta
    from django.db.models import Count, Sum
    from django.utils import timezone
    from apps.accounts.models import AAASession
    from apps.billing.models import DailyUsageSummary

    yesterday = (timezone.now() - timedelta(days=1)).date()
    rows = (
        AAASession.objects.filter(started_at__date=yesterday)
        .values("chip_id")
        .annotate(up=Sum("bytes_uploaded"), down=Sum("bytes_downloaded"), n=Count("id"))
    )
    for row in rows:
        DailyUsageSummary.objects.update_or_create(
            chip_id=row["chip_id"],
            date=yesterday,
            defaults={
                "bytes_uploaded": row["up"] or 0,
                "bytes_downloaded": row["down"] or 0,
                "session_count": row["n"],
            },
        )
