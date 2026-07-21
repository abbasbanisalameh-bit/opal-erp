from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


@receiver(post_save, sender="development_center.Task")
def task_saved(sender, instance, **kwargs):
    from development_center.services.workflow_engine import sync_after_task_change

    sync_after_task_change(task=instance)


@receiver(post_delete, sender="development_center.Task")
def task_deleted(sender, instance, **kwargs):
    from development_center.services.workflow_engine import sync_after_task_change

    sync_after_task_change(task=None)
