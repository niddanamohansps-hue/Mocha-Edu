"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
    Award,
    Plus,
    Search,
    X,
    FileText,
    Calendar,
    User,
    CheckCircle2,
    Clock,
    FileBadge,
    Eye,
    Shield,
    GraduationCap,
    Briefcase,
    Printer,
} from "lucide-react";
import { useCertificates } from "@/hooks/useCertificates";
import { usePermissions } from "@/providers/PermissionProvider";
import {
    Certificate,
    CERTIFICATE_TYPE_LABELS,
    CertificateFilters,
    CertificateStatus,
    CertificateType,
} from "@/types/Certificates";
import { CertificateStatusBadge } from "@/components/dashboard/certificates/CertificateStatusBadge";
import { CertificateSettingsCard } from "@/components/dashboard/certificates/CertificateSettingsCard";
import { PrintableCertificateModal } from "@/components/dashboard/certificates/PrintableCertificateModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
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
import { TableShell } from "@/components/common/table/TableShell";
import { Pagination } from "@/components/ui/pagination";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { Avatar } from "@/components/ui/avatar";

const PAGE_SIZE = 15;

function formatDateDisplay(iso: string | null) {
    if (!iso) return "—";
    try {
        const d = new Date(iso);
        return d.toLocaleDateString("en-IN", {
            day: "numeric",
            month: "short",
            year: "numeric",
        });
    } catch {
        return iso;
    }
}

export default function CertificatesPage() {
    const { can } = usePermissions();
    const [filters, setFilters] = useState<CertificateFilters>({
        page: 1,
        certificate_type: "",
        status: "",
        search: "",
    });

    const [searchInput, setSearchInput] = useState("");
    const [debouncedSearch, setDebouncedSearch] = useState("");
    const [printCert, setPrintCert] = useState<Certificate | null>(null);

    // Debounce search query by 300ms
    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedSearch(searchInput.trim());
        }, 300);
        return () => clearTimeout(handler);
    }, [searchInput]);

    // Sync debounced search with query filters
    useEffect(() => {
        setFilters((prev) => ({ ...prev, page: 1, search: debouncedSearch }));
    }, [debouncedSearch]);

    const { data, isLoading, isError, refetch } = useCertificates(filters);

    if (!can("view_certificates")) {
        return <ErrorState message="You do not have permission to view certificates." />;
    }

    const changeType = (type: string) => {
        setFilters((f) => ({
            ...f,
            page: 1,
            certificate_type: type === "all" ? "" : (type as CertificateType),
        }));
    };

    const changeStatus = (status: string) => {
        setFilters((f) => ({
            ...f,
            page: 1,
            status: status === "all" ? "" : (status as CertificateStatus),
        }));
    };

    const handlePageChange = (nextPage: number) => {
        setFilters((f) => ({ ...f, page: nextPage }));
    };

    const results = data?.results ?? [];
    const totalCount = data?.count ?? 0;
    const canIssue = can("issue_certificates") || can("approve_certificates");

    return (
        <div className="space-y-6 max-w-7xl mx-auto pb-24 animate-in fade-in duration-500">
            {/* 1. Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <FileBadge className="h-7 w-7 text-indigo-600 dark:text-indigo-400" />
                        <span>Institutional Certificates Registry</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Generate and manage Transfer Certificates (TC), Bonafide, Character, and Staff Experience credentials
                    </p>
                </div>

                <div className="flex items-center gap-2.5 shrink-0">
                    <Button
                        asChild
                        variant="outline"
                        size="sm"
                        className="gap-1.5"
                    >
                        <Link href="/dashboard/id-cards">
                            <User className="h-3.5 w-3.5 text-slate-500" />
                            <span>ID Cards Studio</span>
                        </Link>
                    </Button>
                    {canIssue && (
                        <Button
                            asChild
                            size="sm"
                            className="gap-1.5 bg-indigo-600 hover:bg-indigo-500 text-white"
                        >
                            <Link href="/dashboard/certificates/new">
                                <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                                <span>Issue Certificate</span>
                            </Link>
                        </Button>
                    )}
                </div>
            </div>

            {/* 2. Control Bar: Search & Segmentation Filters */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-4 shadow-2xs space-y-3">
                <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
                    {/* Search Input with Clear Button */}
                    <div className="relative flex-1 max-w-md">
                        <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                        <Input
                            placeholder="Search by certificate number or recipient name..."
                            value={searchInput}
                            onChange={(e) => setSearchInput(e.target.value)}
                            className="h-9 pl-8.5 pr-8 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium"
                        />
                        {searchInput && (
                            <button
                                type="button"
                                onClick={() => setSearchInput("")}
                                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5 cursor-pointer"
                            >
                                <X className="w-3 h-3" />
                            </button>
                        )}
                    </div>

                    {/* Certificate Type Select */}
                    <div className="w-full md:w-60 shrink-0">
                        <Select
                            value={filters.certificate_type || "all"}
                            onValueChange={changeType}
                        >
                            <SelectTrigger className="h-9 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium">
                                <SelectValue placeholder="All Certificate Types" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all" className="text-xs">
                                    All Types
                                </SelectItem>
                                {(Object.keys(CERTIFICATE_TYPE_LABELS) as CertificateType[]).map((t) => (
                                    <SelectItem key={t} value={t} className="text-xs cursor-pointer">
                                        {CERTIFICATE_TYPE_LABELS[t]}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                </div>

                {/* Status Segment Filter Pills */}
                <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs border-t border-slate-100 dark:border-slate-800/60 pt-2.5">
                    {[
                        { id: "all", label: "All Statuses" },
                        { id: "issued", label: "Issued" },
                        { id: "cancelled", label: "Cancelled" },
                        { id: "superseded", label: "Superseded" },
                    ].map((tab) => {
                        const active = (filters.status || "all") === tab.id;
                        return (
                            <button
                                key={tab.id}
                                type="button"
                                onClick={() => changeStatus(tab.id)}
                                className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                                    active
                                        ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-2xs"
                                        : "bg-slate-100/70 dark:bg-slate-800/60 text-slate-600 dark:text-slate-400 hover:bg-slate-200/60"
                                }`}
                            >
                                {tab.label}
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* 3. Certificates Table Desk */}
            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load certificates. Please try again." onRetry={refetch} />
            ) : results.length === 0 ? (
                <EmptyState
                    title={
                        filters.search || filters.status || filters.certificate_type
                            ? "No certificates match your search filters"
                            : "No certificates issued yet"
                    }
                    description="Issue your first student transfer certificate, bonafide letter, or staff credential using the button above."
                    className="py-16 text-slate-500"
                />
            ) : (
                <TableShell
                    footer={
                        totalCount > PAGE_SIZE ? (
                            <Pagination
                                page={filters.page || 1}
                                pageSize={PAGE_SIZE}
                                count={totalCount}
                                onPageChange={handlePageChange}
                            />
                        ) : undefined
                    }
                >
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead className="pl-4">
                                    Certificate # &amp; Date
                                </TableHead>
                                <TableHead>
                                    Recipient Details
                                </TableHead>
                                <TableHead>
                                    Certificate Type
                                </TableHead>
                                <TableHead>
                                    Verification Status
                                </TableHead>
                                <TableHead className="text-right pr-4">
                                    Actions
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody striped>
                            {results.map((c) => {
                                const recipientName = c.holder_name || "—";

                                return (
                                    <TableRow
                                        key={c.id}
                                    >
                                        {/* Certificate Number */}
                                        <TableCell className="pl-4">
                                            <code className="text-xs font-mono font-bold text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 px-1.5 py-0.5 rounded border border-indigo-200 dark:border-indigo-800">
                                                {c.certificate_number}
                                            </code>
                                            <div className="text-[10px] text-slate-400 flex items-center gap-1 mt-1 font-medium">
                                                <Calendar className="w-3 h-3" />
                                                <span>{formatDateDisplay(c.issue_date)}</span>
                                            </div>
                                        </TableCell>

                                        {/* Recipient with Avatar */}
                                        <TableCell>
                                            <div className="flex items-center gap-2.5">
                                                <Avatar name={recipientName} size="sm" />
                                                <div>
                                                    <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                        {recipientName}
                                                    </div>
                                                    <div className="text-[10px] font-mono text-slate-400">
                                                        {c.student ? "Student" : "Staff Member"}
                                                    </div>
                                                </div>
                                            </div>
                                        </TableCell>

                                        {/* Certificate Type */}
                                        <TableCell>
                                            <span className="font-semibold text-xs text-slate-800 dark:text-slate-200">
                                                {CERTIFICATE_TYPE_LABELS[c.certificate_type] || c.certificate_type}
                                            </span>
                                        </TableCell>

                                        {/* Status Badge */}
                                        <TableCell>
                                            <CertificateStatusBadge status={c.status} />
                                        </TableCell>

                                        {/* Actions */}
                                        <TableCell className="pr-4 text-right">
                                            <div className="flex items-center justify-end gap-1">
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => setPrintCert(c)}
                                                    className="h-8 px-2 text-xs text-slate-600 hover:text-indigo-600 rounded-lg"
                                                    title="Print Certificate"
                                                >
                                                    <Printer className="w-3.5 h-3.5" />
                                                </Button>
                                                <Button
                                                    asChild
                                                    variant="ghost"
                                                    size="sm"
                                                    className="h-8 px-2 text-xs text-slate-600 hover:text-indigo-600 rounded-lg"
                                                >
                                                    <Link href={`/dashboard/certificates/${c.id}`}>
                                                        <Eye className="w-3.5 h-3.5 mr-1" />
                                                        <span>Details</span>
                                                    </Link>
                                                </Button>
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                );
                            })}
                        </TableBody>
                    </Table>
                </TableShell>
            )}

            {/* Official Printable Certificate Modal */}
            <PrintableCertificateModal
                isOpen={Boolean(printCert)}
                onClose={() => setPrintCert(null)}
                certificate={printCert}
            />
        </div>
    );
}
