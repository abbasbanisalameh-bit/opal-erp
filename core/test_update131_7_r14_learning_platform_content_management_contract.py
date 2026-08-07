import json
from pathlib import Path

from django.test import SimpleTestCase


from core.release_contract_assertions import assert_forward_compatible_release_identity

ROOT = Path(__file__).resolve().parents[1]


def source(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


class LearningPlatformContentManagementContractTests(SimpleTestCase):
    def test_manager_content_routes_and_templates_exist(self):
        urls = source("learning_platform/urls.py")
        views = source("learning_platform/views.py")
        forms = source("learning_platform/forms.py")
        required_routes = [
            'name="manager_account_list"',
            'name="manager_teacher_create"',
            'name="manager_account_toggle"',
            'name="manager_subject_list"',
            'name="manager_subject_create"',
            'name="manager_subject_update"',
            'name="manager_course_list"',
            'name="manager_course_create"',
            'name="manager_course_update"',
            'name="manager_course_status"',
            'name="manager_lesson_list"',
            'name="manager_lesson_create"',
            'name="manager_lesson_update"',
        ]
        for token in required_routes:
            self.assertIn(token, urls)
        for class_name in [
            "LearningTeacherCreateForm",
            "LearningSubjectForm",
            "LearningCourseForm",
            "LearningLessonForm",
        ]:
            self.assertIn(f"class {class_name}", forms)
        self.assertIn("def platform_manager_required", views)
        self.assertIn("is_management_user(request.user)", views)

    def test_mutations_are_post_protected_and_publish_has_minimum_content_gate(self):
        views = source("learning_platform/views.py")
        self.assertIn("@require_POST\ndef manager_account_toggle", views)
        self.assertIn("@require_POST\ndef manager_course_status", views)
        self.assertIn('course.lessons.filter(is_published=True).exists()', views)
        self.assertIn("يجب نشر درس واحد على الأقل قبل نشر الدورة", views)
        self.assertIn("course.status = LearningCourse.Status.DRAFT", views)

    def test_management_uses_existing_models_without_parallel_migration(self):
        migrations = sorted((ROOT / "learning_platform" / "migrations").glob("[0-9][0-9][0-9][0-9]_*.py"))
        migration_names = [path.name for path in migrations]
        self.assertIn("0001_initial.py", migration_names)
        migration_source = "\n".join(path.read_text(encoding="utf-8") for path in migrations)
        models = source("learning_platform/models.py")
        for forbidden_model in ("PlatformTeacher", "PlatformStudent"):
            self.assertNotIn(f"class {forbidden_model}", models)
            self.assertNotIn(forbidden_model, migration_source)

    def test_r14_release_identity_is_coherent(self):
        assert_forward_compatible_release_identity(
            self,
            source,
            min_revision=17,
        )
