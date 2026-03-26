from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, IntervalSchedule


class Command(BaseCommand):
    help = "Register Celery Beat periodic tasks"

    def handle(self, *args, **options):
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=30,
            period=IntervalSchedule.MINUTES,
        )
        PeriodicTask.objects.update_or_create(
            name="Cleanup stale cart reservations",
            defaults={
                "interval": schedule,
                "task": "api.tasks.cleanup_stale_reservations",
                "enabled": True,
            },
        )
        self.stdout.write(self.style.SUCCESS("Periodic tasks registered."))
