"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
    Search,
    CalendarCheck,
    Receipt,
    ShieldCheck,
    Wallet,
    UserPlus,
    BookOpen,
    GraduationCap,
    Briefcase,
    Clock,
    Award,
    Baby,
    ArrowRight,
    User,
    CornerDownLeft,
    Sparkles,
    X,
} from "lucide-react";
import axiosInstance from "@/lib/axios";

interface CommandItem {
    id: string;
    title: string;
    category: "actions" | "navigation" | "students" | "staff";
    href: string;
    description?: string;
    icon: React.ElementType;
}

const STATIC_COMMANDS: CommandItem[] = [
    // Quick Actions
    {
        id: "action-fees",
        title: "Collect Student Fees",
        category: "actions",
        href: "/dashboard/fees/collect",
        description: "Search student & accept cash / online payment",
        icon: Receipt,
    },
    {
        id: "action-attendance",
        title: "Mark Daily Attendance",
        category: "actions",
        href: "/dashboard/attendance",
        description: "Take class attendance with 1-click present toggle",
        icon: CalendarCheck,
    },
    {
        id: "action-visitor",
        title: "Issue Visitor Pass / Gate Pass",
        category: "actions",
        href: "/dashboard/front-office",
        description: "Log campus visitor or early departure student gate pass",
        icon: ShieldCheck,
    },
    {
        id: "action-ptm",
        title: "Schedule PTM Meeting Event",
        category: "actions",
        href: "/dashboard/ptm",
        description: "Create parent-teacher meeting slots & view rosters",
        icon: CalendarCheck,
    },
    {
        id: "action-expense",
        title: "Record Expense Voucher",
        category: "actions",
        href: "/dashboard/expenses",
        description: "Log daily petty cash or payment voucher",
        icon: Wallet,
    },
    {
        id: "action-admission",
        title: "New Student Admission",
        category: "actions",
        href: "/dashboard/students/admissions",
        description: "Admit new student and generate enrollment ID",
        icon: UserPlus,
    },

    // Key Navigation
    {
        id: "nav-students",
        title: "Student Directory",
        category: "navigation",
        href: "/dashboard/students",
        description: "View all enrolled students, PEN & APAAR IDs",
        icon: GraduationCap,
    },
    {
        id: "nav-staff",
        title: "Staff & Faculty Directory",
        category: "navigation",
        href: "/dashboard/staff",
        description: "Instructors, designations, and leave tracking",
        icon: Briefcase,
    },
    {
        id: "nav-exams",
        title: "Examinations & CBSE Report Cards",
        category: "navigation",
        href: "/dashboard/examinations",
        description: "Marks entry, grading, and 20-Point Transfer Certificate",
        icon: Award,
    },
    {
        id: "nav-cashbook",
        title: "Expenses & School Cashbook",
        category: "navigation",
        href: "/dashboard/expenses",
        description: "Daily Day Book reconciliation & cash in hand",
        icon: Wallet,
    },
    {
        id: "nav-timetable",
        title: "School Timetable",
        category: "navigation",
        href: "/dashboard/timetable",
        description: "Class schedule periods and teacher allocations",
        icon: Clock,
    },
    {
        id: "nav-parent-portal",
        title: "Parent Portal Dashboard",
        category: "navigation",
        href: "/dashboard/parent-portal",
        description: "Child overview, attendance, report cards, fees",
        icon: Baby,
    },
];

interface CommandPaletteProps {
    isOpen: boolean;
    onClose: () => void;
}

export function CommandPalette({ isOpen, onClose }: CommandPaletteProps) {
    const router = useRouter();
    const [query, setQuery] = useState("");
    const [selectedIndex, setSelectedIndex] = useState(0);

    const [liveStudents, setLiveStudents] = useState<CommandItem[]>([]);
    const [liveStaff, setLiveStaff] = useState<CommandItem[]>([]);
    const [isSearching, setIsSearching] = useState(false);

    const inputRef = useRef<HTMLInputElement>(null);

    // Focus input on open
    useEffect(() => {
        if (isOpen) {
            setTimeout(() => inputRef.current?.focus(), 50);
            setQuery("");
            setSelectedIndex(0);
        }
    }, [isOpen]);

    // Live backend entity search (debounced)
    useEffect(() => {
        if (!query.trim() || query.length < 2) {
            setLiveStudents([]);
            setLiveStaff([]);
            setIsSearching(false);
            return;
        }

        setIsSearching(true);
        const timer = setTimeout(async () => {
            try {
                const [stuRes, staffRes] = await Promise.allSettled([
                    axiosInstance.get(`/students/?search=${encodeURIComponent(query)}&page_size=4`),
                    axiosInstance.get(`/staff/members/?search=${encodeURIComponent(query)}&page_size=4`),
                ]);

                if (stuRes.status === "fulfilled") {
                    const list = stuRes.value.data?.results || stuRes.value.data || [];
                    setLiveStudents(
                        list.map((s: any) => ({
                            id: `stu-${s.id}`,
                            title: `${s.profile?.first_name || ""} ${s.profile?.last_name || ""}`.trim() || s.enrollment_id,
                            category: "students" as const,
                            href: `/dashboard/students`,
                            description: `Roll: ${s.enrollment_id} • Status: ${s.status}`,
                            icon: User,
                        }))
                    );
                }

                if (staffRes.status === "fulfilled") {
                    const list = staffRes.value.data?.results || staffRes.value.data || [];
                    setLiveStaff(
                        list.map((m: any) => ({
                            id: `staff-${m.id}`,
                            title: `${m.profile_details?.first_name || ""} ${m.profile_details?.last_name || ""}`.trim() || m.employee_id,
                            category: "staff" as const,
                            href: `/dashboard/staff`,
                            description: `${m.designation} • ${m.department || "Faculty"}`,
                            icon: Briefcase,
                        }))
                    );
                }
            } catch (err) {
                // Ignore search errors gracefully
            } finally {
                setIsSearching(false);
            }
        }, 200);

        return () => clearTimeout(timer);
    }, [query]);

    // Filter static commands
    const filteredStatic = STATIC_COMMANDS.filter((cmd) => {
        if (!query.trim()) return true;
        const q = query.toLowerCase();
        return (
            cmd.title.toLowerCase().includes(q) ||
            cmd.description?.toLowerCase().includes(q)
        );
    });

    // Combined items list for arrow navigation
    const allItems: CommandItem[] = [
        ...filteredStatic.filter((c) => c.category === "actions"),
        ...liveStudents,
        ...liveStaff,
        ...filteredStatic.filter((c) => c.category === "navigation"),
    ];

    const handleSelect = (item: CommandItem) => {
        onClose();
        router.push(item.href);
    };

    // Keyboard navigation (ArrowDown, ArrowUp, Enter, Escape)
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (!isOpen) return;

            if (e.key === "Escape") {
                e.preventDefault();
                onClose();
            } else if (e.key === "ArrowDown") {
                e.preventDefault();
                setSelectedIndex((prev) => (prev + 1) % Math.max(1, allItems.length));
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setSelectedIndex((prev) => (prev - 1 + allItems.length) % Math.max(1, allItems.length));
            } else if (e.key === "Enter" && allItems[selectedIndex]) {
                e.preventDefault();
                handleSelect(allItems[selectedIndex]);
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [isOpen, allItems, selectedIndex]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 overflow-y-auto p-4 sm:p-6 md:p-20">
            {/* Backdrop */}
            <div
                onClick={onClose}
                className="fixed inset-0 bg-slate-950/40 backdrop-blur-xs transition-opacity"
            />

            {/* Modal Dialog */}
            <div className="relative mx-auto max-w-2xl transform overflow-hidden rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xl transition-all">
                {/* Search Bar Input */}
                <div className="relative border-b border-slate-100 dark:border-slate-800 px-4 py-3.5 flex items-center gap-3">
                    <Search className="h-5 w-5 text-indigo-600 dark:text-indigo-400 shrink-0" />
                    <input
                        ref={inputRef}
                        type="text"
                        placeholder="Search students, staff, actions, or jump to page... (or use ↑↓ and Enter)"
                        value={query}
                        onChange={(e) => {
                            setQuery(e.target.value);
                            setSelectedIndex(0);
                        }}
                        className="w-full bg-transparent text-sm text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none"
                    />
                    <kbd className="hidden sm:inline-flex items-center gap-1 rounded bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-[10px] font-mono text-slate-500 border border-slate-200 dark:border-slate-700">
                        ESC
                    </kbd>
                </div>

                {/* Results Container */}
                <div className="max-h-96 overflow-y-auto p-3 space-y-3">
                    {allItems.length === 0 ? (
                        <div className="py-12 text-center text-xs text-slate-500">
                            {isSearching ? "Searching school records..." : "No matching commands or records found."}
                        </div>
                    ) : (
                        <>
                            {/* Quick Actions */}
                            {allItems.some((c) => c.category === "actions") && (
                                <div className="space-y-1">
                                    <p className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                                        ⚡ Quick Actions
                                    </p>
                                    {allItems
                                        .filter((c) => c.category === "actions")
                                        .map((item) => {
                                            const itemIndex = allItems.indexOf(item);
                                            const isSelected = itemIndex === selectedIndex;
                                            const Icon = item.icon;

                                            return (
                                                <div
                                                    key={item.id}
                                                    onClick={() => handleSelect(item)}
                                                    onMouseEnter={() => setSelectedIndex(itemIndex)}
                                                    className={`cursor-pointer rounded-xl px-3 py-2 flex items-center justify-between text-xs transition ${
                                                        isSelected
                                                            ? "bg-indigo-50 dark:bg-indigo-950/50 text-indigo-900 dark:text-indigo-200"
                                                            : "text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/40"
                                                    }`}
                                                >
                                                    <div className="flex items-center gap-3">
                                                        <div className={`p-1.5 rounded-lg ${isSelected ? "bg-indigo-600 text-white" : "bg-slate-100 dark:bg-slate-800 text-slate-500"}`}>
                                                            <Icon className="h-4 w-4" />
                                                        </div>
                                                        <div>
                                                            <p className="font-semibold">{item.title}</p>
                                                            {item.description && (
                                                                <p className="text-[11px] text-slate-400">{item.description}</p>
                                                            )}
                                                        </div>
                                                    </div>
                                                    {isSelected && (
                                                        <div className="flex items-center gap-1 text-[11px] text-indigo-600 dark:text-indigo-400 font-medium">
                                                            <span>Press</span>
                                                            <CornerDownLeft className="h-3 w-3" />
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })}
                                </div>
                            )}

                            {/* Students */}
                            {liveStudents.length > 0 && (
                                <div className="space-y-1 pt-1">
                                    <p className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                                        🎓 Students ({liveStudents.length})
                                    </p>
                                    {liveStudents.map((item) => {
                                        const itemIndex = allItems.indexOf(item);
                                        const isSelected = itemIndex === selectedIndex;

                                        return (
                                            <div
                                                key={item.id}
                                                onClick={() => handleSelect(item)}
                                                onMouseEnter={() => setSelectedIndex(itemIndex)}
                                                className={`cursor-pointer rounded-xl px-3 py-2 flex items-center justify-between text-xs transition ${
                                                    isSelected
                                                        ? "bg-indigo-50 dark:bg-indigo-950/50 text-indigo-900 dark:text-indigo-200"
                                                        : "text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/40"
                                                }`}
                                            >
                                                <div className="flex items-center gap-3">
                                                    <div className={`p-1.5 rounded-lg ${isSelected ? "bg-indigo-600 text-white" : "bg-slate-100 dark:bg-slate-800 text-slate-500"}`}>
                                                        <User className="h-4 w-4" />
                                                    </div>
                                                    <div>
                                                        <p className="font-semibold">{item.title}</p>
                                                        <p className="text-[11px] text-slate-400">{item.description}</p>
                                                    </div>
                                                </div>
                                                <span className="text-[11px] text-slate-400">Student Directory →</span>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}

                            {/* Staff */}
                            {liveStaff.length > 0 && (
                                <div className="space-y-1 pt-1">
                                    <p className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                                        👨‍🏫 Staff & Faculty ({liveStaff.length})
                                    </p>
                                    {liveStaff.map((item) => {
                                        const itemIndex = allItems.indexOf(item);
                                        const isSelected = itemIndex === selectedIndex;

                                        return (
                                            <div
                                                key={item.id}
                                                onClick={() => handleSelect(item)}
                                                onMouseEnter={() => setSelectedIndex(itemIndex)}
                                                className={`cursor-pointer rounded-xl px-3 py-2 flex items-center justify-between text-xs transition ${
                                                    isSelected
                                                        ? "bg-indigo-50 dark:bg-indigo-950/50 text-indigo-900 dark:text-indigo-200"
                                                        : "text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/40"
                                                }`}
                                            >
                                                <div className="flex items-center gap-3">
                                                    <div className={`p-1.5 rounded-lg ${isSelected ? "bg-indigo-600 text-white" : "bg-slate-100 dark:bg-slate-800 text-slate-500"}`}>
                                                        <Briefcase className="h-4 w-4" />
                                                    </div>
                                                    <div>
                                                        <p className="font-semibold">{item.title}</p>
                                                        <p className="text-[11px] text-slate-400">{item.description}</p>
                                                    </div>
                                                </div>
                                                <span className="text-[11px] text-slate-400">Staff Profile →</span>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}

                            {/* Navigation */}
                            {allItems.some((c) => c.category === "navigation") && (
                                <div className="space-y-1 pt-1">
                                    <p className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                                        🧭 Modules & Pages
                                    </p>
                                    {allItems
                                        .filter((c) => c.category === "navigation")
                                        .map((item) => {
                                            const itemIndex = allItems.indexOf(item);
                                            const isSelected = itemIndex === selectedIndex;
                                            const Icon = item.icon;

                                            return (
                                                <div
                                                    key={item.id}
                                                    onClick={() => handleSelect(item)}
                                                    onMouseEnter={() => setSelectedIndex(itemIndex)}
                                                    className={`cursor-pointer rounded-xl px-3 py-2 flex items-center justify-between text-xs transition ${
                                                        isSelected
                                                            ? "bg-indigo-50 dark:bg-indigo-950/50 text-indigo-900 dark:text-indigo-200"
                                                            : "text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800/40"
                                                    }`}
                                                >
                                                    <div className="flex items-center gap-3">
                                                        <div className={`p-1.5 rounded-lg ${isSelected ? "bg-indigo-600 text-white" : "bg-slate-100 dark:bg-slate-800 text-slate-500"}`}>
                                                            <Icon className="h-4 w-4" />
                                                        </div>
                                                        <div>
                                                            <p className="font-semibold">{item.title}</p>
                                                            {item.description && (
                                                                <p className="text-[11px] text-slate-400">{item.description}</p>
                                                            )}
                                                        </div>
                                                    </div>
                                                    <ArrowRight className="h-3.5 w-3.5 text-slate-400" />
                                                </div>
                                            );
                                        })}
                                </div>
                            )}
                        </>
                    )}
                </div>

                {/* Footer Tips */}
                <div className="bg-slate-50/80 dark:bg-slate-800/40 px-4 py-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
                    <div className="flex items-center gap-3">
                        <span><kbd className="font-mono bg-white dark:bg-slate-800 px-1 py-0.5 rounded border text-[10px]">↑↓</kbd> Navigate</span>
                        <span><kbd className="font-mono bg-white dark:bg-slate-800 px-1 py-0.5 rounded border text-[10px]">Enter</kbd> Select</span>
                    </div>
                    <span>EduSekai Fast Command</span>
                </div>
            </div>
        </div>
    );
}
