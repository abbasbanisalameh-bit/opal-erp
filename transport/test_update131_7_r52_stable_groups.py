from django.test import SimpleTestCase


class R52StableTransportGroupsContractTests(SimpleTestCase):
    def test_group_workspace_has_establishment_and_manual_workflow(self):
        text = open("transport/templates/transport/groups/list.html", encoding="utf-8").read()
        self.assertIn("تأسيس مجموعات المواصلات", text)
        self.assertIn("حفظ واعتماد المجموعة", text)
        self.assertIn("حفظ التعديل اليدوي", text)

    def test_daily_manual_prepare_action_is_removed(self):
        text = open("transport/templates/transport/trips/list.html", encoding="utf-8").read()
        self.assertNotIn("تجهيز جولات اليوم", text)
        urls = open("transport/urls.py", encoding="utf-8").read()
        self.assertIn('name="prepare-today"', urls)

    def test_stable_group_contract_exists(self):
        models = open("transport/models.py", encoding="utf-8").read()
        services = open("transport/services.py", encoding="utf-8").read()
        self.assertIn("class TransportGroupMember", models)
        self.assertIn("def establish_stable_groups", services)
        self.assertIn("def synchronize_transport_operations", services)
        self.assertIn("planning_group", models)
