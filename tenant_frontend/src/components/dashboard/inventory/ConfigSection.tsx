"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { Field, FormDialog, Pill } from "@/components/dashboard/inventory/shared";
import { ConfigResource, inventoryErrorMessage, useAllOf, useDeleteConfig, useSaveConfig } from "@/hooks/useInventory";

export interface ConfigField {
    name: string;
    label: string;
    required?: boolean;
    type?: "text" | "email";
    maxLength?: number;
}

type Row = { id: string; name: string; is_active?: boolean } & Record<string, unknown>;

function RowDialog({
    resource,
    title,
    fields,
    row,
    hasActive,
    onClose,
}: {
    resource: ConfigResource;
    title: string;
    fields: ConfigField[];
    row: Row | null;
    hasActive: boolean;
    onClose: () => void;
}) {
    const save = useSaveConfig(resource);
    const [values, setValues] = useState<Record<string, string>>(() =>
        Object.fromEntries(fields.map((f) => [f.name, String(row?.[f.name] ?? "")]))
    );
    const [active, setActive] = useState(row?.is_active ?? true);
    const [error, setError] = useState<string | null>(null);

    const submit = () => {
        const missing = fields.find((f) => f.required && !values[f.name].trim());
        if (missing) return setError(`${missing.label} is required.`);
        setError(null);
        const input: Record<string, unknown> = Object.fromEntries(fields.map((f) => [f.name, values[f.name].trim()]));
        if (hasActive && row) input.is_active = active;
        save.mutate({ id: row?.id, input }, { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not save")) });
    };

    return (
        <FormDialog
            open
            onOpenChange={(open) => !open && onClose()}
            title={`${row ? "Edit" : "Add"} ${title.toLowerCase()}`}
            submitLabel={row ? "Save changes" : "Add"}
            pending={save.isPending}
            error={error}
            onSubmit={submit}
        >
            {fields.map((f) => (
                <Field key={f.name} label={f.label} htmlFor={`cfg-${f.name}`}>
                    <Input
                        id={`cfg-${f.name}`}
                        type={f.type ?? "text"}
                        value={values[f.name]}
                        maxLength={f.maxLength}
                        onChange={(e) => setValues((v) => ({ ...v, [f.name]: e.target.value }))}
                    />
                </Field>
            ))}
            {hasActive && row && (
                <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
                    Active
                </label>
            )}
        </FormDialog>
    );
}

/** A small list with add / edit / delete for one configuration table. */
export function ConfigSection({
    resource,
    title,
    hint,
    fields,
    summary,
    canManage,
    hasActive = false,
}: {
    resource: ConfigResource;
    title: string;
    hint: string;
    fields: ConfigField[];
    summary?: (row: Row) => string;
    canManage: boolean;
    hasActive?: boolean;
}) {
    const { data, isLoading, isError, refetch } = useAllOf<Row>(resource);
    const remove = useDeleteConfig(resource);
    const [editing, setEditing] = useState<Row | null | undefined>(undefined); // undefined = closed, null = new
    const [deleting, setDeleting] = useState<Row | null>(null);

    return (
        <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h2 className="font-semibold text-slate-900 dark:text-white">{title}</h2>
                    <p className="text-xs text-slate-500 mt-0.5">{hint}</p>
                </div>
                {canManage && <Button size="sm" onClick={() => setEditing(null)}>Add</Button>}
            </div>

            {isLoading ? (
                <LoadingState className="py-6" />
            ) : isError ? (
                <ErrorState message={`Failed to load ${title.toLowerCase()}.`} onRetry={refetch} />
            ) : (data ?? []).length === 0 ? (
                <p className="text-sm text-slate-500">None yet.</p>
            ) : (
                <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                    {(data ?? []).map((row) => (
                        <li key={row.id} className="py-2 flex flex-wrap items-center gap-2">
                            <span className="font-medium text-slate-800 dark:text-slate-200">{row.name}</span>
                            {hasActive && row.is_active === false && <Pill className="bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-400">Inactive</Pill>}
                            {summary && <span className="text-xs text-slate-500">{summary(row)}</span>}
                            {canManage && (
                                <span className="ml-auto flex gap-1">
                                    <Button size="sm" variant="ghost" onClick={() => setEditing(row)}>Edit</Button>
                                    <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setDeleting(row)}>Delete</Button>
                                </span>
                            )}
                        </li>
                    ))}
                </ul>
            )}

            {editing !== undefined && (
                <RowDialog key={editing?.id ?? "new"} resource={resource} title={title} fields={fields} row={editing} hasActive={hasActive} onClose={() => setEditing(undefined)} />
            )}
            <ConfirmationDialog
                open={!!deleting}
                onOpenChange={(open) => !open && setDeleting(null)}
                title={`Delete ${deleting?.name ?? ""}?`}
                description="This only works if nothing uses it yet. Otherwise deactivate it instead."
                confirmLabel="Delete"
                isLoading={remove.isPending}
                onConfirm={() => deleting && remove.mutate(deleting.id, { onSettled: () => setDeleting(null) })}
            />
        </section>
    );
}
