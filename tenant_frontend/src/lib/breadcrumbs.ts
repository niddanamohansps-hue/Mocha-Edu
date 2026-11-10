export interface BreadcrumbItem {
    label: string;
    href: string;
    isCurrent: boolean;
}

const SEGMENT_LABEL_MAP: Record<string, string> = {
    dashboard: "Dashboard",
    admissions: "Admissions",
    students: "Students",
    attendance: "Attendance",
    timetable: "Timetable",
    examinations: "Examinations",
    "question-bank": "Question Bank",
    fees: "Fees",
    payroll: "Payroll",
    inventory: "Inventory",
    library: "Library",
    staff: "Staff",
    faculty: "Faculty",
    academics: "Academic Structure",
    "course-content": "Course Content",
    "parent-portal": "Parent Portal",
    "front-office": "Front Office",
    certificates: "Certificates",
    expenses: "Expenses",
    announcements: "Announcements",
    "audit-logs": "Audit Logs",
    billing: "Billing",
    "system-health": "System Health",
    "follow-ups": "Follow-ups",
    "admit-cards": "Admit Cards",
    "term-weightage": "Term Weightage",
    "co-scholastic": "Co-scholastic",
    "mark-sheets": "Mark Sheets",
    "marks-progress": "Marks Progress",
    marks: "Marks Entry",
    moderation: "Moderation",
    duties: "Exam Duties",
    allocation: "Room Allocation",
    "room-reports": "Room Reports",
    malpractice: "Malpractice",
    rechecks: "Rechecks",
    supplementary: "Supplementary",
    "rank-list": "Rank List",
    analytics: "Analytics",
    collect: "Fee Collection",
    dues: "Fee Dues",
    structures: "Fee Structures",
    gateways: "Payment Gateways",
    leaves: "Leaves",
    recruitment: "Recruitment",
    salaries: "Salaries",
    payslips: "Payslips",
    promotion: "Promotion",
    "my-schedule": "My Schedule",
    substitutions: "Substitutions",
    import: "Import Data",
    settings: "Settings",
    notifications: "Notifications",
    "id-cards": "ID Cards",
    ptm: "PTM",
    "live-classes": "Live Classes",
    "portal-access": "Portal Access",
};

export function parseBreadcrumbs(pathname: string): {
    items: BreadcrumbItem[];
    parentLabel: string | null;
    currentLabel: string;
} {
    if (!pathname || pathname === "/dashboard") {
        return {
            items: [{ label: "Dashboard", href: "/dashboard", isCurrent: true }],
            parentLabel: null,
            currentLabel: "Dashboard",
        };
    }

    const rawSegments = pathname
        .split("/")
        .filter((part) => part && !/^[0-9a-f]{8}-[0-9a-f]{4}-/i.test(part) && !/^\d+$/.test(part));

    const items: BreadcrumbItem[] = [];
    let accumulatedPath = "";

    for (let i = 0; i < rawSegments.length; i++) {
        const seg = rawSegments[i];
        accumulatedPath += `/${seg}`;
        const isCurrent = i === rawSegments.length - 1;
        const mapped = SEGMENT_LABEL_MAP[seg.toLowerCase()];
        const label = mapped || seg.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

        items.push({
            label,
            href: accumulatedPath,
            isCurrent,
        });
    }

    // Determine parent and current for mobile badge
    const currentLabel = items[items.length - 1]?.label || "Dashboard";
    let parentLabel: string | null = null;

    if (items.length > 2) {
        // e.g. /dashboard/admissions/follow-ups -> parent is Admissions (items[1])
        parentLabel = items[1].label;
    } else if (items.length === 2 && items[0].href === "/dashboard") {
        // /dashboard/students -> single level under dashboard
        parentLabel = null;
    }

    return { items, parentLabel, currentLabel };
}
