import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    Booking,
    BookingStatusEvent,
    CustomerAccessChallenge,
    CustomerAccessSendAttempt,
    NotificationOutbox,
    OTPChallenge,
    OTPSendAttempt,
)

logger = logging.getLogger(__name__)


def _privacy_hash(value, label):
    return hmac.new(settings.SECRET_KEY.encode(), f"{label}:{value}".encode(), hashlib.sha256).hexdigest()


@transaction.atomic
def _record_otp_send(booking, ip_address):
    now = timezone.now()
    window_start = now - timedelta(hours=1)
    phone_hash = _privacy_hash(booking.phone_number, "phone")
    ip_hash = _privacy_hash(ip_address or "unknown", "ip")
    recent = OTPSendAttempt.objects.filter(created_at__gte=window_start)
    if recent.filter(phone_hash=phone_hash).count() >= 5:
        raise ValidationError("Too many verification codes requested for this number. Try again later.")
    if recent.filter(ip_hash=ip_hash).count() >= 20:
        raise ValidationError("Too many verification codes requested from this connection. Try again later.")
    OTPSendAttempt.objects.create(booking=booking, phone_hash=phone_hash, ip_hash=ip_hash)


def issue_otp(booking, ip_address=None):
    if not (settings.OTP_BACKEND == "console" and settings.DEBUG):
        raise ValidationError("SMS verification is not configured. Please try again later.")
    _record_otp_send(booking, ip_address)
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = timezone.now()
    challenge = OTPChallenge.objects.create(
        booking=booking,
        code_hash=make_password(code),
        expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
        last_sent_at=now,
    )
    if settings.OTP_BACKEND == "console" and settings.DEBUG:
        logger.warning("DEV ONLY OTP for booking %s / %s: %s", booking.reference, booking.phone_number, code)
        return challenge


def resend_otp(booking, ip_address=None):
    if not (settings.OTP_BACKEND == "console" and settings.DEBUG):
        raise ValidationError("SMS verification is not configured. Please try again later.")
    challenge = booking.otp_challenges.first()
    if not challenge or challenge.verified_at:
        raise ValidationError("Request a new booking verification code.")
    now = timezone.now()
    wait_until = challenge.last_sent_at + timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS)
    if now < wait_until:
        seconds = max(1, int((wait_until - now).total_seconds()))
        raise ValidationError(f"Please wait {seconds} seconds before requesting another code.")
    if challenge.resend_count >= settings.OTP_MAX_RESENDS:
        raise ValidationError("You have reached the resend limit. Start a new booking request.")
    _record_otp_send(booking, ip_address)
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge.code_hash = make_password(code)
    challenge.expires_at = now + timedelta(seconds=settings.OTP_TTL_SECONDS)
    challenge.last_sent_at = now
    challenge.resend_count += 1
    challenge.attempts = 0
    challenge.save(update_fields=["code_hash", "expires_at", "last_sent_at", "resend_count", "attempts"])
    if settings.OTP_BACKEND == "console" and settings.DEBUG:
        logger.warning("DEV ONLY OTP for booking %s / %s: %s", booking.reference, booking.phone_number, code)
        return


def verify_otp(booking, code):
    error = None
    outbox = None
    with transaction.atomic():
        challenge = OTPChallenge.objects.select_for_update().filter(booking=booking).first()
        if not challenge or challenge.verified_at or challenge.expires_at <= timezone.now():
            raise ValidationError("That code has expired. Request a new one.")
        if challenge.attempts >= settings.OTP_MAX_ATTEMPTS:
            raise ValidationError("Too many incorrect attempts. Start a new booking request.")
        if not check_password(code, challenge.code_hash):
            challenge.attempts += 1
            challenge.save(update_fields=["attempts"])
            error = "The code does not match. Check it and try again."
        else:
            challenge.verified_at = timezone.now()
            challenge.save(update_fields=["verified_at"])
            previous_status = booking.status
            booking.status = Booking.Status.NEW
            booking.verified_at = timezone.now()
            booking.save(update_fields=["status", "verified_at", "updated_at"])
            BookingStatusEvent.objects.create(
                booking=booking,
                previous_status=previous_status,
                new_status=Booking.Status.NEW,
                note="Customer phone verified.",
            )
            outbox = NotificationOutbox.objects.create(booking=booking)
            transaction.on_commit(lambda: deliver_dev_operator_alert(outbox))
    if error:
        raise ValidationError(error)
    return booking


def deliver_dev_operator_alert(outbox):
    if settings.OPERATOR_ALERT_BACKEND == "console" and settings.DEBUG:
        booking = outbox.booking
        logger.warning(
            "DEV ONLY OPERATOR ALERT [%s]: %s; %s; %s trip; %s to %s; pickup %s (landmark: %s); destination %s (landmark: %s); pickup time %s; minimum fare %s %s at %s/km",
            booking.reference, booking.customer_name, booking.phone_number,
            booking.get_trip_type_display(), booking.pickup_location, booking.destination_location,
            booking.pickup_address, booking.pickup_landmark or "not provided",
            booking.destination_address, booking.destination_landmark or "not provided",
            booking.requested_at,
            booking.quoted_currency, booking.quoted_amount, booking.quoted_rate_per_km,
        )
        outbox.state = NotificationOutbox.State.SENT
        outbox.sent_at = timezone.now()
        outbox.attempts += 1
        outbox.save(update_fields=["state", "sent_at", "attempts"])
        return
    outbox.last_error = "No operator alert provider is configured."
    outbox.save(update_fields=["last_error"])


@transaction.atomic
def issue_my_bookings_otp(phone_number, ip_address=None):
    if not (settings.OTP_BACKEND == "console" and settings.DEBUG):
        raise ValidationError("SMS verification is not configured. Please try again later.")
    now = timezone.now()
    window_start = now - timedelta(hours=1)
    phone_hash = _privacy_hash(phone_number, "phone")
    ip_hash = _privacy_hash(ip_address or "unknown", "ip")
    recent = CustomerAccessSendAttempt.objects.filter(created_at__gte=window_start)
    if recent.filter(phone_hash=phone_hash).count() >= 5:
        raise ValidationError("Too many verification codes requested for this number. Try again later.")
    if recent.filter(ip_hash=ip_hash).count() >= 20:
        raise ValidationError("Too many verification codes requested from this connection. Try again later.")
    CustomerAccessSendAttempt.objects.create(phone_hash=phone_hash, ip_hash=ip_hash)
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge = CustomerAccessChallenge.objects.create(
        phone_number=phone_number,
        phone_hash=phone_hash,
        ip_hash=ip_hash,
        code_hash=make_password(code),
        expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
        last_sent_at=now,
    )
    logger.warning("DEV ONLY MY BOOKINGS OTP for %s: %s", phone_number, code)
    return challenge


@transaction.atomic
def resend_my_bookings_otp(challenge, ip_address=None):
    if not (settings.OTP_BACKEND == "console" and settings.DEBUG):
        raise ValidationError("SMS verification is not configured. Please try again later.")
    challenge = CustomerAccessChallenge.objects.select_for_update().get(pk=challenge.pk)
    if challenge.verified_at or challenge.expires_at <= timezone.now():
        raise ValidationError("That verification request has expired. Start again.")
    now = timezone.now()
    wait_until = challenge.last_sent_at + timedelta(seconds=settings.OTP_RESEND_COOLDOWN_SECONDS)
    if now < wait_until:
        seconds = max(1, int((wait_until - now).total_seconds()))
        raise ValidationError(f"Please wait {seconds} seconds before requesting another code.")
    if challenge.resend_count >= settings.OTP_MAX_RESENDS:
        raise ValidationError("You have reached the resend limit. Start again.")
    window_start = now - timedelta(hours=1)
    recent = CustomerAccessSendAttempt.objects.filter(created_at__gte=window_start)
    if recent.filter(phone_hash=challenge.phone_hash).count() >= 5:
        raise ValidationError("Too many verification codes requested for this number. Try again later.")
    ip_hash = _privacy_hash(ip_address or "unknown", "ip")
    if recent.filter(ip_hash=ip_hash).count() >= 20:
        raise ValidationError("Too many verification codes requested from this connection. Try again later.")
    CustomerAccessSendAttempt.objects.create(phone_hash=challenge.phone_hash, ip_hash=ip_hash)
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge.code_hash = make_password(code)
    challenge.expires_at = now + timedelta(seconds=settings.OTP_TTL_SECONDS)
    challenge.last_sent_at = now
    challenge.resend_count += 1
    challenge.attempts = 0
    challenge.save(update_fields=["code_hash", "expires_at", "last_sent_at", "resend_count", "attempts"])
    logger.warning("DEV ONLY MY BOOKINGS OTP for %s: %s", challenge.phone_number, code)
    return challenge


def verify_my_bookings_otp(challenge, code):
    error = None
    phone_number = None
    with transaction.atomic():
        challenge = CustomerAccessChallenge.objects.select_for_update().filter(pk=challenge.pk).first()
        if not challenge or challenge.verified_at or challenge.expires_at <= timezone.now():
            raise ValidationError("That code has expired. Request a new one.")
        if challenge.attempts >= settings.OTP_MAX_ATTEMPTS:
            raise ValidationError("Too many incorrect attempts. Start again.")
        if not check_password(code, challenge.code_hash):
            challenge.attempts += 1
            challenge.save(update_fields=["attempts"])
            error = "The code does not match. Check it and try again."
        else:
            challenge.verified_at = timezone.now()
            challenge.save(update_fields=["verified_at"])
            phone_number = challenge.phone_number
    if error:
        raise ValidationError(error)
    return phone_number
