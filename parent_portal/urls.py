from django.urls import path
from . import views

app_name="parent_portal"

urlpatterns=[
    path("",views.dashboard,name="dashboard"),
]
