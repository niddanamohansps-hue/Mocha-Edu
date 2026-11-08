"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { useFollowUpDesk, useRecordFollowUp, type FollowUpRow } from "@/hooks/useAdmissions";
import { usePermissions } from "@/providers/PermissionProvider";

const GROUPS = [
    { key: "overdue", title: "Overdue", tone: "destructive" },
    { key: "today", title: "Due today", tone: "default" },
    { key: "upcoming", title: "Coming up this week", tone: "secondary" },
    { key: "unscheduled", title: "No follow-up date set", tone: "outline" },
] as const;

export default function FollowUpsPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("view_admissions")) return <Unauthorized />;
    return <Desk canEdit={isOwner || can("manage_admission_enquiries")} />;
}

function Desk({ canEdit }: { canEdit: boolean }) {
    const [mine, setMine] = useState(false);
    const desk = useFollowUpDesk(mine);
    const [open, setOpen] = useState<FollowUpRow | null>(null);

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Admission follow-ups</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    Families who asked about admission and are waiting for a call. Staff with enquiries due also get a reminder each morning.
                </p>
            </div>
            <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} />
                Only the enquiries assigned to me
            </label>

            {desk.isLoading || !desk.data ? (
                <LoadingState />
            ) : GROUPS.every((g) => desk.data[g.key].length === 0) ? (
                <EmptyState title="Nothing to chase" description="No open enquiry is due a call." />
            ) : (
                GROUPS.map((g) =>
                    desk.data[g.key].length === 0 ? null : (
                        <section key={g.key} className="space-y-2">
                            <h2 className="flex items-center gap-2 text-lg font-semibold">
                                {g.title} <Badge variant={g.tone}>{desk.data[g.key].length}</Badge>
                            </h2>
                            <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900">
                                {desk.data[g.key].map((row) => (
                                    <li key={row.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                                        <span className="space-y-0.5">
                                            <span className="font-medium">{row.student_name}</span>{" "}
                                            <span className="text-xs text-slate-400">{row.level}{row.source ? `, ${row.source}` : ""}</span>
                                            <span className="block text-sm text-slate-600 dark:text-slate-300">
                                                {row.guardian_name}:{" "}
                                                <a className="text-indigo-700 underline" href={`tel:${row.guardian_phone}`}>{row.guardian_phone}</a>
                                            </span>
                                            <span className="block text-xs text-slate-500">
                                                {row.follow_up_date ? `Follow up ${row.follow_up_date}` : `Enquired ${row.enquiry_date}`}
                                                {row.days_overdue > 0 ? `, ${row.days_overdue} days late` : ""}
                                                {row.assigned_to_name ? `, ${row.assigned_to_name}` : ", not assigned"}
                                            </span>
                                        </span>
                                        {canEdit && <Button size="sm" onClick={() => setOpen(row)}>Record call</Button>}
                                    </li>
                                ))}
                            </ul>
                        </section>
                    ),
                )
            )}

            {open && <RecordDialog row={open} onClose={() => setOpen(null)} />}
        </div>
    );
}

function RecordDialog({ row, onClose }: { row: FollowUpRow; onClose: () => void }) {
    const record = useRecordFollowUp();
    const [outcome, setOutcome] = useState<"contacted" | "qualified" | "lost">("contacted");
    const [note, setNote] = useState("");
    const [next, setNext] = useState("");
    const lost = outcome === "lost";

    return (
        <Dialog open onOpenChange={(o) => !o && onClose()}>
            <DialogContent className="max-w-lg">
                <DialogHeader>
                    <DialogTitle>{row.student_name}: record the call</DialogTitle>
                </DialogHeader>
                {row.notes && <p className="max-h-28 overflow-y-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs text-slate-600 dark:bg-slate-900 dark:text-slate-300">{row.notes}</p>}
                <div className="grid gap-1.5">
                    <Label>What happened</Label>
                    <select
                        className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950"
                        value={outcome} onChange={(e) => setOutcome(e.target.value as typeof outcome)}
                    >
                        <option value="contacted">Spoke to the family</option>
                        <option value="qualified">Ready to apply</option>
                        <option value="lost">Not joining (close the enquiry)</option>
                    </select>
                </div>
                <div className="grid gap-1.5">
                    <Label>{lost ? "Why are they not joining?" : "What was said"}</Label>
                    <Textarea value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
                </div>
                {!lost && (
                    <div className="grid gap-1.5">
                        <Label>Call again on (optional)</Label>
                        <Input type="date" value={next} onChange={(e) => setNext(e.target.value)} />
                    </div>
                )}
                <Button
                    disabled={record.isPending || !note.trim()}
                    onClick={() => record.mutate({ id: row.id, outcome, note, next_follow_up: lost ? null : next || null }, { onSuccess: onClose })}
                >
                    {record.isPending ? "Saving..." : "Save"}
                </Button>
            </DialogContent>
        </Dialog>
    );
}
