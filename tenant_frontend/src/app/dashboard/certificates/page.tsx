"use client";

import { useState } from "react";
import Link from "next/link";
import { useCertificates } from "@/hooks/useCertificates";
import { usePermissions } from "@/providers/PermissionProvider";
import {
    CERTIFICATE_TYPE_LABELS,
    CertificateFilters,
    CertificateStatus,
    CertificateType,
} from "@/types/Certificates";
import { CertificateStatusBadge } from "@/components/dashboard/certificates/CertificateStatusBadge";
import { CertificateSettingsCard } from "@/components/dashboard/certificates/CertificateSettingsCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

const SELECT_CLASS = "rounded-xl border border-slate-200 dark:border-slate-800 bg-transparent px-3 py-2 text-sm";

export default function CertificatesPage() {
    const { can } = usePermissions();
    const [filters, setFilters] = useState<CertificateFilters>({ page: 1, certificate_type: "", status: "", search: "" });
    const [searchText, setSearchText] = useState("");
    const { data, isLoading, isError, refetch } = useCertificates(filters);

    if (!can("view_certificates")) {
        return <ErrorState message="You do not have permission to view certificates." />;
    }

    const change = (patch: Partial<CertificateFilters>) => setFilters((f) => ({ ...f, page: 1, ...patch }));
    const results = data?.results ?? [];
    const canIssue = can("issue_certificates") || can("approve_certificates");

    return (
        <div className="space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Certificates</h1>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Transfer, bonafide, character and staff experience certificates.
                    </p>
                </div>
                {canIssue && (
                    <Button asChild>
                        <Link href="/dashboard/certificates/new">Issue certificate</Link>
                    </Button>
                )}
            </div>

            <form
                className="flex flex-wrap gap-3"
                onSubmit={(e) => {
                    e.preventDefault();
                    change({ search: searchText.trim() });
                }}
            >
                <Input
                    className="w-full sm:w-64"
                    placeholder="Search number or name"
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                />
                <select
                    aria-label="Type"
                    className={SELECT_CLASS}
                    value={filters.certificate_type}
                    onChange={(e) => change({ certificate_type: e.target.value as CertificateType | "" })}
                >
                    <option value="">All types</option>
                    {(Object.keys(CERTIFICATE_TYPE_LABELS) as CertificateType[]).map((t) => (
                        <option key={t} value={t}>
                            {CERTIFICATE_TYPE_LABELS[t]}
                        </option>
                    ))}
                </select>
                <select
                    aria-label="Status"
                    className={SELECT_CLASS}
                    value={filters.status}
                    onChange={(e) => change({ status: e.target.value as CertificateStatus | "" })}
                >
                    <option value="">All statuses</option>
                    <option value="issued">Issued</option>
                    <option value="cancelled">Cancelled</option>
                    <option value="superseded">Superseded</option>
                </select>
                <Button type="submit" variant="outline">
                    Search
                </Button>
            </form>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load certificates. Please try again." onRetry={refetch} />
            ) : results.length === 0 ? (
                <EmptyState
                    title={filters.search || filters.status || filters.certificate_type ? "No certificates match." : "No certificates issued yet."}
                    className="py-16 text-slate-500 text-sm"
                />
            ) : (
                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 divide-y divide-slate-100 dark:divide-slate-800 overflow-hidden">
                    {results.map((c) => (
                        <Link
                            key={c.id}
                            href={`/dashboard/certificates/${c.id}`}
                            className="block p-4 transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50"
                        >
                            <div className="flex flex-wrap items-center gap-2">
                                <span className="font-semibold text-slate-800 dark:text-slate-200">{c.holder_name}</span>
                                <CertificateStatusBadge status={c.status} />
                            </div>
                            <p className="text-xs text-slate-500 mt-1">
                                {c.certificate_type_label} - {c.certificate_number} - issued {new Date(c.issue_date).toLocaleDateString()}
                            </p>
                        </Link>
                    ))}
                </div>
            )}

            {data && (data.next || data.previous) && (
                <div className="flex items-center justify-between pt-2">
                    <Button variant="outline" size="sm" disabled={!data.previous} onClick={() => setFilters((f) => ({ ...f, page: Math.max(1, f.page - 1) }))}>
                        Previous
                    </Button>
                    <Button variant="outline" size="sm" disabled={!data.next} onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}>
                        Next
                    </Button>
                </div>
            )}

            {can("manage_certificate_settings") && <CertificateSettingsCard />}
        </div>
    );
}
