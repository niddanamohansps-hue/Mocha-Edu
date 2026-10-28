from django.apps import AppConfig


class RolesConfig(AppConfig):
    name = "roles"

    def ready(self):
        import roles.signals
        import roles.cache  # noqa: F401  (connects the cache-invalidation signals)
