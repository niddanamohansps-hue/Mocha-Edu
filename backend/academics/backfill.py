"""
Controlled academic-year backfill (Phase 1.2D).

Creates the approved, tenant-local AcademicYear rows and reports the approved
legacy-value mapping. It never changes a legacy academic_year value, never adds
a foreign key, and never creates a row that the decision block excludes.

Decisions are product-owner values, not derived from data. They are validated
before any database access, and the apply step is idempotent.
"""

import datetime
import re
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django_tenants.utils import tenant_context

from core.models import AuditLog

from .models import AcademicYear

NAME_RE = re.compile(r"^(\d{4})-(\d{2})$")

# The 13 legacy academic-year columns, as (table, column).
LEGACY_FIELDS = [
    ("attendance_attendancesession", "academic_year"),
    ("course_content_subjectenrollment", "academic_year"),
    ("examinations_examination", "academic_year"),
    ("examinations_examresult", "academic_year"),
    ("examinations_examschedule", "academic_year"),
    ("examinations_gradeboundary", "academic_year"),
    ("fees_feestructure", "academic_year"),
    ("fees_studentfee", "academic_year"),
    ("students_promotionrecord", "source_academic_year"),
    ("students_promotionrecord", "target_academic_year"),
    ("students_studentlevel", "academic_year"),
    ("timetable_period", "academic_year"),
    ("timetable_timetableentry", "academic_year"),
]

D = datetime.date

# Product-owner decision block (Phase 1.2D). Authoritative; do not reinterpret.
DECISIONS = {
    "sunrisevalley_school": {
        "rows": [
            # name, start, end, is_current
            ("2025-26", D(2025, 4, 1), D(2026, 3, 31), False),
            ("2026-27", D(2026, 4, 1), D(2027, 3, 31), True),
        ],
        "mapping": {"2025-26": "2025-26", "2026-27": "2026-27"},
        # Legacy values that are intentionally NOT mapped (the approved exception).
        "unmapped_exceptions": {"2024-25": "CREATE_SUNRISE_2024_25_ROW = NO; six grade-boundary rows kept untouched"},
        "current": "2026-27",
    },
    "greenvalley_demo": {
        "rows": [
            ("2024-25", D(2024, 4, 1), D(2025, 3, 31), False),
            ("2025-26", D(2025, 4, 1), D(2026, 3, 31), False),
        ],
        "mapping": {"2025": "2024-25", "2026": "2025-26"},
        "unmapped_exceptions": {},
        "current": None,  # GREENVALLEY_CURRENT_YEAR = NONE
    },
}

INCLUDED_TENANTS = ["greenvalley_demo", "sunrisevalley_school"]
EXCLUDED_TENANTS = ["spsghy", "test_chk"]


class BackfillDecisionError(ValueError):
    pass


def validate_decisions(decisions=DECISIONS):
    """Raises BackfillDecisionError on any invalid decision. No database access."""
    for tenant, cfg in decisions.items():
        if tenant in EXCLUDED_TENANTS:
            raise BackfillDecisionError(f"{tenant} is excluded and must not be processed.")
        names = [r[0] for r in cfg["rows"]]
        if len(set(names)) != len(names):
            raise BackfillDecisionError(f"{tenant}: duplicate AcademicYear names in decision block.")
        currents = [r[0] for r in cfg["rows"] if r[3]]
        if len(currents) > 1:
            raise BackfillDecisionError(f"{tenant}: more than one current year in decision block.")
        if cfg["current"] is not None and cfg["current"] not in names:
            raise BackfillDecisionError(f"{tenant}: current year {cfg['current']} is not a row.")
        if cfg["current"] is None and currents:
            raise BackfillDecisionError(f"{tenant}: decision says NONE but a row is marked current.")
        for name, start, end, _ in cfg["rows"]:
            if not NAME_RE.fullmatch(name):
                raise BackfillDecisionError(f"{tenant}: invalid academic year name {name!r}.")
            if int(name[:4]) + 1 != int("20" + name[-2:]) and (int(name[:4]) + 1) % 100 != int(name[-2:]):
                raise BackfillDecisionError(f"{tenant}: {name!r} is not consecutive years.")
            if not start < end:
                raise BackfillDecisionError(f"{tenant}: {name} start {start} must be before end {end}.")
        targets = set(cfg["mapping"].values())
        if not targets <= set(names):
            raise BackfillDecisionError(f"{tenant}: mapping targets {sorted(targets - set(names))} are not rows.")
        if len(set(cfg["mapping"].values())) != len(cfg["mapping"]):
            raise BackfillDecisionError(f"{tenant}: two legacy values map to the same AcademicYear.")


@dataclass
class TenantResult:
    tenant: str
    created: list = field(default_factory=list)
    existing: list = field(default_factory=list)


def _row_matches(existing, name, start, end, current):
    return existing.start_date == start and existing.end_date == end and existing.is_current == current


def apply_tenant(tenant, cfg, dry_run=False, actor_label="system:phase-1.2d-backfill"):
    """
    Creates or confirms the approved rows for one tenant, inside one atomic block.
    Dry-run performs every check and writes nothing. Re-running with the same
    decisions creates nothing new (idempotent). A conflicting existing row raises.
    """
    from organizations.models import Organization

    org = Organization.objects.get(schema_name=tenant)
    result = TenantResult(tenant=tenant)
    plan = []

    with tenant_context(org):
        for name, start, end, is_current in cfg["rows"]:
            existing = AcademicYear.objects.filter(name=name).first()
            if existing is not None:
                if not _row_matches(existing, name, start, end, is_current):
                    raise BackfillDecisionError(
                        f"{tenant}: {name} already exists with different values; refusing to alter it."
                    )
                result.existing.append(name)
                plan.append(("exists", name))
            else:
                plan.append(("create", name))

        if dry_run:
            return result, plan

        with transaction.atomic():
            # Non-current rows first, so the single-current constraint is never
            # transiently violated while the current row is inserted.
            for name, start, end, is_current in sorted(cfg["rows"], key=lambda r: r[3]):
                if AcademicYear.objects.filter(name=name).exists():
                    continue
                year = AcademicYear(name=name, start_date=start, end_date=end, is_current=is_current)
                year.full_clean()
                year.save()
                AuditLog.objects.create(
                    actor_id=None,
                    actor_username=actor_label,
                    action="academic_year_backfill_created",
                    model_name="AcademicYear",
                    object_id=str(year.id),
                    changes={
                        "tenant": tenant,
                        "name": name,
                        "start_date": str(start),
                        "end_date": str(end),
                        "is_current": is_current,
                    },
                )
                result.created.append(name)

    return result, plan


def validate_tenant(tenant, cfg):
    """
    For every legacy value present in the tenant's 13 fields, confirm it resolves
    to exactly one AcademicYear, or is the approved exception. Read-only.
    """
    from organizations.models import Organization

    org = Organization.objects.get(schema_name=tenant)
    problems = {"unmapped": [], "ambiguous": [], "orphan_rows": []}
    with tenant_context(org):
        names = set(AcademicYear.objects.values_list("name", flat=True))
        with connection.cursor() as cur:
            for table, column in LEGACY_FIELDS:
                cur.execute(f'select distinct {column} from "{table}"')
                for (value,) in cur.fetchall():
                    if value in cfg["mapping"]:
                        target = cfg["mapping"][value]
                        if target not in names:
                            problems["unmapped"].append((table, column, value))
                    elif value in names:
                        continue
                    elif value in cfg["unmapped_exceptions"]:
                        continue
                    else:
                        problems["unmapped"].append((table, column, value))
        referenced = set(cfg["mapping"].values()) | set(cfg["mapping"].keys())
        for name in names:
            if name not in set(cfg["mapping"].values()):
                problems["orphan_rows"].append(name)
    return problems
