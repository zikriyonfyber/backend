import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("zeaipc")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "poll-weather-every-30-min": {
        "task": "weather.poll_all_locations",
        "schedule": crontab(minute="*/30"),
    },
    "expire-stale-subscriptions-hourly": {
        "task": "billing.expire_stale_subscriptions",
        "schedule": crontab(minute=0),
    },
    "roll-up-daily-usage": {
        "task": "billing.roll_up_daily_usage",
        "schedule": crontab(hour=0, minute=15),
    },
}
