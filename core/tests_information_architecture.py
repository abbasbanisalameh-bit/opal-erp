from django.test import SimpleTestCase

from core.information_architecture import (
    COMPATIBILITY_ROUTE_GATEWAYS,
    GATEWAYS,
    audit_gateway_definitions,
    gateway_by_key,
    gateway_for_route,
)


class InformationArchitectureContractTests(SimpleTestCase):
    def test_gateway_definitions_are_unique_and_resolvable(self):
        self.assertEqual(audit_gateway_definitions(), [])

    def test_each_key_is_unique(self):
        keys = [item.key for item in GATEWAYS]
        self.assertEqual(len(keys), len(set(keys)))

    def test_compatibility_routes_point_to_existing_gateways(self):
        for route, key in COMPATIBILITY_ROUTE_GATEWAYS.items():
            with self.subTest(route=route):
                self.assertIsNotNone(gateway_by_key(key))
                self.assertEqual(gateway_for_route(route).key, key)

    def test_parent_finance_is_one_combined_gateway(self):
        gateway = gateway_by_key("parent.finance")
        self.assertEqual(gateway.route, "parent_portal:fees")
        self.assertIn("الإيصالات", gateway.label)

    def test_teacher_exams_and_marks_share_one_gateway(self):
        gateway = gateway_by_key("teacher.exams")
        self.assertEqual(gateway.route, "teachers:portal_workspace")
        self.assertEqual(gateway.query, "mode=marks")
