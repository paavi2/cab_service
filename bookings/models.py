import secrets
import uuid
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.core.files.base import ContentFile
from django.utils import timezone


def validate_vehicle_photo(upload):
    if upload.size > 8 * 1024 * 1024:
        raise ValidationError("Vehicle photos must be 8 MB or smaller.")


def make_booking_reference():
    return f"CAB-{secrets.token_hex(4).upper()}"


class Vehicle(models.Model):
    class ServiceClass(models.TextChoices):
        SEDAN = "sedan", "Sedan"
        SUV = "suv", "SUV / equivalent"

    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=240, blank=True)
    service_class = models.CharField(max_length=8, choices=ServiceClass.choices, default=ServiceClass.SUV)
    passenger_capacity = models.PositiveSmallIntegerField(default=4)
    luggage_capacity = models.PositiveSmallIntegerField(default=2)
    photo = models.ImageField(upload_to="vehicles/", blank=True, validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"]), validate_vehicle_photo])
    photo_small = models.ImageField(upload_to="vehicles/small/", blank=True, editable=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "name")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.photo and not self.photo._committed:
            source_name = Path(self.photo.name).stem
            self.photo.seek(0)
            image = ImageOps.exif_transpose(Image.open(self.photo)).convert("RGB")
            for width, field, suffix in ((480, "photo_small", "480"), (960, "photo", "960")):
                resized = image.copy()
                resized.thumbnail((width, width))
                buffer = BytesIO()
                resized.save(buffer, format="WEBP", quality=78, method=5)
                getattr(self, field).save(
                    f"{source_name}-{suffix}.webp",
                    ContentFile(buffer.getvalue()),
                    save=False,
                )
        super().save(*args, **kwargs)

    def active_price(self, at=None):
        at = at or timezone.now()
        return self.prices.filter(effective_from__lte=at).filter(
            models.Q(effective_until__isnull=True) | models.Q(effective_until__gt=at)
        ).order_by("-effective_from", "-created_at").first()


class VehiclePrice(models.Model):
    vehicle = models.ForeignKey(Vehicle, related_name="prices", on_delete=models.PROTECT)
    amount = models.DecimalField(
        "One-way rate per km",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(1.01)],
    )
    currency = models.CharField(max_length=3, default="INR")
    display_label = models.CharField(max_length=80, default="Starting fare")
    customer_note = models.CharField(max_length=240, blank=True)
    effective_from = models.DateTimeField(default=timezone.now)
    effective_until = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-effective_from",)
        constraints = [models.CheckConstraint(
            condition=models.Q(effective_until__isnull=True) | models.Q(effective_until__gt=models.F("effective_from")),
            name="vehicle_price_valid_period",
        )]

    def __str__(self):
        return f"{self.vehicle}: {self.currency} {self.amount}/km from {self.effective_from:%Y-%m-%d}"

    def rate_for_trip(self, trip_type):
        if trip_type == Booking.TripType.ROUND_TRIP:
            return self.amount - 1
        return self.amount


class LocalTripSettings(models.Model):
    """Admin-managed inclusions, exclusions, and waiting rates for local bookings."""
    local_inclusions = models.TextField(default="Toll\nState tax\nAC\nDriver allowance\nGST/Tax\nParking\n2 bags free")
    local_exclusions = models.TextField(default="Night allowance")
    sedan_waiting_rate_per_hour = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("130.00"))
    suv_waiting_rate_per_hour = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("180.00"))
    local_extra_km_rate = models.DecimalField("Extra distance rate per km", max_digits=8, decimal_places=2, default=Decimal("1.00"), validators=[MinValueValidator(0)])
    luggage_carrier_charge = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("150.00"), validators=[MinValueValidator(0)])

    class Meta:
        verbose_name = "Local trip settings"
        verbose_name_plural = "Local trip settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return "Local trip settings"

    @classmethod
    def current(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings

    def waiting_rate_for(self, vehicle):
        if vehicle.service_class == Vehicle.ServiceClass.SEDAN:
            return self.sedan_waiting_rate_per_hour
        return self.suv_waiting_rate_per_hour


class LocalTripPackage(models.Model):
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="local_packages")
    name = models.CharField(max_length=80, help_text="For example: 4 hours / 40 km")
    duration_hours = models.PositiveSmallIntegerField()
    included_km = models.PositiveSmallIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(1)])
    currency = models.CharField(max_length=3, default="INR")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("sort_order", "duration_hours", "included_km", "vehicle__name")
        constraints = [models.UniqueConstraint(fields=("vehicle", "name"), name="unique_local_package_vehicle_name")]

    def __str__(self):
        return f"{self.vehicle} — {self.name}"


class Booking(models.Model):
    class TripType(models.TextChoices):
        ONE_WAY = "one_way", "One way"
        ROUND_TRIP = "round_trip", "Round trip"
        LOCAL = "local", "Local"

    class Status(models.TextChoices):
        AWAITING_OTP = "awaiting_otp", "Awaiting phone verification"
        NEW = "new", "New — awaiting operator confirmation"
        CONTACTED = "contacted", "Customer contacted"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    reference = models.CharField(max_length=16, unique=True, default=make_booking_reference, editable=False)
    customer_name = models.CharField(max_length=120)
    phone_number = models.CharField(max_length=24, db_index=True)
    trip_type = models.CharField(max_length=16, choices=TripType.choices, default=TripType.ONE_WAY)
    pickup_location = models.CharField(max_length=180, blank=True)
    destination_location = models.CharField(max_length=180, blank=True)
    pickup_address = models.CharField(max_length=300)
    pickup_landmark = models.CharField(max_length=180, blank=True)
    destination_address = models.CharField(max_length=300)
    destination_landmark = models.CharField(max_length=180, blank=True)
    requested_at = models.DateTimeField()
    return_at = models.DateTimeField(null=True, blank=True)
    passenger_count = models.PositiveSmallIntegerField(default=1)
    notes = models.CharField(max_length=500, blank=True)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="bookings")
    price_version = models.ForeignKey(VehiclePrice, null=True, on_delete=models.PROTECT, related_name="bookings")
    local_package = models.ForeignKey(LocalTripPackage, null=True, blank=True, on_delete=models.PROTECT, related_name="bookings")
    quoted_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    quoted_currency = models.CharField(max_length=3, blank=True)
    quoted_label = models.CharField(max_length=80, blank=True)
    quoted_rate_per_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    quoted_minimum_km = models.PositiveSmallIntegerField(default=130)
    quoted_package_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    quoted_waiting_rate_per_hour = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    quoted_local_extra_km_rate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    luggage_carrier_requested = models.BooleanField(default=False)
    quoted_luggage_carrier_amount = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    quoted_inclusions = models.TextField(blank=True)
    quoted_exclusions = models.TextField(blank=True)
    actual_distance_km = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    actual_waiting_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(0)])
    cancellation_charge = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.AWAITING_OTP, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    personal_data_anonymized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.reference} — {self.customer_name}"

    @property
    def minimum_billable_km(self):
        if self.quoted_minimum_km:
            return self.quoted_minimum_km
        return 130 if self.trip_type == self.TripType.ONE_WAY else 250

    @property
    def billable_km(self):
        if self.actual_distance_km is None:
            return None
        return max(self.actual_distance_km, self.minimum_billable_km)

    @property
    def calculated_final_fare(self):
        if self.trip_type == self.TripType.LOCAL:
            if self.quoted_package_amount is None:
                return None
            extra_distance = max(Decimal("0"), (self.actual_distance_km or Decimal("0")) - Decimal(self.quoted_minimum_km))
            distance_charge = extra_distance * (self.quoted_local_extra_km_rate or Decimal("0"))
            waiting_charge = self.actual_waiting_hours * (self.quoted_waiting_rate_per_hour or Decimal("0"))
            carrier_charge = (self.quoted_luggage_carrier_amount or Decimal("0")) if self.luggage_carrier_requested else Decimal("0")
            return self.quoted_package_amount + distance_charge + waiting_charge + carrier_charge
        if self.billable_km is None or self.quoted_rate_per_km is None:
            return None
        fare = self.billable_km * self.quoted_rate_per_km
        if self.trip_type == self.TripType.ONE_WAY:
            fare += self.actual_waiting_hours * (self.quoted_waiting_rate_per_hour or Decimal("0"))
        return fare


class BookingStatusEvent(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="status_events")
    previous_status = models.CharField(max_length=24, choices=Booking.Status.choices)
    new_status = models.CharField(max_length=24, choices=Booking.Status.choices)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"{self.booking.reference}: {self.previous_status} → {self.new_status}"


class OTPChallenge(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="otp_challenges")
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    resend_count = models.PositiveSmallIntegerField(default=0)
    last_sent_at = models.DateTimeField(default=timezone.now)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class CustomerAccessChallenge(models.Model):
    phone_number = models.CharField(max_length=24)
    phone_hash = models.CharField(max_length=64, db_index=True)
    ip_hash = models.CharField(max_length=64, db_index=True)
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    resend_count = models.PositiveSmallIntegerField(default=0)
    last_sent_at = models.DateTimeField(default=timezone.now)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)


class CustomerAccessSendAttempt(models.Model):
    phone_hash = models.CharField(max_length=64, db_index=True)
    ip_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)


class OTPSendAttempt(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="otp_send_attempts")
    phone_hash = models.CharField(max_length=64, db_index=True)
    ip_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)


class NotificationOutbox(models.Model):
    class State(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="notifications")
    channel = models.CharField(max_length=24, default="operator")
    state = models.CharField(max_length=16, choices=State.choices, default=State.QUEUED, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"{self.booking.reference} — {self.channel} — {self.state}"
