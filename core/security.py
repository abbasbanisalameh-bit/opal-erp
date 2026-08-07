from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import requires_csrf_token


def _no_store(response):
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, private, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


@never_cache
@requires_csrf_token
def csrf_failure(request, reason=""):
    """Recover safely from stale login forms and hide Django diagnostics.

    Authentication still requires a fresh, valid CSRF token.  A rejected login
    is never retried automatically and submitted credentials are never copied
    into the redirect or response.
    """

    login_url = reverse("login")
    if request.method == "POST" and request.path == login_url:
        query = {"csrf_retry": "1"}
        next_url = request.POST.get("next", "").strip()
        if next_url:
            query["next"] = next_url
        response = redirect(f"{login_url}?{urlencode(query)}")
        response.delete_cookie(
            settings.CSRF_COOKIE_NAME,
            path=settings.CSRF_COOKIE_PATH,
            domain=settings.CSRF_COOKIE_DOMAIN,
            samesite=settings.CSRF_COOKIE_SAMESITE,
        )
        return _no_store(response)

    if request.path.startswith("/learning/"):
        response = render(
            request,
            "learning_platform/error.html",
            {
                "status_code": 403,
                "error_title": "انتهت صلاحية النموذج",
                "error_message": "حدّث الصفحة ثم أعد المحاولة. لم تُحفظ أي بيانات من الطلب المرفوض.",
            },
            status=403,
        )
        return _no_store(response)

    response = render(request, "403_csrf.html", {"login_url": login_url}, status=403)
    return _no_store(response)


def _friendly_error(request, *, status, title, message):
    if request.path.startswith("/learning/"):
        return render(
            request,
            "learning_platform/error.html",
            {"status_code": status, "error_title": title, "error_message": message},
            status=status,
        )
    return render(
        request,
        "errors/error.html",
        {"status_code": status, "error_title": title, "error_message": message},
        status=status,
    )


@requires_csrf_token
def bad_request(request, exception=None):
    return _friendly_error(
        request,
        status=400,
        title="تعذر تنفيذ الطلب",
        message="تحقق من البيانات وأعد المحاولة. لم يتم حفظ طلب غير صالح.",
    )


@requires_csrf_token
def permission_denied(request, exception=None):
    return _friendly_error(
        request,
        status=403,
        title="غير مصرح بالدخول",
        message="لا يملك حسابك الصلاحية المطلوبة لهذا الإجراء.",
    )


@requires_csrf_token
def page_not_found(request, exception=None):
    return _friendly_error(
        request,
        status=404,
        title="الصفحة غير موجودة",
        message="قد يكون الرابط قديمًا أو أن الصفحة نُقلت إلى مسارها المعتمد.",
    )


@requires_csrf_token
def server_error(request):
    return _friendly_error(
        request,
        status=500,
        title="حدث خطأ غير متوقع",
        message="لم تُعرض أي تفاصيل تقنية. أعد المحاولة أو تواصل مع مدير النظام.",
    )
