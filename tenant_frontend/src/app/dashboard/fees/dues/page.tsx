"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Table,
    TableBody,
    TableCell,
    TableCellNumeric,
    TableCellAction,
    TableHead,
    TableHeadNumeric,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import { Pagination } from "@/components/ui/pagination";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { PageHeader } from "@/components/common/PageLayout";
import { CallDialog, PromiseBadge } from "@/components/fees/CallDialog";
import { useDues } from "@/hooks/useFees";
import { useAcademicLevels } from "@/hooks/useAcademics";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { usePermissions } from "@/providers/PermissionProvider";
import type { DueBand, DueRow } from "@/types/FeeDues";

const BANDS: { value: DueBand; label: string }[] = [
    { value: "current", label: "Not yet due" },
    { value: "1-30", label: "1 to 30 days late" },
    { value: "31-60", label: "31 to 60 days" },
    { value: "61-90", label: "61 to 90 days" },
    { value: "90+", label: "Over 90 days" },
];

const money = (value: string) => Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const selectClass = "h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";

export default function DuesPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("view_financial_reports")) return <Unauthorized />;
    return <Content canCall={isOwner || can("collect_payments")} />;
}

function Content({ canCall }: { canCall: boolean }) {
    const { selectedYear } = useAcademicYear();
    const { data: levels = [] } = useAcademicLevels();
    const [band, setBand] = useState("");
    const [level, setLevel] = useState("");
    const [search, setSearch] = useState("");
    const [sort, setSort] = useState<"amount" | "age" | "name">("amount");
    const [promise, setPromise] = useState("");
    const [calling, setCalling] = useState<DueRow | null>(null);
    const [page, setPage] = useState(1);
    const dues = useDues({ academic_year: selectedYear?.name, band, level, search, sort, promise, page });
    const data = dues.data;

    const reset = <T,>(set: (v: T) => void) => (v: T) => { set(v); setPage(1); };
    const pages = data ? Math.max(Math.ceil(data.count / 25), 1) : 1;

    return (
        <div className="max-w-7xl mx-auto space-y-6">
            <PageHeader
                title="Fee Dues"
                description="Review all students with outstanding balances, oldest due dates, and record collection calls."
                badge={selectedYear ? <Badge variant="outline" className="text-xs font-semibold bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-300">{selectedYear.name}</Badge> : undefined}
            />

            {data && (
                <>
                    <div className="grid grid-cols-3 gap-2 sm:gap-3">
                        <Stat label="Students owing" value={String(data.totals.students)} />
                        <Stat label="Outstanding" value={money(data.totals.outstanding)} />
                        <Stat label="Of which overdue" value={money(data.totals.overdue)} />
                    </div>
                    <div className="flex gap-2 overflow-x-auto pb-1 sm:grid sm:grid-cols-5 no-scrollbar">
                        {BANDS.map((b) => (
                            <button
                                key={b.value} type="button" onClick={() => reset(setBand)(band === b.value ? "" : b.value)}
                                className={`shrink-0 min-w-[130px] sm:min-w-0 rounded-xl border p-2.5 sm:p-3 text-left transition-all cursor-pointer ${
                                    band === b.value
                                        ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950/30 ring-2 ring-indigo-500/20"
                                        : "border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                                }`}
                            >
                                <span className="block text-[11px] text-slate-500 truncate">{b.label}</span>
                                <span className="font-semibold text-xs sm:text-sm">{money(data.totals.bands[b.value])}</span>
                            </button>
                        ))}
                    </div>
                    {data.totals.capped && (
                        <p className="text-xs text-amber-700">This school has a very large number of open fees, so the list shows the first part only. Narrow it by class.</p>
                    )}
                </>
            )}

            <div className="flex flex-wrap gap-3">
                <Input className="max-w-xs" placeholder="Search a name or enrollment id" value={search} onChange={(e) => reset(setSearch)(e.target.value)} />
                <select className={selectClass} value={level} onChange={(e) => reset(setLevel)(e.target.value)}>
                    <option value="">All classes</option>
                    {levels.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
                </select>
                <select className={selectClass} value={promise} onChange={(e) => reset(setPromise)(e.target.value)}>
                    <option value="">Any promise</option>
                    <option value="broken">Broken promises</option>
                    <option value="pending">Promised, not due yet</option>
                    <option value="kept">Promise kept</option>
                    <option value="none">No promise</option>
                </select>
                <select className={selectClass} value={sort} onChange={(e) => reset(setSort)(e.target.value as typeof sort)}>
                    <option value="amount">Biggest amount first</option>
                    <option value="age">Oldest first</option>
                    <option value="name">By name</option>
                </select>
            </div>

            {!data ? <LoadingState /> : data.results.length === 0 ? (
                <EmptyState
                    title="No outstanding fee dues found"
                    description="All students in this class or aging band are up to date with their fees, or no students match the active filter criteria."
                    hint="Try adjusting the class dropdown, aging band, or academic year."
                    className="py-16"
                />
            ) : (
                <>
                <TableShell
                    footer={
                        data.count > 0 && (
                            <Pagination
                                page={page}
                                pageSize={25}
                                count={data.count}
                                onPageChange={setPage}
                            />
                        )
                    }
                >
                    <Table className="min-w-[48rem]">
                        <TableHeader>
                            <TableRow>
                                <TableHead className="sticky left-0 bg-white dark:bg-slate-900 z-10 border-r border-slate-100 dark:border-slate-800 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)] pl-4">Student</TableHead>
                                <TableHeadNumeric>Outstanding</TableHeadNumeric>
                                <TableHead>Oldest due</TableHead>
                                <TableHead>Parent or guardian</TableHead>
                                <TableHead>Last call</TableHead>
                                {canCall && <TableHead className="text-right pr-4">Action</TableHead>}
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {data.results.map((row) => (
                                <TableRow key={row.student} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40">
                                    <TableCell className="sticky left-0 bg-white dark:bg-slate-900 z-10 border-r border-slate-100 dark:border-slate-800 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)] pl-4">
                                        <span className="font-medium text-slate-900 dark:text-white block truncate max-w-[130px] sm:max-w-none">{row.name}</span>
                                        <span className="block text-xs text-slate-400 truncate max-w-[130px] sm:max-w-none">{row.enrollment_id}{row.level ? `, ${row.level}${row.section ? ` ${row.section}` : ""}` : ""}</span>
                                    </TableCell>
                                    <TableCellNumeric>
                                        <span className="font-semibold text-slate-900 dark:text-white">{money(row.outstanding)}</span>
                                        <span className="block text-xs text-slate-400 font-normal">{row.fees} {row.fees === 1 ? "fee" : "fees"}</span>
                                    </TableCellNumeric>
                                    <TableCell>
                                        {row.oldest_due ? (
                                            <div className="flex items-center gap-1.5 flex-wrap">
                                                <span className="font-mono text-xs text-slate-600 dark:text-slate-300">{row.oldest_due}</span>
                                                <Badge variant={row.days_late > 60 ? "destructive" : "secondary"} className="text-[10px] font-semibold">{row.days_late}d late</Badge>
                                            </div>
                                        ) : <span className="text-xs text-slate-400">Not yet due</span>}
                                    </TableCell>
                                    <TableCell>
                                        {row.guardian_name || row.guardian_phone ? (
                                            <div>
                                                <div className="font-medium text-xs text-slate-800 dark:text-slate-200">{row.guardian_name}</div>
                                                {row.guardian_phone && (
                                                    <a className="inline-flex items-center py-1 text-xs sm:text-sm text-indigo-600 dark:text-indigo-400 font-medium hover:underline" href={`tel:${row.guardian_phone}`}>{row.guardian_phone}</a>
                                                )}
                                            </div>
                                        ) : <span className="text-xs text-slate-400">No guardian on file</span>}
                                    </TableCell>
                                    <TableCell className="text-xs">
                                        <div className="font-mono text-slate-600 dark:text-slate-300">
                                            {row.last_call_at ? new Date(row.last_call_at).toLocaleDateString() : <span className="text-slate-400">Never called</span>}
                                        </div>
                                        <PromiseBadge promise={row.promise} />
                                    </TableCell>
                                    {canCall && (
                                        <TableCellAction className="pr-4">
                                            <Button size="sm" variant="outline" className="h-8 text-xs font-semibold" onClick={() => setCalling(row)}>Record call</Button>
                                        </TableCellAction>
                                    )}
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableShell>
                </>
            )}
            {calling && <CallDialog row={calling} onClose={() => setCalling(null)} />}
        </div>
    );
}

function Stat({ label, value }: { label: string; value: string }) {
    return (
        <div className="rounded-xl sm:rounded-2xl border border-slate-200 p-2.5 sm:p-4 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs">
            <span className="block text-[10px] sm:text-xs uppercase font-medium text-slate-500 truncate">{label}</span>
            <span className="text-sm sm:text-2xl font-bold text-slate-900 dark:text-white truncate block">{value}</span>
        </div>
    );
}
