"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Field, FormDialog, SELECT_CLASS, formatMoney, isPositiveDecimal } from "@/components/dashboard/payroll/shared";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { useAddAdjustment, useRunAction } from "@/hooks/usePayroll";
import { useStaffMembers } from "@/hooks/useStaff";
import { PAYMENT_METHOD_LABELS, PaymentMethod, PayrollRun } from "@/types/Payroll";

// --- Record the payment -----------------------------------------------------------------------------

export function PayDialog({ run, onClose }: { run: PayrollRun | null; onClose: () => void }) {
    return run ? <PayForm key={run.id} run={run} onClose={onClose} /> : null;
}

function PayForm({ run, onClose }: { run: PayrollRun; onClose: () => void }) {
    const action = useRunAction();
    const [paidOn, setPaidOn] = useState(() => new Date().toISOString().slice(0, 10));
    const [method, setMethod] = useState<PaymentMethod>("bank_transfer");
    const [reference, setReference] = useState("");
    const [error, setError] = useState<string | null>(null);
    return (
        <FormDialog
            open
            onOpenChange={(open) => !open && onClose()}
            title={`Record payment for ${run.month_label}`}
            description={`Total paid out: NPR ${formatMoney(run.total_net)} to ${run.payslip_count} people. After this the payroll is closed.`}
            submitLabel="Mark as paid"
            pending={action.isPending}
            error={error}
            onSubmit={() => {
                if (!paidOn) return setError("Choose the payment date.");
                setError(null);
                action.mutate(
                    { id: run.id, action: "pay", body: { paid_on: paidOn, method, reference: reference.trim() } },
                    { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not record the payment")) }
                );
            }}
        >
            <Field label="Date paid" htmlFor="pay-date">
                <Input id="pay-date" type="date" value={paidOn} onChange={(e) => setPaidOn(e.target.value)} />
            </Field>
            <Field label="How was it paid?" htmlFor="pay-method">
                <select id="pay-method" className={SELECT_CLASS} value={method} onChange={(e) => setMethod(e.target.value as PaymentMethod)}>
                    {(Object.keys(PAYMENT_METHOD_LABELS) as PaymentMethod[]).map((m) => (
                        <option key={m} value={m}>{PAYMENT_METHOD_LABELS[m]}</option>
                    ))}
                </select>
            </Field>
            <Field label="Reference (optional)" htmlFor="pay-reference" hint="A bank batch or cheque number.">
                <Input id="pay-reference" value={reference} maxLength={100} onChange={(e) => setReference(e.target.value)} />
            </Field>
        </FormDialog>
    );
}

// --- Cancel the payroll ------------------------------------------------------------------------------

export function CancelRunDialog({ run, onClose }: { run: PayrollRun | null; onClose: () => void }) {
    return run ? <CancelForm key={run.id} run={run} onClose={onClose} /> : null;
}

function CancelForm({ run, onClose }: { run: PayrollRun; onClose: () => void }) {
    const action = useRunAction();
    const [reason, setReason] = useState("");
    const [error, setError] = useState<string | null>(null);
    return (
        <FormDialog
            open
            onOpenChange={(open) => !open && onClose()}
            title={`Cancel the ${run.month_label} payroll?`}
            description="Nobody is paid from a cancelled payroll. The payslips are kept as a record, and you can start a new payroll for the month."
            submitLabel="Cancel payroll"
            pending={action.isPending}
            error={error}
            onSubmit={() => {
                if (!reason.trim()) return setError("Say why you are cancelling it.");
                setError(null);
                action.mutate(
                    { id: run.id, action: "cancel", body: { reason: reason.trim() } },
                    { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not cancel")) }
                );
            }}
        >
            <Field label="Reason" htmlFor="cancel-run-reason">
                <Input id="cancel-run-reason" value={reason} maxLength={255} onChange={(e) => setReason(e.target.value)} />
            </Field>
        </FormDialog>
    );
}

// --- Add a one-off adjustment ------------------------------------------------------------------------

export function AdjustmentDialog({ run, open, onClose }: { run: PayrollRun; open: boolean; onClose: () => void }) {
    return open ? <AdjustmentForm key={run.id} run={run} onClose={onClose} /> : null;
}

function AdjustmentForm({ run, onClose }: { run: PayrollRun; onClose: () => void }) {
    const add = useAddAdjustment();
    const [search, setSearch] = useState("");
    const { data: staff } = useStaffMembers({ pageSize: 50, search, isActive: true });
    const [person, setPerson] = useState("");
    const [kind, setKind] = useState("earning");
    const [name, setName] = useState("");
    const [amount, setAmount] = useState("");
    const [reason, setReason] = useState("");
    const [error, setError] = useState<string | null>(null);
    return (
        <FormDialog
            open
            onOpenChange={(open) => !open && onClose()}
            title="Add a one-off amount"
            description="For a bonus, an advance being recovered, or a correction from an earlier month. It only affects this month's payslip."
            submitLabel="Add"
            pending={add.isPending}
            error={error}
            onSubmit={() => {
                if (!person) return setError("Choose the staff member.");
                if (!name.trim()) return setError("Give it a name, like “Festival bonus”.");
                if (!isPositiveDecimal(amount, 2)) return setError("Enter an amount above 0 (up to 2 decimals).");
                if (!reason.trim()) return setError("Say why.");
                setError(null);
                add.mutate(
                    { run: run.id, staff: person, kind, name: name.trim(), amount: amount.trim(), reason: reason.trim() },
                    { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not add it")) }
                );
            }}
        >
            <Field label="Staff member" htmlFor="adj-search">
                <div className="space-y-2">
                    <Input id="adj-search" placeholder="Search by name or ID" value={search} onChange={(e) => setSearch(e.target.value)} />
                    <select aria-label="Staff member" className={SELECT_CLASS} value={person} onChange={(e) => setPerson(e.target.value)}>
                        <option value="">Choose a person</option>
                        {(staff?.results ?? []).map((s) => (
                            <option key={s.id} value={s.id}>
                                {s.profile_details.first_name} {s.profile_details.last_name} ({s.employee_id})
                            </option>
                        ))}
                    </select>
                </div>
            </Field>
            <Field label="Is it added or taken off?" htmlFor="adj-kind">
                <select id="adj-kind" className={SELECT_CLASS} value={kind} onChange={(e) => setKind(e.target.value)}>
                    <option value="earning">Added to their pay (bonus, allowance)</option>
                    <option value="deduction">Taken off their pay (advance, fine)</option>
                </select>
            </Field>
            <Field label="Name" htmlFor="adj-name">
                <Input id="adj-name" value={name} maxLength={100} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label="Amount (NPR)" htmlFor="adj-amount">
                <Input id="adj-amount" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
            </Field>
            <Field label="Reason" htmlFor="adj-reason">
                <Input id="adj-reason" value={reason} maxLength={255} onChange={(e) => setReason(e.target.value)} />
            </Field>
        </FormDialog>
    );
}
