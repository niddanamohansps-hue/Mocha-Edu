"""
EduSekai Staff Leave Management Business Services (Phase 5)

Transactional services for leave calculations, atomic balance reservation,
attendance synchronization, timetable substitution discovery, and audit logging.
"""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
import logging
import os

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.audit import log_action
from notifications.services import notify, queue_email
from profiles.models import Profile

from .models import (
    Instructor,
    LeaveApplication,
    LeaveApproval,
    LeaveType,
    StaffLeaveBalance,
    StaffMember,
)

logger = logging.getLogger(__name__)

ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".docx"}
MAX_DOCUMENT_SIZE = 5 * 1024 * 1024  # 5 MB


def get_staff_member_for_user(user):
    """
    Resolves the authenticated TenantUser to their active StaffMember profile.
    Searches StaffMember directly via profile__user_id to handle existing or signal-created profiles safely.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return None
    return (
        StaffMember.objects.filter(profile__user_id=user.id, is_active=True)
        .select_related("profile")
        .first()
    )


def calculate_working_days(start_date: date, end_date: date, is_half_day: bool = False) -> Decimal:
    """
    Computes the net working days for a leave request:
    - Enforces start_date <= end_date.
    - Excludes the school's weekly off days (Sunday unless the school chose others in its attendance settings).
    - Excludes published school holidays from academics.CalendarEvent.
    - If is_half_day is True, start_date must equal end_date and returns 0.5 if not a holiday.
    - Fails if the range contains 0 working days.
    """
    if start_date > end_date:
        raise ValidationError({"end_date": "End date cannot precede start date."})

    from academics.models import CalendarEvent
    from attendance.models import AttendanceSettings

    weekly_off = AttendanceSettings.weekly_off()

    # Query published school holidays overlapping the requested window
    holiday_events = CalendarEvent.objects.filter(
        is_holiday=True,
        status="PUBLISHED",
        start_date__lte=end_date,
        end_date__gte=start_date,
    )
    holiday_dates = set()
    for ev in holiday_events:
        cur = max(start_date, ev.start_date)
        last = min(end_date, ev.end_date)
        delta = (last - cur).days
        for i in range(delta + 1):
            holiday_dates.add(cur + timedelta(days=i))

    if is_half_day:
        if start_date != end_date:
            raise ValidationError({"end_date": "Half-day leave must start and end on the same date."})
        if start_date.weekday() in weekly_off:
            raise ValidationError({"start_date": "Cannot take leave on a weekly off day of the school."})
        if start_date in holiday_dates:
            raise ValidationError({"start_date": "Cannot take leave on a published school holiday."})
        return Decimal("0.5")

    current = start_date
    working_days = Decimal("0.0")
    while current <= end_date:
        if current.weekday() not in weekly_off and current not in holiday_dates:
            working_days += Decimal("1.0")
        current += timedelta(days=1)

    if working_days <= Decimal("0.0"):
        raise ValidationError(
            {"start_date": "The requested period contains no school working days (all dates are holidays or weekly offs)."}
        )

    return working_days


def validate_leave_document(file_obj):
    """
    Enforces file size, extension, and optional antivirus scanning.
    """
    if not file_obj:
        return
    if file_obj.size > MAX_DOCUMENT_SIZE:
        raise ValidationError(
            f"Document exceeds 5MB size limit ({file_obj.size / (1024 * 1024):.1f}MB)."
        )
    ext = os.path.splitext(file_obj.name)[1].lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_DOCUMENT_EXTENSIONS))}."
        )

    # Magic byte signature check
    try:
        header = file_obj.read(16)
        file_obj.seek(0)
    except Exception:
        header = b""

    if ext == ".pdf" and not header.startswith(b"%PDF"):
        raise ValidationError("File signature does not match a valid PDF document.")
    elif ext in [".jpg", ".jpeg"] and not header.startswith(b"\xff\xd8\xff"):
        raise ValidationError("File signature does not match a valid JPEG image.")
    elif ext == ".png" and not header.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValidationError("File signature does not match a valid PNG image.")
    elif ext == ".docx" and not header.startswith(b"PK\x03\x04"):
        raise ValidationError("File signature does not match a valid DOCX document.")

    # Antivirus stream inspection if enabled
    if getattr(settings, "CLAMAV_ENABLED", False):
        try:
            from students.antivirus import scan_file_for_malware
            is_clean, scan_status, scan_details = scan_file_for_malware(file_obj, filename=file_obj.name)
            if not is_clean:
                raise ValidationError(f"File upload quarantined by antivirus scanner ({scan_status}): {scan_details}")
        except ValidationError:
            raise
        except Exception as err:
            logger.error("Antivirus scan failed during leave document validation: %s", err)
            if getattr(settings, "CLAMAV_FAIL_CLOSED", True):
                raise ValidationError("Antivirus scanning service is currently unavailable. Upload blocked (fail-closed).")


def get_current_academic_year():
    """
    Resolves the active AcademicYear model and string name.
    """
    from academics.models import AcademicYear
    current = AcademicYear.objects.filter(is_current=True).first()
    if current:
        return current, current.name
    # Fallback to most recent academic year
    recent = AcademicYear.objects.order_by("-start_date").first()
    if recent:
        return recent, recent.name
    # Fallback string
    now = timezone.now()
    year_str = f"{now.year}-{str(now.year + 1)[2:]}"
    return None, year_str


def get_or_create_staff_balances(staff: StaffMember, academic_year: str, academic_year_ref=None):
    """
    Ensures a StaffLeaveBalance record exists for each active LeaveType.
    """
    active_types = LeaveType.objects.filter(is_active=True)
    balances = []
    for lt in active_types:
        bal, _ = StaffLeaveBalance.objects.get_or_create(
            staff=staff,
            leave_type=lt,
            academic_year=academic_year,
            defaults={
                "academic_year_ref": academic_year_ref,
                "allocated_days": lt.annual_allocation_days,
                "used_days": Decimal("0.0"),
                "pending_days": Decimal("0.0"),
            },
        )
        balances.append(bal)
    return balances


def submit_leave_application(
    *,
    staff: StaffMember,
    leave_type: LeaveType,
    start_date: date,
    end_date: date,
    reason: str,
    is_half_day: bool = False,
    half_day_session: str = "",
    document=None,
    academic_year: str = None,
    academic_year_ref=None,
    request=None,
) -> LeaveApplication:
    """
    Submits a leave application atomically:
    1. Validates working days and document requirements.
    2. Enforces non-overlapping active applications.
    3. Locks StaffLeaveBalance row via select_for_update().
    4. Enforces balance availability: available_days >= working_days.
    5. Reserves days in pending_days.
    6. Creates LeaveApplication and writes audit log + notification outbox.
    """
    if not staff.is_active:
        raise ValidationError("Inactive staff members cannot apply for leave.")

    if not leave_type.is_active:
        raise ValidationError(f"Leave type '{leave_type.name}' is currently deactivated.")

    if leave_type.requires_document and not document:
        raise ValidationError({"document": f"Supporting proof document is mandatory for '{leave_type.name}'."})

    if document:
        validate_leave_document(document)

    working_days = calculate_working_days(start_date, end_date, is_half_day=is_half_day)

    if leave_type.max_consecutive_days and working_days > Decimal(str(leave_type.max_consecutive_days)):
        raise ValidationError({
            "end_date": (
                f"Requested leave of {working_days} days exceeds the maximum consecutive limit "
                f"of {leave_type.max_consecutive_days} days for {leave_type.name}."
            )
        })

    if not academic_year:
        ref, year_name = get_current_academic_year()
        academic_year = year_name
        academic_year_ref = ref

    with transaction.atomic():
        # Prevent overlapping active applications
        overlap_exists = LeaveApplication.objects.filter(
            staff=staff,
            status__in=["pending", "approved"],
            start_date__lte=end_date,
            end_date__gte=start_date,
        ).exists()
        if overlap_exists:
            raise ValidationError("You already have an overlapping pending or approved leave application covering this date range.")

        # Row-lock the staff leave balance
        balance, _ = StaffLeaveBalance.objects.select_for_update().get_or_create(
            staff=staff,
            leave_type=leave_type,
            academic_year=academic_year,
            defaults={
                "academic_year_ref": academic_year_ref,
                "allocated_days": leave_type.annual_allocation_days,
                "used_days": Decimal("0.0"),
                "pending_days": Decimal("0.0"),
            },
        )

        if balance.available_days < working_days:
            raise ValidationError(
                f"Insufficient leave balance for {leave_type.name}. "
                f"Available: {balance.available_days} days, Requested: {working_days} days."
            )

        # Atomically reserve days in pending
        balance.pending_days += working_days
        balance.save(update_fields=["pending_days", "updated_at"])

        application = LeaveApplication.objects.create(
            staff=staff,
            leave_type=leave_type,
            academic_year=academic_year,
            academic_year_ref=academic_year_ref,
            start_date=start_date,
            end_date=end_date,
            is_half_day=is_half_day,
            half_day_session=half_day_session if is_half_day else "",
            working_days=working_days,
            reason=reason,
            document=document,
            document_name=document.name if document else "",
            status="pending",
        )

        log_action(
            request,
            action="CREATE",
            model_name="LeaveApplication",
            object_id=application.id,
            changes={
                "leave_type": leave_type.code,
                "working_days": str(working_days),
                "start_date": str(start_date),
                "end_date": str(end_date),
            },
        )

        # In-app notification to applicant
        if staff.profile.user_id:
            try:
                notify(
                    recipient_user_id=staff.profile.user_id,
                    title="Leave Application Submitted",
                    body=f"Your {leave_type.name} application ({working_days} days) has been submitted for review.",
                    category="leave",
                    link="/dashboard/staff/leaves",
                )
            except Exception as e:
                logger.warning("Failed to dispatch in-app notification: %s", e)

        return application


def approve_leave_application(
    application_id: str,
    approver_staff: StaffMember,
    comments: str = "",
    request=None,
) -> LeaveApplication:
    """
    Approves a pending leave application atomically:
    1. Locks LeaveApplication via select_for_update().
    2. Prohibits self-approval (approver cannot be applicant).
    3. Shifts reserved days: pending_days -> used_days.
    4. Syncs approved dates into StaffAttendance records with status='leave'.
    5. Appends immutable LeaveApproval record.
    6. Logs audit and notifies applicant.
    """
    with transaction.atomic():
        application = (
            LeaveApplication.objects.select_for_update()
            .select_related("staff__profile", "leave_type")
            .filter(id=application_id)
            .first()
        )
        if not application:
            raise ValidationError("Leave application not found.")

        if application.status != "pending":
            raise ValidationError(
                f"Cannot approve application: current status is '{application.get_status_display()}'."
            )

        if approver_staff and application.staff_id == approver_staff.id:
            raise PermissionDenied("Self-approval is forbidden. An independent authorized reviewer must approve your leave.")

        # Row-lock balance
        balance = (
            StaffLeaveBalance.objects.select_for_update()
            .filter(
                staff=application.staff,
                leave_type=application.leave_type,
                academic_year=application.academic_year,
            )
            .first()
        )
        if not balance:
            raise ValidationError("Associated leave balance record not found.")

        # Transfer pending days to used days
        balance.pending_days = max(Decimal("0.0"), balance.pending_days - application.working_days)
        balance.used_days += application.working_days
        balance.save(update_fields=["pending_days", "used_days", "updated_at"])

        application.status = "approved"
        application.save(update_fields=["status", "updated_at"])

        LeaveApproval.objects.create(
            application=application,
            approver=approver_staff,
            decision="approved",
            comments=comments,
        )

        # Synchronize attendance
        sync_leave_to_attendance(application, approver_staff)

        log_action(
            request,
            action="APPROVE",
            model_name="LeaveApplication",
            object_id=application.id,
            changes={"status": "approved", "comments": comments},
        )

        # Notify applicant
        if application.staff.profile.user_id:
            try:
                notify(
                    recipient_user_id=application.staff.profile.user_id,
                    title="Leave Application Approved",
                    body=f"Your {application.leave_type.name} from {application.start_date} to {application.end_date} has been approved.",
                    category="leave",
                    link="/dashboard/staff/leaves",
                )
                user = application.staff.profile.user
                if user and getattr(user, "email", None):
                    queue_email(
                        to_email=user.email,
                        subject="Leave Application Approved",
                        body=(
                            f"Dear {application.staff.profile.first_name},\n\n"
                            f"Your leave application for {application.leave_type.name} "
                            f"({application.start_date} to {application.end_date}) has been approved.\n\n"
                            f"Comments: {comments or 'None'}\n\n"
                            "Regards,\nSchool Administration"
                        ),
                    )
            except Exception as e:
                logger.warning("Failed to dispatch leave approval notifications: %s", e)

        return application


def reject_leave_application(
    application_id: str,
    approver_staff: StaffMember,
    comments: str,
    request=None,
) -> LeaveApplication:
    """
    Rejects a pending leave application atomically:
    1. Enforces mandatory rejection reason.
    2. Prohibits self-rejection.
    3. Releases reserved pending_days back to available balance.
    4. Appends LeaveApproval record.
    5. Logs audit and notifies applicant.
    """
    if not comments or not comments.strip():
        raise ValidationError({"comments": "A reason or comment is required when rejecting a leave application."})

    with transaction.atomic():
        application = (
            LeaveApplication.objects.select_for_update()
            .select_related("staff__profile", "leave_type")
            .filter(id=application_id)
            .first()
        )
        if not application:
            raise ValidationError("Leave application not found.")

        if application.status != "pending":
            raise ValidationError(
                f"Cannot reject application: current status is '{application.get_status_display()}'."
            )

        if approver_staff and application.staff_id == approver_staff.id:
            raise PermissionDenied("You cannot review or reject your own leave application.")

        balance = (
            StaffLeaveBalance.objects.select_for_update()
            .filter(
                staff=application.staff,
                leave_type=application.leave_type,
                academic_year=application.academic_year,
            )
            .first()
        )
        if balance:
            balance.pending_days = max(Decimal("0.0"), balance.pending_days - application.working_days)
            balance.save(update_fields=["pending_days", "updated_at"])

        application.status = "rejected"
        application.save(update_fields=["status", "updated_at"])

        LeaveApproval.objects.create(
            application=application,
            approver=approver_staff,
            decision="rejected",
            comments=comments,
        )

        log_action(
            request,
            action="REJECT",
            model_name="LeaveApplication",
            object_id=application.id,
            changes={"status": "rejected", "comments": comments},
        )

        if application.staff.profile.user_id:
            try:
                notify(
                    recipient_user_id=application.staff.profile.user_id,
                    title="Leave Application Rejected",
                    body=f"Your {application.leave_type.name} application was rejected: {comments}",
                    category="leave",
                    link="/dashboard/staff/leaves",
                )
            except Exception as e:
                logger.warning("Failed to dispatch leave rejection notification: %s", e)

        return application


def cancel_leave_application(
    application_id: str,
    actor_staff: StaffMember,
    reason: str = "",
    is_admin: bool = False,
    request=None,
) -> LeaveApplication:
    """
    Cancels an application:
    - If pending: releases pending_days back to balance.
    - If approved: releases used_days back to balance and reconciles attendance records.
    - Non-admins can only cancel their own future or current applications.
    """
    with transaction.atomic():
        application = (
            LeaveApplication.objects.select_for_update()
            .select_related("staff__profile", "leave_type")
            .filter(id=application_id)
            .first()
        )
        if not application:
            raise ValidationError("Leave application not found.")

        if application.status not in ["pending", "approved"]:
            raise ValidationError(
                f"Cannot cancel leave application in '{application.get_status_display()}' status."
            )

        # Ownership verification
        if not is_admin:
            if not actor_staff or application.staff_id != actor_staff.id:
                raise PermissionDenied("You can only cancel your own leave applications.")

        balance = (
            StaffLeaveBalance.objects.select_for_update()
            .filter(
                staff=application.staff,
                leave_type=application.leave_type,
                academic_year=application.academic_year,
            )
            .first()
        )

        prev_status = application.status

        if prev_status == "pending":
            if balance:
                balance.pending_days = max(Decimal("0.0"), balance.pending_days - application.working_days)
                balance.save(update_fields=["pending_days", "updated_at"])
        elif prev_status == "approved":
            if balance:
                balance.used_days = max(Decimal("0.0"), balance.used_days - application.working_days)
                balance.save(update_fields=["used_days", "updated_at"])
            # Revert synced attendance
            revert_leave_from_attendance(application)

        application.status = "cancelled"
        application.save(update_fields=["status", "updated_at"])

        LeaveApproval.objects.create(
            application=application,
            approver=actor_staff,
            decision="cancelled",
            comments=reason or "Cancelled by applicant",
        )

        log_action(
            request,
            action="CANCEL",
            model_name="LeaveApplication",
            object_id=application.id,
            changes={"status": "cancelled", "previous_status": prev_status, "reason": reason},
        )

        return application


def sync_leave_to_attendance(application: LeaveApplication, approver_staff: StaffMember):
    """
    Creates or updates StaffAttendance records for all working dates in the leave window.
    Tags attendance with [LEAVE_APP:<uuid>] so only leave-created records are modified.
    """
    from attendance.models import AttendanceSettings, StaffAttendance
    from academics.models import CalendarEvent

    holiday_events = CalendarEvent.objects.filter(
        is_holiday=True,
        status="PUBLISHED",
        start_date__lte=application.end_date,
        end_date__gte=application.start_date,
    )
    holiday_dates = set()
    for ev in holiday_events:
        cur = max(application.start_date, ev.start_date)
        last = min(application.end_date, ev.end_date)
        delta = (last - cur).days
        for i in range(delta + 1):
            holiday_dates.add(cur + timedelta(days=i))

    weekly_off = AttendanceSettings.weekly_off()
    tag = f"[LEAVE_APP:{application.id}]"
    current = application.start_date
    while current <= application.end_date:
        if current.weekday() not in weekly_off and current not in holiday_dates:
            existing = StaffAttendance.objects.filter(staff=application.staff, date=current).first()
            if existing:
                if tag not in existing.remarks:
                    existing.status = "leave"
                    existing.remarks = f"{tag} Approved {application.leave_type.code} (Previous: {existing.status})"
                    existing.recorded_by = approver_staff
                    existing.save(update_fields=["status", "remarks", "recorded_by", "updated_at"])
            else:
                StaffAttendance.objects.create(
                    staff=application.staff,
                    date=current,
                    status="leave",
                    remarks=f"{tag} Approved {application.leave_type.code}",
                    recorded_by=approver_staff,
                )
        current += timedelta(days=1)


def revert_leave_from_attendance(application: LeaveApplication):
    """
    Safely reverts attendance records created by this leave application.
    Never removes manually entered attendance that existed prior to leave.
    """
    from attendance.models import StaffAttendance

    tag = f"[LEAVE_APP:{application.id}]"
    records = StaffAttendance.objects.filter(
        staff=application.staff,
        date__gte=application.start_date,
        date__lte=application.end_date,
        remarks__contains=tag,
    )
    for rec in records:
        if "Previous: " in rec.remarks:
            try:
                prev_status = rec.remarks.split("Previous: ")[1].rstrip(")")
                if prev_status in ["present", "absent", "late", "half_day"]:
                    rec.status = prev_status
                    rec.remarks = f"Reverted from {application.leave_type.code} leave cancellation"
                    rec.save(update_fields=["status", "remarks", "updated_at"])
                    continue
            except Exception:
                pass
        rec.delete()


def get_affected_periods_and_substitutes(application: LeaveApplication):
    """
    Finds teaching periods affected by an instructor's leave,
    and identifies eligible substitute instructors who are free.
    """
    instructor = getattr(application.staff, "instructor_record", None)
    if not instructor:
        return []

    from timetable.models import TimetableEntry, TimetableSubstitution, DAY_OF_WEEK_CHOICES
    from academics.models import CalendarEvent

    holiday_events = CalendarEvent.objects.filter(
        is_holiday=True,
        status="PUBLISHED",
        start_date__lte=application.end_date,
        end_date__gte=application.start_date,
    )
    holiday_dates = set()
    for ev in holiday_events:
        cur = max(application.start_date, ev.start_date)
        last = min(application.end_date, ev.end_date)
        delta = (last - cur).days
        for i in range(delta + 1):
            holiday_dates.add(cur + timedelta(days=i))

    from attendance.models import AttendanceSettings

    weekly_off = AttendanceSettings.weekly_off()
    leave_dates = []
    current = application.start_date
    while current <= application.end_date:
        if current.weekday() not in weekly_off and current not in holiday_dates:
            leave_dates.append(current)
        current += timedelta(days=1)
    weekdays = {d.weekday() for d in leave_dates}

    # Everything the loop needs, in four queries for the whole leave instead of four per period.
    entries_by_day = defaultdict(list)
    for entry in TimetableEntry.objects.filter(
        instructor=instructor,
        academic_year=application.academic_year,
        day_of_week__in=weekdays,
    ).select_related("section__level", "subject", "period", "room"):
        entries_by_day[entry.day_of_week].append(entry)

    # Instructors already teaching each (weekday, period)
    busy_teaching = defaultdict(set)
    for day, period_id, instructor_id in TimetableEntry.objects.filter(
        academic_year=application.academic_year,
        day_of_week__in=weekdays,
        instructor__isnull=False,
    ).values_list("day_of_week", "period_id", "instructor_id"):
        busy_teaching[(day, period_id)].add(instructor_id)

    # Existing substitutions per (entry, date), and instructors already substituting each (date, period)
    existing_subs = {}
    busy_substituting = defaultdict(set)
    for sub in TimetableSubstitution.objects.filter(date__in=leave_dates).select_related(
        "timetable_entry", "substitute_instructor__staff_member__profile"
    ):
        existing_subs.setdefault((sub.timetable_entry_id, sub.date), sub)
        if sub.substitute_instructor_id:
            busy_substituting[(sub.date, sub.timetable_entry.period_id)].add(sub.substitute_instructor_id)

    active_instructors = list(
        Instructor.objects.filter(staff_member__is_active=True).select_related("staff_member__profile")
    )

    affected_slots = []
    for current in leave_dates:
        day_of_week = current.weekday()
        for entry in entries_by_day[day_of_week]:
            existing_sub = existing_subs.get((entry.id, current))
            all_busy = (
                busy_teaching[(day_of_week, entry.period_id)]
                | busy_substituting[(current, entry.period_id)]
                | {instructor.id}
            )
            eligible_instructors = [inst for inst in active_instructors if inst.id not in all_busy]

            substitutes_data = [
                {
                    "instructor_id": inst.id,
                    "name": f"{inst.staff_member.profile.first_name} {inst.staff_member.profile.last_name}",
                    "specialization": inst.specialization,
                    "department": inst.staff_member.department,
                    "is_same_subject": (
                        inst.specialization.lower() in entry.subject.name.lower()
                        or entry.subject.name.lower() in inst.specialization.lower()
                    ),
                }
                for inst in eligible_instructors
            ]
            substitutes_data.sort(key=lambda x: not x["is_same_subject"])

            affected_slots.append({
                "date": current.strftime("%Y-%m-%d"),
                "day_of_week": DAY_OF_WEEK_CHOICES[day_of_week][1],
                "entry_id": str(entry.id),
                "section": f"{entry.section.level.name} - {entry.section.name}",
                "subject": f"{entry.subject.name} ({entry.subject.code})",
                "period": {
                    "id": str(entry.period.id),
                    "name": entry.period.name,
                    "start_time": entry.period.start_time.strftime("%H:%M"),
                    "end_time": entry.period.end_time.strftime("%H:%M"),
                },
                "room": entry.room.name if entry.room else None,
                "existing_substitution": {
                    "id": str(existing_sub.id),
                    "substitute_instructor": (
                        f"{existing_sub.substitute_instructor.staff_member.profile.first_name} "
                        f"{existing_sub.substitute_instructor.staff_member.profile.last_name}"
                    )
                    if existing_sub and existing_sub.substitute_instructor
                    else None,
                    "reason": existing_sub.reason if existing_sub else "",
                }
                if existing_sub
                else None,
                "eligible_substitutes": substitutes_data,
            })

    return affected_slots


def assign_leave_substitution(
    *,
    entry_id: str,
    date_val: date,
    substitute_instructor_id: int,
    reason: str,
    created_by: StaffMember,
    request=None,
):
    """
    Assigns an eligible substitute instructor for a specific class period.
    """
    from timetable.models import TimetableEntry, TimetableSubstitution

    entry = TimetableEntry.objects.filter(id=entry_id).first()
    if not entry:
        raise ValidationError("Timetable entry not found.")

    substitute = Instructor.objects.filter(id=substitute_instructor_id, staff_member__is_active=True).first()
    if not substitute:
        raise ValidationError("Selected substitute instructor not found or inactive.")

    if substitute.id == entry.instructor_id:
        raise ValidationError("Substitute instructor cannot be the assigned instructor.")

    # Check conflict
    conflict_entry = TimetableEntry.objects.filter(
        academic_year=entry.academic_year,
        day_of_week=entry.day_of_week,
        period=entry.period,
        instructor=substitute,
    ).exists()
    if conflict_entry:
        raise ValidationError("Selected substitute has another class scheduled during this period.")

    conflict_sub = TimetableSubstitution.objects.filter(
        date=date_val,
        timetable_entry__period=entry.period,
        substitute_instructor=substitute,
    ).exclude(timetable_entry=entry).exists()
    if conflict_sub:
        raise ValidationError("Selected substitute is already substituting another class during this period.")

    sub, created = TimetableSubstitution.objects.update_or_create(
        timetable_entry=entry,
        date=date_val,
        defaults={
            "substitute_instructor": substitute,
            "reason": reason,
            "created_by": created_by,
        },
    )

    log_action(
        request,
        action="ASSIGN_SUBSTITUTE",
        model_name="TimetableSubstitution",
        object_id=sub.id,
        changes={
            "timetable_entry": str(entry.id),
            "date": str(date_val),
            "substitute": str(substitute.id),
            "reason": reason,
        },
    )

    return sub

