"""Migration-history app for the retired parallel curriculum table.

OPAL Update 131 moved annual plan fields into ``academics.Subject`` and the
``curriculum.Curriculum`` model was deleted by migration 0003.  Keep this app
installed until migration history is squashed; do not add operational models
here.
"""
