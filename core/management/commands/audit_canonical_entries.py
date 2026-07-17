from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Count

from academics.grade_names import grade_name_key
from academics.models import Grade, Section
from exams.models import StudentMark
from students.models import Student
from teachers.models import Teacher


class Command(BaseCommand):
    help = "Audit canonical OPAL entry sources and report duplicate data without changing it."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("OPAL canonical entry audit"))
        total_issues = 0

        total_issues += self._simple_duplicates(
            "طلاب برقم وطني مكرر",
            Student,
            "national_id",
        )
        total_issues += self._simple_duplicates(
            "طلاب برقم وزاري مكرر",
            Student,
            "ministry_student_id",
        )
        total_issues += self._simple_duplicates(
            "معلمون برقم وطني مكرر",
            Teacher,
            "national_id",
        )
        total_issues += self._simple_duplicates(
            "معلمون برقم وزاري مكرر",
            Teacher,
            "ministry_teacher_id",
        )
        total_issues += self._grade_duplicates()
        total_issues += self._section_duplicates()
        total_issues += self._mark_duplicates()

        if total_issues:
            self.stdout.write(
                self.style.WARNING(
                    f"اكتملت المراجعة ووجدت {total_issues} مجموعة تحتاج مراجعة. لم يتم تعديل أي سجل."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("لا توجد ازدواجيات في المصادر الأساسية."))

    def _simple_duplicates(self, title, model, field):
        groups = list(
            model.objects.exclude(**{field: ""})
            .values(field)
            .annotate(total=Count("id"))
            .filter(total__gt=1)
            .order_by(field)
        )
        self.stdout.write(f"\n{title}: {len(groups)}")
        for group in groups:
            self.stdout.write(f"- {group[field]}: {group['total']}")
        return len(groups)

    def _grade_duplicates(self):
        grouped = defaultdict(list)
        for grade in Grade.objects.select_related("school").order_by("school_id", "id"):
            grouped[(grade.school_id, grade_name_key(grade.name))].append(grade)
        groups = [items for (_, key), items in grouped.items() if key and len(items) > 1]
        self.stdout.write(f"\nصفوف مكررة بالاسم الموحّد: {len(groups)}")
        for items in groups:
            self.stdout.write(
                f"- {items[0].school}: " + ", ".join(f"{item.name} (#{item.pk})" for item in items)
            )
        return len(groups)

    def _section_duplicates(self):
        groups = list(
            Section.objects.values("academic_year_id", "branch_id", "grade_id", "name")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
        )
        self.stdout.write(f"\nشعب مكررة ضمن الصف والعام والفرع: {len(groups)}")
        for group in groups:
            self.stdout.write(
                "- year={academic_year_id}, branch={branch_id}, grade={grade_id}, "
                "name={name}: {total}".format(**group)
            )
        return len(groups)

    def _mark_duplicates(self):
        groups = list(
            StudentMark.objects.values("exam_id", "student_id")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
        )
        self.stdout.write(f"\nعلامات مكررة للطالب في الامتحان نفسه: {len(groups)}")
        for group in groups:
            self.stdout.write(
                f"- exam={group['exam_id']}, student={group['student_id']}: {group['total']}"
            )
        return len(groups)
