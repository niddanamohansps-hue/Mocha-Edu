"use client";

import React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { AdmissionsDashboardStats } from "@/types/Admissions";
import {
    Users,
    FileText,
    FileCheck,
    CheckCircle2,
    GraduationCap,
    TrendingUp,
} from "lucide-react";

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
            subtitle: `${stats?.enquiries_new ?? 0} new · ${stats?.enquiries_converted ?? 0} converted`,
            icon: Users,
            color: "text-blue-600 dark:text-blue-400",
            bg: "bg-blue-50 dark:bg-blue-950/40 border-blue-100 dark:border-blue-900",
        },
        {
            title: "Applications Active",
            value: (stats?.applications_submitted ?? 0) + (stats?.applications_under_review ?? 0),
            subtitle: `${stats?.total_applications ?? 0} total applications`,
            icon: FileText,
            color: "text-indigo-600 dark:text-indigo-400",
            bg: "bg-indigo-50 dark:bg-indigo-950/40 border-indigo-100 dark:border-indigo-900",
        },
        {
            title: "Pending Verifications",
            value: stats?.pending_document_verifications ?? 0,
            subtitle: `${stats?.applications_documents_pending ?? 0} waiting on documents`,
            icon: FileCheck,
            color: "text-amber-600 dark:text-amber-400",
            bg: "bg-amber-50 dark:bg-amber-950/40 border-amber-100 dark:border-amber-900",
        },
        {
            title: "Approved / Offers",
            value: stats?.applications_approved ?? 0,
            subtitle: `${stats?.scheduled_interviews ?? 0} interviews scheduled`,
            icon: CheckCircle2,
            color: "text-emerald-600 dark:text-emerald-400",
            bg: "bg-emerald-50 dark:bg-emerald-950/40 border-emerald-100 dark:border-emerald-900",
        },
        {
            title: "Students Enrolled",
            value: stats?.applications_enrolled ?? 0,
            subtitle: `${stats?.conversion_rate ?? 0}% conversion rate`,
            icon: GraduationCap,
            color: "text-teal-600 dark:text-teal-400",
            bg: "bg-teal-50 dark:bg-teal-950/40 border-teal-100 dark:border-teal-900",
        },
    ];

    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {cards.map((c, i) => {
                const Icon = c.icon;
                return (
                    <Card
                        key={i}
                        className={`border rounded-2xl shadow-sm transition-all hover:shadow-md ${c.bg}`}
                    >
                        <CardContent className="p-5 flex flex-col justify-between h-full">
                            <div className="flex items-center justify-between">
                                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                                    {c.title}
                                </span>
                                <div className={`p-2 rounded-xl bg-white/80 dark:bg-slate-900/80 shadow-xs ${c.color}`}>
                                    <Icon className="w-5 h-5" />
                                </div>
                            </div>
                            <div className="mt-4">
                                <div className="text-3xl font-black text-slate-800 dark:text-white">
                                    {isLoading ? "—" : c.value}
                                </div>
                                <div className="text-xs text-slate-500 dark:text-slate-400 mt-1 font-medium">
                                    {c.subtitle}
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                );
            })}
        </div>
    );
}

