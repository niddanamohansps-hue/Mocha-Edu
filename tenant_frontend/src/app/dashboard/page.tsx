"use client";

import { useMe } from "@/hooks/useAuth";
import { useDashboardSummary } from "@/hooks/useDashboard";
import { usePermissions } from "@/providers/PermissionProvider";
import {
    Users,
    BookOpen,
    TrendingUp,
    Activity,
    Bell,
    Wallet,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/feedback/ErrorState";

const ACTION_LABELS: Record<string, string> = {
    promoted: "Promoted",
    retained: "Retained",
    transferred: "Transferred",
    withdrawn: "Withdrawn",
    graduated: "Graduated",
    reversed: "Reversed",
};

export default function DashboardOverview() {
    const { data: user } = useMe();
    const { can, isOwner } = usePermissions();
    const canViewSummary = isOwner || can("view_dashboard");

    const { data: summary, isLoading, isError, refetch } = useDashboardSummary();

    const attendanceValue =
        summary?.attendance.today_percentage !== null && summary?.attendance.today_percentage !== undefined
            ? `${summary.attendance.today_percentage}%`
            : "—";

    const stats = [
        { label: "Active Students", value: summary?.students.active, icon: Users, color: "sky" },
        { label: "Active Staff", value: summary?.staff.active, icon: BookOpen, color: "teal" },
        { label: "Today's Attendance", value: attendanceValue, icon: Activity, color: "indigo" },
        { label: "Outstanding Fees", value: summary ? summary.fees.outstanding : undefined, icon: Wallet, color: "emerald" },
    ];

    return (
        <div className="space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-700">
            {/* Welcome Banner */}
            <div className="relative bg-gradient-to-r from-sky-600 to-teal-600 rounded-[2.5rem] p-10 md:p-14 text-white overflow-hidden shadow-2xl shadow-sky-500/20">
                <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-10"></div>
                <div className="relative z-10 flex flex-col md:flex-row justify-between items-center gap-10">
                    <div className="space-y-4 text-center md:text-left">
                        <div className="inline-block bg-white/20 backdrop-blur-md px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-widest text-sky-50 border border-white/20">
                            Dashboard Overview
                        </div>
                        <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight">
                            Welcome back, <br />
                            <span className="text-sky-200">{user?.profile?.first_name}!</span>
                        </h1>
                        <p className="text-sky-50/80 text-lg max-w-md font-medium">
                            Here&apos;s what&apos;s happening at your institution today.
                        </p>
                    </div>
                    {canViewSummary && summary && (
                        <div className="flex items-center gap-3 bg-white/10 border border-white/20 rounded-2xl px-6 py-4 backdrop-blur-md">
                            <Bell className="h-6 w-6 text-sky-200" />
                            <div>
                                <p className="text-2xl font-black">{summary.notifications.unread}</p>
                                <p className="text-xs text-sky-100 uppercase tracking-wider font-bold">Unread</p>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {!canViewSummary ? (
                <div className="rounded-3xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-10 text-center text-slate-500">
                    Use the sidebar to access the modules assigned to your role.
                </div>
            ) : isError ? (
                <ErrorState message="Failed to load dashboard summary. Please try again later." onRetry={refetch} />
            ) : (
                <>
                    {/* Stats Grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 md:gap-8">
                        {stats.map((stat, i) => (
                            <Card key={i} className="border-none shadow-xl shadow-slate-200/50 dark:shadow-none dark:bg-slate-900 group h-full transition-all hover:-translate-y-1">
                                <CardContent className="p-8">
                                    <div className="flex flex-wrap justify-between gap-2 items-start mb-6">
                                        <div className={`p-4 bg-${stat.color}-100 dark:bg-${stat.color}-500/10 text-${stat.color}-600 rounded-2xl group-hover:scale-110 transition-transform duration-300`}>
                                            <stat.icon className="h-7 w-7" />
                                        </div>
                                    </div>
                                    <h3 className="text-slate-500 dark:text-slate-400 font-bold uppercase tracking-widest text-xs mb-2">{stat.label}</h3>
                                    {isLoading || stat.value === undefined ? (
                                        <Skeleton className="h-9 w-20" />
                                    ) : (
                                        <p className="text-4xl font-black text-slate-900 dark:text-white tracking-tight">{stat.value}</p>
                                    )}
                                </CardContent>
                            </Card>
                        ))}
                    </div>

                    {/* Recent Activity */}
                    <Card className="border-none shadow-xl shadow-slate-200/50 dark:shadow-none dark:bg-slate-900">
                        <CardHeader className="flex flex-wrap flex-row items-center justify-between gap-2 pb-8 border-b border-slate-50 dark:border-slate-800">
                            <div>
                                <CardTitle className="text-xl">Recent Promotion Activity</CardTitle>
                                <CardDescription>Latest student lifecycle changes</CardDescription>
                            </div>
                            <TrendingUp className="h-6 w-6 text-slate-300" />
                        </CardHeader>
                        <CardContent className="pt-8 px-0">
                            {isLoading ? (
                                <div className="px-6 space-y-4">
                                    <Skeleton className="h-14 w-full" />
                                    <Skeleton className="h-14 w-full" />
                                </div>
                            ) : !summary || summary.promotion.recent.length === 0 ? (
                                <p className="text-center text-slate-400 py-10">No recent activity.</p>
                            ) : (
                                <div className="space-y-0">
                                    {summary.promotion.recent.map((record) => (
                                        <div key={record.id} className="flex items-center gap-6 p-6 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors border-b border-slate-50 dark:border-slate-800 last:border-0">
                                            <div className="h-12 w-12 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center flex-shrink-0">
                                                <Activity className="h-6 w-6 text-slate-400" />
                                            </div>
                                            <div className="flex-1">
                                                <p className="font-bold text-slate-800 dark:text-slate-200">
                                                    {record.student_name} — {ACTION_LABELS[record.action] ?? record.action}
                                                </p>
                                                <p className="text-sm text-slate-500">
                                                    {record.source_level_name || "—"}
                                                    {record.target_level_name ? ` → ${record.target_level_name}` : ""}
                                                    {" · "}
                                                    {record.source_academic_year}
                                                    {record.target_academic_year ? ` → ${record.target_academic_year}` : ""}
                                                </p>
                                            </div>
                                            <p className="text-xs font-bold text-slate-400 whitespace-nowrap">
                                                {new Date(record.created_at).toLocaleDateString()}
                                            </p>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </>
            )}
        </div>
    );
}
