# Cab Service

Phase 1 cab booking website and operator portal.

## Architecture

See [docs/PRD.md](docs/PRD.md) for product requirements and [docs/HLD.md](docs/HLD.md) for architecture, security, reliability, and low-bandwidth requirements.

## Development status

The initial Django foundation is being built. Local setup instructions will be added with the first runnable vertical slice. Production OTP and operator alerts require an SMS/notification provider and launch-country configuration; the development OTP backend must not be enabled in production.

## Local setup

1. Use Python 3.13 and create/activate a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and keep `.env` out of Git.
4. Run `python manage.py migrate`, then `python manage.py createsuperuser`.
5. Run `python manage.py runserver` and open `http://127.0.0.1:8000/`.
6. Add an active vehicle and effective price under `/admin/` before trying a booking.

For local development, the OTP and operator alert are printed to the server console. These development-only adapters are rejected when `DJANGO_DEBUG=false`. Production SMS and operator alert providers remain to be selected for the launch country.


### My Bookings and retention

- Customers can open **My Bookings** in the site navigation and verify the Indian mobile number associated with their bookings. During local development, access OTPs are written to the Django development log/terminal; SMS delivery requires the SMS provider integration.
- Customers can cancel future bookings. Cancellations within 24 hours of pickup record a ₹300 charge to deduct from the advance paid.
- When the operator marks a booking Completed in Django admin, `completed_at` is recorded. Run `.venv/bin/python manage.py purge_expired_booking_data` daily in production to anonymize personal fields five days after completion and remove expired customer access OTP records. Add this command to the hosting provider’s scheduled-job facility before launch.

### Local trips
- Set each vehicle's class (Sedan or SUV/equivalent), then add local packages in **Local trip packages** with a duration, included kilometres, and price.
- Edit the displayed inclusion/exclusion lists, local extra-kilometre rate, carrier price, and waiting rates in **Local trip settings**. Defaults include toll, state tax, AC, driver allowance, GST/Tax, parking, and two bags; night allowance is excluded. Excess distance is ₹1/km, carrier luggage is ₹150, and waiting is ₹130/hour for Sedan or ₹180/hour for SUV/equivalent. Waiting applies to local and one-way trips, not round trips.
- Local package prices include the configured inclusions. Excess kilometres use the vehicle's active one-way per-kilometre rate; the operator records waiting hours and actual distance on the booking to calculate the final fare.
