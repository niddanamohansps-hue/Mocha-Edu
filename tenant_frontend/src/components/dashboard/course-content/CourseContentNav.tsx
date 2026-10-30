"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { usePermissions } from "@/providers/PermissionProvider";
import { FileText, CheckCircle2, BookOpen, FolderOpen } from "lucide-react";

export function CourseContentNav() {
    const pathname = usePathname();
    const { can, isOwner, activeRole } = usePermissions();
    const isStudent = activeRole === "student";

    const canCreate = isOwner || can("create_assignment") || !isStudent;

    const tabs = [
        { href: "/dashboard/course-content/assignments", label: "Assignments & Homework", icon: FileText, show: true },
        { href: "/dashboard/course-content/grading", label: "Submissions & Grading", icon: CheckCircle2, show: canCreate },
        { href: "/dashboard/course-content/materials", label: "Study Materials & Notes", icon: BookOpen, show: true },
        { href: "/dashboard/course-content/manage", label: "Upload & Course Catalog", icon: FolderOpen, show: canCreate },
    ];

    return (
        <nav className="flex items-center gap-1 border-b border-slate-200/80 dark:border-slate-800 pb-px overflow-x-auto scrollbar-none" aria-label="Course content sections">
            {tabs.filter(t => t.show).map((tab) => {
                const active = pathname === tab.href;
                const Icon = tab.icon;
                return (
                    <Link
                        key={tab.href}
                        href={tab.href}
                        aria-current={active ? "page" : undefined}
                        className={`flex items-center gap-2 px-3.5 py-2.5 text-xs font-semibold border-b-2 transition-all cursor-pointer whitespace-nowrap ${
                            active
                                ? "border-sky-600 text-sky-600 dark:text-sky-400 bg-sky-50/50 dark:bg-sky-950/20 rounded-t-lg"
                                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 hover:border-slate-300"
                        }`}
                    >
                        <Icon className={`w-3.5 h-3.5 ${active ? "text-sky-600 dark:text-sky-400" : "text-slate-400"}`} />
                        <span>{tab.label}</span>
                    </Link>
                );
            })}
        </nav>
    );
}

