"use client";

import { CURRENCY } from "@/lib/currency";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { LoadingState } from "@/components/feedback/LoadingState";
import { Field, FormDialog, SELECT_CLASS, formatDate, formatMoney, isNonNegativeDecimal, isPositiveDecimal } from "@/components/dashboard/payroll/shared";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import {
    useAllComponents, useAssignComponent, useEndComponent, useSalaryHistory, useSetSalary, useStaffComponents, useStructure,
} from "@/hooks/usePayroll";
import { useStaffMembers } from "@/hooks/useStaff";
import { usePermissions } from "@/providers/PermissionProvider";

// --- Set a salary ------------------------------------------------------------------------------------------

export function SetSalaryDialog({ open, onClose, staffId, staffName }: { open: boolean; onClose: () => void; staffId?: string; staffName?: string }) {
    return open ? <SetSalaryForm key={staffId ?? "new"} onClose={onClose} staffId={staffId} staffName={staffName} /> : null;
}

function SetSalaryForm({ onClose, staffId, staffName }: { onClose: () => void; staffId?: string; staffName?: string }) {
    const set = useSetSalary();
    const [search, setSearch] = useState("");
    const { data: staff } = useStaffMembers({ pageSize: 50, search, isActive: true });
    const [person, setPerson] = useState(staffId ?? "");
    const [amount, setAmount] = useState("");
    const [from, setFrom] = useState(() => new Date().toISOString().slice(0, 10));
    const [note, setNote] = useState("");
    const [error, setError] = useState<string | null>(null);
    return (
        <FormDialog
            open
            onOpenChange={(open) => !open && onClose()}
            title={staffName ? `New salary for ${staffName}` : "Set a salary"}
            description="Salary is the basic monthly pay. A change never rewrites the past: payslips already made keep their old amounts."
            submitLabel="Save salary"
            pending={set.isPending}
            error={error}
            onSubmit={() => {
                if (!person) return setError("Choose the staff member.");
                if (!isPositiveDecimal(amount, 2)) return setError("Enter the monthly salary (above 0, up to 2 decimals).");
                if (!from) return setError("Choose the date it starts.");
                setError(null);
                set.mutate(
                    { staff: person, basic_amount: amount.trim(), effective_from: from, note: note.trim() },
                    { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not save the salary")) }
                );
            }}
        >
            {!staffId && (
                <Field label="Staff member" htmlFor="sal-search">
                    <div className="space-y-2">
                        <Input id="sal-search" placeholder="Search by name or ID" value={search} onChange={(e) => setSearch(e.target.value)} />
                        <select aria-label="Staff member" className={SELECT_CLASS} value={person} onChange={(e) => setPerson(e.target.value)}>
                            <option value="">Choose a person</option>
                            {(staff?.results ?? []).map((s) => (
                                <option key={s.id} value={s.id}>{s.profile_details.first_name} {s.profile_details.last_name} ({s.employee_id})</option>
                            ))}
                        </select>
                    </div>
                </Field>
            )}
            <Field label={`Basic salary per month (${CURRENCY})`} htmlFor="sal-amount">
                <Input id="sal-amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </Field>
            <Field label="Starts from" htmlFor="sal-from" hint="The first day this salary applies. Use the 1st of a month for a clean change.">
                <Input id="sal-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
            </Field>
            <Field label="Note (optional)" htmlFor="sal-note">
                <Input id="sal-note" value={note} maxLength={255} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Yearly raise" />
            </Field>
        </FormDialog>
    );
}

// --- One person's pay structure ---------------------------------------------------------------------------------

export function StructureDialog({ staffId, staffName, onClose }: { staffId: string | null; staffName: string; onClose: () => void }) {
    return (
        <Dialog open={!!staffId} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
                {staffId && <StructureBody staffId={staffId} staffName={staffName} />}
            </DialogContent>
        </Dialog>
    );
}

function StructureBody({ staffId, staffName }: { staffId: string; staffName: string }) {
    const { can } = usePermissions();
    const canEdit = can("manage_salary_structures");
    const structure = useStructure(staffId);
    const history = useSalaryHistory(staffId);
    const assigned = useStaffComponents(staffId);
    const components = useAllComponents();
    const assign = useAssignComponent();
    const end = useEndComponent();
    const [componentId, setComponentId] = useState("");
    const [value, setValue] = useState("");
    const [from, setFrom] = useState(() => new Date().toISOString().slice(0, 10));
    const [error, setError] = useState<string | null>(null);
    const [raising, setRaising] = useState(false);
    const today = new Date().toISOString().slice(0, 10);

    const held = new Set((assigned.data?.results ?? []).map((a) => a.component));
    const available = (components.data ?? []).filter((c) => c.is_active && !held.has(c.id));
    const chosen = available.find((c) => c.id === componentId);

    const submit = () => {
        if (!chosen) return setError("Choose a pay item.");
        if (value.trim() && !isNonNegativeDecimal(value, 3)) return setError("The value must be a number, 0 or more.");
        setError(null);
        assign.mutate(
            { staff: staffId, component: chosen.id, effective_from: from, value: value.trim() || null },
            { onSuccess: () => { setComponentId(""); setValue(""); }, onError: (e) => setError(inventoryErrorMessage(e, "Could not add it")) }
        );
    };

    return (
        <div className="space-y-5">
            <DialogHeader>
                <DialogTitle>{staffName}</DialogTitle>
                <DialogDescription>What this person is paid for a full month, and the items it is made of.</DialogDescription>
            </DialogHeader>

            {structure.isLoading ? (
                <LoadingState className="py-6" />
            ) : structure.data ? (
                <section className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden text-sm">
                    <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                        {structure.data.lines.map((l) => (
                            <li key={l.code} className="px-4 py-2 flex justify-between gap-3">
                                <span>{l.name}{l.detail && l.detail !== "fixed" ? <span className="ml-2 text-xs text-slate-500">{l.detail}</span> : null}</span>
                                <span className={`font-medium ${l.kind === "deduction" ? "text-red-600" : ""}`}>{l.kind === "deduction" ? "−" : ""}{formatMoney(l.amount)}</span>
                            </li>
                        ))}
                        <li className="px-4 py-2 flex justify-between font-bold bg-slate-50 dark:bg-slate-800/40">
                            <span>Net pay for a full month</span>
                            <span className={structure.data.net_is_negative ? "text-red-600" : ""}>{formatMoney(structure.data.net)}</span>
                        </li>
                    </ul>
                </section>
            ) : (
                <p className="text-sm text-slate-500">No salary is set yet. Set one first.</p>
            )}

            {canEdit && (
                <Button size="sm" variant="outline" onClick={() => setRaising(true)}>{structure.data ? "Change the salary" : "Set the salary"}</Button>
            )}
            <SetSalaryDialog open={raising} onClose={() => setRaising(false)} staffId={staffId} staffName={staffName} />

            <section className="space-y-2">
                <h3 className="font-semibold">Pay items this person has</h3>
                {(assigned.data?.results ?? []).length === 0 ? (
                    <p className="text-sm text-slate-500">None. Add allowances or deductions below.</p>
                ) : (
                    <ul className="divide-y divide-slate-100 dark:divide-slate-800 rounded-2xl border border-slate-200 dark:border-slate-800 text-sm">
                        {(assigned.data?.results ?? []).map((a) => (
                            <li key={a.id} className="px-4 py-2 flex flex-wrap items-center gap-2">
                                <span className="font-medium">{a.component_name}</span>
                                <span className="text-slate-500">
                                    {a.kind === "deduction" ? "deduction" : "earning"} · {a.calculation === "percent_of_basic" ? `${Number(a.effective_value)}% of basic` : `${CURRENCY} ${formatMoney(Number(a.effective_value).toFixed(2))}`}
                                    {a.value !== null ? " (set for this person)" : ""} · from {formatDate(a.effective_from)}
                                </span>
                                {canEdit && (
                                    <Button size="sm" variant="ghost" className="ml-auto" disabled={end.isPending} onClick={() => end.mutate({ id: a.id, effective_to: today })}>
                                        End today
                                    </Button>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
                {canEdit && (
                    <div className="rounded-2xl border border-slate-200 dark:border-slate-800 p-4 space-y-3">
                        <p className="text-sm font-medium">Add a pay item</p>
                        <div className="grid sm:grid-cols-3 gap-3">
                            <select aria-label="Pay item" className={SELECT_CLASS} value={componentId} onChange={(e) => setComponentId(e.target.value)}>
                                <option value="">Choose an item</option>
                                {available.map((c) => (
                                    <option key={c.id} value={c.id}>{c.name} ({c.kind === "deduction" ? "deduction" : "earning"})</option>
                                ))}
                            </select>
                            <Input
                                aria-label="Value for this person (optional)"
                                inputMode="decimal"
                                placeholder={chosen ? `Default ${Number(chosen.default_value)}${chosen.calculation === "percent_of_basic" ? "%" : ""}` : "Value (optional)"}
                                value={value}
                                onChange={(e) => setValue(e.target.value)}
                            />
                            <Input aria-label="Starts from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
                        </div>
                        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
                        <Button size="sm" disabled={assign.isPending} onClick={submit}>Add</Button>
                    </div>
                )}
            </section>

            <section className="space-y-2">
                <h3 className="font-semibold">Salary history</h3>
                <ul className="text-sm space-y-1">
                    {(history.data?.results ?? []).map((h) => (
                        <li key={h.id} className="flex justify-between gap-3">
                            <span>from {formatDate(h.effective_from)}{h.note ? ` · ${h.note}` : ""}</span>
                            <span className="font-medium">{formatMoney(h.basic_amount)}</span>
                        </li>
                    ))}
                    {(history.data?.results ?? []).length === 0 && <li className="text-slate-500">No salary recorded.</li>}
                </ul>
            </section>
        </div>
    );
}
