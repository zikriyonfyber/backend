from celery import shared_task


@shared_task(name="weather.poll_all_locations")
def poll_weather_task():
    from apps.weather.services import poll_all_locations
    poll_all_locations()
