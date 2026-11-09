from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from bookings.models import Booking, CustomerAccessChallenge, CustomerAccessSendAttempt


class Command(BaseCommand):
    help = "Anonymize completed bookings after five days and remove old customer OTP challenges."

    def handle(self, *args, **options):
        now = timezone.now()
        retention_cutoff = now - timedelta(days=5)
        expired = Booking.objects.filter(
            status=Booking.Status.COMPLETED,
            completed_at__lte=retention_cutoff,
            personal_data_anonymized_at__isnull=True,
        )
        count = 0
        for booking in expired.iterator():
            with transaction.atomic():
                locked = Booking.objects.select_for_update().get(pk=booking.pk)
                if locked.personal_data_anonymized_at or locked.completed_at is None or locked.completed_at > retention_cutoff:
                    continue
                locked.customer_name = "Former customer"
                locked.phone_number = ""
                locked.pickup_address = ""
                locked.pickup_landmark = ""
                locked.destination_address = ""
                locked.destination_landmark = ""
                locked.notes = ""
                locked.personal_data_anonymized_at = now
                locked.save(update_fields=[
                    "customer_name", "phone_number", "pickup_address", "pickup_landmark",
                    "destination_address", "destination_landmark", "notes",
                    "personal_data_anonymized_at", "updated_at",
                ])
                locked.otp_challenges.all().delete()
                locked.otp_send_attempts.all().delete()
                count += 1
        stale_challenges = CustomerAccessChallenge.objects.filter(created_at__lt=now - timedelta(days=1)).delete()[0]
        stale_send_attempts = CustomerAccessSendAttempt.objects.filter(created_at__lt=now - timedelta(days=30)).delete()[0]
        self.stdout.write(self.style.SUCCESS(
            f"Anonymized {count} completed booking(s); removed {stale_challenges} expired customer access record(s) and {stale_send_attempts} old OTP rate-limit record(s)."
        ))
