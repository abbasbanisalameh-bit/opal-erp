from django.urls import path
from . import views

app_name = "academics"

urlpatterns = [
    path("students/", views.student_list, name="student_list"),
    path("students/add/", views.student_create, name="student_create"),
    path("students/admission/", views.student_admission, name="student_admission"),
    path("students/<int:student_id>/", views.student_detail, name="student_detail"),
    path("students/<int:student_id>/edit/", views.student_update, name="student_update"),
]


from . import academic_core_views

urlpatterns += [
    path("academic-years/", academic_core_views.academic_year_list, name="academic_year_list"),
    path("academic-years/add/", academic_core_views.academic_year_create, name="academic_year_create"),
    path("academic-years/<int:pk>/edit/", academic_core_views.academic_year_update, name="academic_year_update"),

    path("subjects/", academic_core_views.subject_list, name="subject_list"),
    path("subjects/add/", academic_core_views.subject_create, name="subject_create"),
    path("subjects/<int:pk>/edit/", academic_core_views.subject_update, name="subject_update"),
]
