"use client";

import { useState } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useAlertLog } from "@/hooks/useNotifications";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Pagination } from "@/components/ui/pagination";
import { TableShell } from "@/components/common/table/TableShell";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import Unauthorized from "@/components/Unauthorized";
import {
    BellRing,
    Search,
    Filter,
    Calendar,
    RotateCcw,
    CheckCircle2,
    Clock,
    AlertTriangle,
    XCircle,
    Smartphone,
    CreditCard,
    UserX,
} from "lucide-react";
import type { AlertLogItem } from "@/types/Notifications";

const PAGE_SIZE = 25;

const KIND_CONFIG: Record<
    string,
    { label: string; badgeClass: string; icon: React.ComponentType<{ className?: string }> }
> = {
    absence: {
        label: "Student Absence",
        badgeClass: "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20",
        icon: UserX,
    },
    fee_due_soon: {
        label: "Fee Due Soon",
        badgeClass: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
        icon: Clock,
    },
    fee_overdue: {
        label: "Fee Overdue",
        badgeClass: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20",
        icon: AlertTriangle,
    },
    payment_receipt: {
        label: "Payment Receipt",
        badgeClass: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
        icon: CreditCard,
    },
};

const STATUS_CONFIG: Record<
    string,
    { label: string; badgeClass: string; icon: React.ComponentType<{ className?: string }> }
> = {
    sent: {
        label: "Delivered",
        badgeClass: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
        icon: CheckCircle2,
    },
    pending: {
        label: "Queued",
        badgeClass: "bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20",
        icon: Clock,
    },
    retrying: {
        label: "Retrying",
        badgeClass: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
        icon: RotateCcw,
    },
    failed: {
        label: "Failed",
        badgeClass: "bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20",
        icon: XCircle,
    },
    in_app_only: {
        label: "In-App Only",
        badgeClass: "bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20",
        icon: Smartphone,
    },
};

export default function AlertLogPage() {
    const { can, isOwner } = usePermissions();
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();

    const pageParam = Number(searchParams.get("page"));
    const page = Number.isInteger(pageParam) && pageParam >= 1 ? pageParam : 1;

    // Filters from query params
    const kindFilter = searchParams.get("kind") || "";
    const enrollmentFilter = searchParams.get("enrollment_id") || "";
    const createdAfterFilter = searchParams.get("created_after") || "";
    const createdBeforeFilter = searchParams.get("created_before") || "";

    const [enrollmentInput, setEnrollmentInput] = useState(enrollmentFilter);
    const [afterInput, setAfterInput] = useState(createdAfterFilter);
    const [beforeInput, setBeforeInput] = useState(createdBeforeFilter);

    const canView = isOwner || can("view_notification_log");

    const { data, isLoading, isError, refetch } = useAlertLog({
        page,
        pageSize: PAGE_SIZE,
        kind: kindFilter || undefined,
        enrollment_id: enrollmentFilter || undefined,
        created_after: createdAfterFilter || undefined,
        created_before: createdBeforeFilter || undefined,
    });

    const alertLogs = data?.results || [];

    if (!canView) {
        return <Unauthorized />;
    }

    const updateUrlParams = (updates: Record<string, string | null>) => {
        const params = new URLSearchParams(searchParams.toString());
        Object.entries(updates).forEach(([key, val]) => {
            if (val) {
                params.set(key, val);
            } else {
                params.delete(key);
            }
        });
        params.delete("page");
        const query = params.toString();
        router.replace(query ? `${pathname}?${query}` : pathname);
    };

    const handleApplyFilters = (e: React.FormEvent) => {
        e.preventDefault();
        updateUrlParams({
            enrollment_id: enrollmentInput.trim() || null,
            created_after: afterInput || null,
            created_before: beforeInput || null,
        });
    };

    const handleKindChange = (val: string) => {
        updateUrlParams({ kind: val === "all" ? null : val });
    };

    const handleClearFilters = () => {
        setEnrollmentInput("");
        setAfterInput("");
        setBeforeInput("");
        router.replace(pathname);
    };

    const handlePageChange = (nextPage: number) => {
        const params = new URLSearchParams(searchParams.toString());
        if (nextPage <= 1) {
            params.delete("page");
        } else {
            params.set("page", String(nextPage));
        }
        const query = params.toString();
        router.replace(query ? `${pathname}?${query}` : pathname);
    };

    const hasActiveFilters = Boolean(
        kindFilter || enrollmentFilter || createdAfterFilter || createdBeforeFilter
    );

    if (isLoading && !data) {
        return <LoadingState className="h-[60vh]" />;
    }

    if (isError) {
        return <ErrorState onRetry={refetch} className="m-6" />;
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                        <BellRing className="h-8 w-8 text-sky-500" />
                        System Alert Log
                    </h1>
                    <p className="text-slate-500 dark:text-slate-400 mt-2 text-lg">
                        Immutable log of automated parent notifications, attendance alerts, and fee reminders.
                    </p>
                </div>

                <div className="flex items-center gap-2">
                    <Button
                        variant="outline"
                        onClick={() => router.push("/dashboard/notifications/settings")}
                        className="rounded-xl h-11"
                    >
                        Configure Alert Rules
                    </Button>
                </div>
            </div>

            {/* Filter Controls Bar */}
            <form
                onSubmit={handleApplyFilters}
                className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-xs space-y-4"
            >
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    {/* Alert Kind Filter */}
                    <div className="space-y-1.5">
                        <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                            Alert Category
                        </Label>
                        <Select value={kindFilter || "all"} onValueChange={handleKindChange}>
                            <SelectTrigger className="rounded-xl h-10">
                                <SelectValue placeholder="All Categories" />
                            </SelectTrigger>
                            <SelectContent className="rounded-xl">
                                <SelectItem value="all">All Categories</SelectItem>
                                <SelectItem value="absence">Absence Alert</SelectItem>
                                <SelectItem value="fee_due_soon">Fee Due Soon</SelectItem>
                                <SelectItem value="fee_overdue">Fee Overdue</SelectItem>
                                <SelectItem value="payment_receipt">Payment Receipt</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Enrollment ID Filter */}
                    <div className="space-y-1.5">
                        <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                            Student Enrollment ID
                        </Label>
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                            <Input
                                placeholder="e.g. ENR-2026-001"
                                value={enrollmentInput}
                                onChange={(e) => setEnrollmentInput(e.target.value)}
                                className="pl-9 h-10 rounded-xl"
                            />
                        </div>
                    </div>

                    {/* Date From */}
                    <div className="space-y-1.5">
                        <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                            From Date (UTC)
                        </Label>
                        <div className="relative">
                            <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                            <Input
                                type="date"
                                value={afterInput}
                                onChange={(e) => setAfterInput(e.target.value)}
                                className="pl-9 h-10 rounded-xl"
                            />
                        </div>
                    </div>

                    {/* Date To */}
                    <div className="space-y-1.5">
                        <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                            To Date (UTC)
                        </Label>
                        <div className="relative">
                            <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                            <Input
                                type="date"
                                value={beforeInput}
                                onChange={(e) => setBeforeInput(e.target.value)}
                                className="pl-9 h-10 rounded-xl"
                            />
                        </div>
                    </div>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-800">
                    <div className="text-xs text-slate-400">
                        {data?.count ? `${data.count} alert events recorded` : "Zero alert events recorded"}
                    </div>
                    <div className="flex items-center gap-2">
                        {hasActiveFilters && (
                            <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={handleClearFilters}
                                className="rounded-xl h-9 text-xs text-slate-400 hover:text-slate-600"
                            >
                                Clear Filters
                            </Button>
                        )}
                        <Button type="submit" size="sm" className="rounded-xl h-9 px-4">
                            <Filter className="h-3.5 w-3.5 mr-1.5" />
                            Apply Filters
                        </Button>
                    </div>
                </div>
            </form>

            {/* Alert Log Table */}
            <TableShell
                footer={
                    data && (
                        <Pagination
                            page={page}
                            pageSize={PAGE_SIZE}
                            count={data.count}
                            onPageChange={handlePageChange}
                            className="border-t border-slate-200 dark:border-slate-800"
                        />
                    )
                }
            >
                <Table>
                    <TableHeader className="bg-slate-50 dark:bg-slate-800/50">
                        <TableRow>
                            <TableHead className="py-4 pl-6">Timestamp</TableHead>
                            <TableHead>Category</TableHead>
                            <TableHead>Student ID</TableHead>
                            <TableHead>Recipient Hint</TableHead>
                            <TableHead className="text-right pr-6">Delivery Status</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {alertLogs.length > 0 ? (
                            alertLogs.map((log: AlertLogItem) => {
                                const kindConfig = KIND_CONFIG[log.kind] || {
                                    label: log.kind,
                                    badgeClass: "bg-slate-100 text-slate-700",
                                    icon: BellRing,
                                };
                                const statusConfig = STATUS_CONFIG[log.delivery_status] || {
                                    label: log.delivery_status,
                                    badgeClass: "bg-slate-100 text-slate-700",
                                    icon: Clock,
                                };

                                const KindIcon = kindConfig.icon;
                                const StatusIcon = statusConfig.icon;

                                const dateObj = new Date(log.created_at);
                                const dateFormatted = dateObj.toLocaleDateString(undefined, {
                                    year: "numeric",
                                    month: "short",
                                    day: "numeric",
                                });
                                const timeFormatted = dateObj.toLocaleTimeString(undefined, {
                                    hour: "2-digit",
                                    minute: "2-digit",
                                    second: "2-digit",
                                });

                                return (
                                    <TableRow
                                        key={log.id}
                                        className="hover:bg-slate-50/50 dark:hover:bg-slate-800/50 transition-colors"
                                    >
                                        <TableCell className="py-4 pl-6">
                                            <div className="font-medium text-slate-900 dark:text-white text-xs">
                                                {dateFormatted}
                                            </div>
                                            <div className="text-[11px] text-slate-400 font-mono">
                                                {timeFormatted}
                                            </div>
                                        </TableCell>

                                        <TableCell>
                                            <Badge
                                                variant="outline"
                                                className={`text-xs font-semibold rounded-lg flex items-center gap-1.5 w-fit py-1 px-2.5 ${kindConfig.badgeClass}`}
                                            >
                                                <KindIcon className="h-3.5 w-3.5" />
                                                <span>{kindConfig.label}</span>
                                            </Badge>
                                        </TableCell>

                                        <TableCell>
                                            {log.enrollment_id ? (
                                                <code className="text-xs bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded font-mono text-slate-800 dark:text-slate-200">
                                                    {log.enrollment_id}
                                                </code>
                                            ) : (
                                                <span className="text-slate-400 text-xs italic">—</span>
                                            )}
                                        </TableCell>

                                        <TableCell>
                                            <span className="text-xs font-mono text-slate-600 dark:text-slate-300">
                                                {log.recipient || "Masked Contact"}
                                            </span>
                                        </TableCell>

                                        <TableCell className="text-right pr-6">
                                            <Badge
                                                variant="outline"
                                                className={`text-xs font-semibold rounded-lg inline-flex items-center gap-1.5 py-1 px-2.5 ${statusConfig.badgeClass}`}
                                            >
                                                <StatusIcon className="h-3 w-3" />
                                                <span>{statusConfig.label}</span>
                                            </Badge>
                                        </TableCell>
                                    </TableRow>
                                );
                            })
                        ) : (
                            <TableRow>
                                <TableCell colSpan={5} className="h-48 text-center">
                                    <EmptyState
                                        icon={<BellRing className="h-12 w-12 mb-2 opacity-20 text-slate-500" />}
                                        title={
                                            hasActiveFilters
                                                ? "No alerts found matching current filters."
                                                : "No automated alerts recorded in log."
                                        }
                                    />
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableShell>
        </div>
    );
}

