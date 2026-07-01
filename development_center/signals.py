from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Task
from development_center.services.workflow_engine import sync_after_task_change


@receiver(post_save, sender=Task)
def task_saved(sender, instance, **kwargs):
    sync_after_task_change(instance)


@receiver(post_delete, sender=Task)
def task_deleted(sender, instance, **kwargs):
    # A deleted task may affect all aggregate metrics. Keep this conservative and safe.
    from development_center.services.workflow_engine import run_workflow_engine
    run_workflow_engine()
