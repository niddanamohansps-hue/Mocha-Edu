import {
    LayoutDashboard,
    Users,
    GraduationCap,
    BookOpen,
    Settings,
    Briefcase,
    School,
    Lock,
    Bus,
    Baby,
    Receipt,
    CalendarCheck,
    CalendarRange,
    Award,
    Megaphone,
    Boxes,
    Wallet,
    Library,
    ShieldCheck
} from "lucide-react";
import { SidebarItemType } from "@/components/dashboard/Sidebar/SidebarItem";

export const getMenuItems = (
    user: { active_role?: string; [key: string]: unknown } | null | undefined,
    can: (permission: string) => boolean
): SidebarItemType[] => {
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
    if (can("view_family")) {
        studentChildren.push({ label: "Parents & Guardians", href: "/dashboard/students/parents" });
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
    if (can("add_staff") || can("view_recruitment")) {
        staffChildren.push({ label: "Recruitment", href: "/dashboard/hr/recruit" });
    }
    if (can("record_interview_feedback")) {
        staffChildren.push({ label: "My Interviews", href: "/dashboard/hr/interviews" });
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

    // 6.7 Examinations, in the order a school works through an exam: set up, prepare papers, exam day,
    // then marks and results.
    const examinationChildren: SidebarItemType[] = [];
    // Set up
    if (can("view_examinations") || can("manage_examinations")) {
        examinationChildren.push({ label: "Examinations", href: "/dashboard/examinations" });
    }
    if (can("manage_grading")) {
        examinationChildren.push({ label: "Grading", href: "/dashboard/examinations/grading" });
    }
    if (can("manage_examinations") || can("view_examinations")) {
        examinationChildren.push({ label: "Term Weightage", href: "/dashboard/examinations/term-weightage" });
    }
    if (can("manage_examinations") || can("enter_marks")) {
        examinationChildren.push({ label: "Co-scholastic", href: "/dashboard/examinations/co-scholastic" });
    }
    // Prepare papers
    if (can("view_question_bank") || can("create_questions") || can("review_questions") || can("manage_question_bank")) {
        examinationChildren.push({ label: "Question Bank", href: "/dashboard/question-bank" });
    }
    if (can("review_questions")) {
        examinationChildren.push({ label: "Questions to Review", href: "/dashboard/question-bank/review" });
    }
    if (can("prepare_papers") || can("approve_papers")) {
        examinationChildren.push({ label: "Question Papers", href: "/dashboard/question-bank/papers" });
    }
    // Exam day
    if (can("manage_exam_allocation") || can("view_examinations")) {
        examinationChildren.push({ label: "Rooms & Invigilators", href: "/dashboard/examinations/allocation" });
    }
    if (can("manage_examinations") || can("manage_exam_allocation")) {
        examinationChildren.push({ label: "Admit Cards", href: "/dashboard/examinations/admit-cards" });
    }
    if (user?.active_role === "staff" || user?.active_role === "instructor" || can("manage_exam_allocation")) {
        examinationChildren.push({ label: "Exam Duties", href: "/dashboard/examinations/duties" });
    }
    // Marks and results
    if (can("manage_examinations") || can("view_examinations")) {
        examinationChildren.push({ label: "Marks Progress", href: "/dashboard/examinations/marks-progress" });
        examinationChildren.push({ label: "Mark Sheets", href: "/dashboard/examinations/mark-sheets" });
    }
    if (can("enter_marks")) {
        examinationChildren.push({ label: "Marks Entry", href: "/dashboard/examinations/marks" });
    }
    if (can("moderate_exam_marks")) {
        examinationChildren.push({ label: "Moderation", href: "/dashboard/examinations/moderation" });
    }
    if (user?.active_role === "student") {
        examinationChildren.push({ label: "My Exams", href: "/dashboard/examinations/my-exams" });
    }
    if (can("view_results") || user?.active_role === "student") {
        examinationChildren.push({ label: "Results", href: "/dashboard/examinations/results" });
    }
    if (can("view_results")) {
        examinationChildren.push({ label: "Rank List", href: "/dashboard/examinations/rank-list" });
    }
    if (can("view_exam_reports")) {
        examinationChildren.push({ label: "Analytics", href: "/dashboard/examinations/analytics" });
    }
    if (can("manage_marks") || can("view_results") || user?.active_role === "student") {
        examinationChildren.push({ label: "Rechecks", href: "/dashboard/examinations/rechecks" });
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
    if (can("change_family") || can("view_family")) {
        accessChildren.push({ label: "Parent Portal", href: "/dashboard/portal-access/parents" });
    }

    if (accessChildren.length > 0) {
        menuItems.push({
            label: "Portal Access",
            icon: Lock,
            children: accessChildren
        });
    }

    // 7.4 Homework diary: staff set it, students and parents follow it (one page adapts to each).
    if (can("manage_homework") || can("view_homework") || can("view_own_homework") || can("view_child_homework")) {
        menuItems.push({ label: "Homework", icon: BookOpen, href: "/dashboard/homework" });
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
            parentPortalChildren.push({ label: "Exams & Admit Card", href: "/dashboard/parent-portal/exams" });
            parentPortalChildren.push({ label: "Results", href: "/dashboard/parent-portal/results" });
        }
        if (can("view_child_fees") || can("pay_child_fees")) {
            parentPortalChildren.push({ label: "Fees", href: "/dashboard/parent-portal/fees" });
        }
        if (can("view_child_ptm")) {
            parentPortalChildren.push({ label: "PTM Meetings", href: "/dashboard/parent-portal/ptm" });
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
    if (can("manage_payment_gateways")) {
        feesChildren.push({ label: "Payment Gateways", href: "/dashboard/fees/payment-gateways" });
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

    // 7.7 Expenses & School Cashbook
    if (can("view_expenses")) {
        menuItems.push({
            label: "Expenses & Cashbook",
            icon: Wallet,
            href: "/dashboard/expenses"
        });
    }

    // 7.8 Front Office & Visitor Management
    if (can("view_front_office")) {
        menuItems.push({
            label: "Front Office",
            icon: ShieldCheck,
            href: "/dashboard/front-office"
        });
    }

    // 7.9 Parent-Teacher Meetings (PTM)
    if (can("view_ptm") || can("manage_ptm") || can("record_ptm_feedback")) {
        menuItems.push({
            label: "PTM Meetings",
            icon: CalendarCheck,
            href: "/dashboard/ptm"
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
    if (can("view_notification_log")) {
        adminChildren.push({ label: "Alert Log", href: "/dashboard/notifications/alert-log" });
    }
    if (can("add_student") || can("add_staff") || can("manage_fee_structures")) {
        adminChildren.push({ label: "Import data", href: "/dashboard/import" });
    }
    if (can("manage_billing")) {
        adminChildren.push({ label: "Billing", href: "/dashboard/billing" });
    }
    if (can("view_system_health")) {
        adminChildren.push({ label: "System Health", href: "/dashboard/system-health" });
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

    return organiseMenu(menuItems);
};

/**
 * Top-level items in the order a school office works, with the heading each is listed under. Items a user
 * cannot see are simply absent (every item above is already permission-gated), so a heading only appears
 * when something under it does.
 */
const MENU_ORDER: { group: string; labels: string[] }[] = [
    { group: "Overview", labels: ["Dashboard"] },
    { group: "People", labels: ["Student Management", "Staff", "Portal Access", "Parent Portal"] },
    { group: "Academics", labels: ["Academics", "Course Content", "Timetable", "Attendance", "Examinations", "Certificates", "Homework"] },
    { group: "Communication", labels: ["Announcements", "PTM Meetings"] },
    { group: "Finance", labels: ["Fees", "Expenses & Cashbook", "Payroll"] },
    { group: "Operations", labels: ["Front Office", "Inventory", "Transport", "Library"] },
    { group: "Admin", labels: ["Administration"] },
];

/**
 * The order of the links inside each group: the work people do every day first, reports next, and set-up or
 * settings last. Links a role cannot see are simply absent, and anything not listed keeps its place after the
 * listed ones, so a new link never disappears or reshuffles the rest.
 */
const CHILD_ORDER: Record<string, string[]> = {
    "Student Management": ["Student Directory", "Admissions", "Parents & Guardians", "Promotion & Transfer"],
    Staff: ["Staff Directory", "Faculty Directory", "Recruitment", "My Interviews", "Leave Management"],
    Academics: ["Academic Structure", "Academic Calendar", "Homework"],
    "Course Content": ["Study Materials", "Manage Content", "Assignments", "Grade Submissions"],
    Attendance: ["Mark Attendance", "History", "Reports", "Staff Attendance", "Attendance Settings"],
    Timetable: ["Timetable", "My Schedule", "Substitutions"],
    Examinations: [
        "Examinations", "Grading", "Term Weightage", "Co-scholastic",
        "Question Bank", "Questions to Review", "Question Papers",
        "Rooms & Invigilators", "Admit Cards", "Exam Duties",
        "Marks Progress", "Mark Sheets", "Marks Entry", "Moderation", "My Exams", "Results", "Rank List", "Analytics", "Rechecks",
    ],
    Fees: ["Student Fees / Collect Payment", "Outstanding Report", "My Fees", "Fee Structures", "Payment Gateways"],
    Payroll: ["Payroll runs", "Salaries", "My payslips", "Setup"],
    Inventory: ["Stock", "Movements", "Purchases", "Assets", "Setup"],
    Certificates: ["Certificates", "ID Cards"],
    Administration: [
        "Institution Profile", "Roles & Permissions", "Import data",
        "Automatic Alerts", "Alert Log", "Audit Logs", "Billing", "System Health",
    ],
};

function orderChildren(item: SidebarItemType): SidebarItemType {
    const order = CHILD_ORDER[item.label];
    if (!order || !item.children) return item;
    const rank = (label: string) => {
        const index = order.indexOf(label);
        return index === -1 ? order.length : index;
    };
    const children = item.children
        .map((child, index) => ({ child, index }))
        .sort((x, y) => rank(x.child.label) - rank(y.child.label) || x.index - y.index)
        .map(({ child }) => child);
    return { ...item, children };
}

function organiseMenu(items: SidebarItemType[]): SidebarItemType[] {
    let menu = [...items];

    // Faculty has a single link, so it lives under Staff instead of being a group of its own.
    const faculty = menu.find((i) => i.label === "Faculty");
    if (faculty) {
        const staff = menu.find((i) => i.label === "Staff");
        if (staff) {
            staff.children = [...(staff.children ?? []), ...(faculty.children ?? [])];
            menu = menu.filter((i) => i !== faculty);
        } else {
            faculty.label = "Staff";
            faculty.icon = Briefcase;
        }
    }

    // Homework is part of the academic day: a link under Academics when that group exists.
    const homework = menu.find((i) => i.label === "Homework" && i.href);
    const academics = menu.find((i) => i.label === "Academics");
    if (homework && academics) {
        academics.children = [...(academics.children ?? []), { label: "Homework", href: homework.href }];
        menu = menu.filter((i) => i !== homework);
    }

    const rank = new Map<string, { group: string; position: number }>();
    let position = 0;
    for (const { group, labels } of MENU_ORDER) {
        for (const label of labels) rank.set(label, { group, position: position++ });
    }
    const last = { group: "Operations", position: position };
    return menu
        .map((item, index) => ({ item, index, ...(rank.get(item.label) ?? last) }))
        .sort((a, b) => a.position - b.position || a.index - b.index)
        .map(({ item, group }) => ({ ...orderChildren(item), group }));
}
