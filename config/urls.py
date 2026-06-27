from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.contrib.auth.views import LoginView


urlpatterns = [
    path(
        'accounts/login/',
        LoginView.as_view(
            template_name='registration/login.html',
            redirect_authenticated_user=True
        ),
        name='login'
    ),
    path('login/', lambda request: redirect('/accounts/login/')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('admin/', admin.site.urls),

    path('', include('dashboard.urls')),
    path('academics/', include('academics.urls')),
    path('admissions/', include('admissions.urls')),
    path('documents/', include('documents.urls')),
    path('exams/', include('exams.urls')),
    path('accounting/', include('accounting.urls')),
    path('attendance/', include('attendance_v2.urls')),

    path('students/', lambda request: redirect('academics:student_list')),
    path('students/add/', lambda request: redirect('academics:student_admission')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
