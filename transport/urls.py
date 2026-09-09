from django.urls import path

from . import views

app_name = "transport"

urlpatterns = [
    path("", views.transport_dashboard, name="transport-dashboard"),

    path("routes/", views.route_list, name="route-list"),
    path("routes/add/", views.route_create, name="route-create"),
    path("routes/<int:pk>/edit/", views.route_edit, name="route-edit"),
    path("routes/<int:pk>/toggle/", views.route_toggle, name="route-toggle"),

    path("drivers/", views.driver_list, name="driver-list"),
    path("drivers/add/", views.driver_create, name="driver-create"),
    path("drivers/<int:pk>/credentials/", views.driver_credentials, name="driver-credentials"),
    path("drivers/<int:pk>/edit/", views.driver_edit, name="driver-edit"),
    path("drivers/<int:pk>/impersonate/", views.driver_impersonate, name="driver-impersonate"),
    path("drivers/impersonate/stop/", views.driver_impersonate_stop, name="driver-impersonate-stop"),

    path("trips/", views.trip_list, name="trip-list"),
    path("trips/prepare-today/", views.prepare_today, name="prepare-today"),
    path("trips/add/", views.trip_create, name="trip-create"),
    path("trips/<int:pk>/edit/", views.trip_edit, name="trip-edit"),
    path("trips/<int:pk>/detail/", views.trip_detail, name="trip-detail"),
    path("trips/<int:pk>/start/", views.driver_start_trip, name="driver-start-trip"),
    path("trips/<int:pk>/finish/", views.driver_finish_trip, name="driver-finish-trip"),
    path("trips/<int:pk>/rebuild-stops/", views.trip_rebuild_stops, name="trip-rebuild-stops"),

    path("subscriptions/", views.subscription_list, name="subscription-list"),
    path("subscriptions/<int:pk>/edit/", views.subscription_edit, name="subscription-edit"),

    path("groups/", views.group_list, name="group-list"),
    path("family-locations/", views.family_location_list, name="family-location-list"),
    path("family-locations/<int:family_id>/edit/", views.family_location_edit, name="family-location-edit"),
    path("family-locations/request-missing/", views.request_missing_family_locations, name="request-missing-family-locations"),
    path("assignments/", views.assignment_list, name="assignment-list"),
    path("assignments/add/", views.assignment_create, name="assignment-create"),
    path("assignments/<int:pk>/deactivate/", views.assignment_deactivate, name="assignment-deactivate"),

    path("parent/", views.parent_transport_dashboard, name="parent-transport-dashboard"),
    path("driver/", views.driver_transport_dashboard, name="driver-transport-dashboard"),
    path("tracking/", views.manager_tracking, name="manager-tracking"),
    path("tracking/api/", views.tracking_api, name="tracking-api"),
    path("stops/<int:pk>/arrive/", views.trip_stop_arrive, name="trip-stop-arrive"),
    path("stops/<int:pk>/depart/", views.trip_stop_depart, name="trip-stop-depart"),
    path("driver/trips/<int:pk>/gps/", views.driver_gps_ingest, name="driver-gps-ingest"),
]
