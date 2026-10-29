"use client";

import React from "react";
import { AdmissionsDashboardStats } from "@/types/Admissions";
import {
    Users,
    FileText,
    FileCheck,
    CheckCircle2,
    GraduationCap,
} from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

interface AdmissionsStatsCardsProps {
    stats?: AdmissionsDashboardStats;
    isLoading?: boolean;
}

export default function AdmissionsStatsCards({
    stats,
    isLoading = false,
}: AdmissionsStatsCardsProps) {
    const cards = [
        {
            title: "Total Enquiries",
            value: stats?.total_enquiries ?? 0,
            subtitle: `${stats?.enquiries_new ?? 0} new • ${stats?.enquiries_converted ?? 0} converted`,
            icon: Users,
            color: "text-sky-600 dark:text-sky-400 bg-sky-50 dark:bg-sky-950/60",
        },
        {
            title: "Applications Active",
            value: (stats?.applications_submitted ?? 0) + (stats?.applications_under_review ?? 0),
            subtitle: `${stats?.total_applications ?? 0} total applications`,
            icon: FileText,
            color: "text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60",
        },
        {
            title: "Pending Verifications",
            value: stats?.pending_document_verifications ?? 0,
            subtitle: `${stats?.applications_documents_pending ?? 0} waiting on documents`,
            icon: FileCheck,
            color: "text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/60",
        },
        {
            title: "Approved / Offers",
            value: stats?.applications_approved ?? 0,
            subtitle: `${stats?.scheduled_interviews ?? 0} interviews scheduled`,
            icon: CheckCircle2,
            color: "text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60",
        },
        {
            title: "Students Enrolled",
            value: stats?.applications_enrolled ?? 0,
            subtitle: `${stats?.conversion_rate ?? 0}% conversion rate`,
            icon: GraduationCap,
            color: "text-teal-600 dark:text-teal-400 bg-teal-50 dark:bg-teal-950/60",
        },
    ];

    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
            {cards.map((c, i) => {
                const Icon = c.icon;
                return (
                    <div
                        key={i}
                        className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 shadow-2xs hover:border-slate-300 dark:hover:border-slate-700 transition flex flex-col justify-between"
                    >
                        <div className="flex items-center justify-between">
                            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                                {c.title}
                            </span>
                            <div className={`p-1.5 rounded-lg ${c.color}`}>
                                <Icon className="w-4 h-4" />
                            </div>
                        </div>
                        <div className="mt-2.5">
                            {isLoading ? (
                                <Skeleton className="h-8 w-16" />
                            ) : (
                                <div className="text-2xl sm:text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
                                    {c.value}
                                </div>
                            )}
                            <div className="text-[11px] text-slate-400 dark:text-slate-500 mt-1 font-medium truncate">
                                {c.subtitle}
                            </div>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
