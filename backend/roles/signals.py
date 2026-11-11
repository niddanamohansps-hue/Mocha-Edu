from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models.signals import post_migrate
from django.dispatch import receiver

# System roles and the permissions each one receives ONCE, when the role row is first created.
# Later migrations never re-apply these: an owner may legitimately remove a permission, rename a
# role or empty it completely, and none of that may be undone by the next `migrate_schemas`.
# The owner role is created with every registered permission (and bypasses permission checks in
# any case); existing tenants are never backfilled with newly introduced permissions.
SYSTEM_ROLES = [
    {
        "slug": "owner",
        "name": "Owner",
        "description": "Instance owner and primary administrator",
        "default_permissions": None,  # None = every registered permission
    },
    {
        "slug": "staff",
        "name": "Staff",
        "description": "Non-teaching administrative staff",
        "default_permissions": [
            "view_calendar_events",
            "manage_calendar_events",
            "view_admissions",
            "manage_admission_enquiries",
            "manage_admission_applications",
            "review_admission_documents",
            "review_admission_applications",
            "make_admission_decisions",
            "enroll_admitted_students",
            "view_own_leaves",
            "apply_staff_leave",
            "cancel_own_leave",
            "view_all_leaves",
            "manage_staff_leaves",
            "manage_leave_types",
            "view_ptm",
            "manage_ptm",
            "record_ptm_feedback",
            "record_interview_feedback",
            "report_exam_malpractice",
        ],
    },
    {
        "slug": "instructor",
        "name": "Instructor",
        "description": "Teaching faculty and instructors",
        "default_permissions": [
            "view_calendar_events",
            "view_admissions",
            "review_admission_applications",
            "view_own_leaves",
            "apply_staff_leave",
            "cancel_own_leave",
            "view_homework",
            "manage_homework",
            "view_ptm",
            "record_ptm_feedback",
            "record_interview_feedback",
            "report_exam_malpractice",
            "view_health_records",
        ],
    },
    {
        "slug": "student",
        "name": "Student",
        "description": "Enrolled students",
        "default_permissions": ["view_own_fees", "pay_own_fees", "view_calendar_events", "view_own_homework"],
    },
    {
        "slug": "parent",
        "name": "Parent",
        "description": "Parents/guardians of enrolled students",
        # Results, fee data and payment initiation (view_child_results, view_child_fees,
        # pay_child_fees) are deliberately NOT default: a school opts in through the Roles UI.
        "default_permissions": [
            "view_own_children",
            "view_child_attendance",
            "view_child_timetable",
            "view_calendar_events",
            "view_child_homework",
            "view_child_ptm",
        ],
    },
]


def seed_default_roles():
    """Register permissions and create any missing system role for the CURRENT tenant schema.

    - Permissions are registered/refreshed (labels only); this never touches role grants.
    - A role that already exists is left exactly as it is (name, description, permissions).
    - A role that does not exist yet is created together with its default permissions, inside one
      transaction so a role can never exist half-seeded (which would later look "existing").
    Safe to call repeatedly. Returns the slugs of the roles created by this call.
    """
    from .constants import SYSTEM_PERMISSIONS
    from .models import Permission, Role

    created_slugs = []
    with transaction.atomic():
        registered = {}
        for perm_data in SYSTEM_PERMISSIONS:
            permission, _ = Permission.objects.update_or_create(
                codename=perm_data["codename"],
                defaults={
                    "name": perm_data["name"],
                    "module": perm_data["module"],
                    "description": perm_data["description"],
                },
            )
            registered[permission.codename] = permission

        for spec in SYSTEM_ROLES:
            role, created = Role.objects.get_or_create(
                slug=spec["slug"],
                defaults={
                    "name": spec["name"],
                    "description": spec["description"],
                    "is_system_role": True,
                },
            )
            if not created:
                continue

            codenames = spec["default_permissions"]
            if codenames is None:
                role.permissions.set(registered.values())
            else:
                missing = [c for c in codenames if c not in registered]
                if missing:
                    raise ImproperlyConfigured(
                        f"Default permissions for system role '{spec['slug']}' are not registered: "
                        f"{', '.join(missing)}"
                    )
                role.permissions.set([registered[c] for c in codenames])
            created_slugs.append(spec["slug"])

    return created_slugs


@receiver(post_migrate)
def seed_roles(sender, **kwargs):
    if sender.name == "roles":
        from django.db import connection

        # IMPORTANT: Only seed roles in TENANT schemas, not in public schema
        # This prevents errors when roles app is in TENANT_APPS
        if connection.schema_name == "public":
            print(
                "[ROLES] Skipping role seeding in public schema (roles are tenant-specific)"
            )
            return

        print(
            f"[ROLES] Seeding roles and permissions for schema: {connection.schema_name}"
        )
        seed_default_roles()
