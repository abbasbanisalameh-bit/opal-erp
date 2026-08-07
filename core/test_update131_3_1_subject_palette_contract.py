from django.test import SimpleTestCase

from academics.subject_identity import (
    SUBJECT_PALETTE, colour_distance, default_subject_colour, normalize_subject_key,
)


CAPACITY_SUBJECTS = (
    "اللغة العربية", "الرياضيات", "التربية الرياضية", "اللغة الإنجليزية",
    "التربية المهنية", "التربية الإسلامية", "الحاسوب", "التربية الفنية",
    "الثقافة المالية", "العلوم", "الاجتماعيات", "التاريخ", "الجغرافيا",
    "التربية الوطنية", "الفيزياء", "الكيمياء", "الأحياء", "علوم الأرض",
)


class Update13131SubjectPaletteContractTests(SimpleTestCase):
    def test_palette_has_headroom_and_preserves_collision_distance(self):
        self.assertGreaterEqual(len(SUBJECT_PALETTE), 30)
        minimum = min(
            colour_distance(first, second)
            for index, first in enumerate(SUBJECT_PALETTE)
            for second in SUBJECT_PALETTE[index + 1:]
        )
        self.assertGreaterEqual(minimum, 45)

    def test_capacity_subjects_allocate_without_exhaustion(self):
        used = []
        for name in CAPACITY_SUBJECTS:
            used.append(default_subject_colour(normalize_subject_key(name), used))
        self.assertEqual(len(used), 18)
        self.assertEqual(len(set(used)), 18)
        minimum = min(
            colour_distance(first, second)
            for index, first in enumerate(used)
            for second in used[index + 1:]
        )
        self.assertGreaterEqual(minimum, 45)
