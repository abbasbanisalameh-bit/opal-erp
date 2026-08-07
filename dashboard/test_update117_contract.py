from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_TEMPLATE = ROOT / "dashboard" / "templates" / "dashboard" / "home.html"
EXECUTIVE_CSS = ROOT / "static" / "css" / "opal_dashboard_executive.css"
WORKFLOW = ROOT / "dashboard" / "workflow.py"
SIDEBAR_CATALOG = ROOT / "core" / "workflow_catalog.py"
NOTIFICATION_CONTEXT = ROOT / "enterprise_ops" / "context_processors.py"
NOTIFICATION_SERVICES = ROOT / "enterprise_ops" / "services.py"
ENTERPRISE_VIEWS = ROOT / "enterprise_ops" / "views.py"


class Update117CommunicationMergeContractTests(SimpleTestCase):
    def test_three_interactive_cards_precede_daily_attendance_cards(self):
        source = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
        action_position = source.index('class="opal-dashboard-action-grid opal-actions-fixed-row"')
        daily_position = source.index('aria-label="غياب الطلبة والمعلمين اليوم"')
        self.assertLess(action_position, daily_position)
        self.assertIn("enterprise_ops:feedback_list", source[action_position:daily_position])
        self.assertIn("enterprise_ops:broadcast_list", source[action_position:daily_position])
        self.assertIn("announcements:list", source[action_position:daily_position])
        self.assertIn("opal-action-badge", source[action_position:daily_position])

    def test_requested_analytics_use_the_fixed_dashboard_contract(self):
        source = DASHBOARD_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('id="teacherEvaluationChart"', source)
        self.assertIn('id="ratingDistributionChart"', source)
        self.assertNotIn('id="opal-teacher-rating-details"', source)
        self.assertNotIn('teacherEvaluationDetails.addEventListener("toggle"', source)

    def test_dashboard_uses_lightweight_counts_only(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('feedback_status = _feedback_scope(school).aggregate(', source)
        self.assertIn('BroadcastMessage.objects.filter(is_active=True).count()', source)
        self.assertIn('Announcement.objects.filter(is_active=True)', source)
        self.assertIn("request._opal_active_announcement", source)
        self.assertNotIn('recent_feedback', source)

    def test_standalone_center_is_removed_from_management_navigation(self):
        source = SIDEBAR_CATALOG.read_text(encoding="utf-8")
        management_sidebar = source[source.index("SIDEBAR_SECTIONS ="):source.index("TEACHER:", source.index("SIDEBAR_SECTIONS ="))]
        self.assertNotIn('("communication-center", "documents")', management_sidebar)
        communication_group = source[source.index('"key": "communication"'):source.index('"key": "documents"')]
        self.assertNotIn('"communication-center"', communication_group)

    def test_new_feedback_is_not_duplicated_in_manager_bell(self):
        services = NOTIFICATION_SERVICES.read_text(encoding="utf-8")
        context = NOTIFICATION_CONTEXT.read_text(encoding="utf-8")
        views = ENTERPRISE_VIEWS.read_text(encoding="utf-8")
        self.assertIn('exclude(event_key__startswith="feedback:")', services)
        self.assertIn("visible_notifications_for_user(request.user)", context)
        self.assertNotIn('event_key=f"feedback:{item.pk}:manager:', views)

    def test_action_cards_have_responsive_opal_styling(self):
        source = EXECUTIVE_CSS.read_text(encoding="utf-8")
        self.assertIn("OPAL Update 117 — merged communication actions", source)
        self.assertIn("grid-template-columns:repeat(3,minmax(0,1fr))", source)
        self.assertIn(".opal-dashboard-action-card .opal-action-badge", source)
        self.assertIn("@media(max-width:900px)", source)
