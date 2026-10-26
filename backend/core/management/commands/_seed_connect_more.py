"""The second half of ``seed_connect_school``: calendar, leave, timetable, announcements, certificates and
ID cards, admissions, and inventory. Kept apart only to keep each file readable; see seed_connect_school.py.

Every step goes through the real services where one exists, so the data obeys the same rules as the screens.
Nothing here sends real email: announcements are in-app only.
"""
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

D = Decimal
EMAIL_DOMAIN = "example.test"

CHILD_FIRST = {
    "male": ["Aarav", "Vihaan", "Ishaan", "Rudra", "Kabir", "Arnav", "Dhruv", "Reyansh", "Pranjal", "Ayush", "Neel", "Rohan"],
    "female": ["Aadhya", "Ananya", "Diya", "Myra", "Saanvi", "Ira", "Riya", "Pari", "Mrinmoyee", "Anika", "Navya", "Tanvi"],
}
CHILD_LAST = ["Sharma", "Gupta", "Verma", "Bora", "Choudhury", "Deka", "Phukan", "Barman", "Singh", "Das", "Baruah", "Kalita"]
PREVIOUS_SCHOOLS = ["Little Flower Nursery School", "Don Bosco Academy", "St. Mary's Kindergarten", "Kendriya Vidyalaya", "Holy Child School", ""]

LEAVE_TYPES = [
    # name, code, days a year, paid, longest stretch
    ("Casual Leave", "CL", "12.0", True, 3),
    ("Sick Leave", "SL", "10.0", True, 5),
    ("Earned Leave", "EL", "15.0", True, 10),
    ("Maternity Leave", "ML", "182.0", True, None),
    ("Leave Without Pay", "LWP", "30.0", False, 10),
]
LEAVE_REASONS = {
    "CL": ["Family function", "Personal work", "Attending a wedding", "Bank and government office work"],
    "SL": ["Fever and cold", "Stomach infection", "Doctor's advice for rest", "Viral fever"],
    "EL": ["Family trip", "Travelling to hometown", "Rest and family time"],
    "LWP": ["Urgent personal matter", "Family emergency out of town"],
}

# title, body, audience
ANNOUNCEMENTS = [
    ("Annual Sports Day: Saturday, 12 December", "The Annual Sports Day will be held on the school ground from 8:30 am. Students should come in their house colours. Parents are warmly invited.", "all"),
    ("Parent-Teacher Meeting this Saturday", "The Parent-Teacher Meeting for the Half-Yearly results is on Saturday from 9:00 am to 1:00 pm. Please collect the progress report from your child's class teacher.", "all_parents"),
    ("Staff meeting: Monday 3:30 pm", "All teaching and non-teaching staff are requested to attend the monthly staff meeting in the conference room. The agenda covers the Half-Yearly results and the Annual Day plan.", "all_staff"),
    ("Autumn festival break", "The school will remain closed for the autumn festival break from 19 to 23 October and will reopen on Monday. Wishing everyone a joyful festival.", "all"),
    ("Class 10 Pre-Board examination schedule", "The Pre-Board examination for Class 10 begins next month. The timetable is on the notice board and in the portal. Students must carry their admit card every day.", "level"),
    ("Fee payment reminder", "Parents are requested to clear any pending fees before the end of the month to avoid disruption in the next term. Fees can be paid at the school office or online.", "all_parents"),
    ("Library: new books have arrived", "More than forty new titles are now in the library, including science, biography and story books. Students can borrow two books for fourteen days.", "all_students"),
    ("Class meeting: choosing class monitors", "Class monitors will be chosen in the next class period by a class vote. Class teachers will guide the process.", "section"),
]


class MoreSteps:
    """Steps mixed into the seed_connect_school command. Uses ``self.rng``, ``self.today``, ``self.staff``,
    ``self.students`` and ``self.owner_id`` set up by the command."""

    # --- shared ---------------------------------------------------------------------------------------------

    def _year(self):
        """``(name, AcademicYear or None)`` of the school year in progress."""
        from academics.models import AcademicYear
        from students.models import StudentLevel

        name = StudentLevel.objects.filter(is_current=True).values_list("academic_year", flat=True).first()
        row = AcademicYear.objects.filter(name=name).first() if name else AcademicYear.objects.filter(is_current=True).first()
        if row is not None:
            return row.name, row
        return name or f"{self.today.year}-{str(self.today.year + 1)[2:]}", None

    def _first_year(self, name):
        try:
            return int(name[:4])
        except ValueError:
            return self.today.year if self.today.month >= 4 else self.today.year - 1

    def _admin_staff(self, exclude=None):
        """A staff member to act as approver or coordinator (an office role first), other than ``exclude``."""
        office = [s for s in self.staff if s.designation == "Administrative Officer" and s != exclude]
        anyone = [s for s in self.staff if s != exclude]
        return (office or anyone)[0]

    # --- academic calendar ----------------------------------------------------------------------------------

    def _step_calendar(self):
        from academics.models import CalendarEvent

        if CalendarEvent.objects.filter(title="Independence Day").exists():
            return "skipped: calendar events already exist"
        name, year = self._year()
        y = self._first_year(name)
        events = [
            # title, type, start, end, audience
            ("Bohag Bihu holidays", "HOLIDAY", date(y, 4, 14), date(y, 4, 16), "ALL"),
            ("Annual Examination results", "ACADEMIC", date(y, 4, 2), date(y, 4, 2), "STUDENTS"),
            ("Parent-Teacher Meeting (Term 1)", "MEETING", date(y, 7, 11), date(y, 7, 11), "STUDENTS"),
            ("Independence Day", "HOLIDAY", date(y, 8, 15), date(y, 8, 15), "ALL"),
            ("Teachers' Day celebration", "ACTIVITY", date(y, 9, 5), date(y, 9, 5), "ALL"),
            ("Half-Yearly Examinations", "EXAMINATION", date(y, 9, 14), date(y, 9, 25), "STUDENTS"),
            ("Gandhi Jayanti", "HOLIDAY", date(y, 10, 2), date(y, 10, 2), "ALL"),
            ("Autumn festival break", "HOLIDAY", date(y, 10, 19), date(y, 10, 23), "ALL"),
            ("Children's Day programme", "ACTIVITY", date(y, 11, 14), date(y, 11, 14), "ALL"),
            ("Annual Sports Day", "ACTIVITY", date(y, 12, 12), date(y, 12, 12), "ALL"),
            ("Christmas holiday", "HOLIDAY", date(y, 12, 25), date(y, 12, 25), "ALL"),
            ("Magh Bihu holidays", "HOLIDAY", date(y + 1, 1, 14), date(y + 1, 1, 16), "ALL"),
            ("Republic Day", "HOLIDAY", date(y + 1, 1, 26), date(y + 1, 1, 26), "ALL"),
            ("Annual Day and prize distribution", "ACTIVITY", date(y + 1, 2, 20), date(y + 1, 2, 20), "ALL"),
            ("Annual Examinations", "EXAMINATION", date(y + 1, 3, 1), date(y + 1, 3, 15), "STUDENTS"),
            ("Last day to submit projects", "DEADLINE", date(y + 1, 2, 5), date(y + 1, 2, 5), "STUDENTS"),
        ]
        for title, kind, start, end, audience in events:
            CalendarEvent.objects.create(
                title=title, event_type=kind, start_date=start, end_date=end, academic_year=year, audience=audience,
                status="PUBLISHED", description=f"{title}.", created_by_id=self.owner_id,
                created_by_username="admin", location="School campus" if kind in ("ACTIVITY", "MEETING") else "",
            )
        holidays = sum(1 for e in events if e[1] == "HOLIDAY")
        return f"{len(events)} calendar events for {name} ({holidays} holidays)"

    def _holiday_dates(self, first, last):
        from academics.models import CalendarEvent

        days = set()
        for event in CalendarEvent.objects.filter(is_holiday=True, status="PUBLISHED", start_date__lte=last, end_date__gte=first):
            current = max(first, event.start_date)
            while current <= min(last, event.end_date):
                days.add(current)
                current += timedelta(days=1)
        return days

    # --- staff leave ----------------------------------------------------------------------------------------------

    def _step_leave(self):
        from rest_framework.exceptions import ValidationError as DRFValidationError
        from django.core.exceptions import ValidationError as DjangoValidationError

        from staff import leave_services as svc
        from staff.models import LeaveApplication, LeaveType

        if LeaveApplication.objects.exists():
            return "skipped: leave applications already exist"
        types = {
            code: LeaveType.objects.get_or_create(
                code=code,
                defaults={"name": name, "annual_allocation_days": D(days), "is_paid": paid, "max_consecutive_days": longest},
            )[0]
            for name, code, days, paid, longest in LEAVE_TYPES
        }
        errors = (DRFValidationError, DjangoValidationError)
        ref, year_name = svc.get_current_academic_year()
        for member in self.staff:
            svc.get_or_create_staff_balances(member, year_name, ref)

        counts = {"approved": 0, "rejected": 0, "pending": 0}
        staff = list(self.staff)
        self.rng.shuffle(staff)
        for member in staff[: max(6, round(len(staff) * 0.45))]:
            approver = self._admin_staff(exclude=member)
            for _ in range(self.rng.choice([1, 1, 2, 3])):
                code = self.rng.choices(["CL", "SL", "EL", "LWP"], weights=[55, 28, 10, 7])[0]
                length = {"CL": self.rng.choice([1, 1, 2]), "SL": self.rng.choice([1, 2, 3]), "EL": self.rng.choice([3, 4, 5]), "LWP": self.rng.choice([1, 2])}[code]
                start = self.today - timedelta(days=self.rng.randint(5, 68))
                end = start + timedelta(days=length - 1)
                try:
                    application = svc.submit_leave_application(
                        staff=member, leave_type=types[code], start_date=start, end_date=end,
                        reason=self.rng.choice(LEAVE_REASONS[code]), academic_year=year_name, academic_year_ref=ref,
                    )
                except errors:
                    continue  # no working days in that range, an overlap, or no balance left: pick another
                if self.rng.random() < 0.87:
                    svc.approve_leave_application(str(application.id), approver, comments="Approved")
                    counts["approved"] += 1
                else:
                    svc.reject_leave_application(str(application.id), approver, comments="Too many staff on leave that week")
                    counts["rejected"] += 1
        # A few requests still waiting, starting soon.
        waiting = 0
        for member in staff[-5:]:
            start = self.today + timedelta(days=self.rng.randint(3, 20))
            try:
                svc.submit_leave_application(
                    staff=member, leave_type=types["CL"], start_date=start, end_date=start + timedelta(days=self.rng.choice([0, 1])),
                    reason=self.rng.choice(LEAVE_REASONS["CL"]), academic_year=year_name, academic_year_ref=ref,
                )
                waiting += 1
            except errors:
                continue
        return f"{len(types)} leave types, {counts['approved']} approved, {counts['rejected']} rejected, {waiting} waiting for a decision"

    # --- timetable --------------------------------------------------------------------------------------------------

    def _step_timetable(self):
        from academics.models import Section, SubjectAssignment
        from attendance.models import AttendanceSettings
        from staff.models import LeaveApplication
        from timetable.models import Period, Room, TimetableEntry, TimetableSubstitution

        if Period.objects.exists():
            return "skipped: the timetable already exists"
        name, year = self._year()
        slots = [
            ("Period 1", time(8, 0), time(8, 40), False), ("Period 2", time(8, 40), time(9, 20), False),
            ("Period 3", time(9, 20), time(10, 0), False), ("Short break", time(10, 0), time(10, 20), True),
            ("Period 4", time(10, 20), time(11, 0), False), ("Period 5", time(11, 0), time(11, 40), False),
            ("Period 6", time(11, 40), time(12, 20), False), ("Lunch break", time(12, 20), time(13, 0), True),
        ]
        periods = [
            Period.objects.create(academic_year=name, academic_year_ref=year, name=n, order=i + 1, start_time=s, end_time=e, is_break=b)
            for i, (n, s, e, b) in enumerate(slots)
        ]
        teaching = [p for p in periods if not p.is_break]
        off = AttendanceSettings.weekly_off()
        days = [d for d in range(7) if d not in off]  # a school week without the weekly off days

        sections = list(Section.objects.select_related("level").order_by("level__order", "name"))
        assignments = {}
        for a in SubjectAssignment.objects.select_related("subject").filter(instructor__isnull=False):
            assignments.setdefault(a.section_id, []).append(a)
        rooms = {s.id: Room.objects.create(name=f"{s.level.name} - {s.name}", capacity=s.capacity) for s in sections}

        busy = set()  # (instructor, day, period): a teacher is in one place at a time
        entries = []
        for section in sections:
            offered = assignments.get(section.id, [])
            if not offered:
                continue
            remaining = {a.id: max(1, round(len(days) * len(teaching) / len(offered))) for a in offered}
            for day in days:
                used_today = set()
                for period in teaching:
                    options = sorted(offered, key=lambda a: (a.subject_id in used_today, -remaining[a.id], self.rng.random()))
                    for a in options:
                        if remaining[a.id] <= 0 or (a.instructor_id, day, period.id) in busy:
                            continue
                        busy.add((a.instructor_id, day, period.id))
                        remaining[a.id] -= 1
                        used_today.add(a.subject_id)
                        entries.append(TimetableEntry(
                            academic_year=name, academic_year_ref=year, section=section, subject=a.subject,
                            instructor_id=a.instructor_id, room=rooms[section.id], day_of_week=day, period=period,
                        ))
                        break  # a slot with no free teacher stays a free or activity period
        TimetableEntry.objects.bulk_create(entries)
        possible = len(sections) * len(days) * len(teaching)

        # Cover for teachers who were on approved leave in the last two weeks.
        window_start, window_end = self.today - timedelta(days=14), self.today - timedelta(days=1)
        holidays = self._holiday_dates(window_start, window_end)
        by_slot = {}
        for e in TimetableEntry.objects.filter(academic_year=name, instructor__isnull=False):
            by_slot.setdefault((e.instructor_id, e.day_of_week), []).append(e)
        all_instructors = {e.instructor_id for e in TimetableEntry.objects.filter(instructor__isnull=False)}
        creator = self._admin_staff()
        covers = 0
        for leave in LeaveApplication.objects.filter(status="approved", end_date__gte=window_start, start_date__lte=window_end).select_related("staff"):
            instructor = getattr(leave.staff, "instructor_record", None)
            if instructor is None:
                continue
            current = max(leave.start_date, window_start)
            while current <= min(leave.end_date, window_end) and covers < 25:
                if current.weekday() in days and current not in holidays:
                    for entry in by_slot.get((instructor.id, current.weekday()), []):
                        free = [i for i in all_instructors if i != instructor.id and (i, entry.day_of_week, entry.period_id) not in busy]
                        if not free:
                            continue
                        substitute = self.rng.choice(sorted(free, key=str))
                        TimetableSubstitution.objects.get_or_create(
                            timetable_entry=entry, date=current,
                            defaults={"substitute_instructor_id": substitute, "reason": "Regular teacher on approved leave", "created_by": creator},
                        )
                        covers += 1
                current += timedelta(days=1)
        return (f"{len(periods)} periods ({len(teaching)} teaching), {len(rooms)} classrooms, {len(entries)} timetable entries "
                f"({round(100 * len(entries) / possible)}% of slots; the rest are free periods), {covers} substitutions")

    # --- announcements -------------------------------------------------------------------------------------------------------

    def _step_announcements(self):
        from academics.models import AcademicLevel, Section
        from announcements import services as svc
        from announcements.models import Announcement
        from notifications.models import Notification

        if Announcement.objects.exists():
            return "skipped: announcements already exist"
        level = AcademicLevel.objects.filter(name="Class 10").first() or AcademicLevel.objects.order_by("-order").first()
        section = Section.objects.filter(level__name="Class 8").first() or Section.objects.first()
        published = skipped = 0
        for index, (title, body, audience) in enumerate(ANNOUNCEMENTS):
            row = Announcement.objects.create(
                title=title, body=body, created_by_user_id=self.owner_id, audience_type=audience, send_email=False,
                audience_level=level if audience == "level" else None, audience_section=section if audience == "section" else None,
            )
            try:
                svc.publish_announcement(row.id)
            except Exception:
                skipped += 1  # nobody to send to (for example an empty class)
                row.delete()
                continue
            ago = timedelta(days=2 + index * 6, hours=3)
            published_at = timezone.now() - ago
            Announcement.objects.filter(pk=row.pk).update(published_at=published_at)
            Notification.objects.filter(link=f"/dashboard/announcements/{row.id}").update(created_at=published_at)
            published += 1
        # One draft, one scheduled for next week, one archived.
        Announcement.objects.create(
            title="Draft: Winter uniform from 1 November", body="Students may wear the winter uniform from 1 November. Details to follow.",
            created_by_user_id=self.owner_id, audience_type="all_parents",
        )
        scheduled = Announcement.objects.create(
            title="Reminder: Half-Yearly report cards", body="Report cards will be handed over in the Parent-Teacher Meeting next week.",
            created_by_user_id=self.owner_id, audience_type="all_parents",
        )
        svc.schedule_announcement(scheduled.id, timezone.now() + timedelta(days=5))
        old = Announcement.objects.create(
            title="Annual Day rehearsal timings", body="Rehearsals are over. Thank you to all participants.",
            created_by_user_id=self.owner_id, audience_type="all_students",
        )
        svc.publish_announcement(old.id)
        svc.archive_announcement(old.id)
        return f"{published + 1} published ({skipped} skipped for an empty audience), 1 scheduled, 1 draft, 1 archived"

    # --- certificates and ID cards --------------------------------------------------------------------------------------------

    def _step_certificates(self):
        from certificates import idcards
        from certificates import services as svc
        from certificates.models import Certificate, CertificateSettings
        from profiles.models import Profile
        from staff.models import StaffMember
        from students.models import Student

        if Certificate.objects.exists():
            return "skipped: certificates already exist"
        settings_row = CertificateSettings.objects.first() or CertificateSettings.objects.create()
        settings_row.signatory_name, settings_row.signatory_title = "Ananya Chatterjee", "Principal"
        settings_row.save()
        approver = self._admin_staff().profile.user_id or self.owner_id

        issued = {"bonafide": 0, "character": 0, "transfer": 0, "experience": 0}

        def issue(kind, subject, data):
            """The certificate, or None when the rules refuse this person (for example, no enrolment this year)."""
            try:
                return svc.issue_certificate(
                    certificate_type=kind, subject=subject, data=data, issued_by_user_id=self.owner_id,
                    approved_by_user_id=approver if kind in ("transfer", "experience") else None,
                )
            except svc.IntegrityKeyError:
                raise
            except svc.CertificateError:
                return None

        students = list(self.students)
        self.rng.shuffle(students)
        try:
            purposes = ["Opening a bank account", "Passport application", "Scholarship application", "Travel concession"]
            for student in students[:8]:
                if issue("bonafide", student, {"reason": self.rng.choice(purposes)}):
                    issued["bonafide"] += 1
            for student in students[8:14]:
                if issue("character", student, {"conduct": self.rng.choice(["Excellent", "Very good", "Good"])}):
                    issued["character"] += 1
        except svc.IntegrityKeyError:
            return "skipped: the certificate signing key is not configured (set CERTIFICATE_INTEGRITY_KEYS, or run with DEBUG on)"

        # Transfer certificates: only for students whose exit is recorded in Promotion & Transfer.
        for student in Student.objects.filter(status__in=svc.TRANSFER_ELIGIBLE_STATUSES).order_by("enrollment_id")[:4]:
            exit_record = svc.authoritative_exit_record(student)
            if exit_record is None:
                continue
            leaving = min(self.today, max(exit_record.created_at.date(), student.admission_date or exit_record.created_at.date()))
            if issue("transfer", student, {"leaving_date": leaving.isoformat(), "reason": "Family relocated to another city", "conduct": "Good"}):
                issued["transfer"] += 1

        # Former staff, each with a long record, get experience certificates.
        for i, (first, last, joined, left, dept) in enumerate([
            ("Rina", "Dutta", date(2009, 6, 1), date(2022, 3, 31), "Mathematics"),
            ("Mahendra", "Saikia", date(2013, 4, 1), date(2024, 3, 31), "English"),
        ]):
            profile = Profile.objects.create(first_name=first, last_name=last, gender="female" if i == 0 else "male", phone=f"+91-9{self.rng.randint(100000000, 999999999)}")
            member = StaffMember.objects.create(
                profile=profile, employee_id=f"EMP/{joined.year}/9{i + 1:03d}", designation="Teacher", department=dept,
                joining_date=joined, is_active=False, experience_years=(left.year - joined.year),
            )
            if issue("experience", member, {"period_end": left.isoformat(), "reason": "Retired after long service", "conduct": "Excellent"}):
                issued["experience"] += 1

        # One certificate cancelled, as happens when a name is misspelt.
        spare = students[14] if len(students) > 14 else students[0]
        mistaken = issue("character", spare, {"conduct": "Good"})
        if mistaken:
            svc.cancel_certificate(certificate_id=mistaken.id, user_id=self.owner_id, reason="Name was misspelt on the first copy")

        # ID cards: a card number is created the first time someone's card is generated.
        cards = 0
        for student in students[:30]:
            idcards.card_token(idcards.KIND_STUDENT, student)
            cards += 1
        for member in self.staff[:12]:
            idcards.card_token(idcards.KIND_STAFF, member)
            cards += 1
        return (f"{issued['bonafide']} bonafide, {issued['character']} character, {issued['transfer']} transfer and "
                f"{issued['experience']} experience certificates (1 cancelled), {cards} ID cards generated")

    # --- admissions --------------------------------------------------------------------------------------------------------------

    def _step_admissions(self):
        from academics.models import AcademicLevel, AcademicYear
        from students import admissions_services as svc
        from students.models import AdmissionApplication, AdmissionEnquiry, AdmissionInterview

        if AdmissionEnquiry.objects.exists():
            return "skipped: admission enquiries already exist"
        name, _ = self._year()
        y = self._first_year(name)
        next_name = f"{y + 1}-{str(y + 2)[2:]}"
        next_ref = AcademicYear.objects.filter(name=next_name).first()
        levels = list(AcademicLevel.objects.filter(order__lte=12).order_by("order"))
        coordinator = self._admin_staff()
        statuses = ["new"] * 9 + ["contacted"] * 8 + ["qualified"] * 6 + ["closed"] * 4 + ["converted"] * 9
        self.rng.shuffle(statuses)

        enquiries = []
        for index, status in enumerate(statuses):
            level = self.rng.choice(levels)
            gender = self.rng.choice(["male", "female"])
            child = self.rng.choice(CHILD_FIRST[gender])
            surname = self.rng.choice(CHILD_LAST)
            father = self.rng.choice(["Ramesh", "Suresh", "Dilip", "Anil", "Manoj", "Bhaskar", "Pradip", "Kamal", "Rupam"])
            dob_year = self.today.year - (level.order + 2)  # Nursery is 3, Class 1 is 6
            enquiries.append(AdmissionEnquiry.objects.create(
                enquiry_number=svc.generate_enquiry_number(), student_name=f"{child} {surname}",
                date_of_birth=date(max(2008, dob_year), self.rng.randint(1, 12), self.rng.randint(1, 28)), gender=gender,
                guardian_name=f"{father} {surname}", guardian_relationship="father",
                guardian_phone=f"+91-9{self.rng.randint(100000000, 999999999)}",
                guardian_email=f"enquiry{index:03d}@{EMAIL_DOMAIN}" if self.rng.random() < 0.7 else "",
                address=f"House {self.rng.randint(1, 120)}, {self.rng.choice(['Beltola', 'Six Mile', 'Khanapara', 'Ganeshguri', 'Maligaon'])}, Guwahati",
                previous_school=self.rng.choice(PREVIOUS_SCHOOLS), academic_year=next_name, academic_year_ref=next_ref,
                preferred_level=level, source=self.rng.choice(["website", "walk_in", "phone", "referral", "campaign"]),
                status="new" if status == "converted" else status, assigned_to=coordinator,
                enquiry_date=self.today - timedelta(days=self.rng.randint(1, 75)),
                follow_up_date=self.today + timedelta(days=self.rng.randint(1, 14)) if status in ("new", "contacted", "qualified") else None,
                notes=self.rng.choice(["Asked about fees and transport.", "Prefers the morning bus.", "Elder sibling already studies here.", "Wants a campus visit.", ""]),
            ))

        # Where the application stands, as the steps it has been through.
        paths = {
            "draft": [], "submitted": ["submitted"], "under_review": ["submitted", "under_review"],
            "documents_pending": ["submitted", "documents_pending"], "assessment_pending": ["submitted", "under_review", "assessment_pending"],
            "approved": ["submitted", "under_review", "approved"], "offer_accepted": ["submitted", "under_review", "approved", "offer_accepted"],
            "waitlisted": ["submitted", "under_review", "waitlisted"], "rejected": ["submitted", "under_review", "rejected"],
        }
        targets = ["submitted", "under_review", "documents_pending", "assessment_pending", "approved", "offer_accepted",
                   "waitlisted", "rejected", "draft"]  # one application at each stage
        converted = [e for e, s in zip(enquiries, statuses) if s == "converted"]
        applications = []
        for enquiry, target in zip(converted, targets + targets):
            application = svc.convert_enquiry_to_application(enquiry.id)
            for step in paths[target]:
                svc.transition_application_status(
                    application, step, notes=f"Moved to {step.replace('_', ' ')}",
                    reason="Seats are full for this class" if step == "rejected" else ("Meets the admission criteria" if step == "approved" else ""),
                )
            application.refresh_from_db()
            applications.append(application)

        interviews = 0
        for application in applications:
            if application.status not in ("under_review", "assessment_pending", "approved", "offer_accepted", "waitlisted", "rejected"):
                continue
            done = application.status != "assessment_pending"
            scheduled = timezone.now() + timedelta(days=self.rng.randint(2, 9)) if not done else timezone.now() - timedelta(days=self.rng.randint(3, 25))
            AdmissionInterview.objects.create(
                application=application, interview_type=self.rng.choice(["student_interview", "written_test", "parent_interaction"]),
                scheduled_at=scheduled, completed_at=scheduled if done else None, interviewer=coordinator,
                status="completed" if done else "scheduled",
                score=D(self.rng.randint(55, 98)) if done else None,
                recommendation={"approved": "recommended", "offer_accepted": "recommended", "waitlisted": "waitlist", "rejected": "not_recommended"}.get(application.status, "conditional") if done else "",
                feedback="Confident and well prepared." if done else "",
            )
            interviews += 1
        status_counts = {}
        for s in statuses:
            status_counts[s] = status_counts.get(s, 0) + 1
        return (f"{len(enquiries)} enquiries for {next_name} ({status_counts.get('new', 0)} new, "
                f"{status_counts.get('contacted', 0)} contacted, {status_counts.get('qualified', 0)} qualified), "
                f"{len(applications)} applications moved through the pipeline, {interviews} interviews")

    # --- inventory -----------------------------------------------------------------------------------------------------------------

    def _step_inventory(self):
        from django.db import connection

        try:
            call_command("seed_inventory_demo", schema=connection.schema_name, verbosity=0)
        except CommandError as exc:
            return f"skipped: {exc}"
        return "stock, purchases and assets added by seed_inventory_demo"
