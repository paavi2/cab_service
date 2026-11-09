import django.contrib.auth.hashers
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
import bookings.models
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="Vehicle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, unique=True)),
                ("description", models.CharField(blank=True, max_length=240)),
                ("passenger_capacity", models.PositiveSmallIntegerField(default=4)),
                ("luggage_capacity", models.PositiveSmallIntegerField(default=2)),
                ("photo", models.ImageField(blank=True, upload_to="vehicles/", validators=[django.core.validators.FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), bookings.models.validate_vehicle_photo])),
                ("photo_small", models.ImageField(blank=True, editable=False, upload_to="vehicles/small/")),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("sort_order", "name")},
        ),
        migrations.CreateModel(
            name="VehiclePrice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("currency", models.CharField(default="INR", max_length=3)),
                ("display_label", models.CharField(default="Starting fare", max_length=80)),
                ("customer_note", models.CharField(blank=True, max_length=240)),
                ("effective_from", models.DateTimeField(default=django.utils.timezone.now)),
                ("effective_until", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("vehicle", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="prices", to="bookings.vehicle")),
            ],
            options={"ordering": ("-effective_from",), "constraints": [models.CheckConstraint(condition=models.Q(("effective_until__isnull", True), ("effective_until__gt", models.F("effective_from")), _connector="OR"), name="vehicle_price_valid_period")]},
        ),
        migrations.CreateModel(
            name="Booking",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("idempotency_key", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("reference", models.CharField(default=bookings.models.make_booking_reference, editable=False, max_length=16, unique=True)),
                ("customer_name", models.CharField(max_length=120)),
                ("phone_number", models.CharField(db_index=True, max_length=24)),
                ("pickup_address", models.CharField(max_length=300)),
                ("destination_address", models.CharField(max_length=300)),
                ("requested_at", models.DateTimeField()),
                ("passenger_count", models.PositiveSmallIntegerField(default=1)),
                ("notes", models.CharField(blank=True, max_length=500)),
                ("quoted_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("quoted_currency", models.CharField(blank=True, max_length=3)),
                ("quoted_label", models.CharField(blank=True, max_length=80)),
                ("status", models.CharField(choices=[("awaiting_otp", "Awaiting phone verification"), ("new", "New — awaiting operator confirmation"), ("contacted", "Customer contacted"), ("accepted", "Accepted"), ("rejected", "Rejected"), ("cancelled", "Cancelled"), ("completed", "Completed")], db_index=True, default="awaiting_otp", max_length=24)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("price_version", models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="bookings", to="bookings.vehicleprice")),
                ("vehicle", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="bookings", to="bookings.vehicle")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="BookingStatusEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("previous_status", models.CharField(choices=[("awaiting_otp", "Awaiting phone verification"), ("new", "New — awaiting operator confirmation"), ("contacted", "Customer contacted"), ("accepted", "Accepted"), ("rejected", "Rejected"), ("cancelled", "Cancelled"), ("completed", "Completed")], max_length=24)),
                ("new_status", models.CharField(choices=[("awaiting_otp", "Awaiting phone verification"), ("new", "New — awaiting operator confirmation"), ("contacted", "Customer contacted"), ("accepted", "Accepted"), ("rejected", "Rejected"), ("cancelled", "Cancelled"), ("completed", "Completed")], max_length=24)),
                ("note", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("booking", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="status_events", to="bookings.booking")),
                ("changed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("created_at",)},
        ),
        migrations.CreateModel(
            name="OTPChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code_hash", models.CharField(max_length=128)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("resend_count", models.PositiveSmallIntegerField(default=0)),
                ("last_sent_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("booking", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="otp_challenges", to="bookings.booking")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="OTPSendAttempt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("phone_hash", models.CharField(db_index=True, max_length=64)),
                ("ip_hash", models.CharField(db_index=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("booking", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="otp_send_attempts", to="bookings.booking")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="NotificationOutbox",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel", models.CharField(default="operator", max_length=24)),
                ("state", models.CharField(choices=[("queued", "Queued"), ("sent", "Sent"), ("failed", "Failed")], db_index=True, default="queued", max_length=16)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("last_error", models.CharField(blank=True, max_length=240)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("booking", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to="bookings.booking")),
            ],
            options={"ordering": ("created_at",)},
        ),
    ]
