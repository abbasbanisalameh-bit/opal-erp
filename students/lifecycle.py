"""Public entry points for the OPAL student lifecycle experience.

Keep views and other apps coupled to this module rather than to the internal
Student 360 context builder. The implementation remains delegated to the
existing builder to preserve current behaviour.
"""

from .student360 import build_student_360_context


def build_student_profile_context(student):
    """Return the canonical context used by student profile and print views."""
    return build_student_360_context(student)
