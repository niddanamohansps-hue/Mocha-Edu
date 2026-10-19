"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { usePermissions } from "@/providers/PermissionProvider";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Calendar, Check, ChevronDown, PlusCircle, Settings2 } from "lucide-react";

export function AcademicYearSelector() {
    const router = useRouter();
    const { selectedYear, academicYears, setSelectedYear, isLoading, hasAccess } = useAcademicYear();
    const { can, isOwner } = usePermissions();

    const canManageAcademics = isOwner || can("change_academic_level") || can("add_academic_level");

    if (!hasAccess) {
        return null;
    }

    if (isLoading) {
        return (
            <div className="h-9 w-36 animate-pulse bg-slate-200/60 dark:bg-slate-800/60 rounded-lg hidden sm:block" />
        );
    }

    if (academicYears.length === 0) {
        return (
            <div className="relative">
                {canManageAcademics ? (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => router.push("/dashboard/academics?tab=years")}
                        className="h-9 gap-1.5 border-dashed border-amber-300 dark:border-amber-700/60 text-amber-700 dark:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-950/30 text-xs font-medium"
                    >
                        <PlusCircle className="h-3.5 w-3.5" />
                        <span>Add Academic Year</span>
                    </Button>
                ) : (
                    <div className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-slate-400 bg-slate-100 dark:bg-slate-800 rounded-lg">
                        <Calendar className="h-3.5 w-3.5" />
                        <span>No Academic Year</span>
                    </div>
                )}
            </div>
        );
    }

    const formatDateRange = (startDateStr: string, endDateStr: string) => {
        try {
            const start = new Date(startDateStr);
            const end = new Date(endDateStr);
            const startFormatted = start.toLocaleDateString(undefined, { month: "short", year: "numeric" });
            const endFormatted = end.toLocaleDateString(undefined, { month: "short", year: "numeric" });
            return `${startFormatted} – ${endFormatted}`;
        } catch {
            return `${startDateStr} to ${endDateStr}`;
        }
    };

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <button
                    type="button"
                    className="flex items-center gap-2 px-2.5 py-1.5 h-9 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700 rounded-lg shadow-xs hover:bg-slate-50 dark:hover:bg-slate-800/60 transition-all text-xs font-medium text-slate-700 dark:text-slate-200 focus:outline-hidden focus:ring-2 focus:ring-sky-500/20"
                    aria-label="Select Academic Year"
                >
                    <Calendar className="h-4 w-4 text-sky-600 dark:text-sky-400 shrink-0" />
                    <span className="font-semibold">{selectedYear?.name || "Select Year"}</span>
                    {selectedYear?.is_current ? (
                        <span className="hidden sm:inline-flex items-center px-1.5 py-0.5 text-[10px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-500/20 rounded">
                            Current
                        </span>
                    ) : (
                        <span className="hidden sm:inline-flex items-center px-1.5 py-0.5 text-[10px] font-semibold bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 border border-slate-200 dark:border-slate-700 rounded">
                            Past
                        </span>
                    )}
                    <ChevronDown className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                </button>
            </DropdownMenuTrigger>

            <DropdownMenuContent align="end" className="w-64 p-1.5">
                <DropdownMenuLabel className="px-2 py-1.5">
                    <p className="text-xs font-semibold text-slate-900 dark:text-white">Academic Year</p>
                    <p className="text-[11px] text-slate-500 font-normal">Filters records across modules</p>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />

                <div className="max-h-60 overflow-y-auto space-y-0.5">
                    {academicYears.map((year) => {
                        const isSelected = selectedYear?.id === year.id;
                        return (
                            <DropdownMenuItem
                                key={year.id}
                                onClick={() => setSelectedYear(year)}
                                className={`flex items-center justify-between px-2 py-2 rounded-md cursor-pointer transition-colors ${
                                    isSelected
                                        ? "bg-sky-50 dark:bg-sky-950/50 text-sky-900 dark:text-sky-200 font-medium"
                                        : "hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300"
                                }`}
                            >
                                <div className="flex items-center gap-2 min-w-0">
                                    <div className="w-4 flex items-center justify-center shrink-0">
                                        {isSelected && <Check className="h-4 w-4 text-sky-600 dark:text-sky-400" />}
                                    </div>
                                    <div className="truncate">
                                        <div className="flex items-center gap-1.5">
                                            <span className="text-xs font-semibold">{year.name}</span>
                                            {year.is_current ? (
                                                <Badge
                                                    variant="outline"
                                                    className="border-emerald-500/30 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 text-[9px] px-1 py-0 leading-tight"
                                                >
                                                    Current
                                                </Badge>
                                            ) : (
                                                <Badge
                                                    variant="outline"
                                                    className="border-slate-200 text-slate-400 dark:border-slate-800 dark:text-slate-500 text-[9px] px-1 py-0 leading-tight"
                                                >
                                                    Past
                                                </Badge>
                                            )}
                                        </div>
                                        <p className="text-[10px] text-slate-400 font-normal">
                                            {formatDateRange(year.start_date, year.end_date)}
                                        </p>
                                    </div>
                                </div>
                            </DropdownMenuItem>
                        );
                    })}
                </div>

                {canManageAcademics && (
                    <>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                            onClick={() => router.push("/dashboard/academics?tab=years")}
                            className="flex items-center gap-2 px-2 py-1.5 text-xs text-sky-600 dark:text-sky-400 hover:text-sky-700 dark:hover:text-sky-300 font-medium cursor-pointer"
                        >
                            <Settings2 className="h-3.5 w-3.5" />
                            <span>Manage Academic Years</span>
                        </DropdownMenuItem>
                    </>
                )}
            </DropdownMenuContent>
        </DropdownMenu>
    );
}

