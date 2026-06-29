from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Module, Task


def update_module_progress(module):
    tasks = module.tasks.all()
    total = tasks.count()

    if total == 0:
        module.progress = 0
        module.status = "planned"
    else:
        done = tasks.filter(status="done").count()
        module.progress = round((done / total) * 100)

        if module.progress == 100:
            module.status = "completed"
        elif module.progress == 0:
            module.status = "planned"
        else:
            module.status = "development"

    module.save(update_fields=["progress", "status"])


@receiver(post_save, sender=Task)
def task_saved(sender, instance, **kwargs):
    update_module_progress(instance.module)


@receiver(post_delete, sender=Task)
def task_deleted(sender, instance, **kwargs):
    update_module_progress(instance.module)
