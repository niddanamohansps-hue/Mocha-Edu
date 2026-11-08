"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
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
        <div className="max-w-6xl mx-auto space-y-6">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Fee dues</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    Every student who owes fees, one row each, with how late their oldest fee is and a number to call.
                </p>
            </div>

            {data && (
                <>
                    <div className="grid gap-3 sm:grid-cols-3">
                        <Stat label="Students owing" value={String(data.totals.students)} />
                        <Stat label="Outstanding" value={money(data.totals.outstanding)} />
                        <Stat label="Of which overdue" value={money(data.totals.overdue)} />
                    </div>
                    <div className="grid gap-2 sm:grid-cols-5">
                        {BANDS.map((b) => (
                            <button
                                key={b.value} type="button" onClick={() => reset(setBand)(band === b.value ? "" : b.value)}
                                className={`rounded-xl border p-3 text-left text-sm ${band === b.value ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950/30" : "border-slate-200 dark:border-slate-800"}`}
                            >
                                <span className="block text-xs text-slate-500">{b.label}</span>
                                <span className="font-semibold">{money(data.totals.bands[b.value])}</span>
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
                <EmptyState title="Nobody owes anything here" description="Change the filters, or all fees in this view are paid." />
            ) : (
                <>
                    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
                        <table className="w-full text-sm">
                            <thead className="border-b border-slate-200 text-left text-xs uppercase text-slate-500 dark:border-slate-800">
                                <tr>
                                    <th className="whitespace-nowrap px-4 py-2">Student</th>
                                    <th className="whitespace-nowrap px-4 py-2 text-right">Outstanding</th>
                                    <th className="whitespace-nowrap px-4 py-2">Oldest due</th>
                                    <th className="whitespace-nowrap px-4 py-2">Parent or guardian</th>
                                    <th className="whitespace-nowrap px-4 py-2">Last call</th>
                                    {canCall && <th className="whitespace-nowrap px-4 py-2" />}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                {data.results.map((row) => (
                                    <tr key={row.student}>
                                        <td className="px-4 py-2">
                                            <span className="font-medium">{row.name}</span>
                                            <span className="block text-xs text-slate-400">{row.enrollment_id}{row.level ? `, ${row.level}${row.section ? ` ${row.section}` : ""}` : ""}</span>
                                        </td>
                                        <td className="px-4 py-2 text-right">
                                            <span className="font-semibold">{money(row.outstanding)}</span>
                                            <span className="block text-xs text-slate-400">{row.fees} {row.fees === 1 ? "fee" : "fees"}</span>
                                        </td>
                                        <td className="px-4 py-2">
                                            {row.oldest_due ? (
                                                <>
                                                    {row.oldest_due}
                                                    <Badge variant={row.days_late > 60 ? "destructive" : "secondary"} className="ml-2">{row.days_late} days late</Badge>
                                                </>
                                            ) : <span className="text-xs text-slate-400">Not yet due</span>}
                                        </td>
                                        <td className="px-4 py-2">
                                            {row.guardian_name || row.guardian_phone ? (
                                                <>
                                                    {row.guardian_name}
                                                    {row.guardian_phone && (
                                                        <a className="block text-indigo-700 underline" href={`tel:${row.guardian_phone}`}>{row.guardian_phone}</a>
                                                    )}
                                                </>
                                            ) : <span className="text-xs text-slate-400">No guardian on file</span>}
                                        </td>
                                        <td className="px-4 py-2 text-xs">
                                            {row.last_call_at ? new Date(row.last_call_at).toLocaleDateString() : <span className="text-slate-400">Never called</span>}
                                            <PromiseBadge promise={row.promise} />
                                        </td>
                                        {canCall && (
                                            <td className="px-4 py-2 text-right">
                                                <Button size="sm" variant="outline" onClick={() => setCalling(row)}>Record call</Button>
                                            </td>
                                        )}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    <div className="flex items-center justify-between text-sm text-slate-500">
                        <span>{data.count} students, page {page} of {pages}</span>
                        <span className="flex gap-2">
                            <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
                            <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
                        </span>
                    </div>
                </>
            )}
            {calling && <CallDialog row={calling} onClose={() => setCalling(null)} />}
        </div>
    );
}

function Stat({ label, value }: { label: string; value: string }) {
    return (
        <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
            <span className="block text-xs uppercase text-slate-500">{label}</span>
            <span className="text-2xl font-bold">{value}</span>
        </div>
    );
}
