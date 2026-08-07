from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from enterprise_ops.permissions import has_feature_permission

from .forms import ParentFamilyPersonalForm


class ParentPortalUpdate123Tests(SimpleTestCase):
    def test_parent_personal_form_builds_without_undeclared_photo_field(self):
        form = ParentFamilyPersonalForm()
        self.assertEqual(
            list(form.fields),
            ["phone", "secondary_phone", "email", "job_title", "address", "medical_notes"],
        )
        self.assertNotIn("photo", form.fields)

    @patch("enterprise_ops.permissions.role_code", return_value="parent")
    def test_parent_complaint_channel_cannot_be_hidden_by_old_permission_rows(self, _role):
        user = SimpleNamespace(is_authenticated=True, is_superuser=False, is_staff=False)
        self.assertTrue(has_feature_permission(user, "workflow", "view"))
        self.assertTrue(has_feature_permission(user, "workflow", "create"))
