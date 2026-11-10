"use client";

import { useState } from "react";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { PageHeader } from "@/components/common/PageLayout";
import { Badge } from "@/components/ui/badge";
import {
    Table,
    TableBody,
    TableCell,
    TableCellNumeric,
    TableHead,
    TableHeadNumeric,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import { useCollection } from "@/hooks/useFees";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { usePermissions } from "@/providers/PermissionProvider";
import type { CollectionLine } from "@/types/FeeDues";

const money = (value: string) => Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const monthName = (key: string) =>
    key === "undated" ? "No due date" : new Date(`${key}-01T00:00:00`).toLocaleDateString("en-IN", { month: "long", year: "numeric" });

export default function CollectionPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("view_financial_reports")) return <Unauthorized />;
    return <Content />;
}

function Content() {
    const { selectedYear } = useAcademicYear();
    const year = selectedYear?.name || "";
    const [month, setMonth] = useState("");
    const summary = useCollection(year, month);
    const data = summary.data;

    if (!year) return <EmptyState title="Choose an academic year" description="Pick the year at the top of the page." />;

    return (
        <div className="max-w-7xl mx-auto space-y-6">
            <PageHeader
                title="Fee Collection"
                description={`Academic year ${year}. Billed is what fell due in a month, Collected is what has been paid against those fees, and Received is cash received during the month.`}
                badge={year ? <Badge variant="outline" className="text-xs font-semibold bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-300">{year}</Badge> : undefined}
            />

            {!data ? <LoadingState /> : data.by_month.length === 0 ? (
                <EmptyState
                    title="No fee transactions recorded for this year"
                    description="Fee billing and collection metrics will appear here as soon as student fees are assigned and payment receipts are generated."
                    hint="Use Quick Action › Collect Fee to record your first tuition or bus payment."
                    className="py-16"
                />
            ) : (
                <>
                    <div className="grid grid-cols-2 gap-2 sm:gap-3 sm:grid-cols-4">
                        <Stat label="Billed" value={money(data.totals.billed)} />
                        <Stat label="Collected" value={money(data.totals.collected)} />
                        <Stat label="Outstanding" value={money(data.totals.outstanding)} />
                        <Stat label="Collection rate" value={data.totals.rate === null ? "-" : `${data.totals.rate}%`} />
                    </div>
                    {data.totals.capped && <p className="text-xs text-amber-700">This school has a very large number of fees, so the figures cover the first part only.</p>}

                    <section className="space-y-2">
                        <h2 className="text-lg font-semibold">By month</h2>
                        <p className="text-xs text-slate-500">Select a month to see it by class.</p>
                        <TableShell>
                            <Table className="min-w-[38rem]">
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="sticky left-0 bg-white dark:bg-slate-900 z-10 border-r border-slate-100 dark:border-slate-800 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)] pl-4">Month</TableHead>
                                        <TableHeadNumeric>Billed</TableHeadNumeric>
                                        <TableHeadNumeric>Collected</TableHeadNumeric>
                                        <TableHeadNumeric>Outstanding</TableHeadNumeric>
                                        <TableHeadNumeric>Rate</TableHeadNumeric>
                                        <TableHeadNumeric className="pr-4">Received in month</TableHeadNumeric>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {data.by_month.map((m) => (
                                        <TableRow
                                            key={m.month}
                                            onClick={() => setMonth(month === m.month ? "" : m.month)}
                                            className={`cursor-pointer transition-colors active:bg-indigo-100 dark:active:bg-indigo-900/40 ${month === m.month ? "bg-indigo-50/80 dark:bg-indigo-950/40" : "hover:bg-slate-50/70 dark:hover:bg-slate-800/40"}`}
                                        >
                                            <TableCell className="font-medium sticky left-0 bg-white dark:bg-slate-900 z-10 border-r border-slate-100 dark:border-slate-800 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)] pl-4">{monthName(m.month)}</TableCell>
                                            <TableCellNumeric>{money(m.billed)}</TableCellNumeric>
                                            <TableCellNumeric>{money(m.collected)}</TableCellNumeric>
                                            <TableCellNumeric>{money(m.outstanding)}</TableCellNumeric>
                                            <TableCellNumeric><Rate line={m} /></TableCellNumeric>
                                            <TableCellNumeric className="pr-4">{money(m.received)}</TableCellNumeric>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableShell>
                    </section>

                    <section className="space-y-2">
                        <h2 className="text-lg font-semibold">By class {month ? `for ${monthName(month)}` : "for the whole year"}</h2>
                        <TableShell>
                            <Table className="min-w-[38rem]">
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="sticky left-0 bg-white dark:bg-slate-900 z-10 border-r border-slate-100 dark:border-slate-800 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)] pl-4">Class</TableHead>
                                        <TableHeadNumeric>Billed</TableHeadNumeric>
                                        <TableHeadNumeric>Collected</TableHeadNumeric>
                                        <TableHeadNumeric>Outstanding</TableHeadNumeric>
                                        <TableHeadNumeric className="pr-4">Rate</TableHeadNumeric>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {data.by_class.map((c) => (
                                        <TableRow key={c.level}>
                                            <TableCell className="font-medium sticky left-0 bg-white dark:bg-slate-900 z-10 border-r border-slate-100 dark:border-slate-800 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)] pl-4">{c.level}</TableCell>
                                            <TableCellNumeric>{money(c.billed)}</TableCellNumeric>
                                            <TableCellNumeric>{money(c.collected)}</TableCellNumeric>
                                            <TableCellNumeric>{money(c.outstanding)}</TableCellNumeric>
                                            <TableCellNumeric className="pr-4"><Rate line={c} /></TableCellNumeric>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableShell>
                    </section>
                </>
            )}
        </div>
    );
}

function Rate({ line }: { line: CollectionLine }) {
    if (line.rate === null) return <span className="text-slate-400">-</span>;
    return <span className={line.rate < 50 ? "font-semibold text-red-600" : line.rate < 80 ? "text-amber-700" : "text-emerald-700"}>{line.rate}%</span>;
}

function Stat({ label, value }: { label: string; value: string }) {
    return (
        <div className="rounded-xl sm:rounded-2xl border border-slate-200 p-2.5 sm:p-4 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs">
            <span className="block text-[10px] sm:text-xs uppercase font-medium text-slate-500 truncate">{label}</span>
            <span className="text-sm sm:text-2xl font-bold text-slate-900 dark:text-white truncate block">{value}</span>
        </div>
    );
}
