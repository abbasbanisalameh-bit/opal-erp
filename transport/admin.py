from django.contrib import admin
from .models import DriverProfile, TransportRoute, StudentTransportInfo

@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'vehicle_details', 'is_active_driver')
    search_fields = ('phone_number', 'vehicle_details')

@admin.register(TransportRoute)
class TransportRouteAdmin(admin.ModelAdmin):
    list_display = ('name', 'driver', 'description')
    search_fields = ('name',)

@admin.register(StudentTransportInfo)
class StudentTransportInfoAdmin(admin.ModelAdmin):
    list_display = ('student', 'route', 'pickup_address', 'is_active')
    search_fields = ('student__first_name', 'pickup_address')
