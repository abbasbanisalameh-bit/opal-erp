from django.test import SimpleTestCase

from academics import workflow


class AcademicWorkflowContractTests(SimpleTestCase):
    def test_workflow_exposes_complete_read_entry_points(self):
        expected = {
            "academic_school",
            "academic_structure_url",
            "build_academic_year_list_context",
            "build_semester_list_context",
            "build_subject_list_context",
            "build_academic_catalogue_snapshot",
            "build_lifecycle_list_context",
        }
        self.assertTrue(expected.issubset(set(dir(workflow))))

    def test_catalogue_snapshot_contract_is_stable(self):
        self.assertEqual(
            set(workflow.build_academic_catalogue_snapshot.__annotations__),
            set(),
        )
