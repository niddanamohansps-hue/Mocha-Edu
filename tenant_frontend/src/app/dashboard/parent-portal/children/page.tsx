"use client";

import Link from "next/link";
import {
    Users,
    GraduationCap,
    CalendarCheck,
    CreditCard,
    Clock,
    Video,
    Shield,
    ChevronRight,
    ArrowUpRight,
} from "lucide-react";
import { useLinkedChildren } from "@/hooks/useParentPortal";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

const RELATION_LABELS: Record<string, string> = {
    father: "Father",
    mother: "Mother",
    guardian: "Guardian",
    brother: "Brother",
    sister: "Sister",
    other: "Other",
};

const AVATAR_PALETTES = [
    { bg: "bg-sky-100 dark:bg-sky-950/70", text: "text-sky-700 dark:text-sky-300", border: "border-sky-300/60 dark:border-sky-800" },
    { bg: "bg-emerald-100 dark:bg-emerald-950/70", text: "text-emerald-700 dark:text-emerald-300", border: "border-emerald-300/60 dark:border-emerald-800" },
    { bg: "bg-indigo-100 dark:bg-indigo-950/70", text: "text-indigo-700 dark:text-indigo-300", border: "border-indigo-300/60 dark:border-indigo-800" },
    { bg: "bg-purple-100 dark:bg-purple-950/70", text: "text-purple-700 dark:text-purple-300", border: "border-purple-300/60 dark:border-purple-800" },
    { bg: "bg-amber-100 dark:bg-amber-950/70", text: "text-amber-700 dark:text-amber-300", border: "border-amber-300/60 dark:border-amber-800" },
];

function getAvatarStyle(name: string) {
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    const index = Math.abs(hash) % AVATAR_PALETTES.length;
    return AVATAR_PALETTES[index];
}

export default function ParentPortalChildrenPage() {
    const { can, isOwner } = usePermissions();
    const canView = isOwner || can("view_own_children");

    const { data: children, isLoading, isError, refetch } = useLinkedChildren();

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Users className="w-6 h-6 text-sky-600 dark:text-sky-400" />
                        <span>My Enrolled Children</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Overview of all student profiles linked to this parent account.
                    </p>
                </div>

                <Badge className="bg-sky-50 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300 border border-sky-200/80 text-xs py-1 self-start sm:self-auto">
                    {children?.length || 0} Child Profile{children?.length === 1 ? "" : "s"} Linked
                </Badge>
            </div>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState onRetry={refetch} />
            ) : !children || children.length === 0 ? (
                <EmptyState
                    title="No children linked to your parent account."
                    description="Please contact the school administrative desk to link your registered student profiles."
                    className="py-16"
                />
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                    {children.map((child) => {
                        const avatar = getAvatarStyle(child.full_name);
                        const relation = RELATION_LABELS[child.relation_type] || child.relation_type;

                        return (
                            <div
                                key={child.student_id}
                                className="p-5 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 shadow-2xs hover:shadow-md transition space-y-4 flex flex-col justify-between"
                            >
                                <div className="space-y-3.5">
                                    {/* Card Header: Avatar & Info */}
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="flex items-center gap-3">
                                            <div
                                                className={`w-12 h-12 rounded-xl ${avatar.bg} ${avatar.text} ${avatar.border} border flex items-center justify-center font-bold text-base shrink-0`}
                                            >
                                                {child.full_name.slice(0, 2).toUpperCase()}
                                            </div>
                                            <div>
                                                <h3 className="text-sm font-bold text-slate-900 dark:text-white leading-snug">
                                                    {child.full_name}
                                                </h3>
                                                <div className="text-xs text-slate-500 dark:text-slate-400 font-mono">
                                                    Adm: {child.enrollment_id}
                                                </div>
                                            </div>
                                        </div>

                                        {child.is_primary_contact && (
                                            <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 border-emerald-300/80 text-[10px] py-0">
                                                Primary
                                            </Badge>
                                        )}
                                    </div>

                                    {/* Placement Pills */}
                                    <div className="p-3 bg-slate-50 dark:bg-slate-950/60 rounded-xl border border-slate-100 dark:border-slate-800 space-y-1.5 text-xs">
                                        <div className="flex items-center justify-between">
                                            <span className="text-slate-500">Grade & Section:</span>
                                            <span className="font-semibold text-slate-900 dark:text-white">
                                                {child.level || "—"} {child.section ? `• Section ${child.section}` : ""}
                                            </span>
                                        </div>
                                        <div className="flex items-center justify-between">
                                            <span className="text-slate-500">Parent Relation:</span>
                                            <span className="font-medium text-slate-700 dark:text-slate-300 capitalize">
                                                {relation}
                                            </span>
                                        </div>
                                    </div>
                                </div>

                                {/* Quick Action Link Pills */}
                                <div className="pt-2 border-t border-slate-100 dark:border-slate-800 grid grid-cols-2 gap-2 text-xs">
                                    <Link href="/dashboard/parent-portal/attendance">
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="w-full h-8 text-[11px] font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-50 text-slate-700 dark:text-slate-300 gap-1.5 cursor-pointer"
                                        >
                                            <CalendarCheck className="w-3.5 h-3.5 text-sky-600" />
                                            <span>Attendance</span>
                                        </Button>
                                    </Link>
                                    <Link href="/dashboard/parent-portal/fees">
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="w-full h-8 text-[11px] font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-50 text-slate-700 dark:text-slate-300 gap-1.5 cursor-pointer"
                                        >
                                            <CreditCard className="w-3.5 h-3.5 text-emerald-600" />
                                            <span>Fee Invoices</span>
                                        </Button>
                                    </Link>
                                    <Link href="/dashboard/parent-portal/results">
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="w-full h-8 text-[11px] font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-50 text-slate-700 dark:text-slate-300 gap-1.5 cursor-pointer"
                                        >
                                            <GraduationCap className="w-3.5 h-3.5 text-purple-600" />
                                            <span>Report Cards</span>
                                        </Button>
                                    </Link>
                                    <Link href="/dashboard/parent-portal/timetable">
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="w-full h-8 text-[11px] font-semibold border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:bg-slate-50 text-slate-700 dark:text-slate-300 gap-1.5 cursor-pointer"
                                        >
                                            <Clock className="w-3.5 h-3.5 text-amber-600" />
                                            <span>Timetable</span>
                                        </Button>
                                    </Link>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
