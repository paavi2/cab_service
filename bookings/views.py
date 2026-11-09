import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import BookingRequestForm, MyBookingsOTPForm, MyBookingsPhoneForm, TripSearchForm
from .models import Booking, BookingStatusEvent, CustomerAccessChallenge, LocalTripPackage, LocalTripSettings, Vehicle
from .services import (
    issue_my_bookings_otp,
    issue_otp,
    resend_my_bookings_otp,
    resend_otp,
    verify_my_bookings_otp,
    verify_otp,
)


def _trip_search_from_session(request):
    values = request.session.get("trip_search")
    if not values:
        return None
    return {
        **values,
        "requested_at": datetime.fromisoformat(values["requested_at"]),
        "return_at": datetime.fromisoformat(values["return_at"]) if values.get("return_at") else None,
    }


def home(request):
    default_pickup = (timezone.localtime() + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)
    form = TripSearchForm(initial={"requested_at": default_pickup})
    if request.method == "POST":
        form = TripSearchForm(request.POST)
        if form.is_valid():
            request.session["trip_search"] = {
                "trip_type": form.cleaned_data["trip_type"],
                "pickup_location": form.cleaned_data["pickup_location"].strip(),
                "destination_location": form.cleaned_data["destination_location"].strip(),
                "requested_at": form.cleaned_data["requested_at"].isoformat(),
                "return_at": form.cleaned_data["return_at"].isoformat() if form.cleaned_data["return_at"] else "",
            }
            request.session.pop("selected_vehicle_id", None)
            request.session.pop("selected_local_package_id", None)
            return redirect("search_cabs")
    return render(request, "bookings/home.html", {"form": form})


def search_cabs(request):
    trip = _trip_search_from_session(request)
    if not trip:
        return redirect("home")
    vehicles = []
    local_settings = LocalTripSettings.current()
    if trip["trip_type"] == Booking.TripType.LOCAL:
        for package in LocalTripPackage.objects.filter(is_active=True, vehicle__is_active=True).select_related("vehicle"):
            vehicles.append({
                "vehicle": package.vehicle,
                "package": package,
                "price": package,
                "rate": local_settings.local_extra_km_rate,
                "minimum_km": package.included_km,
                "minimum_fare": package.amount,
                "waiting_rate": local_settings.waiting_rate_for(package.vehicle),
            })
    else:
        for vehicle in Vehicle.objects.filter(is_active=True):
            price = vehicle.active_price()
            if not price:
                continue
            rate = price.rate_for_trip(trip["trip_type"])
            minimum_km = 130 if trip["trip_type"] == Booking.TripType.ONE_WAY else 250
            vehicles.append({
                "vehicle": vehicle,
                "price": price,
                "rate": rate,
                "minimum_km": minimum_km,
                "minimum_fare": rate * minimum_km,
                "waiting_rate": local_settings.waiting_rate_for(vehicle) if trip["trip_type"] == Booking.TripType.ONE_WAY else None,
            })
    search_form = TripSearchForm(initial={
        "trip_type": trip["trip_type"],
        "pickup_location": trip["pickup_location"],
        "destination_location": trip["destination_location"],
        "requested_at": trip["requested_at"],
        "return_at": trip["return_at"],
    })
    return render(request, "bookings/car_results.html", {
        "trip": trip,
        "vehicles": vehicles,
        "search_form": search_form,
        "local_settings": local_settings,
    })


def choose_vehicle(request):
    if request.method != "POST" or not _trip_search_from_session(request):
        return redirect("home")
    vehicle = get_object_or_404(Vehicle, pk=request.POST.get("vehicle_id"), is_active=True)
    local_package = None
    if _trip_search_from_session(request)["trip_type"] == Booking.TripType.LOCAL:
        local_package = get_object_or_404(LocalTripPackage, pk=request.POST.get("package_id"), vehicle=vehicle, is_active=True)
        request.session["selected_local_package_id"] = local_package.id
    else:
        request.session.pop("selected_local_package_id", None)
    if not local_package and not vehicle.active_price():
        messages.error(request, "This vehicle has no active price. Please choose another vehicle.")
        return redirect("search_cabs")
    request.session["selected_vehicle_id"] = vehicle.id
    return redirect("create_booking")


def create_booking(request):
    trip = _trip_search_from_session(request)
    vehicle_id = request.session.get("selected_vehicle_id")
    if not trip or not vehicle_id:
        return redirect("home")
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id, is_active=True)
    price = vehicle.active_price()
    local_package = None
    local_settings = LocalTripSettings.current()
    if trip["trip_type"] == Booking.TripType.LOCAL:
        package_id = request.session.get("selected_local_package_id")
        local_package = get_object_or_404(LocalTripPackage, pk=package_id, vehicle=vehicle, is_active=True)
    if not price and not local_package:
        messages.error(request, "This vehicle's price is no longer active. Please choose a vehicle again.")
        return redirect("search_cabs")

    key = request.session.get("booking_idempotency_key")
    if not key:
        key = str(uuid.uuid4())
        request.session["booking_idempotency_key"] = key
    if request.method == "POST":
        form = BookingRequestForm(request.POST, idempotency_key=key)
        if form.is_valid():
            rate = local_settings.local_extra_km_rate if local_package else price.rate_for_trip(trip["trip_type"])
            minimum_km = local_package.included_km if local_package else (130 if trip["trip_type"] == Booking.TripType.ONE_WAY else 250)
            carrier_selected = bool(local_package and form.cleaned_data.get("luggage_carrier_requested"))
            carrier_charge = local_settings.luggage_carrier_charge if carrier_selected else Decimal("0.00")
            if rate < 0 or (not local_package and rate == 0):
                form.add_error(None, "The configured vehicle rate cannot be used for this trip type.")
            else:
                booking_values = {
                    "customer_name": form.cleaned_data["customer_name"],
                    "phone_number": form.cleaned_data["phone_number"],
                    "pickup_location": trip["pickup_location"],
                    "destination_location": trip["destination_location"],
                    "pickup_address": form.cleaned_data["pickup_address"],
                    "pickup_landmark": form.cleaned_data["pickup_landmark"],
                    "destination_address": form.cleaned_data["destination_address"],
                    "destination_landmark": form.cleaned_data["destination_landmark"],
                    "trip_type": trip["trip_type"],
                    "requested_at": trip["requested_at"],
                    "return_at": trip["return_at"],
                    "passenger_count": form.cleaned_data["passenger_count"],
                    "luggage_carrier_requested": carrier_selected,
                    "notes": form.cleaned_data["notes"],
                    "vehicle": vehicle,
                    "price_version": price,
                    "local_package": local_package,
                    "quoted_rate_per_km": rate,
                    "quoted_minimum_km": minimum_km,
                    "quoted_amount": local_package.amount + carrier_charge if local_package else rate * minimum_km,
                    "quoted_package_amount": local_package.amount if local_package else None,
                    "quoted_waiting_rate_per_hour": local_settings.waiting_rate_for(vehicle) if (local_package or trip["trip_type"] == Booking.TripType.ONE_WAY) else None,
                    "quoted_local_extra_km_rate": local_settings.local_extra_km_rate if local_package else None,
                    "quoted_luggage_carrier_amount": local_settings.luggage_carrier_charge if local_package else None,
                    "quoted_inclusions": local_settings.local_inclusions if local_package else "",
                    "quoted_exclusions": local_settings.local_exclusions if local_package else "",
                    "quoted_currency": local_package.currency if local_package else price.currency,
                    "quoted_label": ("Local package + carrier" if carrier_selected else "Local package fare") if local_package else f"Minimum fare ({minimum_km} km; extras excluded)",
                }
                with transaction.atomic():
                    booking, created = Booking.objects.get_or_create(
                        idempotency_key=form.cleaned_data["idempotency_key"],
                        defaults=booking_values,
                    )
                    if not created and booking.status != Booking.Status.AWAITING_OTP:
                        request.session["booking_idempotency_key"] = str(uuid.uuid4())
                        form.add_error(None, "This request was already submitted. Start a new booking if you need another ride.")
                    else:
                        try:
                            if created or not booking.otp_challenges.exists():
                                issue_otp(booking, request.META.get("REMOTE_ADDR"))
                            else:
                                resend_otp(booking, request.META.get("REMOTE_ADDR"))
                        except ValidationError as error:
                            form.add_error(None, error.messages[0])
                        else:
                            request.session["pending_booking_id"] = booking.id
                            request.session["booking_idempotency_key"] = str(uuid.uuid4())
                            return redirect("verify_booking_otp")
    else:
        form = BookingRequestForm(idempotency_key=key)
    return render(request, "bookings/booking_form.html", {
        "form": form,
        "trip": trip,
        "vehicle": vehicle,
        "price": price,
        "rate": local_settings.local_extra_km_rate if local_package else price.rate_for_trip(trip["trip_type"]),
        "minimum_km": local_package.included_km if local_package else (130 if trip["trip_type"] == Booking.TripType.ONE_WAY else 250),
        "minimum_fare": (local_package.amount + (local_settings.luggage_carrier_charge if request.POST and request.POST.get("luggage_carrier_requested") else Decimal("0.00"))) if local_package else price.rate_for_trip(trip["trip_type"]) * (130 if trip["trip_type"] == Booking.TripType.ONE_WAY else 250),
        "local_package": local_package,
        "local_settings": local_settings,
        "waiting_rate": local_settings.waiting_rate_for(vehicle) if (local_package or trip["trip_type"] == Booking.TripType.ONE_WAY) else None,
        "trip_display": "Local" if trip["trip_type"] == Booking.TripType.LOCAL else ("Round trip" if trip["trip_type"] == Booking.TripType.ROUND_TRIP else "One way"),
        "luggage_carrier_charge": local_settings.luggage_carrier_charge,
        "currency": local_package.currency if local_package else price.currency,
    })


def verify_booking_otp(request):
    booking_id = request.session.get("pending_booking_id")
    if not booking_id:
        return redirect("create_booking")
    booking = get_object_or_404(Booking, id=booking_id, status=Booking.Status.AWAITING_OTP)
    error = None
    if request.method == "POST":
        action = request.POST.get("action", "verify")
        try:
            if action == "resend":
                resend_otp(booking, request.META.get("REMOTE_ADDR"))
                messages.success(request, "A new verification code was sent.")
            else:
                code = request.POST.get("code", "").strip()
                if len(code) != 6 or not code.isdigit():
                    raise ValidationError("Enter the six-digit code.")
                verify_otp(booking, code)
                request.session["my_bookings_phone"] = booking.phone_number
                request.session["my_bookings_verified_at"] = timezone.now().isoformat()
                request.session.set_expiry(900)
                request.session.pop("pending_booking_id", None)
                return redirect("booking_confirmation", reference=booking.reference)
        except ValidationError as exception:
            error = exception.messages[0]
    return render(request, "bookings/verify_otp.html", {"booking": booking, "error": error})


def booking_confirmation(request, reference):
    booking = get_object_or_404(Booking, reference=reference, status__in=[
        Booking.Status.NEW, Booking.Status.CONTACTED, Booking.Status.ACCEPTED,
        Booking.Status.REJECTED, Booking.Status.CANCELLED, Booking.Status.COMPLETED,
    ])
    return render(request, "bookings/confirmation.html", {"booking": booking})



def my_bookings(request):
    if request.session.get("my_bookings_phone"):
        return redirect("my_bookings_list")
    form = MyBookingsPhoneForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            challenge = issue_my_bookings_otp(
                form.cleaned_data["phone_number"], request.META.get("REMOTE_ADDR")
            )
        except ValidationError as error:
            form.add_error(None, error.messages[0])
        else:
            request.session["my_bookings_challenge_id"] = challenge.id
            return redirect("my_bookings_verify")
    return render(request, "bookings/my_bookings_phone.html", {"form": form})


def my_bookings_verify(request):
    challenge_id = request.session.get("my_bookings_challenge_id")
    challenge = CustomerAccessChallenge.objects.filter(pk=challenge_id).first() if challenge_id else None
    if not challenge:
        return redirect("my_bookings")
    is_resend = request.method == "POST" and request.POST.get("action") == "resend"
    form = MyBookingsOTPForm() if is_resend else MyBookingsOTPForm(request.POST or None)
    error = None
    if request.method == "POST":
        if is_resend:
            try:
                if challenge.expires_at <= timezone.now():
                    challenge = issue_my_bookings_otp(challenge.phone_number, request.META.get("REMOTE_ADDR"))
                    request.session["my_bookings_challenge_id"] = challenge.id
                else:
                    challenge = resend_my_bookings_otp(challenge, request.META.get("REMOTE_ADDR"))
                messages.success(request, "A new verification code was sent.")
            except ValidationError as exception:
                error = exception.messages[0]
        elif form.is_valid():
            try:
                phone_number = verify_my_bookings_otp(challenge, form.cleaned_data["code"])
            except ValidationError as exception:
                error = exception.messages[0]
            else:
                request.session["my_bookings_phone"] = phone_number
                request.session["my_bookings_verified_at"] = timezone.now().isoformat()
                request.session.pop("my_bookings_challenge_id", None)
                request.session.set_expiry(900)
                return redirect("my_bookings_list")
    return render(request, "bookings/my_bookings_otp.html", {
        "form": form,
        "challenge": challenge,
        "error": error,
    })


def my_bookings_list(request):
    phone_number = request.session.get("my_bookings_phone")
    if not phone_number:
        return redirect("my_bookings")
    recent_cutoff = timezone.now() - timedelta(days=5)
    bookings = Booking.objects.filter(phone_number=phone_number).exclude(
        status=Booking.Status.AWAITING_OTP
    ).exclude(personal_data_anonymized_at__isnull=False).filter(
        ~Q(status=Booking.Status.COMPLETED) | Q(completed_at__gt=recent_cutoff)
    )
    rows = []
    for booking in bookings:
        if booking.status in (Booking.Status.NEW, Booking.Status.CONTACTED):
            customer_status = "Booked"
        elif booking.status == Booking.Status.ACCEPTED:
            customer_status = "Confirmed"
        elif booking.status == Booking.Status.CANCELLED:
            customer_status = "Cancelled"
        elif booking.status == Booking.Status.REJECTED:
            customer_status = "Not confirmed"
        else:
            customer_status = "Completed"
        can_cancel = (
            booking.status in (Booking.Status.NEW, Booking.Status.CONTACTED, Booking.Status.ACCEPTED)
            and booking.requested_at > timezone.now()
        )
        charge_if_cancelled = booking.requested_at <= timezone.now() + timedelta(hours=24)
        rows.append({
            "booking": booking,
            "customer_status": customer_status,
            "can_cancel": can_cancel,
            "charge_if_cancelled": charge_if_cancelled,
        })
    return render(request, "bookings/my_bookings_list.html", {"rows": rows})


def cancel_customer_booking(request, booking_id):
    phone_number = request.session.get("my_bookings_phone")
    if not phone_number:
        return redirect("my_bookings")
    if request.method != "POST":
        return redirect("my_bookings_list")
    with transaction.atomic():
        booking = get_object_or_404(
            Booking.objects.select_for_update(), pk=booking_id, phone_number=phone_number
        )
        allowed_statuses = (Booking.Status.NEW, Booking.Status.CONTACTED, Booking.Status.ACCEPTED)
        if booking.status not in allowed_statuses or booking.requested_at <= timezone.now():
            messages.error(request, "This booking can no longer be cancelled online. Please contact the operator.")
            return redirect("my_bookings_list")
        previous_status = booking.status
        cutoff = timezone.now() + timedelta(hours=24)
        charge = Decimal("300.00") if booking.requested_at <= cutoff else Decimal("0.00")
        booking.status = Booking.Status.CANCELLED
        booking.cancellation_charge = charge
        booking.save(update_fields=["status", "cancellation_charge", "updated_at"])
        BookingStatusEvent.objects.create(
            booking=booking,
            previous_status=previous_status,
            new_status=Booking.Status.CANCELLED,
            note=("Customer cancelled; ₹300 cancellation charge to be deducted from advance paid."
                  if charge else "Customer cancelled more than 24 hours before pickup."),
        )
    if charge:
        messages.success(request, "Booking cancelled. A ₹300 cancellation charge will be deducted from the advance paid.")
    else:
        messages.success(request, "Booking cancelled. No cancellation charge applies.")
    return redirect("my_bookings_list")


def my_bookings_logout(request):
    request.session.pop("my_bookings_phone", None)
    request.session.pop("my_bookings_verified_at", None)
    request.session.pop("my_bookings_challenge_id", None)
    messages.success(request, "You have signed out of My Bookings.")
    return redirect("my_bookings")
