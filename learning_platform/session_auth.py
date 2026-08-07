from functools import wraps
from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from .models import LearningAccount, LearningAuditEvent


LEARNING_SESSION_KEY = "opal_learning_account_id"
LEARNING_AUTH_VERSION_KEY = "opal_learning_auth_version"
REQUEST_CACHE_ATTRIBUTE = "_opal_learning_account"


def get_learning_account(request):
    if hasattr(request, REQUEST_CACHE_ATTRIBUTE):
        return getattr(request, REQUEST_CACHE_ATTRIBUTE)
    account = None
    account_id = request.session.get(LEARNING_SESSION_KEY)
    if account_id:
        account = LearningAccount.objects.filter(pk=account_id, is_active=True).first()
        session_auth_version = request.session.get(LEARNING_AUTH_VERSION_KEY, 1)
        if account is None or session_auth_version != account.auth_version:
            account = None
            request.session.pop(LEARNING_SESSION_KEY, None)
            request.session.pop(LEARNING_AUTH_VERSION_KEY, None)
    setattr(request, REQUEST_CACHE_ATTRIBUTE, account)
    return account


def start_learning_session(request, account, *, ip_address=None, action=LearningAuditEvent.Action.LOGIN):
    request.session.cycle_key()
    request.session[LEARNING_SESSION_KEY] = account.pk
    request.session[LEARNING_AUTH_VERSION_KEY] = account.auth_version
    setattr(request, REQUEST_CACHE_ATTRIBUTE, account)
    account.last_login_at = timezone.now()
    account.save(update_fields=["last_login_at"])
    LearningAuditEvent.objects.create(account=account, action=action, ip_address=ip_address)


def end_learning_session(request, *, ip_address=None):
    account = get_learning_account(request)
    if account is not None:
        LearningAuditEvent.objects.create(
            account=account,
            action=LearningAuditEvent.Action.LOGOUT,
            ip_address=ip_address,
        )
    request.session.pop(LEARNING_SESSION_KEY, None)
    request.session.pop(LEARNING_AUTH_VERSION_KEY, None)
    if hasattr(request, REQUEST_CACHE_ATTRIBUTE):
        delattr(request, REQUEST_CACHE_ATTRIBUTE)
    request.session.cycle_key()


def learning_login_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        account = get_learning_account(request)
        if account is None:
            login_url = reverse("learning_platform:login")
            query = urlencode({"next": request.get_full_path()})
            return redirect(f"{login_url}?{query}")
        request.learning_account = account
        if bool(getattr(settings, "OPAL_LEARNING_PUBLIC_LAUNCH", False)) and (
            not account.terms_accepted_at or not account.privacy_accepted_at
        ):
            return redirect("learning_platform:legal_acceptance")
        return view_func(request, *args, **kwargs)

    return wrapped
