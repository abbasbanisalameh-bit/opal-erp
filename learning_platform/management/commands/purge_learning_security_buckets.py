from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from learning_platform.models import LearningAPIToken, LearningRateLimitBucket


class Command(BaseCommand):
    help = "احذف نوافذ الحد القديمة ورموز API المنتهية أو الملغاة القديمة."

    def handle(self, *args, **options):
        now = timezone.now()
        buckets, _ = LearningRateLimitBucket.objects.filter(
            window_started_at__lt=now - timedelta(days=2)
        ).delete()
        tokens, _ = LearningAPIToken.objects.filter(
            expires_at__lt=now - timedelta(days=30)
        ).delete()
        self.stdout.write(self.style.SUCCESS(f"buckets_deleted={buckets} tokens_deleted={tokens}"))
