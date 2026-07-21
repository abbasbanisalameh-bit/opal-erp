"""Public entry points for the OPAL admission workflow.

Views and external callers should import admission orchestration from this module.
The implementation remains in ``admissions.services`` for backward compatibility.
"""

from .services import create_student_registration

__all__ = ["create_student_registration"]
