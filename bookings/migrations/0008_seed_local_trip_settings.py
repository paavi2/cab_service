from django.db import migrations


def create_default_settings(apps, schema_editor):
    LocalTripSettings = apps.get_model("bookings", "LocalTripSettings")
    LocalTripSettings.objects.get_or_create(
        pk=1,
        defaults={
            "local_inclusions": "Driver beta\nToll\nTax\n2 luggages\nGST",
            "local_exclusions": "Travel beyond the package distance\nWaiting charges\nExtra luggage",
            "sedan_waiting_rate_per_hour": "130.00",
            "suv_waiting_rate_per_hour": "180.00",
        },
    )


class Migration(migrations.Migration):
    dependencies = [("bookings", "0007_localtripsettings_booking_actual_waiting_hours_and_more")]
    operations = [migrations.RunPython(create_default_settings, migrations.RunPython.noop)]
