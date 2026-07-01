from django.urls import path
from . import views
from . import academic_core_views

app_name = "academics"

urlpatterns = [
    path("students/", views.student_list, name="student_list"),
    path("students/add/", views.student_create, name="student_create"),
    path("students/admission/", views.student_admission, name="student_admission"),
    path("students/<int:student_id>/", views.student_detail, name="student_detail"),
    path("students/<int:student_id>/edit/", views.student_update, name="student_update"),

    path("grades/", academic_core_views.grade_list, name="grade_list"),
    path("grades/add/", academic_core_views.grade_create, name="grade_create"),
    path("grades/<int:pk>/edit/", academic_core_views.grade_update, name="grade_update"),
    path("grades/<int:pk>/delete/", academic_core_views.grade_delete, name="grade_delete"),

    path("sections/", academic_core_views.section_list, name="section_list"),
    path("sections/add/", academic_core_views.section_create, name="section_create"),
    path("sections/<int:pk>/edit/", academic_core_views.section_update, name="section_update"),
    path("sections/<int:pk>/delete/", academic_core_views.section_delete, name="section_delete"),


    path("academic-years/", academic_core_views.academic_year_list, name="academic_year_list"),
    path("academic-years/add/", academic_core_views.academic_year_create, name="academic_year_create"),
    path("academic-years/<int:pk>/edit/", academic_core_views.academic_year_update, name="academic_year_update"),

    path("subjects/", academic_core_views.subject_list, name="subject_list"),
    path("subjects/add/", academic_core_views.subject_create, name="subject_create"),
    path("subjects/<int:pk>/edit/", academic_core_views.subject_update, name="subject_update"),
]

urlpatterns += [
    path("students/<int:pk>/academic-profile/", views.student_academic_profile, name="student_academic_profile"),
]
