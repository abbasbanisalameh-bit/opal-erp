"""Stage the annual Subject plan and move every existing reference safely.

The migration deliberately keeps ``curriculum.Curriculum`` and
``TeacherAssignment.weekly_periods`` until all foreign keys have been mapped.
The destructive removals happen in the dependent app migrations only after
this mapping succeeds.
"""

import json
import math
import re
import unicodedata
from collections import defaultdict

import django.db.models.deletion
from django.db import migrations, models


_ARABIC_TRANSLATION = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي", "ة": "ه",
})

_PALETTE = (
    "#2563EB", "#DC2626", "#16A34A", "#9333EA", "#EA580C", "#0891B2",
    "#4F46E5", "#BE123C", "#15803D", "#7E22CE", "#C2410C", "#0E7490",
    "#1D4ED8", "#B91C1C", "#047857", "#6D28D9", "#B45309", "#0369A1",
)


_CANONICAL_ALIASES = {
    "الرياضيات": "رياضيات", "رياضيات": "رياضيات",
    "اللغهالعربيه": "اللغهالعربيه", "لغهعربيه": "اللغهالعربيه", "العربيه": "اللغهالعربيه",
    "اللغهالانجليزيه": "اللغهالانجليزيه", "لغهانجليزيه": "اللغهالانجليزيه",
    "الانجليزيه": "اللغهالانجليزيه", "انجليزي": "اللغهالانجليزيه",
    "العلوم": "علوم", "علوم": "علوم",
    "التربيهالاسلاميه": "التربيهالاسلاميه", "تربيهاسلاميه": "التربيهالاسلاميه",
    "الحاسوب": "حاسوب", "حاسوب": "حاسوب", "الكمبيوتر": "حاسوب", "كمبيوتر": "حاسوب",
}


def _key(value):
    text = re.sub(r"\s+", " ", str(value or "").strip()).translate(_ARABIC_TRANSLATION)
    text = "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )
    text = text.replace("ـ", "").lower()
    raw = re.sub(r"[^0-9a-z\u0621-\u064a]+", "", text)
    return _CANONICAL_ALIASES.get(raw, raw)


_SEMANTIC = {
    _key("الرياضيات"): "#2563EB",
    _key("اللغة العربية"): "#DC2626",
    _key("العربية"): "#DC2626",
    _key("العلوم"): "#16A34A",
    _key("اللغة الإنجليزية"): "#9333EA",
    _key("الإنجليزية"): "#9333EA",
    _key("التربية الإسلامية"): "#EA580C",
    _key("الحاسوب"): "#0891B2",
}


def _rgb(colour):
    return tuple(int(colour[index:index + 2], 16) for index in (1, 3, 5))


def _distance(first, second):
    return math.sqrt(sum((left - right) ** 2 for left, right in zip(_rgb(first), _rgb(second))))


def _available(colour, used, minimum=45):
    return all(_distance(colour, item) >= minimum for item in used)


def _stable_colour(key, assigned):
    used = tuple(assigned.values())
    semantic = _SEMANTIC.get(key)
    if semantic:
        if not _available(semantic, used):
            raise RuntimeError(f"Semantic subject colour collision for canonical identity {key}.")
        return semantic
    seed = sum((index + 1) * ord(char) for index, char in enumerate(key))
    ordered = _PALETTE[seed % len(_PALETTE):] + _PALETTE[:seed % len(_PALETTE)]
    colour = next((item for item in ordered if _available(item, used)), None)
    if colour is None:
        raise RuntimeError(
            "The subject colour palette has no visually distinct colour left; "
            "extend the palette before completing the migration."
        )
    return colour


def _model_or_none(apps, app_label, model_name):
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def _normalise_snapshot_payload(payload, *, year_id, mapping, plans, Subject):
    if not isinstance(payload, dict):
        return payload

    old_subject_rows = payload.get("subjects") or []
    curriculum_rows = payload.get("curricula") or []
    curriculum_by_old_subject = {
        row.get("subject_id"): row
        for row in curriculum_rows
        if isinstance(row, dict) and row.get("subject_id")
    }
    new_subjects = []
    seen = set()

    for row in old_subject_rows:
        if not isinstance(row, dict):
            continue
        old_id = row.get("id") or row.get("subject_id")
        new_id = mapping.get((old_id, year_id))
        if not new_id or new_id in seen:
            continue
        seen.add(new_id)
        annual = Subject.objects.filter(pk=new_id).first()
        if annual is None:
            continue
        plan = plans[(old_id, year_id)]
        merged = dict(row)
        merged.update({
            "id": new_id,
            "academic_year_id": year_id,
            "grade_id": annual.grade_id,
            "name": annual.name,
            "code": annual.code,
            "weekly_periods": plan[0],
            "is_required": plan[1],
            "canonical_key": annual.canonical_key,
            "color": annual.color,
            "is_active": annual.is_active,
        })
        legacy_plan = curriculum_by_old_subject.get(old_id)
        if legacy_plan:
            merged["weekly_periods"] = legacy_plan.get("weekly_periods", merged["weekly_periods"])
            merged["is_required"] = legacy_plan.get("is_required", merged["is_required"])
            merged["is_active"] = legacy_plan.get("is_active", merged["is_active"])
        new_subjects.append(merged)

    # Older snapshots may contain a plan row without a parallel subjects row.
    for old_id, legacy_plan in curriculum_by_old_subject.items():
        new_id = mapping.get((old_id, year_id))
        if not new_id or new_id in seen:
            continue
        annual = Subject.objects.filter(pk=new_id).first()
        if annual is None:
            continue
        seen.add(new_id)
        plan = plans[(old_id, year_id)]
        new_subjects.append({
            "id": new_id,
            "academic_year_id": year_id,
            "grade_id": annual.grade_id,
            "name": annual.name,
            "code": annual.code,
            "weekly_periods": legacy_plan.get("weekly_periods", plan[0]),
            "is_required": legacy_plan.get("is_required", plan[1]),
            "canonical_key": annual.canonical_key,
            "color": annual.color,
            "is_active": legacy_plan.get("is_active", annual.is_active),
        })

    for collection_name in ("assignments", "timetable"):
        rows = payload.get(collection_name) or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            old_id = row.get("subject_id")
            new_id = mapping.get((old_id, year_id))
            if new_id:
                row["subject_id"] = new_id

    payload["schema"] = 2
    payload["subjects"] = new_subjects
    payload.pop("curricula", None)
    return payload


def migrate_subject_plan(apps, schema_editor):
    Subject = apps.get_model("academics", "Subject")
    Grade = apps.get_model("academics", "Grade")
    AcademicYear = apps.get_model("core", "AcademicYear")
    Curriculum = apps.get_model("curriculum", "Curriculum")
    TeacherAssignment = apps.get_model("teachers", "TeacherAssignment")
    TimetableEntry = apps.get_model("timetable", "TimetableEntry")
    Exam = apps.get_model("exams", "Exam")
    SemesterSubjectResult = apps.get_model("exams", "SemesterSubjectResult")
    AnnualSubjectResult = apps.get_model("exams", "AnnualSubjectResult")
    Snapshot = _model_or_none(apps, "core", "SemesterStructureSnapshot")

    original_subjects = list(Subject.objects.all().order_by("pk"))
    original_ids = {item.pk for item in original_subjects}
    pair_sources = defaultdict(set)
    curriculum_by_pair = defaultdict(list)
    assignment_periods = defaultdict(set)

    for item in Curriculum.objects.all().order_by("pk"):
        if item.subject_id not in original_ids:
            raise RuntimeError(f"Curriculum {item.pk} references a missing Subject {item.subject_id}.")
        subject = next(row for row in original_subjects if row.pk == item.subject_id)
        if item.grade_id != subject.grade_id:
            raise RuntimeError(
                f"Curriculum {item.pk} grade {item.grade_id} does not match Subject {subject.pk} grade {subject.grade_id}."
            )
        pair = (item.subject_id, item.academic_year_id)
        pair_sources[pair].add("curriculum")
        curriculum_by_pair[pair].append(item)

    owner_specs = [
        (TeacherAssignment, "teacher assignment", "academic_year_id", "section"),
        (TimetableEntry, "timetable entry", "academic_year_id", "section"),
        (Exam, "exam", "academic_year_id", "grade"),
        (SemesterSubjectResult, "semester result", "semester__academic_year_id", None),
        (AnnualSubjectResult, "annual result", "academic_year_id", None),
    ]

    for Model, label, year_path, grade_source in owner_specs:
        select_related = ["subject"]
        if grade_source == "section":
            select_related.append("section")
        elif grade_source == "grade":
            select_related.append("grade")
        if year_path.startswith("semester__"):
            select_related.append("semester")
        for item in Model.objects.select_related(*select_related).all().order_by("pk"):
            old_id = item.subject_id
            if old_id not in original_ids:
                raise RuntimeError(f"{label} {item.pk} references a missing Subject {old_id}.")
            year_id = item.semester.academic_year_id if year_path.startswith("semester__") else item.academic_year_id
            subject = item.subject
            if grade_source == "section" and item.section.grade_id != subject.grade_id:
                raise RuntimeError(
                    f"{label} {item.pk} grade {item.section.grade_id} does not match Subject {old_id} grade {subject.grade_id}."
                )
            if grade_source == "grade" and item.grade_id != subject.grade_id:
                raise RuntimeError(
                    f"{label} {item.pk} grade {item.grade_id} does not match Subject {old_id} grade {subject.grade_id}."
                )
            pair_sources[(old_id, year_id)].add(label)
            if Model is TeacherAssignment:
                assignment_periods[(old_id, year_id)].add(item.weekly_periods)

    plans = {}
    for pair in sorted(pair_sources):
        rows = curriculum_by_pair.get(pair, [])
        curriculum_values = {
            (item.weekly_periods, item.is_required, item.is_active)
            for item in rows
        }
        if len(curriculum_values) > 1:
            raise RuntimeError(f"Conflicting Curriculum values for Subject/year pair {pair}: {sorted(curriculum_values)}")
        assignment_values = {value for value in assignment_periods.get(pair, set()) if value is not None}
        if len(assignment_values) > 1:
            raise RuntimeError(f"Conflicting TeacherAssignment.weekly_periods for Subject/year pair {pair}: {sorted(assignment_values)}")
        if curriculum_values:
            weekly, required, active = next(iter(curriculum_values))
            if assignment_values and next(iter(assignment_values)) != weekly:
                raise RuntimeError(
                    f"Curriculum and TeacherAssignment periods disagree for Subject/year pair {pair}: "
                    f"{weekly} versus {next(iter(assignment_values))}."
                )
        elif assignment_values:
            weekly = next(iter(assignment_values))
            required = True
            active = True
        else:
            raise RuntimeError(
                f"No annual plan or unambiguous assignment periods exist for used Subject/year pair {pair}."
            )
        if not 1 <= int(weekly) <= 20:
            raise RuntimeError(f"Invalid weekly period count {weekly} for Subject/year pair {pair}.")
        plans[pair] = (int(weekly), bool(required), bool(active))

    grades = {item.pk: item for item in Grade.objects.all()}
    years_by_school = defaultdict(list)
    for year in AcademicYear.objects.all().order_by("-is_current", "-start_date", "-pk"):
        years_by_school[year.school_id].append(year)

    # Preserve unused catalogue items by assigning them only when an unambiguous
    # current/latest year exists for their school. No used record is guessed.
    for subject in original_subjects:
        if any(old_id == subject.pk for old_id, _year_id in pair_sources):
            continue
        grade = grades.get(subject.grade_id)
        candidates = years_by_school.get(getattr(grade, "school_id", None), [])
        if not candidates:
            raise RuntimeError(f"Unused Subject {subject.pk} has no academic year in its school.")
        year = next((row for row in candidates if row.is_current), candidates[0])
        pair = (subject.pk, year.pk)
        pair_sources[pair].add("unused-catalogue")
        plans[pair] = (1, True, bool(subject.is_active))
        print(
            f"OPAL 131 migration note: unused Subject {subject.pk} assigned to academic year {year.pk} with one weekly period."
        )

    colour_by_key = {}
    for subject in original_subjects:
        canonical = _key(subject.name)
        if not canonical:
            raise RuntimeError(f"Subject {subject.pk} has no usable canonical identity.")
        if canonical not in colour_by_key:
            colour_by_key[canonical] = _stable_colour(canonical, colour_by_key)

    mapping = {}
    pairs_by_subject = defaultdict(list)
    for pair in pair_sources:
        pairs_by_subject[pair[0]].append(pair[1])

    year_rows = {item.pk: item for item in AcademicYear.objects.all()}
    for subject in original_subjects:
        year_ids = sorted(
            pairs_by_subject[subject.pk],
            key=lambda pk: (
                not bool(getattr(year_rows.get(pk), "is_current", False)),
                getattr(year_rows.get(pk), "start_date", None),
                pk,
            ),
        )
        canonical = _key(subject.name)
        colour = colour_by_key[canonical]
        for index, year_id in enumerate(year_ids):
            weekly, required, active = plans[(subject.pk, year_id)]
            values = {
                "academic_year_id": year_id,
                "weekly_periods": weekly,
                "is_required": required,
                "canonical_key": canonical,
                "color": colour,
                "is_active": bool(subject.is_active and active),
            }
            if index == 0:
                Subject.objects.filter(pk=subject.pk).update(**values)
                annual_id = subject.pk
            else:
                annual = Subject.objects.create(
                    name=subject.name,
                    code=subject.code,
                    grade_id=subject.grade_id,
                    **values,
                )
                annual_id = annual.pk
            mapping[(subject.pk, year_id)] = annual_id

    def remap(Model, year_getter):
        updates = 0
        for item in Model.objects.all().order_by("pk"):
            old_id = item.subject_id
            year_id = year_getter(item)
            new_id = mapping.get((old_id, year_id))
            if new_id is None:
                raise RuntimeError(
                    f"Missing annual Subject mapping for {Model._meta.label} {item.pk}: subject {old_id}, year {year_id}."
                )
            if new_id != old_id:
                Model.objects.filter(pk=item.pk).update(subject_id=new_id)
                updates += 1
        return updates

    remap(TeacherAssignment, lambda item: item.academic_year_id)
    remap(TimetableEntry, lambda item: item.academic_year_id)
    remap(Exam, lambda item: item.academic_year_id)
    remap(SemesterSubjectResult, lambda item: item.semester.academic_year_id)
    remap(AnnualSubjectResult, lambda item: item.academic_year_id)

    if Snapshot is not None:
        for snapshot in Snapshot.objects.select_related("semester").all().order_by("pk"):
            payload = snapshot.payload
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except (TypeError, ValueError):
                    continue
            payload = _normalise_snapshot_payload(
                payload,
                year_id=snapshot.semester.academic_year_id,
                mapping=mapping,
                plans=plans,
                Subject=Subject,
            )
            Snapshot.objects.filter(pk=snapshot.pk).update(payload=payload)

    # Final data-level safeguards before dependent migrations remove old storage.
    for item in Subject.objects.all():
        if not item.academic_year_id or not item.canonical_key or not item.color or not item.weekly_periods:
            raise RuntimeError(f"Subject {item.pk} was not fully converted to the annual plan contract.")


def reverse_unavailable(apps, schema_editor):
    raise RuntimeError(
        "OPAL annual Subject consolidation is intentionally irreversible after dependent tables are removed. "
        "Restore the pre-update SQLite safety copy instead."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("academics", "0015_lifecycle_section_snapshots"),
        ("core", "0011_bootstrap_update_engine_v3"),
        ("curriculum", "0002_alter_curriculum_academic_year"),
        ("teachers", "0013_teacher_workload_and_free_period_policy"),
        ("timetable", "0007_smart_break_groups_and_generated_slots"),
        ("exams", "0008_exam_marks_due_date"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="subject",
            name="uniq_subject_name_per_grade",
        ),
        migrations.RemoveConstraint(
            model_name="subject",
            name="uniq_subject_code_per_grade",
        ),
        migrations.AddField(
            model_name="subject",
            name="academic_year",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="subjects",
                to="core.academicyear",
            ),
        ),
        migrations.AddField(
            model_name="subject",
            name="weekly_periods",
            field=models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="عدد الحصص أسبوعيًا"),
        ),
        migrations.AddField(
            model_name="subject",
            name="is_required",
            field=models.BooleanField(default=True, verbose_name="مادة إلزامية"),
        ),
        migrations.AddField(
            model_name="subject",
            name="canonical_key",
            field=models.CharField(blank=True, db_index=True, default="", editable=False, max_length=140, verbose_name="هوية المادة الموحدة"),
        ),
        migrations.AddField(
            model_name="subject",
            name="color",
            field=models.CharField(blank=True, default="", max_length=7, verbose_name="لون المادة"),
        ),
        migrations.RunPython(migrate_subject_plan, reverse_unavailable),
    ]
