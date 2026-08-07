"""Context processor for the shared mandatory monthly evaluation modal."""

from .evaluation_services import monthly_evaluation_prompt_for_user


def monthly_evaluation_prompt(request):
    empty = {"opal_monthly_evaluation_prompt": None}
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or user.is_staff or user.is_superuser:
        return empty
    try:
        return {
            "opal_monthly_evaluation_prompt": monthly_evaluation_prompt_for_user(
                user
            )
        }
    except Exception:
        # A satisfaction prompt is secondary and must never stop a school task.
        return empty
