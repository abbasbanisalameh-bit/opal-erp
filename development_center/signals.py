from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from development_center.models import Task
from development_center.services.workflow_engine import sync_after_task_change

@receiver(post_save, sender=Task)
def task_saved(sender, instance, **kwargs):
    sync_after_task_change(task=instance)

@receiver(post_delete, sender=Task)
def task_deleted(sender, instance, **kwargs):
    sync_after_task_change(task=None)
