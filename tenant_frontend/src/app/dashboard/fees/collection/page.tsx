"use client";

import { useState } from "react";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
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
        <div className="max-w-5xl mx-auto space-y-8">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Fee collection</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    Academic year {year}. <strong>Billed</strong> is what fell due in a month, after discounts. <strong>Collected</strong> is
                    what has been paid against those fees so far. <strong>Received</strong> is the cash that came in during the month,
                    whichever month it was for.
                </p>
            </div>

            {!data ? <LoadingState /> : data.by_month.length === 0 ? (
                <EmptyState title="No fees yet for this year" description="Fees assigned to students will be counted here." />
            ) : (
                <>
                    <div className="grid gap-3 sm:grid-cols-4">
                        <Stat label="Billed" value={money(data.totals.billed)} />
                        <Stat label="Collected" value={money(data.totals.collected)} />
                        <Stat label="Outstanding" value={money(data.totals.outstanding)} />
                        <Stat label="Collection rate" value={data.totals.rate === null ? "-" : `${data.totals.rate}%`} />
                    </div>
                    {data.totals.capped && <p className="text-xs text-amber-700">This school has a very large number of fees, so the figures cover the first part only.</p>}

                    <section className="space-y-2">
                        <h2 className="text-lg font-semibold">By month</h2>
                        <p className="text-xs text-slate-500">Select a month to see it by class.</p>
                        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
                            <table className="w-full min-w-[38rem] text-sm">
                                <thead className="border-b border-slate-200 text-left text-xs uppercase text-slate-500 dark:border-slate-800">
                                    <tr>
                                        <th className="px-4 py-2">Month</th>
                                        <th className="px-4 py-2 text-right">Billed</th>
                                        <th className="px-4 py-2 text-right">Collected</th>
                                        <th className="px-4 py-2 text-right">Outstanding</th>
                                        <th className="px-4 py-2 text-right">Rate</th>
                                        <th className="px-4 py-2 text-right">Received in month</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                    {data.by_month.map((m) => (
                                        <tr
                                            key={m.month}
                                            onClick={() => setMonth(month === m.month ? "" : m.month)}
                                            className={`cursor-pointer transition-colors active:bg-indigo-100 dark:active:bg-indigo-900/40 ${month === m.month ? "bg-indigo-50 dark:bg-indigo-950/30" : "hover:bg-slate-50 dark:hover:bg-slate-800/50"}`}
                                        >
                                            <td className="px-4 py-2.5 sm:py-2 font-medium">{monthName(m.month)}</td>
                                            <td className="px-4 py-2.5 sm:py-2 text-right">{money(m.billed)}</td>
                                            <td className="px-4 py-2.5 sm:py-2 text-right">{money(m.collected)}</td>
                                            <td className="px-4 py-2.5 sm:py-2 text-right">{money(m.outstanding)}</td>
                                            <td className="px-4 py-2.5 sm:py-2 text-right"><Rate line={m} /></td>
                                            <td className="px-4 py-2.5 sm:py-2 text-right">{money(m.received)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </section>

                    <section className="space-y-2">
                        <h2 className="text-lg font-semibold">By class {month ? `for ${monthName(month)}` : "for the whole year"}</h2>
                        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
                            <table className="w-full min-w-[38rem] text-sm">
                                <thead className="border-b border-slate-200 text-left text-xs uppercase text-slate-500 dark:border-slate-800">
                                    <tr>
                                        <th className="px-4 py-2">Class</th>
                                        <th className="px-4 py-2 text-right">Billed</th>
                                        <th className="px-4 py-2 text-right">Collected</th>
                                        <th className="px-4 py-2 text-right">Outstanding</th>
                                        <th className="px-4 py-2 text-right">Rate</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                    {data.by_class.map((c) => (
                                        <tr key={c.level}>
                                            <td className="px-4 py-2 font-medium">{c.level}</td>
                                            <td className="px-4 py-2 text-right">{money(c.billed)}</td>
                                            <td className="px-4 py-2 text-right">{money(c.collected)}</td>
                                            <td className="px-4 py-2 text-right">{money(c.outstanding)}</td>
                                            <td className="px-4 py-2 text-right"><Rate line={c} /></td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
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
        <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
            <span className="block text-xs uppercase text-slate-500">{label}</span>
            <span className="text-2xl font-bold">{value}</span>
        </div>
    );
}
