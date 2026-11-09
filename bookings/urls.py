from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("cabs/", views.search_cabs, name="search_cabs"),
    path("cabs/select/", views.choose_vehicle, name="choose_vehicle"),
    path("book/", views.create_booking, name="create_booking"),
    path("book/verify/", views.verify_booking_otp, name="verify_booking_otp"),
    path("booking/<str:reference>/", views.booking_confirmation, name="booking_confirmation"),
    path("my-bookings/", views.my_bookings, name="my_bookings"),
    path("my-bookings/verify/", views.my_bookings_verify, name="my_bookings_verify"),
    path("my-bookings/list/", views.my_bookings_list, name="my_bookings_list"),
    path("my-bookings/cancel/<int:booking_id>/", views.cancel_customer_booking, name="cancel_customer_booking"),
    path("my-bookings/sign-out/", views.my_bookings_logout, name="my_bookings_logout"),
]
