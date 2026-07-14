from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LoginView
from django.urls import include, path
from django.views.generic import RedirectView
from core import views as core_views


urlpatterns = [
    path('students/', include('students.urls')),
    path('parent/', include('parent_portal.urls')),
    path(
        'accounts/login/',
        LoginView.as_view(
            template_name='registration/login.html',
            redirect_authenticated_user=True,
        ),
        name='login',
    ),
    path('login/', RedirectView.as_view(pattern_name='login', permanent=False)),
    path('accounts/', include('accounts.urls')),
    path('admin/', core_views.admin_disabled, name='admin_disabled'),
    path('settings/', include('core.urls')),
    path('', include('dashboard.urls')),
    path('academics/', include('academics.urls')),
    path('curriculum/', include('curriculum.urls')),
    path('admissions/', include('admissions.urls')),
    path('documents/', include('documents.urls')),
    path('exams/', include('exams.urls')),
    path('accounting/', include('accounting.urls')),
    path('attendance/', include('attendance_v2.urls')),
    path('teachers/', include('teachers.urls')),
    path('timetable/', include('timetable.urls')),
    path('enterprise/', include('enterprise_ops.urls')),
]

if settings.OPAL_ENABLE_OPENEMIS:
    urlpatterns.append(path('openemis/', include('openemis_integration.urls')))

if settings.OPAL_ENABLE_DEVELOPMENT_CENTER:
    urlpatterns.append(path('development/', include('development_center.urls')))

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
