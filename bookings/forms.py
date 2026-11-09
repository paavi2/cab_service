import re
import uuid

from django import forms
from django.utils import timezone

from .models import Booking


class TripSearchForm(forms.Form):
    trip_type = forms.ChoiceField(
        choices=Booking.TripType.choices,
        initial=Booking.TripType.ONE_WAY,
        widget=forms.RadioSelect,
    )
    pickup_location = forms.CharField(
        max_length=180,
        label="From",
        widget=forms.TextInput(attrs={"placeholder": "Enter pickup city", "autocomplete": "address-level2"}),
    )
    destination_location = forms.CharField(
        max_length=180,
        label="To",
        widget=forms.TextInput(attrs={"placeholder": "Enter destination city", "autocomplete": "off"}),
    )
    requested_at = forms.DateTimeField(
        label="Pick-up date and time",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    return_at = forms.DateTimeField(
        label="Return date and time",
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )

    def clean(self):
        cleaned = super().clean()
        pickup_at = cleaned.get("requested_at")
        return_at = cleaned.get("return_at")
        trip_type = cleaned.get("trip_type")
        if pickup_at and timezone.is_naive(pickup_at):
            pickup_at = timezone.make_aware(pickup_at, timezone.get_current_timezone())
            cleaned["requested_at"] = pickup_at
        if return_at and timezone.is_naive(return_at):
            return_at = timezone.make_aware(return_at, timezone.get_current_timezone())
            cleaned["return_at"] = return_at
        if pickup_at and pickup_at < timezone.now():
            self.add_error("requested_at", "Choose a future pick-up date and time.")
        if trip_type == Booking.TripType.ROUND_TRIP:
            if not return_at:
                self.add_error("return_at", "Enter the return date and time for a round trip.")
            elif pickup_at and return_at <= pickup_at:
                self.add_error("return_at", "Return date and time must be after pick-up.")
        else:
            cleaned["return_at"] = None
        return cleaned


class BookingRequestForm(forms.ModelForm):
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)

    class Meta:
        model = Booking
        fields = (
            "customer_name",
            "phone_number",
            "pickup_address",
            "pickup_landmark",
            "destination_address",
            "destination_landmark",
            "passenger_count",
            "luggage_carrier_requested",
            "notes",
        )
        widgets = {
            "phone_number": forms.TextInput(attrs={"type": "tel", "inputmode": "numeric", "autocomplete": "tel-national", "maxlength": "10", "placeholder": "10-digit mobile number"}),
            "pickup_address": forms.TextInput(attrs={"autocomplete": "street-address", "placeholder": "House or building, street, area"}),
            "destination_address": forms.TextInput(attrs={"placeholder": "House or building, street, area"}),
            "pickup_landmark": forms.TextInput(attrs={"placeholder": "Nearby shop, gate, or other landmark"}),
            "destination_landmark": forms.TextInput(attrs={"placeholder": "Nearby shop, gate, or other landmark"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "phone_number": "Mobile number",
            "pickup_address": "Doorstep pick-up address",
            "pickup_landmark": "Pick-up landmark (optional)",
            "destination_address": "Drop-off address",
            "destination_landmark": "Drop-off landmark (optional)",
            "luggage_carrier_requested": "Add luggage carrier",
        }
        help_texts = {
            "phone_number": "Enter your 10-digit Indian mobile number. We’ll add +91 automatically.",
            "pickup_address": "Enter the house/building number, street, area, and city. The driver will come here.",
            "destination_address": "Enter the exact place where you want to be dropped.",
        }

    def __init__(self, *args, **kwargs):
        key = kwargs.pop("idempotency_key", None)
        super().__init__(*args, **kwargs)
        self.fields["idempotency_key"] = forms.UUIDField(widget=forms.HiddenInput, initial=key or uuid.uuid4())

    def clean_phone_number(self):
        raw = self.cleaned_data["phone_number"].strip()
        phone = re.sub(r"[\s().-]", "", raw)
        if not re.fullmatch(r"[6-9][0-9]{9}", phone):
            raise forms.ValidationError("Enter a valid 10-digit Indian mobile number.")
        return f"+91{phone}"


class MyBookingsPhoneForm(forms.Form):
    phone_number = forms.CharField(
        max_length=24,
        label="Mobile number",
        widget=forms.TextInput(attrs={"type": "tel", "inputmode": "numeric", "autocomplete": "tel-national", "maxlength": "10", "placeholder": "10-digit mobile number"}),
        help_text="Enter the same 10-digit Indian mobile number used for your booking.",
    )

    def clean_phone_number(self):
        raw = self.cleaned_data["phone_number"].strip()
        phone = re.sub(r"[\s().-]", "", raw)
        if not re.fullmatch(r"[6-9][0-9]{9}", phone):
            raise forms.ValidationError("Enter a valid 10-digit Indian mobile number.")
        return f"+91{phone}"


class MyBookingsOTPForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        label="Verification code",
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "one-time-code", "pattern": "[0-9]{6}"}),
    )

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        if not code.isdigit():
            raise forms.ValidationError("Enter the six-digit code.")
        return code
