from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.db import connection
from django.apps import apps
from django_tenants.utils import schema_context
import logging

logger = logging.getLogger(__name__)

from .models import User
from organizations.models import Organization


@receiver(pre_delete, sender=User)
def cleanup_user_tenant_data(sender, instance, **kwargs):
    """
    Ensures that when a global User is removed, their secondary data is
    wiped across all tenant schemas to prevent orphaned entries.
    """
    user_id = instance.id
    db = instance._state.db or "default"

    # 1. Fetch all tenants requiring cleanup
    try:
        tenants = list(Organization.objects.using(db).exclude(schema_name="public"))
    except Exception as e:
        logger.error(f"Failed to fetch tenants for user cleanup: {str(e)}")
        return

    # 2. Iterate through each tenant and perform the purge
    for tenant in tenants:
        with schema_context(tenant.schema_name):
            try:
                ProfileModel = apps.get_model("profiles", "Profile")
                # Using .all() to force a clean queryset on the current schema context
                ProfileModel.objects.using(db).filter(user_id=user_id).delete()
            except Exception as e:
                logger.warning(
                    f"Could not purge data for user {user_id} in schema {tenant.schema_name}: {str(e)}"
                )
                continue

            try:
                # UserRole.user is now on_delete=DO_NOTHING / db_constraint=False
                # (the cross-schema FK to accounts.User was removed - see
                # roles/models.py and roles/migrations/0002_alter_userrole_user.py)
                # specifically because Postgres cannot enforce a real FK across
                # tenant schemas. That means neither the database nor Django's
                # ORM will auto-remove UserRole rows for a deleted user anymore -
                # this explicit per-tenant purge is now the ONLY cleanup path,
                # mirroring the Profile purge immediately above.
                UserRoleModel = apps.get_model("roles", "UserRole")
                UserRoleModel.objects.using(db).filter(user_id=user_id).delete()
            except Exception as e:
                logger.warning(
                    f"Could not purge UserRole rows for user {user_id} in schema {tenant.schema_name}: {str(e)}"
                )
                continue
