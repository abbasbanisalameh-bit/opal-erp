import inspect

from django.test import SimpleTestCase

from students.student360 import (
    _build_student_supporting_profile,
    build_student_360_context,
)


class Student360SupportingProfileContractTests(SimpleTestCase):
    def test_supporting_profile_owns_remaining_operational_sections(self):
        source = inspect.getsource(_build_student_supporting_profile)
        for token in (
            'StudentInvoice.objects.filter',
            'StudentPayment.objects.filter',
            'FeePaymentAllocation.objects.filter',
            'TimetableEntry.objects.filter',
            'data_completeness',
            '_build_student_timeline',
        ):
            self.assertIn(token, source)

    def test_main_builder_uses_supporting_profile_once(self):
        source = inspect.getsource(build_student_360_context)
        self.assertEqual(source.count('_build_student_supporting_profile('), 1)
        for key in (
            'invoices', 'payments', 'allocations', 'timetable',
            'data_completeness', 'activity_timeline',
        ):
            self.assertIn(f'supporting_profile["{key}"]', source)
