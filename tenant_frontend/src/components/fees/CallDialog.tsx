"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogBody,
    DialogContent,
    DialogFooter,
} from "@/components/ui/dialog";
import { ModalHeader } from "@/components/ui/modal-header";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    FormGrid,
    FormFieldWrapper,
} from "@/components/ui/form-layout";
import { useRecordCall, useStudentCalls } from "@/hooks/useFees";
import type { DueRow, PromiseInfo } from "@/types/FeeDues";
import { Loader2, PhoneCall } from "lucide-react";

export const money = (value: string) =>
    Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function PromiseBadge({ promise }: { promise: PromiseInfo | null }) {
    if (!promise) return null;
    const label = promise.status === "kept" ? "Promise kept" : promise.status === "broken" ? "Promise broken" : "Promised";
    return (
        <span className="mt-1 block">
            <Badge variant={promise.status === "broken" ? "destructive" : promise.status === "kept" ? "default" : "secondary"}>
                {label}: {promise.amount ? `₹${money(promise.amount)} by ` : ""}{promise.date}
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

    const handleSave = () => {
        record.mutate(
            {
                student: row.student,
                outcome,
                note: note.trim(),
                promise_date: promised ? date : null,
                promise_amount: promised && amount ? amount : null,
            },
            {
                onSuccess: () => {
                    setNote("");
                    setDate("");
                    setAmount("");
                    setOutcome("reached");
                },
            },
        );
    };

    return (
        <Dialog open onOpenChange={(o) => !o && onClose()}>
            <DialogContent className="max-w-lg max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                <ModalHeader
                    icon={<PhoneCall className="w-5 h-5 text-sky-600" />}
                    title={`Record Fee Follow-up Call: ${row.name}`}
                    subtitle={`₹${money(row.outstanding)} outstanding. Contact: ${row.guardian_name}${row.guardian_phone ? ` (${row.guardian_phone})` : ""}`}
                    onClose={onClose}
                />

                <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-5">
                    <FormFieldWrapper label="Call Outcome" htmlFor="call_outcome" required colSpan="full">
                        <Select value={outcome} onValueChange={setOutcome}>
                            <SelectTrigger id="call_outcome">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="reached">Spoke to the family</SelectItem>
                                <SelectItem value="no_answer">No answer</SelectItem>
                                <SelectItem value="promised">Promised to pay</SelectItem>
                                <SelectItem value="refused">Refused or disputes the fee</SelectItem>
                            </SelectContent>
                        </Select>
                    </FormFieldWrapper>

                    <FormFieldWrapper label="Discussion Details" htmlFor="call_note" required colSpan="full">
                        <Textarea
                            id="call_note"
                            maxLength={500}
                            rows={3}
                            placeholder="Summary of conversation, reasons for delay, next steps..."
                            value={note}
                            onChange={(e) => setNote(e.target.value)}
                        />
                    </FormFieldWrapper>

                    {promised && (
                        <div className="p-4 rounded-xl border border-amber-200/80 dark:border-amber-900/60 bg-amber-50/50 dark:bg-amber-950/20 space-y-3">
                            <span className="text-[11px] font-bold uppercase tracking-wider text-amber-700 dark:text-amber-400">
                                Payment Promise Details
                            </span>
                            <FormGrid>
                                <FormFieldWrapper label="Will Pay By" htmlFor="promise_date" required>
                                    <Input
                                        id="promise_date"
                                        type="date"
                                        value={date}
                                        onChange={(e) => setDate(e.target.value)}
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Promised Amount (Optional)" htmlFor="promise_amount">
                                    <Input
                                        id="promise_amount"
                                        type="number"
                                        min={0}
                                        placeholder="e.g. 5000"
                                        value={amount}
                                        onChange={(e) => setAmount(e.target.value)}
                                    />
                                </FormFieldWrapper>
                            </FormGrid>
                        </div>
                    )}

                    <div className="space-y-2 border-t border-slate-100 dark:border-slate-800 pt-4">
                        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                            Earlier Call History
                        </h4>
                        {(calls.data ?? []).length === 0 && (
                            <p className="text-xs text-slate-400 py-2">No previous calls logged for this student.</p>
                        )}
                        {(calls.data ?? []).map((c) => (
                            <div key={c.id} className="rounded-lg border border-slate-200/80 dark:border-slate-800 p-3 text-xs bg-slate-50/40 dark:bg-slate-900/40 space-y-1">
                                <div className="flex items-center justify-between text-[11px] text-slate-400">
                                    <span>{new Date(c.at).toLocaleString()}</span>
                                    <span className="font-medium text-slate-600 dark:text-slate-300">{c.by} • {c.outcome_label}</span>
                                </div>
                                <p className="text-slate-700 dark:text-slate-300">{c.note}</p>
                                <PromiseBadge promise={c.promise} />
                            </div>
                        ))}
                    </div>
                </DialogBody>

                <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                    <Button variant="outline" onClick={onClose} disabled={record.isPending}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleSave}
                        disabled={record.isPending || !note.trim() || (promised && !date)}
                        className="min-w-[120px]"
                    >
                        {record.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                        Save Call
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
