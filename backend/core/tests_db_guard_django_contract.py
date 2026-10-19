"""Contract test: the installed Django exposes the test-environment marker that config.db_guard relies on.

Runs the REAL ``django.test.utils`` functions in a separate subprocess with its own minimal
``settings.configure(...)``. It never imports the EduSekai settings, never reads .env, does not
execute ``config/__init__.py`` (and so no Celery import), opens no database connection and does
not run Django's test runner or any management command. Run from the backend folder:

    python -B -m unittest -v core.tests_db_guard_django_contract

What it proves: the marker lifecycle of the installed Django (inactive, active after
setup_test_environment(), inactive after teardown_test_environment(), a second setup call is
refused) as seen by the adapter's real ``_test_environment_active()`` and
``_derived_test_database_allowed()``. What it does not prove: the order in which Django's runner
calls these functions, the database-name switch, parallel-worker names, or the value of the
setting under ``manage.py test`` (those need the runner and a database).
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

SCRIPT = r'''
import json, os, sys, types
from pathlib import Path

backend = Path(sys.argv[1])
expected_version = sys.argv[2]

# Stand-in "config" package: gives db_guard its `from config import db_identity` WITHOUT running
# config/__init__.py (which imports Celery) and without importing config.settings.
config_package = types.ModuleType("config")
config_package.__path__ = [str(backend / "config")]
sys.modules["config"] = config_package

import django
from django.conf import settings

settings.configure(
    DEBUG=False,
    ALLOWED_HOSTS=[],
    EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
    DATABASES={},
)
django.setup()

from django.core import mail
from django.db import connections
from django.test.utils import _TestState, setup_test_environment, teardown_test_environment

from config import db_guard


class Flagged:
    EDUSEKAI_ALLOW_DERIVED_TEST_DB = True


class NotFlagged:
    pass


def state():
    """(adapter says active, Django marker present, mail.outbox present)"""
    return (db_guard._test_environment_active(), hasattr(_TestState, "saved_data"), hasattr(mail, "outbox"))


def no_connection(where):
    initialised = connections.all(initialized_only=True)
    assert not initialised, f"a database connection was initialised ({where}): {initialised!r}"


# 9. the installed Django is the pinned one
assert django.get_version() == expected_version, (django.get_version(), expected_version)

# 8. the real project settings and Celery were not loaded
assert "DJANGO_SETTINGS_MODULE" not in os.environ
assert settings.SETTINGS_MODULE is None, settings.SETTINGS_MODULE
for name in ("config.settings", "config.celery", "celery"):
    assert name not in sys.modules, f"{name} was imported"
assert sys.modules["config"] is config_package and not hasattr(config_package, "__file__")

# 1 + 2. before setup: marker absent, adapter inactive, exception disabled even with the flag
no_connection("start")
assert state() == (False, False, False), state()
assert db_guard._derived_test_database_allowed(Flagged) is False
assert db_guard._derived_test_database_allowed(NotFlagged) is False

setup_test_environment()
try:
    # 3. after setup: marker present, adapter active
    assert state() == (True, True, True), state()
    marker = _TestState.saved_data
    no_connection("after setup")

    # 4. the exception only for the setting exactly True
    assert db_guard._derived_test_database_allowed(Flagged) is True
    assert db_guard._derived_test_database_allowed(NotFlagged) is False
    for value in (False, None, "True", "true", 1, 2, [True], object()):
        holder = types.SimpleNamespace(EDUSEKAI_ALLOW_DERIVED_TEST_DB=value)
        assert db_guard._derived_test_database_allowed(holder) is False, value

    # 5. a second setup call is refused and leaves the marker untouched
    try:
        setup_test_environment()
    except RuntimeError:
        pass
    else:
        raise AssertionError("a second setup_test_environment() call must fail")
    assert _TestState.saved_data is marker
    assert state() == (True, True, True), state()
    no_connection("after the refused second setup")
finally:
    # always attempt cleanup, even if an assertion above failed
    if hasattr(_TestState, "saved_data"):
        teardown_test_environment()

# 6. after teardown: marker absent, exception disabled again
assert state() == (False, False, False), state()
assert db_guard._derived_test_database_allowed(Flagged) is False
no_connection("after teardown")

print("EVIDENCE " + json.dumps({
    "django_version": django.get_version(),
    "django_file": django.__file__,
    "settings_module": settings.SETTINGS_MODULE,
    "env_settings_module": os.environ.get("DJANGO_SETTINGS_MODULE"),
    "config_package_is_stub": not hasattr(config_package, "__file__"),
    "project_or_celery_modules_loaded": sorted(m for m in sys.modules
                                              if m in ("config.settings", "config.celery", "celery")),
    "initialised_connections": [str(c) for c in connections.all(initialized_only=True)],
}))
print("contract-ok")
'''

ENV_ALLOW = ("SYSTEMROOT", "PATH", "APPDATA", "LOCALAPPDATA", "USERPROFILE", "HOME", "HOMEDRIVE", "HOMEPATH",
             "TEMP", "TMP")


def pinned_django_version():
    text = (BACKEND / "requirements.txt").read_text(encoding="utf-8")
    match = re.search(r"^Django==(\S+)\s*$", text, flags=re.MULTILINE)
    if match is None:
        raise AssertionError("requirements.txt has no 'Django==<version>' line")
    return match.group(1)


class DjangoTestEnvironmentContractTests(unittest.TestCase):
    def test_marker_lifecycle_matches_what_the_adapter_expects(self):
        # No DJANGO_SETTINGS_MODULE, DB_*, PG*, EDUSEKAI_* or other project variables are passed on.
        env = {name: os.environ[name] for name in ENV_ALLOW if name in os.environ}
        with tempfile.TemporaryDirectory() as empty_directory:
            result = subprocess.run(
                [sys.executable, "-E", "-B", "-c", SCRIPT, str(BACKEND), pinned_django_version()],
                cwd=empty_directory, env=env, capture_output=True, text=True, timeout=120,
            )
        self.assertEqual(result.returncode, 0, (result.stdout + result.stderr)[-3000:])
        self.assertIn("contract-ok", result.stdout)
        evidence_lines = [line for line in result.stdout.splitlines() if line.startswith("EVIDENCE ")]
        self.assertEqual(len(evidence_lines), 1)
        evidence = json.loads(evidence_lines[0][len("EVIDENCE "):])
        print("\n  contract evidence:", json.dumps(evidence, sort_keys=True))
        self.assertEqual(evidence["django_version"], pinned_django_version())
        self.assertIsNone(evidence["settings_module"])
        self.assertIsNone(evidence["env_settings_module"])
        self.assertTrue(evidence["config_package_is_stub"])
        self.assertEqual(evidence["project_or_celery_modules_loaded"], [])
        self.assertEqual(evidence["initialised_connections"], [])


if __name__ == "__main__":
    unittest.main()
