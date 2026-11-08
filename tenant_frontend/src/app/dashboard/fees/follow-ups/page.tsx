"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { CallDialog, PromiseBadge, money } from "@/components/fees/CallDialog";
import { useFollowUpDesk } from "@/hooks/useFees";
import { usePermissions } from "@/providers/PermissionProvider";
import type { DueRow } from "@/types/FeeDues";

const GROUPS = [
    { key: "broken", title: "Broken promises", hint: "They said they would pay and did not.", tone: "destructive" },
    { key: "due_today", title: "Promised for today", hint: "Check whether the money has come in.", tone: "default" },
    { key: "uncalled", title: "Overdue, not called for two weeks", hint: "Oldest dues first.", tone: "secondary" },
] as const;

export default function FeeFollowUpsPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("view_financial_reports")) return <Unauthorized />;
    return <Desk canCall={isOwner || can("collect_payments")} />;
}

function Desk({ canCall }: { canCall: boolean }) {
    const desk = useFollowUpDesk();
    const [calling, setCalling] = useState<DueRow | null>(null);
    const data = desk.data;

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Fee follow-ups</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    Who to call about unpaid fees today. People who collect payments also get a reminder each morning when a promise
                    has been broken or falls due.
                </p>
            </div>
            {!data ? <LoadingState /> : GROUPS.every((g) => data.summary[g.key] === 0) ? (
                <EmptyState title="Nothing to chase today" description="No broken promises, nothing promised for today, and nobody overdue has gone uncalled." />
            ) : (
                GROUPS.map((g) =>
                    data[g.key].length === 0 ? null : (
                        <section key={g.key} className="space-y-2">
                            <h2 className="flex items-center gap-2 text-lg font-semibold">
                                {g.title} <Badge variant={g.tone}>{data.summary[g.key]}</Badge>
                            </h2>
                            <p className="text-xs text-slate-500">{g.hint}</p>
                            <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900">
                                {data[g.key].map((row) => (
                                    <li key={row.student} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                                        <span className="space-y-0.5">
                                            <span className="font-medium">{row.name}</span>{" "}
                                            <span className="text-xs text-slate-400">{row.enrollment_id}{row.level ? `, ${row.level}${row.section ? ` ${row.section}` : ""}` : ""}</span>
                                            <span className="block text-sm">
                                                {money(row.outstanding)} outstanding, oldest {row.days_late} days late
                                            </span>
                                            <span className="block text-sm text-slate-600 dark:text-slate-300">
                                                {row.guardian_name || "No guardian on file"}
                                                {row.guardian_phone && <>: <a className="text-indigo-700 underline" href={`tel:${row.guardian_phone}`}>{row.guardian_phone}</a></>}
                                            </span>
                                            <PromiseBadge promise={row.promise} />
                                        </span>
                                        {canCall && <Button size="sm" onClick={() => setCalling(row)}>Record call</Button>}
                                    </li>
                                ))}
                            </ul>
                            {data.summary[g.key] > data[g.key].length && (
                                <p className="text-xs text-slate-500">Showing the first {data[g.key].length} of {data.summary[g.key]}. See the full list on Fee Dues.</p>
                            )}
                        </section>
                    ),
                )
            )}
            {calling && <CallDialog row={calling} onClose={() => setCalling(null)} />}
        </div>
    );
}
