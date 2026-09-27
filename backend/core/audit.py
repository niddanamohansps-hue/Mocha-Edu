import logging

from .models import AuditLog

logger = logging.getLogger(__name__)


def _get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_action(request, action, model_name, object_id=None, changes=None):
    """
    Best-effort audit log write. Never raises - a logging failure must not
    block the actual business operation (e.g. saving a Role) that triggered it.
    """
    try:
        user = getattr(request, "user", None)
        actor_id = getattr(user, "id", None) if user and user.is_authenticated else None
        actor_username = getattr(user, "username", None) if user and user.is_authenticated else None

        AuditLog.objects.create(
            actor_id=actor_id,
            actor_username=actor_username,
            action=action,
            model_name=model_name,
            object_id=str(object_id) if object_id is not None else None,
            changes=changes,
            ip_address=_get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
        )
    except Exception:
        logger.exception("log_action failed for action=%s model=%s", action, model_name)
