"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { Field, FormDialog, PageHeader, Pill, SELECT_CLASS, isNonNegativeDecimal } from "@/components/dashboard/payroll/shared";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { useAllComponents, useDeleteComponent, usePayrollSettings, useSaveComponent, useUpdatePayrollSettings } from "@/hooks/usePayroll";
import { usePermissions } from "@/providers/PermissionProvider";
import { Calculation, ComponentKind, SalaryComponent } from "@/types/Payroll";

function ComponentDialog({ component, onClose }: { component: SalaryComponent | null | undefined; onClose: () => void }) {
    // undefined = closed, null = a new one
    return component === undefined ? null : <ComponentForm key={component?.id ?? "new"} component={component} onClose={onClose} />;
}

function ComponentForm({ component, onClose }: { component: SalaryComponent | null; onClose: () => void }) {
    const save = useSaveComponent();
    const inUse = (component?.assigned_count ?? 0) > 0;
    const [name, setName] = useState(component?.name ?? "");
    const [code, setCode] = useState(component?.code ?? "");
    const [kind, setKind] = useState<ComponentKind>(component?.kind ?? "earning");
    const [calculation, setCalculation] = useState<Calculation>(component?.calculation ?? "fixed");
    const [value, setValue] = useState(component ? String(Number(component.default_value)) : "0");
    const [description, setDescription] = useState(component?.description ?? "");
    const [active, setActive] = useState(component?.is_active ?? true);
    const [error, setError] = useState<string | null>(null);
    return (
        <FormDialog
            open
            onOpenChange={(open) => !open && onClose()}
            title={component ? "Edit pay item" : "New pay item"}
            description="A pay item is an allowance (added to pay) or a deduction (taken off), like transport, provident fund or a staff welfare contribution."
            submitLabel={component ? "Save changes" : "Add pay item"}
            pending={save.isPending}
            error={error}
            onSubmit={() => {
                if (!name.trim() || !code.trim()) return setError("Name and a short code are required.");
                if (!isNonNegativeDecimal(value, 3)) return setError("The value must be a number, 0 or more.");
                if (calculation === "percent_of_basic" && Number(value) > 100) return setError("A percentage cannot be above 100.");
                setError(null);
                save.mutate(
                    { id: component?.id, input: { name: name.trim(), code: code.trim(), kind, calculation, default_value: value.trim(), description: description.trim(), is_active: active } },
                    { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not save")) }
                );
            }}
        >
            <Field label="Name" htmlFor="pc-name"><Input id="pc-name" value={name} maxLength={100} onChange={(e) => setName(e.target.value)} /></Field>
            <Field label="Short code" htmlFor="pc-code" hint="Letters and numbers, like PF or TRANSPORT."><Input id="pc-code" value={code} maxLength={30} onChange={(e) => setCode(e.target.value)} /></Field>
            <Field label="Is it added or taken off?" htmlFor="pc-kind" hint={inUse ? "Cannot change: staff already have this item." : undefined}>
                <select id="pc-kind" className={SELECT_CLASS} value={kind} disabled={inUse} onChange={(e) => setKind(e.target.value as ComponentKind)}>
                    <option value="earning">Added to pay (allowance)</option>
                    <option value="deduction">Taken off pay (deduction)</option>
                </select>
            </Field>
            <Field label="How is the amount worked out?" htmlFor="pc-calc" hint={inUse ? "Cannot change: staff already have this item." : undefined}>
                <select id="pc-calc" className={SELECT_CLASS} value={calculation} disabled={inUse} onChange={(e) => setCalculation(e.target.value as Calculation)}>
                    <option value="fixed">A fixed amount each month</option>
                    <option value="percent_of_basic">A percentage of the basic salary</option>
                </select>
            </Field>
            <Field label={calculation === "percent_of_basic" ? "Usual percentage (%)" : "Usual amount (NPR)"} htmlFor="pc-value" hint="Each person can have their own value when you give them this item.">
                <Input id="pc-value" inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value)} />
            </Field>
            <Field label="Description (optional)" htmlFor="pc-desc"><Input id="pc-desc" value={description} maxLength={255} onChange={(e) => setDescription(e.target.value)} /></Field>
            {component && (
                <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
                    Active (an inactive item is left out of new payslips)
                </label>
            )}
        </FormDialog>
    );
}

function SettingsCard({ canEdit }: { canEdit: boolean }) {
    const { data, isLoading } = usePayrollSettings();
    const update = useUpdatePayrollSettings();
    return (
        <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-3">
            <h2 className="font-semibold text-slate-900 dark:text-white">Payroll rules</h2>
            {isLoading || !data ? (
                <LoadingState className="py-4" />
            ) : (
                <>
                    <label className="flex items-start gap-2 text-sm">
                        <input type="checkbox" className="mt-1" disabled={!canEdit || update.isPending} checked={data.round_to_whole_rupee} onChange={(e) => update.mutate({ round_to_whole_rupee: e.target.checked })} />
                        <span>Round every pay line to a whole rupee<span className="block text-xs text-slate-500">Half a rupee rounds up. Turn off to keep paisa.</span></span>
                    </label>
                    <label className="flex items-start gap-2 text-sm">
                        <input type="checkbox" className="mt-1" disabled={!canEdit || update.isPending} checked={data.require_separate_approver} onChange={(e) => update.mutate({ require_separate_approver: e.target.checked })} />
                        <span>A different person must approve the payroll<span className="block text-xs text-slate-500">The person who calculated it cannot also approve it. Recommended.</span></span>
                    </label>
                    <p className="text-xs text-slate-500">Weekly off days (which decide the working days of each month) are set under Attendance → Attendance Settings.</p>
                </>
            )}
        </section>
    );
}

export default function PayrollSetupPage() {
    const { can } = usePermissions();
    const canEdit = can("manage_salary_structures");
    const { data, isLoading, isError, refetch } = useAllComponents();
    const remove = useDeleteComponent();
    const [editing, setEditing] = useState<SalaryComponent | null | undefined>(undefined);
    const [deleting, setDeleting] = useState<SalaryComponent | null>(null);

    if (!can("view_payroll")) return <ErrorState message="You do not have permission to view payroll setup." />;
    const items = data ?? [];

    return (
        <div className="space-y-6">
            <PageHeader
                title="Payroll setup"
                description="The pay items your school uses, and the rules for calculating payroll."
                actions={canEdit && <Button onClick={() => setEditing(null)}>New pay item</Button>}
            />
            <SettingsCard canEdit={canEdit} />
            <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-3">
                <h2 className="font-semibold text-slate-900 dark:text-white">Pay items</h2>
                {isLoading ? (
                    <LoadingState className="py-6" />
                ) : isError ? (
                    <ErrorState message="Failed to load the pay items." onRetry={refetch} />
                ) : items.length === 0 ? (
                    <p className="text-sm text-slate-500">None yet. Add the allowances and deductions your school uses, then give them to staff on the Salaries tab.</p>
                ) : (
                    <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                        {items.map((c) => (
                            <li key={c.id} className="py-2 flex flex-wrap items-center gap-2 text-sm">
                                <span className="font-medium">{c.name}</span>
                                <Pill className={c.kind === "deduction" ? "bg-red-100 text-red-700" : "bg-emerald-100 text-emerald-700"}>{c.kind === "deduction" ? "Deduction" : "Allowance"}</Pill>
                                {!c.is_active && <Pill className="bg-slate-200 text-slate-600">Inactive</Pill>}
                                <span className="text-xs text-slate-500">
                                    {c.calculation === "percent_of_basic" ? `${Number(c.default_value)}% of basic` : `NPR ${Number(c.default_value).toLocaleString()}`} · given to {c.assigned_count}
                                </span>
                                {canEdit && (
                                    <span className="ml-auto flex gap-1">
                                        <Button size="sm" variant="ghost" onClick={() => setEditing(c)}>Edit</Button>
                                        <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setDeleting(c)}>Delete</Button>
                                    </span>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
            </section>
            <ComponentDialog component={editing} onClose={() => setEditing(undefined)} />
            <ConfirmationDialog
                open={!!deleting}
                onOpenChange={(open) => !open && setDeleting(null)}
                title={`Delete ${deleting?.name ?? ""}?`}
                description="This only works if no staff member has had it. Otherwise make it inactive instead."
                confirmLabel="Delete"
                isLoading={remove.isPending}
                onConfirm={() => deleting && remove.mutate(deleting.id, { onSettled: () => setDeleting(null) })}
            />
        </div>
    );
}
