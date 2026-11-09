from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="pickup_landmark",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AddField(
            model_name="booking",
            name="destination_landmark",
            field=models.CharField(blank=True, max_length=180),
        ),
    ]
