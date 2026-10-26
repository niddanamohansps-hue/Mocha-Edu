import {
    LayoutDashboard,
    Users,
    UserPlus,
    GraduationCap,
    BookOpen,
    FileText,
    Shield,
    Settings,
    Briefcase,
    School,
    Lock,
    UserCog,
    Bus,
    Baby,
    Receipt,
    CalendarCheck,
    CalendarRange,
    Award,
    Megaphone,
    Boxes,
    Wallet,
    Library
} from "lucide-react";
import { SidebarItemType } from "@/components/dashboard/Sidebar/SidebarItem";

export const getMenuItems = (user: any, can: (permission: string) => boolean): SidebarItemType[] => {
    // 1. Dashboard (Global)
    const menuItems: SidebarItemType[] = [
        {
            label: "Dashboard",
            icon: LayoutDashboard,
            href: "/dashboard"
        }
    ];

    // 2. Student Management (Core Domain)
    const studentChildren: SidebarItemType[] = [];
    if (can("view_student")) {
        studentChildren.push({ label: "Student Directory", href: "/dashboard/students" });
    }
    if (can("add_student") || can("view_admissions")) {
        studentChildren.push({ label: "Admissions", href: "/dashboard/students/admissions" });
    }
    if (can("manage_student_promotion")) {
        studentChildren.push({ label: "Promotion & Transfer", href: "/dashboard/students/promotion" });
    }

    if (studentChildren.length > 0) {
        menuItems.push({
            label: "Student Management",
            icon: Users,
            children: studentChildren
        });
    }

    // 3. Staff (Operational HR)
    const staffChildren: SidebarItemType[] = [];
    if (can("view_staff")) {
        staffChildren.push({ label: "Staff Directory", href: "/dashboard/staff" });
    }
    if (can("add_staff")) {
        staffChildren.push({ label: "Recruit Staff", href: "/dashboard/hr/recruit" });
    }
    if (can("view_own_leaves") || can("view_all_leaves") || can("manage_staff_leaves") || user?.active_role === "staff" || user?.active_role === "instructor" || user?.active_role === "owner") {
        staffChildren.push({ label: "Leave Management", href: "/dashboard/staff/leaves" });
    }

    if (staffChildren.length > 0) {
        menuItems.push({
            label: "Staff",
            icon: Briefcase,
            children: staffChildren
        });
    }

    // 4. Instructors (Academic Faculty)
    const instructorChildren: SidebarItemType[] = [];
    if (can("view_staff") || can("view_student")) {
        instructorChildren.push({ label: "Faculty Directory", href: "/dashboard/instructors" });
    }

    if (instructorChildren.length > 0) {
        menuItems.push({
            label: "Faculty",
            icon: School,
            children: instructorChildren
        });
    }

    // 5. Academics
    const academicChildren: SidebarItemType[] = [];

    if (can("view_program") || can("view_academic_level")) {
        academicChildren.push({ label: "Academic Structure", href: "/dashboard/academics" });
    }
    if (can("view_calendar_events") || user?.active_role) {
        academicChildren.push({ label: "Academic Calendar", href: "/dashboard/academics/calendar" });
    }

    if (academicChildren.length > 0) {
        menuItems.push({
            label: "Academics",
            icon: GraduationCap,
            children: academicChildren
        });
    }

    // 6. Course Content
    const courseContentChildren: SidebarItemType[] = [];

    if (can("view_course_content")) {
        courseContentChildren.push({ label: "Study Materials", href: "/dashboard/course-content/materials" });
    }
    if (can("manage_course_content")) {
        courseContentChildren.push({ label: "Manage Content", href: "/dashboard/course-content/manage" });
    }
    if (can("view_course_content") || can("submit_assignment")) {
        courseContentChildren.push({ label: "Assignments", href: "/dashboard/course-content/assignments" });
    }
    if (can("grade_assignment")) {
        courseContentChildren.push({ label: "Grade Submissions", href: "/dashboard/course-content/grading" });
    }

    if (courseContentChildren.length > 0) {
        menuItems.push({
            label: "Course Content",
            icon: BookOpen,
            children: courseContentChildren
        });
    }

    // 6.5 Attendance
    const attendanceChildren: SidebarItemType[] = [];
    if (can("mark_attendance")) {
        attendanceChildren.push({ label: "Mark Attendance", href: "/dashboard/attendance/mark" });
    }
    if (can("view_attendance") || user?.active_role === "student") {
        attendanceChildren.push({ label: "History", href: "/dashboard/attendance/history" });
    }
    if (can("view_attendance_reports")) {
        attendanceChildren.push({ label: "Reports", href: "/dashboard/attendance/reports" });
    }
    if (can("mark_staff_attendance")) {
        attendanceChildren.push({ label: "Staff Attendance", href: "/dashboard/attendance/staff" });
    }
    if (user?.active_role === "owner") {
        attendanceChildren.push({ label: "Attendance Settings", href: "/dashboard/attendance/settings" });
    }

    if (attendanceChildren.length > 0) {
        menuItems.push({
            label: "Attendance",
            icon: CalendarCheck,
            children: attendanceChildren
        });
    }

    // 6.6 Timetable
    const timetableChildren: SidebarItemType[] = [];
    if (can("view_timetable")) {
        timetableChildren.push({ label: "Timetable", href: "/dashboard/timetable" });
        timetableChildren.push({ label: "My Schedule", href: "/dashboard/timetable/my-schedule" });
    }
    if (can("manage_substitutions")) {
        timetableChildren.push({ label: "Substitutions", href: "/dashboard/timetable/substitutions" });
    }

    if (timetableChildren.length > 0) {
        menuItems.push({
            label: "Timetable",
            icon: CalendarRange,
            children: timetableChildren
        });
    }

    // 6.7 Examinations
    const examinationChildren: SidebarItemType[] = [];
    if (can("view_examinations") || can("manage_examinations")) {
        examinationChildren.push({ label: "Examinations", href: "/dashboard/examinations" });
    }
    if (can("enter_marks")) {
        examinationChildren.push({ label: "Marks Entry", href: "/dashboard/examinations/marks" });
    }
    if (can("view_results") || user?.active_role === "student") {
        examinationChildren.push({ label: "Results", href: "/dashboard/examinations/results" });
    }
    if (can("manage_grading")) {
        examinationChildren.push({ label: "Grading", href: "/dashboard/examinations/grading" });
    }

    if (can("view_question_bank") || can("create_questions") || can("review_questions") || can("manage_question_bank")) {
        examinationChildren.push({ label: "Question Bank", href: "/dashboard/question-bank" });
    }
    if (can("review_questions")) {
        examinationChildren.push({ label: "Questions to Review", href: "/dashboard/question-bank/review" });
    }

    if (examinationChildren.length > 0) {
        menuItems.push({
            label: "Examinations",
            icon: Award,
            children: examinationChildren
        });
    }

    // 7. Portal Access
    const accessChildren: SidebarItemType[] = [];
    if (can("activate_student_portal")) {
        accessChildren.push({ label: "Student Portal", href: "/dashboard/portal-access/students" });
    }
    if (can("activate_staff_portal")) {
        accessChildren.push({ label: "Staff Portal", href: "/dashboard/portal-access/staff" });
    }

    if (accessChildren.length > 0) {
        menuItems.push({
            label: "Portal Access",
            icon: Lock,
            children: accessChildren
        });
    }

    // 7.5 Parent Portal - gated on view_own_children per spec; sub-items are
    // further narrowed by their own permission in case a role somehow has
    // view_own_children without one of the child-scoped permissions.
    if (can("view_own_children")) {
        const parentPortalChildren: SidebarItemType[] = [
            { label: "Dashboard", href: "/dashboard/parent-portal" },
            { label: "My Children", href: "/dashboard/parent-portal/children" },
        ];
        if (can("view_child_attendance")) {
            parentPortalChildren.push({ label: "Attendance", href: "/dashboard/parent-portal/attendance" });
        }
        if (can("view_child_timetable")) {
            parentPortalChildren.push({ label: "Timetable", href: "/dashboard/parent-portal/timetable" });
        }
        if (can("view_child_results")) {
            parentPortalChildren.push({ label: "Results", href: "/dashboard/parent-portal/results" });
        }
        if (can("view_child_fees") || can("pay_child_fees")) {
            parentPortalChildren.push({ label: "Fees", href: "/dashboard/parent-portal/fees" });
        }

        menuItems.push({
            label: "Parent Portal",
            icon: Baby,
            children: parentPortalChildren
        });
    }

    // 7.6 Fees
    const feesChildren: SidebarItemType[] = [];
    if (can("view_fees")) {
        feesChildren.push({ label: "Student Fees / Collect Payment", href: "/dashboard/fees/collect" });
    }
    if (can("manage_fee_structures") || can("view_fees")) {
        feesChildren.push({ label: "Fee Structures", href: "/dashboard/fees/structures" });
    }
    if (can("view_financial_reports")) {
        feesChildren.push({ label: "Outstanding Report", href: "/dashboard/fees/reports" });
    }
    if (can("view_own_fees") || can("pay_own_fees")) {
        feesChildren.push({ label: "My Fees", href: "/dashboard/fees/my-fees" });
    }

    if (feesChildren.length > 0) {
        menuItems.push({
            label: "Fees",
            icon: Receipt,
            children: feesChildren
        });
    }

    // 7. Administration
    const adminChildren: SidebarItemType[] = [];

    if (can("view_institution_profile")) {
        adminChildren.push({ label: "Institution Profile", href: "/dashboard/institution/settings" });
    }

    if (can("view_role")) {
        adminChildren.push({ label: "Roles & Permissions", href: "/dashboard/institution/roles" });
    }

    if (can("view_audit_log")) {
        adminChildren.push({ label: "Audit Logs", href: "/dashboard/audit-logs" });
    }

    if (can("manage_notification_settings") || can("view_notification_log")) {
        adminChildren.push({ label: "Automatic Alerts", href: "/dashboard/notifications/settings" });
    }

    if (adminChildren.length > 0) {
        menuItems.push({
            label: "Administration",
            icon: Settings,
            children: adminChildren
        });
    }

    // 10. Certificates & ID cards - each entry gated on its own permission.
    const certificateChildren: SidebarItemType[] = [];
    if (can("view_certificates")) {
        certificateChildren.push({ label: "Certificates", href: "/dashboard/certificates" });
    }
    if (can("generate_id_cards")) {
        certificateChildren.push({ label: "ID Cards", href: "/dashboard/id-cards" });
    }
    if (certificateChildren.length > 0) {
        menuItems.push({
            label: "Certificates",
            icon: Award,
            children: certificateChildren
        });
    }

    // 11. Inventory - the same five sections, in the same order and with the same permission
    // rules, as the tabs at the top of the inventory pages (InventoryNav).
    const inventoryChildren: SidebarItemType[] = [];
    if (can("view_inventory")) {
        inventoryChildren.push({ label: "Stock", href: "/dashboard/inventory" });
        inventoryChildren.push({ label: "Movements", href: "/dashboard/inventory/movements" });
        inventoryChildren.push({ label: "Purchases", href: "/dashboard/inventory/purchases" });
    }
    if (can("view_assets")) {
        inventoryChildren.push({ label: "Assets", href: "/dashboard/inventory/assets" });
    }
    if (can("view_inventory")) {
        inventoryChildren.push({ label: "Setup", href: "/dashboard/inventory/setup" });
    }
    if (inventoryChildren.length > 0) {
        menuItems.push({
            label: "Inventory",
            icon: Boxes,
            children: inventoryChildren
        });
    }

    // 12. Payroll - managers see runs, salaries and setup; staff see only their own payslips.
    const payrollChildren: SidebarItemType[] = [];
    if (can("view_payroll")) {
        payrollChildren.push({ label: "Payroll runs", href: "/dashboard/payroll" });
        payrollChildren.push({ label: "Salaries", href: "/dashboard/payroll/salaries" });
        payrollChildren.push({ label: "Setup", href: "/dashboard/payroll/setup" });
    }
    if (user?.active_role === "staff" || user?.active_role === "instructor" || user?.active_role === "owner") {
        payrollChildren.push({ label: "My payslips", href: "/dashboard/payroll/my-payslips" });
    }
    if (payrollChildren.length > 0) {
        menuItems.push({
            label: "Payroll",
            icon: Wallet,
            children: payrollChildren
        });
    }

    // 13. Transport - everything sits behind view_transport; each tab hides what the person cannot do.
    if (can("view_transport")) {
        menuItems.push({
            label: "Transport",
            icon: Bus,
            children: [
                { label: "Routes", href: "/dashboard/transport" },
                { label: "Vehicles & drivers", href: "/dashboard/transport/fleet" },
                { label: "Students", href: "/dashboard/transport/students" },
                { label: "Billing", href: "/dashboard/transport/billing" },
            ],
        });
    }

    // 14. Library - everything sits behind view_library; each tab hides what the person cannot do.
    if (can("view_library")) {
        menuItems.push({
            label: "Library",
            icon: Library,
            children: [
                { label: "Books", href: "/dashboard/library" },
                { label: "Loans", href: "/dashboard/library/loans" },
                { label: "Fines", href: "/dashboard/library/fines" },
                { label: "Setup", href: "/dashboard/library/setup" },
            ],
        });
    }

    // 9. Announcements - every signed-in user can read what was sent to them
    // (served by the recipient-scoped mine/ endpoints); managing is permission-gated.
    const announcementChildren: SidebarItemType[] = [
        { label: "My Announcements", href: "/dashboard/announcements" }
    ];
    if (can("view_announcements")) {
        announcementChildren.push({ label: "Manage Announcements", href: "/dashboard/announcements/manage" });
    }
    menuItems.push({
        label: "Announcements",
        icon: Megaphone,
        children: announcementChildren
    });

    return menuItems;
};
