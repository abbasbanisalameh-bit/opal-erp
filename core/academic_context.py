"""One authoritative resolver for OPAL's current academic context."""

from dataclasses import dataclass
from datetime import date

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import AcademicYear, School, Semester


@dataclass(frozen=True)
class AcademicContext:
    year: AcademicYear | None
    semester: Semester | None
    reference_date: date
    semester_changed: bool = False


def resolve_academic_context(*, school: School | None = None, reference_date=None, persist=True):
    """Resolve the year and semester without asking users for known context.

    A semester is active only inside its official boundaries. Mid-year and
    summer holidays intentionally return no semester so daily operations do
    not leak into an adjacent term.
    """
    reference_date = reference_date or timezone.localdate()
    years = AcademicYear.objects.filter(is_closed=False)
    if school is not None:
        years = years.filter(school=school)

    year_candidates = list(
        years.filter(
            Q(is_current=True)
            | Q(start_date__lte=reference_date, end_date__gte=reference_date)
        ).order_by("-start_date")
    )
    current = next((item for item in year_candidates if item.is_current), None)
    dated = next(
        (
            item
            for item in year_candidates
            if item.start_date <= reference_date <= item.end_date
        ),
        None,
    )
    year = dated or current
    if year is None:
        return AcademicContext(None, None, reference_date)

    if persist and dated is not None and (current is None or current.pk != dated.pk):
        with transaction.atomic():
            AcademicYear.objects.select_for_update().filter(school=dated.school, is_current=True).update(is_current=False)
            AcademicYear.objects.filter(pk=dated.pk, is_closed=False).update(is_current=True)
        year.is_current = True

    semester_candidates = list(
        year.semesters.filter(
            Q(is_current=True)
            | Q(
                start_date__lte=reference_date,
                end_date__gte=reference_date,
                is_closed=False,
            )
        ).order_by("start_date", "code")
    )
    semester = next(
        (
            item
            for item in semester_candidates
            if not item.is_closed
            and item.start_date <= reference_date <= item.end_date
        ),
        None,
    )
    # The second semester must never become operational merely because its
    # calendar date arrived. Academic closure of the first semester is the
    # explicit gate that protects the ordered school workflow.
    if semester is not None and semester.code == "second":
        first_semester = year.semesters.filter(code="first").first()
        if first_semester is None or not first_semester.is_closed:
            semester = None
    changed = False
    current_semester = next(
        (item for item in semester_candidates if item.is_current),
        None,
    )
    current_id = current_semester.pk if current_semester else None
    wanted_id = semester.pk if semester else None
    if persist and current_id != wanted_id:
        with transaction.atomic():
            Semester.objects.select_for_update().filter(academic_year=year).update(is_current=False)
            if wanted_id:
                Semester.objects.filter(pk=wanted_id, is_closed=False).update(is_current=True)
        changed = True
        if semester:
            semester.is_current = True
    return AcademicContext(year, semester, reference_date, changed)


def current_academic_year(*, school=None, reference_date=None):
    return resolve_academic_context(school=school, reference_date=reference_date).year


def current_semester(*, school=None, reference_date=None):
    return resolve_academic_context(school=school, reference_date=reference_date).semester
