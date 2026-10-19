from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def seed_roles(sender, **kwargs):
    if sender.name == "roles":
        from django.db import connection
        from .models import Role, Permission
        from .constants import SYSTEM_PERMISSIONS

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

        # 1. Seed Permissions
        created_permissions = []
        for perm_data in SYSTEM_PERMISSIONS:
            permission, _ = Permission.objects.update_or_create(
                codename=perm_data["codename"],
                defaults={
                    "name": perm_data["name"],
                    "module": perm_data["module"],
                    "description": perm_data["description"],
                },
            )
            created_permissions.append(permission)

        # 2. Seed System Roles
        roles = [
            {
                "slug": "owner",
                "name": "Owner",
                "description": "Instance owner and primary administrator",
            },
            {
                "slug": "staff",
                "name": "Staff",
                "description": "Non-teaching administrative staff",
            },
            {
                "slug": "instructor",
                "name": "Instructor",
                "description": "Teaching faculty and instructors",
            },
            {"slug": "student", "name": "Student", "description": "Enrolled students"},
            {
                "slug": "parent",
                "name": "Parent",
                "description": "Parents/guardians of enrolled students",
            },
        ]

        perm_by_codename = {p.codename: p for p in created_permissions}

        for role_data in roles:
            role, created = Role.objects.update_or_create(
                slug=role_data["slug"],
                defaults={
                    "name": role_data["name"],
                    "description": role_data["description"],
                    "is_system_role": True,
                },
            )

            # 3. Assign Permissions
            if role.slug == "owner":
                role.permissions.set(created_permissions)
            elif role.slug == "staff":
                staff_codenames = [
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
                ]
                staff_perms = [perm_by_codename[c] for c in staff_codenames if c in perm_by_codename]
                role.permissions.add(*staff_perms)
            elif role.slug == "instructor":
                inst_codenames = [
                    "view_calendar_events",
                    "view_admissions",
                    "review_admission_applications",
                    "view_own_leaves",
                    "apply_staff_leave",
                    "cancel_own_leave",
                ]
                inst_perms = [perm_by_codename[c] for c in inst_codenames if c in perm_by_codename]
                role.permissions.add(*inst_perms)
            elif role.slug == "student":
                student_codenames = ["view_own_fees", "pay_own_fees", "view_calendar_events"]
                student_perms = [perm_by_codename[c] for c in student_codenames if c in perm_by_codename]
                role.permissions.add(*student_perms)
            elif role.slug == "parent":
                parent_codenames = [
                    "view_own_children",
                    "view_child_attendance",
                    "view_child_timetable",
                    "view_child_results",
                    "view_child_fees",
                    "pay_child_fees",
                    "view_calendar_events",
                ]
                parent_perms = [perm_by_codename[c] for c in parent_codenames if c in perm_by_codename]
                role.permissions.add(*parent_perms)
