"use client";

import React, { useState, useMemo } from "react";
import { usePermissions } from "@/providers/PermissionProvider";
import { useAuditLogs, useAuditLogMetadata, auditLogErrorMessage } from "@/hooks/useAuditLogs";
import { AuditLogItem } from "@/types/AuditLog";
import { AuditLogDetailModal } from "@/components/dashboard/audit-logs/AuditLogDetailModal";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
    TableCellAction,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import { Pagination } from "@/components/ui/pagination";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Shield,
    Search,
    RefreshCw,
    FilterX,
    Eye,
    Calendar,
    ChevronLeft,
    ChevronRight,
    AlertCircle,
    User,
    Hash
} from "lucide-react";
import { format } from "date-fns";

function getActionBadgeVariant(action: string): "default" | "secondary" | "destructive" | "outline" {
    const act = action.toLowerCase();
    if (act.includes("delete") || act.includes("remove") || act.includes("cancel") || act.includes("revers")) {
        return "destructive";
    }
    if (act.includes("create") || act.includes("add") || act.includes("enroll") || act.includes("publish")) {
        return "default";
    }
    if (act.includes("update") || act.includes("change") || act.includes("edit")) {
        return "secondary";
    }
    return "outline";
}

export default function AuditLogsPage() {
    const { can, isOwner } = usePermissions();
    const canView = isOwner || can("view_audit_log");

    // Filter states
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(20);
    const [searchInput, setSearchInput] = useState("");
    const [activeSearch, setActiveSearch] = useState("");
    const [selectedAction, setSelectedAction] = useState<string>("ALL");
    const [selectedModel, setSelectedModel] = useState<string>("ALL");
    const [actorUsername, setActorUsername] = useState("");
    const [activeActorUsername, setActiveActorUsername] = useState("");
    const [dateFrom, setDateFrom] = useState("");
    const [dateTo, setDateTo] = useState("");
    const [dateError, setDateError] = useState<string | null>(null);

    // Detail modal state
    const [selectedLog, setSelectedLog] = useState<AuditLogItem | null>(null);
    const [isDetailOpen, setIsDetailOpen] = useState(false);

    // Metadata for dropdowns
    const { data: metadata } = useAuditLogMetadata();

    // Query filters
    const queryFilters = useMemo(() => {
        return {
            page,
            page_size: pageSize,
            search: activeSearch || undefined,
            action: selectedAction !== "ALL" ? selectedAction : undefined,
            model_name: selectedModel !== "ALL" ? selectedModel : undefined,
            actor_username: activeActorUsername || undefined,
            date_from: dateFrom || undefined,
            date_to: dateTo || undefined,
        };
    }, [page, pageSize, activeSearch, selectedAction, selectedModel, activeActorUsername, dateFrom, dateTo]);

    // Audit logs query
    const {
        data,
        isLoading,
        isError,
        error,
        refetch,
        isFetching,
    } = useAuditLogs(queryFilters);

    if (!canView) {
        return <Unauthorized />;
    }

    const handleSearchSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        setPage(1);
        setActiveSearch(searchInput.trim());
        setActiveActorUsername(actorUsername.trim());
    };

    const handleDateFromChange = (val: string) => {
        setDateFrom(val);
        setPage(1);
        if (dateTo && val && val > dateTo) {
            setDateError("Start date cannot be after end date.");
        } else {
            setDateError(null);
        }
    };

    const handleDateToChange = (val: string) => {
        setDateTo(val);
        setPage(1);
        if (dateFrom && val && dateFrom > val) {
            setDateError("End date cannot be before start date.");
        } else {
            setDateError(null);
        }
    };

    const handleClearFilters = () => {
        setSearchInput("");
        setActiveSearch("");
        setSelectedAction("ALL");
        setSelectedModel("ALL");
        setActorUsername("");
        setActiveActorUsername("");
        setDateFrom("");
        setDateTo("");
        setDateError(null);
        setPage(1);
    };

    const hasActiveFilters = Boolean(
        activeSearch ||
        selectedAction !== "ALL" ||
        selectedModel !== "ALL" ||
        activeActorUsername ||
        dateFrom ||
        dateTo
    );

    const totalCount = data?.count || 0;
    const totalPages = Math.ceil(totalCount / pageSize) || 1;
    const startIndex = (page - 1) * pageSize + 1;
    const endIndex = Math.min(page * pageSize, totalCount);

    return (
        <div className="space-y-6">
            {/* Header Section */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                        <Shield className="w-8 h-8 text-indigo-600 dark:text-indigo-400" />
                        Audit Logs & Security Trail
                    </h1>
                    <p className="text-slate-500 dark:text-slate-400 mt-1">
                        Inspect tenant-isolated administrative actions, data changes, and security events.
                    </p>
                </div>

                <div className="flex items-center gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => refetch()}
                        disabled={isFetching}
                        className="text-xs"
                    >
                        <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${isFetching ? "animate-spin" : ""}`} />
                        Refresh
                    </Button>
                </div>
            </div>

            {/* Filter Card */}
            <Card className="border border-slate-200 dark:border-slate-800 shadow-xs dark:bg-slate-900/50">
                <CardContent className="p-4 space-y-4">
                    <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                        {/* Search Input */}
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                            <Input aria-label="Search keyword or object ID..."
                                placeholder="Search keyword or object ID..."
                                value={searchInput}
                                onChange={(e) => setSearchInput(e.target.value)}
                                className="pl-9 text-xs"
                            />
                        </div>

                        {/* Actor Username Input */}
                        <div className="relative">
                            <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                            <Input aria-label="Filter by actor username..."
                                placeholder="Filter by actor username..."
                                value={actorUsername}
                                onChange={(e) => setActorUsername(e.target.value)}
                                className="pl-9 text-xs"
                            />
                        </div>

                        {/* Action Select */}
                        <div>
                            <Select
                                value={selectedAction}
                                onValueChange={(val) => {
                                    setSelectedAction(val);
                                    setPage(1);
                                }}
                            >
                                <SelectTrigger className="text-xs">
                                    <SelectValue placeholder="All Actions" />
                                </SelectTrigger>
                                <SelectContent className="max-h-60">
                                    <SelectItem value="ALL">All Actions</SelectItem>
                                    {metadata?.actions.map((act) => (
                                        <SelectItem key={act} value={act}>
                                            {act}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        {/* Model / Resource Select */}
                        <div>
                            <Select
                                value={selectedModel}
                                onValueChange={(val) => {
                                    setSelectedModel(val);
                                    setPage(1);
                                }}
                            >
                                <SelectTrigger className="text-xs">
                                    <SelectValue placeholder="All Resources" />
                                </SelectTrigger>
                                <SelectContent className="max-h-60">
                                    <SelectItem value="ALL">All Resources</SelectItem>
                                    {metadata?.model_names.map((mod) => (
                                        <SelectItem key={mod} value={mod}>
                                            {mod}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        {/* Date Range Controls */}
                        <div className="sm:col-span-2 lg:col-span-2 flex flex-col sm:flex-row items-center gap-2">
                            <div className="w-full relative">
                                <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                                <Input
                                    type="date"
                                    value={dateFrom}
                                    onChange={(e) => handleDateFromChange(e.target.value)}
                                    className="pl-9 text-xs"
                                    aria-label="Start Date"
                                />
                            </div>
                            <span className="text-xs text-slate-400">to</span>
                            <div className="w-full relative">
                                <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
                                <Input
                                    type="date"
                                    value={dateTo}
                                    onChange={(e) => handleDateToChange(e.target.value)}
                                    className="pl-9 text-xs"
                                    aria-label="End Date"
                                />
                            </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="sm:col-span-2 lg:col-span-2 flex items-center justify-end gap-2">
                            <Button type="submit" size="sm" className="text-xs">
                                <Search className="w-3.5 h-3.5 mr-1" />
                                Apply Filters
                            </Button>
                            {hasActiveFilters && (
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    onClick={handleClearFilters}
                                    className="text-xs text-slate-500 hover:text-slate-900 dark:hover:text-white"
                                >
                                    <FilterX className="w-3.5 h-3.5 mr-1" />
                                    Clear
                                </Button>
                            )}
                        </div>
                    </form>

                    {dateError && (
                        <div className="flex items-center gap-1.5 text-xs text-rose-600 dark:text-rose-400 font-medium">
                            <AlertCircle className="w-3.5 h-3.5" />
                            {dateError}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Error State */}
            {isError && (
                <Card className="border-rose-200 dark:border-rose-900 bg-rose-50/50 dark:bg-rose-950/20">
                    <CardContent className="p-4 flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2 text-rose-800 dark:text-rose-300 text-sm">
                            <AlertCircle className="w-5 h-5 shrink-0" />
                            <span>{auditLogErrorMessage(error, "Failed to load audit logs. Please try again.")}</span>
                        </div>
                        <Button variant="outline" size="sm" onClick={() => refetch()} className="text-xs">
                            Retry
                        </Button>
                    </CardContent>
                </Card>
            )}

            {/* Table or Empty State */}
            {isLoading ? (
                <LoadingState className="h-64" />
            ) : !data || data.results.length === 0 ? (
                <EmptyState
                    title="No audit events found"
                    description={
                        hasActiveFilters
                            ? "No audit records matched your active filters. Try clearing some criteria."
                            : "No administrative or security events have been recorded in this school tenant yet."
                    }
                />
            ) : (
                <TableShell
                    footer={
                        <Pagination
                            page={page}
                            pageSize={pageSize}
                            count={totalCount}
                            onPageChange={setPage}
                            pageSizeOptions={[10, 20, 50]}
                            onPageSizeChange={(val) => {
                                setPageSize(val);
                                setPage(1);
                            }}
                        />
                    }
                >
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead className="w-[180px]">Timestamp</TableHead>
                                <TableHead>Done by</TableHead>
                                <TableHead>Action</TableHead>
                                <TableHead>What</TableHead>
                                <TableHead>Record ID</TableHead>
                                <TableHead>Changes</TableHead>
                                <TableHead>IP Address</TableHead>
                                <TableHead className="text-right">Details</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody striped>
                            {data.results.map((log) => {
                                let dateLabel = log.created_at;
                                try {
                                    dateLabel = format(new Date(log.created_at), "yyyy-MM-dd HH:mm:ss");
                                } catch {
                                    dateLabel = log.created_at;
                                }

                                const changeCount = log.changes ? Object.keys(log.changes).length : 0;

                                return (
                                    <TableRow
                                        key={log.id}
                                        className="text-xs"
                                    >
                                        <TableCell className="font-mono text-slate-600 dark:text-slate-400">
                                            {dateLabel}
                                        </TableCell>
                                        <TableCell className="font-medium text-slate-900 dark:text-white">
                                            {log.actor_username ? (
                                                <span className="flex items-center gap-1.5">
                                                    <User className="w-3.5 h-3.5 text-slate-400" />
                                                    {log.actor_username}
                                                </span>
                                            ) : (
                                                <span className="text-slate-400 italic">System</span>
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            <Badge
                                                variant={getActionBadgeVariant(log.action)}
                                                className="font-mono text-[11px] font-normal"
                                            >
                                                {log.action}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="font-medium text-slate-700 dark:text-slate-300">
                                            {log.model_name}
                                        </TableCell>
                                        <TableCell className="font-mono text-slate-500">
                                            {log.object_id ? (
                                                <span className="flex items-center gap-1">
                                                    <Hash className="w-3 h-3 text-slate-400" />
                                                    {log.object_id}
                                                </span>
                                            ) : (
                                                <span className="text-slate-400">-</span>
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            {changeCount > 0 ? (
                                                <Badge variant="outline" className="text-[10px] font-normal text-slate-600">
                                                    {changeCount} {changeCount === 1 ? "field" : "fields"}
                                                </Badge>
                                            ) : (
                                                <span className="text-slate-400 italic text-[11px]">None</span>
                                            )}
                                        </TableCell>
                                        <TableCell className="font-mono text-slate-500 text-[11px]">
                                            {log.ip_address || "-"}
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => {
                                                    setSelectedLog(log);
                                                    setIsDetailOpen(true);
                                                }}
                                                className="h-7 text-xs text-indigo-600 dark:text-indigo-400 hover:text-indigo-900 dark:hover:text-indigo-200"
                                            >
                                                <Eye className="w-3.5 h-3.5 mr-1" />
                                                View
                                            </Button>
                                        </TableCell>
                                    </TableRow>
                                );
                            })}
                        </TableBody>
                    </Table>
                </TableShell>
            )}

            {/* Event Detail Modal */}
            <AuditLogDetailModal
                log={selectedLog}
                isOpen={isDetailOpen}
                onClose={() => {
                    setIsDetailOpen(false);
                    setSelectedLog(null);
                }}
            />
        </div>
    );
}

