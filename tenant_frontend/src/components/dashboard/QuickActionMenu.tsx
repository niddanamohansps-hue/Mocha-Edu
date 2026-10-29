"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { usePermissions } from "@/providers/PermissionProvider";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
    Plus,
    CreditCard,
    CheckSquare,
    UserPlus,
    CalendarCheck2,
    CalendarDays,
    Megaphone,
    Receipt,
    Sparkles,
} from "lucide-react";

export function QuickActionMenu() {
    const router = useRouter();
    const { can, isOwner } = usePermissions();

    const actions = [
        {
            label: "Collect Fee",
            desc: "Record student tuition or bus fee",
            icon: CreditCard,
            color: "text-emerald-500 bg-emerald-50 dark:bg-emerald-950/50",
            href: "/dashboard/fees",
            visible: isOwner || can("add_paymentallocation") || can("view_fee"),
        },
        {
            label: "Mark Attendance",
            desc: "Take daily roll call for any class",
            icon: CheckSquare,
            color: "text-indigo-500 bg-indigo-50 dark:bg-indigo-950/50",
            href: "/dashboard/attendance/mark",
            visible: isOwner || can("add_studentattendance") || can("change_studentattendance"),
        },
        {
            label: "New Student Admission",
            desc: "Register a newly admitted student",
            icon: UserPlus,
            color: "text-sky-500 bg-sky-50 dark:bg-sky-950/50",
            href: "/dashboard/students",
            visible: isOwner || can("add_student"),
        },
        {
            label: "Schedule PTM",
            desc: "Create parent-teacher meeting slots",
            icon: CalendarCheck2,
            color: "text-teal-500 bg-teal-50 dark:bg-teal-950/50",
            href: "/dashboard/ptm",
            visible: isOwner || can("view_dashboard"),
        },
        {
            label: "Staff Leave Applications",
            desc: "Review or apply for staff leave",
            icon: CalendarDays,
            color: "text-amber-500 bg-amber-50 dark:bg-amber-950/50",
            href: "/dashboard/staff/leaves",
            visible: true,
        },
        {
            label: "Record Expense Voucher",
            desc: "Log operational cash or bank expense",
            icon: Receipt,
            color: "text-rose-500 bg-rose-50 dark:bg-rose-950/50",
            href: "/dashboard/expenses",
            visible: isOwner || can("add_expense") || can("view_expense"),
        },
        {
            label: "Broadcast Notice",
            desc: "Send school announcement to parents & staff",
            icon: Megaphone,
            color: "text-purple-500 bg-purple-50 dark:bg-purple-950/50",
            href: "/dashboard/communication/announcements",
            visible: isOwner || can("add_announcement"),
        },
    ].filter((a) => a.visible);

    if (actions.length === 0) return null;

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <button
                    type="button"
                    className="flex items-center gap-1.5 px-3 py-1.5 h-9 bg-gradient-to-r from-sky-600 to-teal-600 hover:from-sky-500 hover:to-teal-500 text-white rounded-lg shadow-sm hover:shadow-md transition-all text-xs font-semibold cursor-pointer active:scale-95"
                    aria-label="Quick Actions"
                >
                    <Plus className="h-4 w-4 stroke-[2.5]" />
                    <span className="hidden sm:inline">Quick Action</span>
                </button>
            </DropdownMenuTrigger>

            <DropdownMenuContent align="end" className="w-72 p-2">
                <DropdownMenuLabel className="px-2 py-1.5 flex items-center justify-between text-xs font-semibold text-slate-800 dark:text-slate-100">
                    <span>Quick Actions</span>
                    <Sparkles className="h-3.5 w-3.5 text-sky-500" />
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <div className="space-y-1 py-1">
                    {actions.map((act) => (
                        <DropdownMenuItem
                            key={act.href}
                            onClick={() => router.push(act.href)}
                            className="flex items-center gap-3 p-2 rounded-lg cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800 focus:bg-slate-100 dark:focus:bg-slate-800"
                        >
                            <div className={`p-2 rounded-lg shrink-0 ${act.color}`}>
                                <act.icon className="h-4 w-4" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="text-xs font-semibold text-slate-800 dark:text-slate-200 truncate">
                                    {act.label}
                                </p>
                                <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                                    {act.desc}
                                </p>
                            </div>
                        </DropdownMenuItem>
                    ))}
                </div>
            </DropdownMenuContent>
        </DropdownMenu>
    );
}

