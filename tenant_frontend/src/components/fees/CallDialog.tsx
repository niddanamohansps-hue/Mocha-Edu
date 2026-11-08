"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useRecordCall, useStudentCalls } from "@/hooks/useFees";
import type { DueRow, PromiseInfo } from "@/types/FeeDues";

export const money = (value: string) => Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });
const selectClass = "h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";

export function PromiseBadge({ promise }: { promise: PromiseInfo | null }) {
    if (!promise) return null;
    const label = promise.status === "kept" ? "Promise kept" : promise.status === "broken" ? "Promise broken" : "Promised";
    return (
        <span className="mt-1 block">
            <Badge variant={promise.status === "broken" ? "destructive" : promise.status === "kept" ? "default" : "secondary"}>
                {label}: {promise.amount ? `${money(promise.amount)} by ` : ""}{promise.date}
            </Badge>
        </span>
    );
}

export function CallDialog({ row, onClose }: { row: DueRow; onClose: () => void }) {
    const calls = useStudentCalls(row.student);
    const record = useRecordCall();
    const [outcome, setOutcome] = useState("reached");
    const [note, setNote] = useState("");
    const [date, setDate] = useState("");
    const [amount, setAmount] = useState("");
    const promised = outcome === "promised";
    return (
        <Dialog open onOpenChange={(o) => !o && onClose()}>
            <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>{row.name}: record a call</DialogTitle>
                </DialogHeader>
                <p className="text-sm text-slate-500">
                    {money(row.outstanding)} outstanding. {row.guardian_name}
                    {row.guardian_phone && <>, <a className="text-indigo-700 underline" href={`tel:${row.guardian_phone}`}>{row.guardian_phone}</a></>}
                </p>
                <div className="grid gap-1.5">
                    <Label>What happened</Label>
                    <select className={selectClass} value={outcome} onChange={(e) => setOutcome(e.target.value)}>
                        <option value="reached">Spoke to the family</option>
                        <option value="no_answer">No answer</option>
                        <option value="promised">Promised to pay</option>
                        <option value="refused">Refused or disputes the fee</option>
                    </select>
                </div>
                <div className="grid gap-1.5">
                    <Label>What was said</Label>
                    <Textarea maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
                </div>
                {promised && (
                    <div className="grid grid-cols-2 gap-3">
                        <div className="grid gap-1.5">
                            <Label>Will pay by</Label>
                            <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
                        </div>
                        <div className="grid gap-1.5">
                            <Label>Amount (optional)</Label>
                            <Input type="number" min={0} value={amount} onChange={(e) => setAmount(e.target.value)} />
                        </div>
                    </div>
                )}
                <Button
                    disabled={record.isPending || !note.trim() || (promised && !date)}
                    onClick={() =>
                        record.mutate(
                            { student: row.student, outcome, note, promise_date: promised ? date : null, promise_amount: promised && amount ? amount : null },
                            { onSuccess: () => { setNote(""); setDate(""); setAmount(""); setOutcome("reached"); } },
                        )
                    }
                >
                    {record.isPending ? "Saving..." : "Save call"}
                </Button>
                <div className="space-y-2 border-t border-slate-100 pt-3 dark:border-slate-800">
                    <h3 className="text-sm font-semibold">Earlier calls</h3>
                    {(calls.data ?? []).length === 0 && <p className="text-sm text-slate-500">None yet.</p>}
                    {(calls.data ?? []).map((c) => (
                        <div key={c.id} className="rounded-lg border border-slate-200 p-2 text-sm dark:border-slate-800">
                            <span className="text-xs text-slate-500">{new Date(c.at).toLocaleString()}, {c.by}: {c.outcome_label}</span>
                            <p>{c.note}</p>
                            <PromiseBadge promise={c.promise} />
                        </div>
                    ))}
                </div>
            </DialogContent>
        </Dialog>
    );
}

