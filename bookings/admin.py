from django.contrib import admin
from django.utils import timezone
from .models import Booking, BookingStatusEvent, LocalTripPackage, LocalTripSettings, NotificationOutbox, Vehicle, VehiclePrice


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("name", "service_class", "passenger_capacity", "luggage_capacity", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name", "description")


@admin.register(LocalTripSettings)
class LocalTripSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Customer-facing local-trip terms", {"fields": ("local_inclusions", "local_exclusions")}),
        ("Additional local charges", {"fields": ("local_extra_km_rate", "luggage_carrier_charge")}),
        ("Waiting charges per hour", {"fields": ("sedan_waiting_rate_per_hour", "suv_waiting_rate_per_hour")}),
    )

    def has_add_permission(self, request):
        return not LocalTripSettings.objects.exists()


@admin.register(LocalTripPackage)
class LocalTripPackageAdmin(admin.ModelAdmin):
    list_display = ("name", "vehicle", "duration_hours", "included_km", "amount", "currency", "is_active", "sort_order")
    list_filter = ("is_active", "vehicle__service_class", "vehicle")
    search_fields = ("name", "vehicle__name")
    ordering = ("sort_order", "vehicle__name", "duration_hours")

@admin.register(VehiclePrice)
class VehiclePriceAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "amount", "currency", "effective_from", "effective_until", "created_by")
    list_filter = ("currency", "vehicle")
    readonly_fields = ("created_by", "created_at")
    search_fields = ("vehicle__name", "customer_note")

    def has_change_permission(self, request, obj=None):
        return obj is None

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class BookingStatusEventInline(admin.TabularInline):
    model = BookingStatusEvent
    extra = 0
    can_delete = False
    fields = ("previous_status", "new_status", "changed_by", "note", "created_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("reference", "customer_name", "trip_type", "vehicle", "local_package", "requested_at", "status", "cancellation_charge", "actual_distance_km", "actual_waiting_hours", "calculated_fare", "created_at")
    list_filter = ("status", "trip_type", "vehicle", "created_at")
    search_fields = ("reference", "customer_name", "phone_number", "pickup_location", "destination_location", "pickup_address", "pickup_landmark", "destination_address", "destination_landmark")
    readonly_fields = ("reference", "idempotency_key", "price_version", "local_package", "quoted_amount", "quoted_currency", "quoted_label", "quoted_rate_per_km", "quoted_minimum_km", "quoted_package_amount", "quoted_waiting_rate_per_hour", "quoted_local_extra_km_rate", "luggage_carrier_requested", "quoted_luggage_carrier_amount", "quoted_inclusions", "quoted_exclusions", "minimum_billable_km", "billable_km", "calculated_fare", "cancellation_charge", "completed_at", "personal_data_anonymized_at", "created_at", "verified_at", "updated_at")
    date_hierarchy = "created_at"
    list_per_page = 50
    inlines = (BookingStatusEventInline,)

    @admin.display(description="Calculated fare")
    def calculated_fare(self, obj):
        return obj.calculated_final_fare

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change:
            previous_status = Booking.objects.only("status").get(pk=obj.pk).status
        if obj.status == Booking.Status.COMPLETED and not obj.completed_at:
            obj.completed_at = timezone.now()
        super().save_model(request, obj, form, change)
        if previous_status and previous_status != obj.status:
            BookingStatusEvent.objects.create(
                booking=obj,
                previous_status=previous_status,
                new_status=obj.status,
                changed_by=request.user,
                note="Status changed in admin.",
            )


@admin.register(NotificationOutbox)
class NotificationOutboxAdmin(admin.ModelAdmin):
    list_display = ("booking", "channel", "state", "attempts", "created_at", "sent_at")
    list_filter = ("state", "channel", "created_at")
    readonly_fields = ("booking", "channel", "state", "attempts", "last_error", "created_at", "sent_at")
