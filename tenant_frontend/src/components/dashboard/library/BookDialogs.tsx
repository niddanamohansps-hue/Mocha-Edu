"use client";

import { CURRENCY } from "@/lib/currency";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { LoadingState } from "@/components/feedback/LoadingState";
import { Field, FormDialog, Pill, SELECT_CLASS, formatMoney, isNonNegativeDecimal } from "@/components/dashboard/library/shared";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { useCategories, useCopies, useDeleteCopy, useSaveBook, useSaveCopy } from "@/hooks/useLibrary";
import { usePermissions } from "@/providers/PermissionProvider";
import { Book, COPY_STATUS_LABELS } from "@/types/Library";

// --- A book --------------------------------------------------------------------------------------

export function BookDialog({ book, onClose }: { book: Book | null | undefined; onClose: () => void }) {
    // undefined = closed, null = a new one
    return book === undefined ? null : <BookForm key={book?.id ?? "new"} book={book} onClose={onClose} />;
}

function BookForm({ book, onClose }: { book: Book | null; onClose: () => void }) {
    const save = useSaveBook();
    const categories = useCategories();
    const [title, setTitle] = useState(book?.title ?? "");
    const [author, setAuthor] = useState(book?.author ?? "");
    const [isbn, setIsbn] = useState(book?.isbn ?? "");
    const [category, setCategory] = useState(book?.category ?? "");
    const [publisher, setPublisher] = useState(book?.publisher ?? "");
    const [year, setYear] = useState(book?.publication_year ? String(book.publication_year) : "");
    const [shelf, setShelf] = useState(book?.shelf_location ?? "");
    const [price, setPrice] = useState(book?.price ? String(Number(book.price)) : "");
    const [active, setActive] = useState(book?.is_active ?? true);
    const [error, setError] = useState<string | null>(null);
    return (
        <FormDialog
            open
            onOpenChange={(open) => !open && onClose()}
            title={book ? "Edit book" : "New book"}
            description="Add the title here, then add its copies. Each physical copy is lent out on its own."
            submitLabel={book ? "Save changes" : "Add book"}
            pending={save.isPending}
            error={error}
            onSubmit={() => {
                const yearValue = year.trim() ? Number(year) : null;
                if (!title.trim()) return setError("Enter the title.");
                if (yearValue !== null && (!Number.isInteger(yearValue) || yearValue < 1000)) return setError("Enter a real year, like 2019.");
                if (price.trim() && !isNonNegativeDecimal(price, 2)) return setError("The price must be a number, 0 or more.");
                setError(null);
                save.mutate(
                    {
                        id: book?.id,
                        input: {
                            title: title.trim(), author: author.trim(), isbn: isbn.trim(), category: category || null,
                            publisher: publisher.trim(), publication_year: yearValue, shelf_location: shelf.trim(),
                            price: price.trim() || null, ...(book ? { is_active: active } : {}),
                        },
                    },
                    { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not save the book")) }
                );
            }}
        >
            <Field label="Title" htmlFor="bk-title"><Input id="bk-title" value={title} maxLength={255} onChange={(e) => setTitle(e.target.value)} /></Field>
            <Field label="Author (optional)" htmlFor="bk-author"><Input id="bk-author" value={author} maxLength={255} onChange={(e) => setAuthor(e.target.value)} /></Field>
            <Field label="ISBN (optional)" htmlFor="bk-isbn"><Input id="bk-isbn" value={isbn} maxLength={20} onChange={(e) => setIsbn(e.target.value)} /></Field>
            <Field label="Category (optional)" htmlFor="bk-cat">
                <select id="bk-cat" className={SELECT_CLASS} value={category} onChange={(e) => setCategory(e.target.value)}>
                    <option value="">No category</option>
                    {(categories.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
            </Field>
            <Field label="Publisher (optional)" htmlFor="bk-pub"><Input id="bk-pub" value={publisher} maxLength={150} onChange={(e) => setPublisher(e.target.value)} /></Field>
            <Field label="Year published (optional)" htmlFor="bk-year"><Input id="bk-year" inputMode="numeric" value={year} onChange={(e) => setYear(e.target.value)} /></Field>
            <Field label="Shelf (optional)" htmlFor="bk-shelf"><Input id="bk-shelf" value={shelf} maxLength={100} onChange={(e) => setShelf(e.target.value)} placeholder="e.g. Rack 3, shelf B" /></Field>
            <Field label={`Price (${CURRENCY}, optional)`} htmlFor="bk-price" hint="Charged to the borrower if a copy is lost. Leave empty to charge nothing.">
                <Input id="bk-price" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />
            </Field>
            {book && (
                <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
                    In the catalogue (switch off to stop lending this title)
                </label>
            )}
        </FormDialog>
    );
}

// --- The copies of one book ----------------------------------------------------------------------

export function CopiesDialog({ book, onClose }: { book: Book | null; onClose: () => void }) {
    return (
        <Dialog open={!!book} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                {book && <CopiesBody book={book} />}
            </DialogContent>
        </Dialog>
    );
}

function CopiesBody({ book }: { book: Book }) {
    const { can } = usePermissions();
    const canEdit = can("manage_library");
    const { data, isLoading } = useCopies(book.id);
    const save = useSaveCopy();
    const remove = useDeleteCopy();
    const [accession, setAccession] = useState("");
    const [error, setError] = useState<string | null>(null);
    const copies = data?.results ?? [];

    return (
        <div className="space-y-5">
            <DialogHeader>
                <DialogTitle>{book.title}</DialogTitle>
                <DialogDescription>
                    {book.author ? `${book.author} · ` : ""}{book.copies_available} of {book.copies_total} copies on the shelf
                    {book.price ? ` · lost copy costs ${CURRENCY} ${formatMoney(book.price)}` : ""}
                </DialogDescription>
            </DialogHeader>

            {isLoading ? (
                <LoadingState className="py-6" />
            ) : copies.length === 0 ? (
                <p className="text-sm text-slate-500">No copies yet.{canEdit ? " Add the first one below." : ""}</p>
            ) : (
                <ul className="divide-y divide-slate-100 dark:divide-slate-800 rounded-2xl border border-slate-200 dark:border-slate-800 text-sm">
                    {copies.map((c) => (
                        <li key={c.id} className="px-4 py-2 flex flex-wrap items-center gap-x-3 gap-y-1">
                            <span className="font-medium">{c.accession_number}</span>
                            <Pill className={
                                c.status === "available" ? "bg-emerald-100 text-emerald-700"
                                    : c.status === "issued" ? "bg-sky-100 text-sky-700"
                                    : c.status === "lost" ? "bg-red-100 text-red-700"
                                    : "bg-slate-200 text-slate-600"
                            }>{COPY_STATUS_LABELS[c.status]}</Pill>
                            {c.borrower_name && <span className="text-xs text-slate-500">with {c.borrower_name}</span>}
                            {canEdit && (
                                <span className="ml-auto flex gap-1">
                                    {c.status === "available" && (
                                        <Button size="sm" variant="ghost" disabled={save.isPending} onClick={() => save.mutate({ id: c.id, input: { status: "withdrawn" } })}>Withdraw</Button>
                                    )}
                                    {(c.status === "withdrawn" || c.status === "lost") && (
                                        <Button size="sm" variant="ghost" disabled={save.isPending} onClick={() => save.mutate({ id: c.id, input: { status: "available" } })}>
                                            {c.status === "lost" ? "Found" : "Put back"}
                                        </Button>
                                    )}
                                    {c.status !== "issued" && (
                                        <Button size="sm" variant="ghost" className="text-red-600" disabled={remove.isPending} onClick={() => remove.mutate(c.id)}>Delete</Button>
                                    )}
                                </span>
                            )}
                        </li>
                    ))}
                </ul>
            )}

            {canEdit && (
                <form
                    className="rounded-2xl border border-slate-200 dark:border-slate-800 p-4 space-y-3"
                    onSubmit={(e) => {
                        e.preventDefault();
                        if (!accession.trim()) return setError("Enter the accession number printed on the book.");
                        setError(null);
                        save.mutate(
                            { input: { book: book.id, accession_number: accession.trim() } },
                            { onSuccess: () => setAccession(""), onError: (err) => setError(inventoryErrorMessage(err, "Could not add the copy")) }
                        );
                    }}
                >
                    <Field label="Add a copy" htmlFor="cp-acc" hint="The accession number is unique to each physical book.">
                        <Input id="cp-acc" value={accession} maxLength={40} onChange={(e) => setAccession(e.target.value)} />
                    </Field>
                    {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
                    <Button type="submit" size="sm" disabled={save.isPending}>Add copy</Button>
                </form>
            )}
        </div>
    );
}
