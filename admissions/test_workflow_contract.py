from django.test import SimpleTestCase

from . import services, workflow


class AdmissionWorkflowFacadeTests(SimpleTestCase):
    def test_public_workflow_entry_points_to_existing_orchestrator(self):
        self.assertIs(workflow.create_student_registration, services.create_student_registration)

    def test_public_workflow_exports_only_the_registration_entry_point(self):
        self.assertEqual(workflow.__all__, ["create_student_registration"])
