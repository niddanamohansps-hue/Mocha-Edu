"use client";

import { useState } from "react";
import { LoaderCircle, Plus, Trash2, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogBody, DialogContent, DialogFooter, ModalHeader } from "@/components/ui/dialog";
import { formatIndianCurrency } from "@/lib/currency";
import {
    FeeInstallment,
    useChargePreview,
    useChargeStructure,
    useInstallmentPlan,
    useSaveInstallmentPlan,
} from "@/hooks/useFeeCharging";
import type { FeeStructure } from "@/types/Fees";

const blank = (): FeeInstallment => ({ name: "", percent: "", due_date: "" });

/** Split a fee structure into instalments, preview who it charges, and charge the class. */
export function ChargeClassDialog({ structure, onClose }: { structure: FeeStructure; onClose: () => void }) {
    const { data: plan, isLoading } = useInstallmentPlan(structure.id);
    const save = useSaveInstallmentPlan(structure.id);
    const charge = useChargeStructure(structure.id);
    // Unsaved edits; null means "show what is saved".
    const [draft, setDraft] = useState<FeeInstallment[] | null>(null);
    const dirty = draft !== null;
    const saved = (plan?.installments ?? []).map(({ name, percent, due_date }) => ({ name, percent, due_date }));
    const rows = draft ?? saved;
    const setRows = (update: (prev: FeeInstallment[]) => FeeInstallment[]) => setDraft(update(rows));
    const setDirty = (value: boolean) => { if (!value) setDraft(null); };
    const preview = useChargePreview(structure.id, !!plan && !dirty);

    const total = rows.reduce((sum, r) => sum + (Number(r.percent) || 0), 0);
    const locked = plan?.locked ?? false;
    const edit = (i: number, patch: Partial<FeeInstallment>) => {
        
        setRows((prev) => prev.map((r, j) => (j === i ? { ...r, ...patch } : r)));
    };
    const planValid = rows.length === 0 || (Math.abs(total - 100) < 0.001 && rows.every((r) => r.name.trim() && r.due_date && Number(r.percent) > 0));
    const p = preview.data;
    const target = [structure.level_name || "All classes", structure.section_name ? `Section ${structure.section_name}` : ""].filter(Boolean).join(" · ");

    return (
        <Dialog open onOpenChange={(o) => !o && onClose()}>
            <DialogContent className="max-w-2xl max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                <ModalHeader
                    icon={<Users className="w-5 h-5 text-sky-600" />}
                    title={`Charge ${structure.fee_head_name} to class`}
                    subtitle={`${formatIndianCurrency(structure.amount)} · ${target} · ${structure.academic_year}`}
                    onClose={onClose}
                />
                <DialogBody className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
                    <section className="space-y-3">
                        <div className="flex items-center justify-between">
                            <h3 className="text-sm font-semibold">Instalments</h3>
                            {!locked && (
                                <Button type="button" variant="outline" size="sm" onClick={() => { setRows((r) => [...r, blank()]); }}>
                                    <Plus className="h-3.5 w-3.5" /> Add instalment
                                </Button>
                            )}
                        </div>
                        {isLoading ? (
                            <LoaderCircle className="h-4 w-4 animate-spin" />
                        ) : rows.length === 0 ? (
                            <p className="text-xs text-slate-500">
                                No instalments: the full amount is charged once{structure.due_date ? `, due ${structure.due_date}` : ""}.
                                {!locked && " Add instalments to split it into terms."}
                            </p>
                        ) : (
                            <div className="space-y-2">
                                {rows.map((r, i) => (
                                    <div key={i} className="grid grid-cols-[1fr_90px_150px_32px] gap-2 items-end">
                                        <div className="grid gap-1">
                                            <Label htmlFor={`inst-name-${i}`} className="text-xs">Name</Label>
                                            <Input id={`inst-name-${i}`} value={r.name} disabled={locked} placeholder={`Term ${i + 1}`} onChange={(e) => edit(i, { name: e.target.value })} />
                                        </div>
                                        <div className="grid gap-1">
                                            <Label htmlFor={`inst-pct-${i}`} className="text-xs">Percent</Label>
                                            <Input id={`inst-pct-${i}`} type="number" inputMode="decimal" value={r.percent} disabled={locked} onChange={(e) => edit(i, { percent: e.target.value })} />
                                        </div>
                                        <div className="grid gap-1">
                                            <Label htmlFor={`inst-due-${i}`} className="text-xs">Due date</Label>
                                            <Input id={`inst-due-${i}`} type="date" value={r.due_date} disabled={locked} onChange={(e) => edit(i, { due_date: e.target.value })} />
                                        </div>
                                        {!locked && (
                                            <Button type="button" variant="ghost" size="icon" aria-label={`Remove instalment ${i + 1}`} onClick={() => { setRows((prev) => prev.filter((_, j) => j !== i)); }}>
                                                <Trash2 className="h-4 w-4" />
                                            </Button>
                                        )}
                                    </div>
                                ))}
                                <p className={`text-xs ${Math.abs(total - 100) < 0.001 ? "text-emerald-600" : "text-rose-600"}`}>
                                    Adds up to {Number(total.toFixed(2))}%{Math.abs(total - 100) < 0.001 ? "" : " (must be 100%)"}
                                </p>
                            </div>
                        )}
                        {locked && <p className="text-xs text-slate-500">Students have been charged from this structure, so its instalments are fixed.</p>}
                        {dirty && !locked && (
                            <div className="flex gap-2">
                                <Button size="sm" disabled={!planValid || save.isPending} onClick={() => save.mutate(rows, { onSuccess: () => setDirty(false) })}>
                                    {save.isPending && <LoaderCircle className="h-4 w-4 animate-spin" />} Save instalments
                                </Button>
                                <Button size="sm" variant="outline" onClick={() => setDirty(false)}>Undo changes</Button>
                            </div>
                        )}
                    </section>

                    <section className="space-y-3">
                        <h3 className="text-sm font-semibold">Who will be charged</h3>
                        {dirty ? (
                            <p className="text-xs text-slate-500">Save the instalments to see the preview.</p>
                        ) : preview.isLoading ? (
                            <LoaderCircle className="h-4 w-4 animate-spin" />
                        ) : preview.isError ? (
                            <p className="text-xs text-rose-600">Could not load the preview.</p>
                        ) : p ? (
                            <>
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                                    <Stat label="Students to charge" value={String(p.students_to_charge)} />
                                    <Stat label="Already charged" value={String(p.students_already_charged)} />
                                    <Stat label="Amount to charge" value={formatIndianCurrency(p.amount_to_charge)} />
                                    <Stat label="Concessions" value={formatIndianCurrency(p.concession_total)} />
                                </div>
                                {p.students.length === 0 ? (
                                    <p className="text-xs text-slate-500">No active students are in this class for {structure.academic_year}.</p>
                                ) : (
                                    <div className="max-h-56 overflow-y-auto rounded-lg border border-slate-200 dark:border-slate-800">
                                        <table className="w-full text-xs">
                                            <thead className="bg-slate-50 dark:bg-slate-800/60 text-left">
                                                <tr><th className="px-3 py-2">Student</th><th className="px-3 py-2">Concession</th><th className="px-3 py-2 text-right">Status</th></tr>
                                            </thead>
                                            <tbody>
                                                {p.students.map((s) => (
                                                    <tr key={s.student} className="border-t border-slate-100 dark:border-slate-800">
                                                        <td className="px-3 py-1.5">{s.name}{s.section && <span className="text-slate-400"> · {s.section}</span>}</td>
                                                        <td className="px-3 py-1.5">{s.concessions ? `${s.concessions} (−${formatIndianCurrency(s.discount)})` : "—"}</td>
                                                        <td className="px-3 py-1.5 text-right">{s.new_fees ? `${s.new_fees} new` : "Already charged"}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </>
                        ) : null}
                    </section>
                </DialogBody>
                <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800">
                    <Button variant="outline" onClick={onClose}>Close</Button>
                    <Button
                        disabled={dirty || !p || p.fees_to_create === 0 || charge.isPending}
                        onClick={() => {
                            if (!p) return;
                            if (!window.confirm(`Charge ${p.students_to_charge} students ${formatIndianCurrency(p.amount_to_charge)} in total?`)) return;
                            charge.mutate(undefined, { onSuccess: onClose });
                        }}
                    >
                        {charge.isPending && <LoaderCircle className="h-4 w-4 animate-spin" />}
                        {p && p.fees_to_create > 0 ? `Charge ${p.students_to_charge} students` : "Nothing to charge"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

function Stat({ label, value }: { label: string; value: string }) {
    return (
        <div className="rounded-lg border border-slate-200 dark:border-slate-800 px-3 py-2">
            <div className="text-[11px] text-slate-500">{label}</div>
            <div className="font-semibold text-sm">{value}</div>
        </div>
    );
}
