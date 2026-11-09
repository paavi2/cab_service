# Cab Booking Website — Product Requirements Document

**Status:** Draft for discussion  
**Version:** 0.1  
**Date:** 9 November 2026  
**Product:** Public cab booking website and lightweight operator admin portal

## 1. Product summary

Build a mobile-friendly public website where a customer can request a cab after verifying their phone number with an SMS one-time password (OTP). On a successful booking, the operator (the site owner) receives the booking details through a configured notification channel: WhatsApp, SMS, or phone call. The operator can review bookings, manage the available vehicles and their photos, and change prices as conditions change.

The first release is an operator-assisted booking service. A booking request is not presented as a confirmed ride until the operator accepts it. The first release does not require automated driver dispatch, online payment, or live vehicle tracking.

## 2. Goals

- Let a customer submit a real booking request on a public website with minimal friction.
- Verify the customer's phone number before accepting a booking request.
- Notify the operator promptly and reliably when a booking is created.
- Let the operator view booking history and manage vehicles, photos, and current prices without developer help.
- Make prices and their effective dates/conditions clear to customers before they submit.
- Establish a phased product foundation that can grow into dispatch, payments, and trip tracking.

## 3. Non-goals for Phase 1

- Automatic driver matching, driver app, or live GPS tracking.
- Online card/wallet payments, refunds, or driver payouts.
- Guaranteed instant ride availability. The operator confirms availability after receiving the request.
- Surge pricing calculated automatically from traffic, weather, or demand.
- Native iOS/Android applications.
- Multi-operator marketplace or customer ratings.

## 4. Users and roles

### Customer

Needs to see available vehicle choices and pricing, provide trip details, verify a phone number, submit a booking, and know whether the request was received and later accepted.

### Operator / administrator

Needs to receive booking alerts, review and update booking status, contact the customer, manage vehicle listings and images, and update prices with a record of changes.

### Future driver role

May accept assigned trips and update trip progress in a later phase. Not needed in Phase 1.

## 5. Phase plan

### Phase 1 — Public booking and operator-assisted fulfilment (MVP)

**Customer capabilities**

- Browse listed vehicle varieties with name, passenger/luggage details, description, and photos.
- Search one-way, round-trip, or local journeys by pickup area, destination, and trip date/time. Round trips also require a return date/time. Local journeys use admin-configured vehicle packages (duration, included kilometres, and package price); airport trips are later.
- Enter exact doorstep pickup and destination addresses, with optional landmarks.
- Compare vehicle cards with capacity, photos, per-kilometre rate, minimum distance, and minimum fare.
- Enter name and mobile number; verify the number by OTP. Live SMS delivery is scheduled as a final integration step; local development may use the console OTP adapter.
- Submit the booking only after OTP verification.
- After OTP verification, see the booking status as **Booked** and a booking reference. Tell the customer the owner will confirm within 12 hours and, after confirmation, request a 10% advance.
- Open **My Bookings** to review requests associated with their OTP-verified mobile number. New customers verify their number with an OTP; a recently verified booking session may access the page directly.
- See customer-facing statuses: **Booked**, **Confirmed**, **Cancelled**, plus clear outcomes for rejected and completed requests.
- Cancel a future booking from My Bookings. If cancellation is made within 24 hours before pickup, record a ₹300 fee to deduct from the advance paid; no fee applies earlier. Show this policy before booking and before final cancellation.
- Make completed booking details available to the customer until five days after completion. A daily scheduled cleanup anonymizes personal details after that period while retaining the non-personal booking record for operations.
- Receive booking status updates through the contact method selected for the release (initially SMS is recommended; WhatsApp may be added if the provider setup is ready).

**Operator capabilities**

- Sign into a protected admin website.
- View/search booking history and booking details, including contact and trip information.
- Update booking status: New, Contacted, Accepted, Rejected, Cancelled, Completed. Record timestamps and the operator action where practical.
- Receive a notification for each new verified booking through the configured WhatsApp, SMS, or voice-call integration. If delivery fails, show the failure in the admin interface and retain the booking.
- Manage vehicle varieties: add/edit/deactivate, descriptions, capacities, and photos.
- Manage pricing: set/edit price, pricing basis, vehicle category, effective-from time, optional effective-until time, and customer-facing notes. Keep a change history showing who changed what and when.
- Configure local-trip packages per vehicle, Sedan/SUV-equivalent class, local inclusions/exclusions, and charges. Local defaults include toll, state tax, AC, driver allowance, GST/Tax, parking, and two bags. Night allowance is excluded. Distance beyond the package is ₹1/km, and an optional luggage carrier is ₹150. These amounts and displayed terms are editable in admin. Waiting defaults remain ₹130/hour for Sedan and ₹180/hour for SUV/equivalent; waiting applies to local and one-way bookings, but not round trips.
- Record actual travelled kilometres on a booking after the trip. The admin view calculates the final distance-based fare using the price snapshot and minimum distance.
- Configure the operator notification destination and preferred channel(s).

**Phase 1 acceptance criteria**

1. A customer cannot create a booking until a valid OTP sent to the entered phone number has been verified.
2. OTPs expire, have a limited number of attempts and resends, and cannot be reused after successful verification.
3. A successful submission creates one booking with a unique reference; repeated taps or network retries do not create duplicate bookings.
4. The customer sees the fare/pricing basis and the request/confirmation status without ambiguity.
5. The operator can see every created booking in the admin portal even if a notification provider is unavailable.
6. A new booking triggers the configured operator notification; failed notifications are visible and can be retried or handled manually.
7. Only authorized administrators can view customer data or change prices, vehicles, bookings, and notification settings.
8. Price changes are auditable and apply according to their effective dates; the one-way rate and applicable minimum fare are snapshotted on the booking.
9. A customer can access **My Bookings** only after phone OTP verification and sees only bookings for that phone number.
10. The customer can cancel a future eligible booking; cancellation within 24 hours of pickup records the ₹300 charge and immediately changes customer status to Cancelled.
11. Marking a booking Completed records the completion time; the scheduled cleanup anonymizes customer-identifying details five days later.
12. The website is usable on common mobile and desktop screen sizes and deployed over HTTPS on a public domain.

### Phase 2 — Customer communication and operational reliability

- Automated customer SMS/WhatsApp updates when an operator accepts, rejects, or changes a booking.
- Admin filters, exports, and daily/weekly booking summaries.
- Notification retry queue, delivery status, provider health checks, and operational alerts.
- Configurable service area, operating hours, lead time, blackout dates, and booking limits.
- Basic abuse controls such as rate limits, OTP throttling, duplicate-request detection, and optional CAPTCHA after suspicious activity.

### Phase 3 — Driver assignment and trip progress

- Driver profiles and availability managed by the operator.
- Assign a booking to a driver/vehicle and notify both parties.
- Driver-facing mobile web view to accept/decline and update trip states (Assigned, En route, Arrived, Started, Completed).
- Customer status notifications and optional location sharing during an active trip, with explicit consent and limited retention.
- Dispatch board for operators and basic driver performance/history.

### Phase 4 — Online payments and commercial operations

- Payment provider integration for deposits or full fare, configurable by service and vehicle.
- Payment status, receipts, cancellation/refund handling, and reconciliation reports.
- Optional promo codes, taxes/fees, and invoices.
- Enhanced reporting and role-based access for multiple staff members.

### Phase 5 — Scale and optimization

- Native apps or progressive web app enhancements if customer/driver usage justifies them.
- Automated dispatch suggestions, demand/availability insights, and carefully governed dynamic pricing.
- Multi-city/service-area support, localization, and multiple currencies where required.
- Customer feedback, support workflows, and service quality analytics.

## 6. Core flows

### Customer booking

1. Customer searches a one-way or round-trip route, dates, and times.
2. Website displays vehicle cards and minimum fare. The final distance-based fare uses actual kilometres recorded after the trip.
3. Customer selects a vehicle and enters doorstep addresses, landmarks, passenger details, name, and phone number.
4. Customer verifies the phone by OTP; the SMS provider is added in the final integration stage.
5. Server snapshots the applicable vehicle rate and minimum fare, then saves the request after verification.
6. Website displays the booking reference and **Booked** status. The owner is expected to confirm within 12 hours; after confirmation, the owner contacts the customer to arrange a 10% advance.
7. Customer can enter My Bookings, verify the same mobile number with OTP, and review all matching bookings. The website exposes only bookings for the verified number.
8. Customer may cancel an eligible future booking. Within 24 hours before pickup, the system records a ₹300 charge to deduct from the advance paid and changes the customer status to Cancelled.
9. After the operator marks a journey Completed, a daily cleanup anonymizes customer personal data after five days.
10. System queues operator notification and records delivery result. Operator contacts customer and updates status.


### My Bookings and cancellation

1. Customer enters the Indian mobile number used for booking and receives a short-lived OTP.
2. After OTP verification, list only that phone number’s non-expired bookings and show the customer-facing status.
3. For a future booking, customer may request cancellation. Before submission, state whether a ₹300 fee applies based on whether pickup is within 24 hours.
4. Record the cancellation status and any applicable fee in the booking history. The operator handles deduction from the advance paid; online payment collection is a later phase.

### Operator notification and management

1. A verified booking is saved before attempting external notification delivery.
2. System sends the configured alert with the booking reference, customer contact, pickup/drop-off, requested time, selected vehicle, and quoted price. Avoid including OTPs or unnecessary sensitive data.
3. Operator opens the admin portal, reviews details, and accepts/rejects or contacts the customer.
4. Status and price snapshot remain in booking history for audit and customer support.

### Price update

1. Authorized operator edits a vehicle/category price and pricing basis, plus effective date and customer-facing notes.
2. System validates the values and records the prior and new values, actor, and timestamp.
3. New bookings use the active price version. Existing bookings retain their original quoted price unless explicitly re-quoted with customer agreement.

## 7. Functional requirements

### Booking and pricing

- Store customer name, normalized phone number, full pickup and destination addresses, optional landmarks, requested date/time, selected vehicle, passenger count if applicable, notes, quoted price, pricing version, status, and timestamps.
- Admin configures each vehicle's one-way rate per kilometre. Round-trip rate is one-way rate minus ₹1/km. Minimum billable distance is 130 km for one-way and 250 km for round trips.
- Local bookings use an active local package configured for the selected vehicle, with duration, included kilometres, and package price. After the trip, final fare is package price plus distance beyond included kilometres at the configured local extra-distance rate, plus recorded waiting hours at the snapshotted category rate and any selected carrier charge. Local inclusions/exclusions and rates are snapshotted on the booking.
- The result card shows the minimum fare calculated using that minimum distance. After the trip, the operator records actual kilometres; billable kilometres are the greater of actual kilometres or the trip minimum.
- For outstation bookings, driver beta/allowance, tolls, and GST are excluded from the per-kilometre fare and charged separately. For local packages, admin-configured inclusions default to driver beta, toll, tax, two luggage items, and GST; extra distance, waiting charges, and extra luggage are excluded. No automatic route-distance estimate is required for the MVP.
- Store the rate, trip type, minimum distance, and minimum fare snapshot on each booking. Calculate the final distance-based fare from the actual kilometres and the snapshotted rate.
- Never silently change the accepted booking price. Any revised quote requires operator action and customer agreement.
- Keep bookings after cancellation or rejection for operational history; do not hard-delete them through normal admin actions. After a booking is marked completed, anonymize personal fields five days later while retaining the non-personal operational record. The scheduled cleanup command must run daily in production.
- A cancellation made within 24 hours before the scheduled pickup incurs a ₹300 charge deducted from the advance paid; record the amount separately from booking status.

### OTP and abuse prevention

- Send OTP only to the phone number supplied by the customer through an SMS provider.
- Use short-lived, single-use OTPs; store only a secure hash where feasible.
- Enforce attempt, resend, and per-phone/IP rate limits; avoid revealing whether a phone number already has bookings.
- Invalidate OTP after successful verification, expiration, or too many failed attempts.
- Do not treat phone verification alone as proof of identity or guaranteed protection against all abuse.

### Notifications

- Notification preference is an admin configuration, not a customer choice for where the operator is alerted.
- Support one or more configured channels: SMS, WhatsApp Business messaging, or automated voice call, subject to provider availability and account approval.
- Store channel, recipient, attempt count, provider result, and timestamps. Do not store provider secrets in application data or source control.
- Provide a manual fallback: bookings remain visible in the admin portal and a delivery failure can be retried.
- Customer-facing OTP SMS is a separate message flow from operator booking alerts.

### Admin and content

- Admin authentication must use strong password/session controls; add MFA if supported by the selected identity provider.
- Restrict image uploads by file type and size; store images in managed object storage and serve optimized derivatives.
- Allow vehicle listing to be hidden without deleting its past booking references.
- Log administrative changes to prices, vehicle listings, notification settings, and booking statuses.

## 8. Non-functional requirements

- Responsive and accessible interface; keyboard operation, readable contrast, and labeled form fields.
- Treat low-bandwidth mobile access as a product requirement. Render the booking flow as server-generated HTML and keep JavaScript optional for core booking tasks; progressively enhance interactions where useful.
- Keep the initial booking screen lean: target no more than 200 KB compressed for HTML, CSS, and JavaScript combined, excluding images. Do not load map SDKs, large analytics bundles, or custom web fonts on the initial screen.
- Optimize vehicle photos into small responsive sizes and modern formats; load only images near the viewport and lazy-load images further down the page. The booking form and price must remain usable while images load or fail.
- Set a measurable low-network target: on a mobile viewport with 1 Mbps downstream bandwidth and 400 ms round-trip latency, the main booking content should become usable within 3 seconds of navigation. Validate this using network throttling before release.
- Preserve entered booking details when a request is delayed or temporarily fails; show a clear retry state and prevent duplicate bookings when the customer retries.
- Monitor real-user loading performance after launch; target a 75th-percentile Largest Contentful Paint (LCP) of 2.5 seconds or less where field conditions allow.
- HTTPS everywhere; secure cookies; server-side authorization for every admin operation.
- Protect personal data in transit and at rest; collect only data required to fulfil and support bookings.
- Define retention and deletion rules for customer details, OTP metadata, notification logs, and booking history based on applicable local law.
- Back up production data and document restore steps before public launch.
- Monitor application errors, booking creation, OTP delivery, and operator-notification failures without logging OTPs or unnecessary personal information.
- Use a production/staging separation and keep provider credentials in a managed secrets store.
- State supported browser versions and service availability targets before launch; initial operations should have a documented manual fallback.

## 9. Success measures

- Number of verified booking requests and percentage successfully submitted.
- OTP delivery and verification completion rates; resend and abuse rates.
- Operator notification delivery rate and time from booking to alert.
- Time from new request to operator response and acceptance rate.
- Booking completion, cancellation, and rejection rates.
- Cancellation-charge incidence and collection status.
- Customer drop-off at vehicle selection, trip details, and OTP steps.

## 10. Dependencies and risks

- SMS OTP and notification providers, sender registration, WhatsApp Business approval/templates, and voice-call support vary by country.
- Maps/geocoding, distance calculation, and route pricing require a provider and incur usage charges; MVP may instead use pickup/drop-off text and operator-confirmed quote.
- Transportation licensing, commercial vehicle insurance, consumer disclosures, privacy, tax, and cancellation obligations depend on operating location.
- Dynamic or manually adjusted pricing must be disclosed clearly and applied consistently to avoid customer disputes.
- SMS delivery is not guaranteed; admin booking history and a fallback alert process are essential.

## 11. Decisions to confirm before implementation

These decisions do not block drafting the PRD, but they affect the implementation plan:

1. **Launch location and service area:** country/city or cities, and whether trips can cross those boundaries.
2. **Initial pricing model:** per-vehicle one-way rate per kilometre; round-trip rate is ₹1/km lower; 130 km one-way and 250 km round-trip minimums. Driver beta, tolls, and GST are extra.
3. **What does “booking success” mean?** Recommended MVP meaning: verified request saved and operator alerted; ride remains pending until operator acceptance.
4. **Operator alert channel:** preferred primary channel and fallback (SMS, WhatsApp, automated voice call); destination number; should alerts go to one person or several?
5. **Customer updates:** SMS only in Phase 1, or WhatsApp as well? What should happen if a customer cannot receive SMS OTP?
6. **Booking inputs:** immediate rides, scheduled rides, or both; required lead time; passenger/luggage details; extra stops; special requests.
7. **Fleet:** vehicle categories and details, which the owner will provide; whether a customer selects a specific car or only a category.
8. **Admin access:** one owner account initially or multiple staff accounts; who can change prices and statuses?
9. **Payments:** confirm no online payment in Phase 1 and whether payment is collected by the driver, cash, or another method.
10. **Public brand/domain:** business name, logo, preferred domain, and languages/currency.

## 12. Suggested delivery order

1. Confirm the decisions above and collect initial fleet photos/details and sample price rules.
2. Produce screen flows and a data model for customer booking, OTP verification, price versions, notification attempts, and admin actions.
3. Build the public booking flow and protected admin portal against a staging environment.
4. Integrate SMS OTP and the selected operator notification channel; verify provider delivery and fallback behavior.
5. Review privacy, local transport requirements, customer-facing terms, and support procedures.
6. Run acceptance checks with test bookings, mobile devices, failed SMS delivery, duplicate submissions, price changes, and admin access controls.
7. Deploy to a public domain with HTTPS, backups, monitoring, and a documented incident/manual booking process.

## 13. Glossary

- **Booking request:** customer request awaiting operator confirmation.
- **Accepted booking:** operator-confirmed ride with availability agreed.
- **Price version:** auditable set of pricing values and effective dates used to quote a booking.
- **OTP:** one-time password sent by SMS to verify access to the supplied phone number.
- **Operator:** business owner or staff member managing bookings and fleet content.
