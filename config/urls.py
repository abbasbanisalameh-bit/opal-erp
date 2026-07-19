from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LoginView
from django.urls import include, path
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import RedirectView
from core import views as core_views


handler400 = "core.security.bad_request"
handler403 = "core.security.permission_denied"
handler404 = "core.security.page_not_found"
handler500 = "core.security.server_error"


opal_login_view = never_cache(
    ensure_csrf_cookie(
        LoginView.as_view(
            template_name='registration/login.html',
            redirect_authenticated_user=True,
        )
    )
)


urlpatterns = [
    path('students/', include('students.urls')),
    path('parent/', include('parent_portal.urls')),
    path(
        'accounts/login/',
        opal_login_view,
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
    path('announcements/', include('announcements.urls')),
]

if settings.OPAL_ENABLE_OPENEMIS:
    urlpatterns.append(path('openemis/', include('openemis_integration.urls')))

if settings.OPAL_ENABLE_DEVELOPMENT_CENTER:
    urlpatterns.append(path('development/', include('development_center.urls')))

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
