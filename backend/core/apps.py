from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Core Utilities"

    def ready(self):
        # Registers the database-identity system check (warning only; it
        # compares configuration values and never opens a database connection).
        from . import checks  # noqa: F401
