from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Module, Task


def update_progress(module):
    tasks = module.tasks.all()
    total = tasks.count()

    if total == 0:
        module.progress = 0
    else:
        done = tasks.filter(status="done").count()
        module.progress = round(done * 100 / total)

    module.save(update_fields=["progress"])


@receiver(post_save, sender=Task)
def task_saved(sender, instance, **kwargs):
    update_progress(instance.module)


@receiver(post_delete, sender=Task)
def task_deleted(sender, instance, **kwargs):
    update_progress(instance.module)
