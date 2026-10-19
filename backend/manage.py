#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import importlib
import os
import sys


def _load_target():
    """Configured database and identity settings, for the migration gate.

    Imports the settings module Django will use (DJANGO_SETTINGS_MODULE) as a
    plain module: no django.setup() and no database connection. Only the values
    the gate needs are returned; nothing else from the database entry is read.
    """
    settings_module = importlib.import_module(os.environ["DJANGO_SETTINGS_MODULE"])
    default = settings_module.DATABASES["default"]
    return {
        "NAME": default.get("NAME"),
        "HOST": default.get("HOST"),
        "PORT": default.get("PORT"),
        "EDUSEKAI_ENV": getattr(settings_module, "EDUSEKAI_ENV", ""),
        "EDUSEKAI_EXPECTED_DATABASE": getattr(settings_module, "EDUSEKAI_EXPECTED_DATABASE", ""),
    }


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    # Migration gate (config/migration_gate.py). It inspects only this
    # `python manage.py ...` command line: it does not see call_command(),
    # django-admin, `python -m django`, shell sessions or other scripts.
    from config import migration_gate

    decision = migration_gate.evaluate(sys.argv, _load_target)
    if decision.message:
        sys.stderr.write(decision.message + "\n")
    if not decision.allowed:
        sys.exit(decision.exit_code)
    if decision.notice:
        sys.stderr.write(decision.notice + "\n")
    execute_from_command_line(decision.argv)


if __name__ == '__main__':
    main()
