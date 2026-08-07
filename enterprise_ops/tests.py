from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import ApprovalAction, Notification, RolePermissionRule, WorkflowRequest
from .permissions import has_feature_permission
from .services import notify, transition_workflow


class EnterpriseWorkflowTests(TestCase):
    def setUp(self):
        self.requester = User.objects.create_user("workflow_requester", password="pass")
        self.manager = User.objects.create_user("workflow_manager", password="pass", is_staff=True)
        self.owner = User.objects.create_superuser("workflow_owner", "owner@example.test", "pass")
        self.workflow = WorkflowRequest.objects.create(
            request_type="general",
            title="طلب تشغيلي",
            requester=self.requester,
            status="new",
        )

    def test_workflow_transition_is_audited_and_invalid_transition_is_rejected(self):
        old, new = transition_workflow(self.workflow, self.manager, "approve", "تمت المراجعة")
        self.workflow.refresh_from_db()
        self.assertEqual((old, new), ("new", "approved"))
        self.assertEqual(self.workflow.status, "approved")
        self.assertTrue(ApprovalAction.objects.filter(workflow=self.workflow, action="approve").exists())
        with self.assertRaises(ValidationError):
            transition_workflow(self.workflow, self.manager, "review")

    def test_permission_matrix_is_superuser_only(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("enterprise_ops:permission_matrix"))
        self.assertRedirects(response, reverse("dashboard:home"), fetch_redirect_response=False)
        self.assertEqual(RolePermissionRule.objects.count(), 0)

        self.client.force_login(self.owner)
        response = self.client.get(reverse("enterprise_ops:permission_matrix"))
        self.assertEqual(response.status_code, 200)
        self.assertGreater(RolePermissionRule.objects.count(), 0)

    def test_event_notification_is_not_duplicated(self):
        first = notify(self.requester, "اختبار", "حدث واحد", event_key="payment:1")
        second = notify(self.requester, "اختبار", "حدث واحد", event_key="payment:1")
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Notification.objects.filter(recipient=self.requester).count(), 1)

    def test_notification_opens_its_local_event_and_is_retained(self):
        item = notify(
            self.requester,
            "افتح الطلب",
            "انتقال مباشر",
            link=reverse("enterprise_ops:workflow_detail", args=[self.workflow.pk]),
            event_key="workflow:open-test",
        )
        self.client.force_login(self.requester)
        response = self.client.post(reverse("enterprise_ops:notification_read", args=[item.pk]))
        self.assertRedirects(response, self.workflow.get_absolute_url(), fetch_redirect_response=False)
        item.refresh_from_db()
        self.assertTrue(item.is_read)
        self.assertTrue(Notification.objects.filter(pk=item.pk).exists())

    def test_reports_and_audit_are_management_only(self):
        self.assertFalse(has_feature_permission(self.requester, "reports", "view"))
        self.assertFalse(has_feature_permission(self.requester, "audit", "view"))
        self.assertTrue(has_feature_permission(self.manager, "reports", "view"))
