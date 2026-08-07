"""Compatibility bridge for deployments that still reference the old processor."""


def parent_teacher_evaluation_prompt(request):
    """Delegate to the single OPAL monthly-evaluation context processor."""
    from enterprise_ops.evaluation_context import monthly_evaluation_prompt

    return monthly_evaluation_prompt(request)
