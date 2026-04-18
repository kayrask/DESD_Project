from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, IntervalSchedule


class Command(BaseCommand):
    help = "Register Celery Beat periodic tasks"

    def handle(self, *args, **options):
        schedule_30m, _ = IntervalSchedule.objects.get_or_create(
            every=30,
            period=IntervalSchedule.MINUTES,
        )
        PeriodicTask.objects.update_or_create(
            name="Cleanup stale cart reservations",
            defaults={
                "interval": schedule_30m,
                "task": "api.tasks.cleanup_stale_reservations",
                "enabled": True,
            },
        )

        schedule_15m, _ = IntervalSchedule.objects.get_or_create(
            every=15,
            period=IntervalSchedule.MINUTES,
        )
        PeriodicTask.objects.update_or_create(
            name="Expire pending orders past 48h",
            defaults={
                "interval": schedule_15m,
                "task": "api.tasks.expire_pending_orders",
                "enabled": True,
            },
        )

        self.stdout.write(self.style.SUCCESS("Periodic tasks registered."))
