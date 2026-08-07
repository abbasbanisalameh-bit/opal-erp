from __future__ import annotations

import json
from collections.abc import Callable


def assert_forward_compatible_release_identity(
    test_case,
    source: Callable[[str], str],
    *,
    min_revision: int,
) -> None:
    """Validate the installed 131.7 release without pinning a historical revision.

    Historical feature contracts remain executable after later revisions.  The
    current release identity is authoritative in OPAL_RELEASE_NAME.txt and the
    manifest, while each historical contract only enforces its minimum package
    revision.
    """

    version = source("OPAL_VERSION.txt").strip()
    release_name = source("OPAL_RELEASE_NAME.txt").strip()
    manifest = json.loads(source("OPAL_UPDATE_MANIFEST.json"))

    test_case.assertEqual(version, "131.7")
    test_case.assertRegex(release_name, r"OPAL Update 131\.7 R\d+ - .+")
    test_case.assertEqual(manifest["version"], version)
    test_case.assertEqual(manifest["version_name"], release_name)
    test_case.assertGreaterEqual(manifest["package_revision"], min_revision)
    test_case.assertTrue(manifest["code_only"])
