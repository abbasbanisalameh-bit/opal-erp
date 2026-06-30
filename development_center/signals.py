from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Module, Task


def update_module_progress(module):
    if not module:
        return

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


def update_milestone_progress(release):
    if not release:
        return

    milestones = release.milestone_set.all()
    tasks = release.tasks.all()
    total = tasks.count()

    if total == 0:
        progress = 0
    else:
        done = tasks.filter(status="done").count()
        progress = round((done / total) * 100)

    for milestone in milestones:
        milestone.progress = progress
        milestone.completed = progress == 100
        milestone.save(update_fields=["progress", "completed"])


@receiver(post_save, sender=Task)
def task_saved(sender, instance, **kwargs):
    update_module_progress(instance.module)

    if instance.release:
        update_milestone_progress(instance.release)


@receiver(post_delete, sender=Task)
def task_deleted(sender, instance, **kwargs):
    update_module_progress(instance.module)

    if instance.release:
        update_milestone_progress(instance.release)
