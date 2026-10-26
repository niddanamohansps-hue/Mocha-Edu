"use client";

import { useState } from "react";
import { CURRENCY } from "@/lib/currency";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { Field, FormDialog, PageHeader, isNonNegativeDecimal } from "@/components/dashboard/library/shared";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { useCategories, useDeleteCategory, useLibrarySettings, useSaveCategory, useUpdateLibrarySettings } from "@/hooks/useLibrary";
import { usePermissions } from "@/providers/PermissionProvider";
import { BookCategory, LibrarySettings } from "@/types/Library";

const whole = (value: string, min: number, max: number) => /^\d+$/.test(value.trim()) && Number(value) >= min && Number(value) <= max;

function RulesForm({ data, canEdit }: { data: LibrarySettings; canEdit: boolean }) {
    const update = useUpdateLibrarySettings();
    const [studentDays, setStudentDays] = useState(String(data.student_loan_days));
    const [staffDays, setStaffDays] = useState(String(data.staff_loan_days));
    const [studentMax, setStudentMax] = useState(String(data.student_max_books));
    const [staffMax, setStaffMax] = useState(String(data.staff_max_books));
    const [renewals, setRenewals] = useState(String(data.max_renewals));
    const [fine, setFine] = useState(String(Number(data.fine_per_day)));
    const [error, setError] = useState<string | null>(null);

    const save = () => {
        if (!whole(studentDays, 1, 365) || !whole(staffDays, 1, 365)) return setError("Loan periods must be whole days, from 1 to 365.");
        if (!whole(studentMax, 1, 50) || !whole(staffMax, 1, 50)) return setError("Books allowed must be a whole number, from 1 to 50.");
        if (!whole(renewals, 0, 20)) return setError("Renewals must be a whole number, from 0 to 20.");
        if (!isNonNegativeDecimal(fine, 2)) return setError("The daily fine must be a number, 0 or more.");
        setError(null);
        update.mutate(
            {
                student_loan_days: Number(studentDays), staff_loan_days: Number(staffDays), student_max_books: Number(studentMax),
                staff_max_books: Number(staffMax), max_renewals: Number(renewals), fine_per_day: fine.trim(),
            },
            { onError: (e) => setError(inventoryErrorMessage(e, "Could not save the rules")) }
        );
    };

    const field = (label: string, id: string, value: string, set: (v: string) => void, hint?: string) => (
        <Field label={label} htmlFor={id} hint={hint}>
            <Input id={id} inputMode="decimal" disabled={!canEdit} value={value} onChange={(e) => set(e.target.value)} />
        </Field>
    );

    return (
        <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-3">
            <h2 className="font-semibold text-slate-900 dark:text-white">Lending rules</h2>
            <div className="grid sm:grid-cols-2 gap-3">
                {field("Students keep a book for (days)", "lr-sdays", studentDays, setStudentDays)}
                {field("Staff keep a book for (days)", "lr-tdays", staffDays, setStaffDays)}
                {field("Books a student may have out", "lr-smax", studentMax, setStudentMax)}
                {field("Books a staff member may have out", "lr-tmax", staffMax, setStaffMax)}
                {field("Times a loan may be renewed", "lr-ren", renewals, setRenewals, "0 means no renewals.")}
                {field(`Fine for each day late (${CURRENCY})`, "lr-fine", fine, setFine, "0 means the library charges no fines.")}
            </div>
            {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
            {canEdit && <Button size="sm" disabled={update.isPending} onClick={save}>Save rules</Button>}
        </section>
    );
}

function CategoryDialog({ category, onClose }: { category: BookCategory | null | undefined; onClose: () => void }) {
    return category === undefined ? null : <CategoryForm key={category?.id ?? "new"} category={category} onClose={onClose} />;
}

function CategoryForm({ category, onClose }: { category: BookCategory | null; onClose: () => void }) {
    const save = useSaveCategory();
    const [name, setName] = useState(category?.name ?? "");
    const [error, setError] = useState<string | null>(null);
    return (
        <FormDialog
            open
            onOpenChange={(o) => !o && onClose()}
            title={category ? "Rename category" : "New category"}
            submitLabel={category ? "Save" : "Add category"}
            pending={save.isPending}
            error={error}
            onSubmit={() => {
                if (!name.trim()) return setError("Enter the category name.");
                setError(null);
                save.mutate({ id: category?.id, name: name.trim() }, { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not save the category")) });
            }}
        >
            <Field label="Name" htmlFor="ct-name"><Input id="ct-name" value={name} maxLength={100} onChange={(e) => setName(e.target.value)} placeholder="e.g. Science" /></Field>
        </FormDialog>
    );
}

export default function LibrarySetupPage() {
    const { can } = usePermissions();
    const canEdit = can("manage_library");
    const settings = useLibrarySettings();
    const categories = useCategories();
    const remove = useDeleteCategory();
    const [editing, setEditing] = useState<BookCategory | null | undefined>(undefined);
    const [deleting, setDeleting] = useState<BookCategory | null>(null);

    if (!can("view_library")) return <ErrorState message="You do not have permission to view the library." />;

    return (
        <div className="space-y-6">
            <PageHeader title="Library setup" description="How long books may be kept, how many at a time, and what late books cost." />
            {settings.isLoading || !settings.data ? (
                settings.isError ? <ErrorState message="Failed to load the rules." onRetry={settings.refetch} /> : <LoadingState className="py-6" />
            ) : (
                <RulesForm
                    key={JSON.stringify(settings.data)}
                    data={settings.data}
                    canEdit={canEdit}
                />
            )}

            <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-3">
                <div className="flex items-center justify-between gap-3">
                    <h2 className="font-semibold text-slate-900 dark:text-white">Categories</h2>
                    {canEdit && <Button size="sm" onClick={() => setEditing(null)}>New category</Button>}
                </div>
                {categories.isLoading ? <LoadingState className="py-4" /> : (categories.data ?? []).length === 0 ? (
                    <p className="text-sm text-slate-500">None yet. Categories help people find books, like Science or Fiction.</p>
                ) : (
                    <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                        {(categories.data ?? []).map((c) => (
                            <li key={c.id} className="py-2 flex flex-wrap items-center gap-3 text-sm">
                                <span className="font-medium">{c.name}</span>
                                <span className="text-xs text-slate-500">{c.books_count} book{c.books_count === 1 ? "" : "s"}</span>
                                {canEdit && (
                                    <span className="ml-auto flex gap-1">
                                        <Button size="sm" variant="ghost" onClick={() => setEditing(c)}>Rename</Button>
                                        <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setDeleting(c)}>Delete</Button>
                                    </span>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
            </section>

            <CategoryDialog category={editing} onClose={() => setEditing(undefined)} />
            <ConfirmationDialog
                open={!!deleting}
                onOpenChange={(o) => !o && setDeleting(null)}
                title={`Delete ${deleting?.name ?? ""}?`}
                description="This only works if no book uses the category."
                confirmLabel="Delete"
                isLoading={remove.isPending}
                onConfirm={() => deleting && remove.mutate(deleting.id, { onSettled: () => setDeleting(null) })}
            />
        </div>
    );
}
