"""
Statutory Government and Board Data Exports for Indian K-12 Schools:
1. UDISE+ (Unified District Information System for Education Plus) SDMS Export.
2. CBSE LOC (List of Candidates) Export for Board Exam Registration (Classes 9, 10, 11, 12).
"""
import csv
import io
from django.http import HttpResponse
from django.utils import timezone


def format_dob(d):
    if not d:
        return ""
    return d.strftime("%d/%m/%Y")


def export_udise_plus_csv(students=None):
    """
    Exports active students in the official Ministry of Education UDISE+
    Student Database Management System (SDMS) CSV format.
    """
    if students is None:
        from .models import Student
        students = Student.objects.all().select_related("profile").prefetch_related("enrollments__level", "enrollments__section", "parent_links__parent__profile")

    output = io.StringIO()
    writer = csv.writer(output)

    # Statutory UDISE+ SDMS Headers
    headers = [
        "PEN",
        "APAAR_ID",
        "STUDENT_NAME",
        "GENDER",
        "DOB_DD_MM_YYYY",
        "MOTHER_NAME",
        "FATHER_NAME",
        "GUARDIAN_NAME",
        "AADHAAR_LAST_4",
        "CLASS",
        "SECTION",
        "ADMISSION_NO",
        "ADMISSION_DATE",
        "SOCIAL_CATEGORY",
        "RTE_25_PERCENT",
        "BPL_STATUS",
        "CWSN_STATUS",
        "MOTHER_TONGUE",
        "RELIGION",
        "CONTACT_MOBILE",
    ]
    writer.writerow(headers)

    for student in students:
        profile = student.profile
        enrollment = student.enrollments.filter(is_current=True).select_related("level", "section").first()

        writer.writerow([
            student.pen or "",
            student.apaar_id or "",
            f"{profile.first_name} {profile.middle_name + ' ' if profile.middle_name else ''}{profile.last_name}".strip(),
            (profile.gender or "other").capitalize(),
            format_dob(profile.date_of_birth),
            student.get_mother_name(),
            student.get_father_name(),
            student.get_guardian_name(),
            student.aadhaar_last_4 or "",
            enrollment.level.name if enrollment and enrollment.level else "",
            enrollment.section.name if enrollment and enrollment.section else "",
            student.enrollment_id,
            format_dob(student.admission_date),
            student.caste_category or "",
            "Yes" if student.is_rte else "No",
            "Yes" if student.bpl_status else "No",
            student.cwsn_status or "None",
            student.mother_tongue or "",
            student.religion or "",
            profile.phone or "",
        ])

    csv_data = output.getvalue()
    response = HttpResponse(csv_data, content_type="text/csv; charset=utf-8")
    filename = f"udise_plus_students_{timezone.now().strftime('%Y%m%d')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def export_cbse_loc_csv(students=None, academic_year=None):
    """
    Exports candidate registration data matching the CBSE List of Candidates (LOC)
    portal specification for Classes 9, 10, 11, and 12.
    """
    from fees.models import StudentFee

    if students is None:
        from .models import Student
        students = Student.objects.all().select_related("profile").prefetch_related("enrollments__level__subjects", "enrollments__section", "parent_links__parent__profile")

    output = io.StringIO()
    writer = csv.writer(output)

    headers = [
        "REG_NO_OR_PEN",
        "APAAR_ID",
        "CANDIDATE_NAME",
        "MOTHER_NAME",
        "FATHER_NAME",
        "GENDER",
        "CATEGORY",
        "CWSN",
        "DOB_DD_MM_YYYY",
        "CLASS",
        "SECTION",
        "ADMISSION_NO",
        "ADMISSION_DATE",
        "SUBJECT_1",
        "SUBJECT_2",
        "SUBJECT_3",
        "SUBJECT_4",
        "SUBJECT_5",
        "ADDITIONAL_SUBJECT",
        "FEE_STATUS",
    ]
    writer.writerow(headers)

    for student in students:
        profile = student.profile
        enrollment = student.enrollments.filter(is_current=True).select_related("level", "section").first()

        # Check fee clearance
        unpaid_fees = StudentFee.objects.filter(
            student=student, status__in=["unpaid", "partially_paid"]
        ).exists()
        fee_status = "Cleared" if not unpaid_fees else "Dues Pending"

        # Determine subjects from class level
        subjects = []
        if enrollment and enrollment.level:
            subjects = list(
                enrollment.level.subjects.values_list("name", flat=True)[:6]
            )

        sub1 = subjects[0] if len(subjects) > 0 else ""
        sub2 = subjects[1] if len(subjects) > 1 else ""
        sub3 = subjects[2] if len(subjects) > 2 else ""
        sub4 = subjects[3] if len(subjects) > 3 else ""
        sub5 = subjects[4] if len(subjects) > 4 else ""
        sub6 = subjects[5] if len(subjects) > 5 else ""

        writer.writerow([
            student.pen or "",
            student.apaar_id or "",
            f"{profile.first_name} {profile.middle_name + ' ' if profile.middle_name else ''}{profile.last_name}".strip(),
            student.get_mother_name(),
            student.get_father_name(),
            (profile.gender or "other").capitalize(),
            student.caste_category or "",
            "Yes" if student.cwsn_status else "No",
            format_dob(profile.date_of_birth),
            enrollment.level.name if enrollment and enrollment.level else "",
            enrollment.section.name if enrollment and enrollment.section else "",
            student.enrollment_id,
            format_dob(student.admission_date),
            sub1,
            sub2,
            sub3,
            sub4,
            sub5,
            sub6,
            fee_status,
        ])

    csv_data = output.getvalue()
    response = HttpResponse(csv_data, content_type="text/csv; charset=utf-8")
    filename = f"cbse_loc_candidates_{timezone.now().strftime('%Y%m%d')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
