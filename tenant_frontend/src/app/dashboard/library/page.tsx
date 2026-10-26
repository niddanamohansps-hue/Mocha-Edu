"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ResponsiveList } from "@/components/common/ResponsiveList";
import { EmptyHint, FilterBar } from "@/components/common/PageLayout";
import { BookDialog, CopiesDialog } from "@/components/dashboard/library/BookDialogs";
import { FILTER_SELECT_CLASS, PageHeader, Pager, Pill } from "@/components/dashboard/library/shared";
import { useBooks, useCategories, useDeleteBook, useLibrarySummary } from "@/hooks/useLibrary";
import { usePermissions } from "@/providers/PermissionProvider";
import { Book } from "@/types/Library";

function Summary() {
    const { data } = useLibrarySummary();
    if (!data) return null;
    const items = [
        { label: "Titles", value: data.titles },
        { label: "Copies on the shelf", value: `${data.copies.available} / ${data.copies.total}` },
        { label: "Out on loan", value: data.open_loans },
        { label: "Overdue", value: data.overdue_loans, warn: data.overdue_loans > 0 },
        { label: "Fines waiting", value: data.pending_fines, warn: data.pending_fines > 0 },
    ];
    return (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {items.map((item) => (
                <div key={item.label} className="rounded-2xl border border-slate-200 dark:border-slate-800 p-3">
                    <p className="text-xs text-slate-500">{item.label}</p>
                    <p className={`text-xl font-bold ${item.warn ? "text-amber-600" : "text-slate-900 dark:text-white"}`}>{item.value}</p>
                </div>
            ))}
        </div>
    );
}

export default function LibraryBooksPage() {
    const { can } = usePermissions();
    const canEdit = can("manage_library");
    const [page, setPage] = useState(1);
    const [search, setSearch] = useState("");
    const [searchText, setSearchText] = useState("");
    const [category, setCategory] = useState("");
    const [onlyAvailable, setOnlyAvailable] = useState(false);
    const { data, isLoading, isError, refetch } = useBooks({ page, search, category, available: onlyAvailable });
    const categories = useCategories();
    const remove = useDeleteBook();
    const [editing, setEditing] = useState<Book | null | undefined>(undefined);
    const [copiesOf, setCopiesOf] = useState<Book | null>(null);
    const [deleting, setDeleting] = useState<Book | null>(null);

    if (!can("view_library")) return <ErrorState message="You do not have permission to view the library." />;
    const rows = data?.results ?? [];

    return (
        <div className="space-y-6">
            <PageHeader
                title="Books"
                description="The catalogue. Open a book to see and add its copies."
                actions={canEdit && <Button onClick={() => setEditing(null)}>New book</Button>}
            />
            <Summary />
            <FilterBar onSubmit={() => { setPage(1); setSearch(searchText.trim()); }}>
                <Input type="text" placeholder="Search title, author, ISBN or accession number" aria-label="Search books" value={searchText} onChange={(e) => setSearchText(e.target.value)} />
                <select aria-label="Category" className={FILTER_SELECT_CLASS} value={category} onChange={(e) => { setPage(1); setCategory(e.target.value); }}>
                    <option value="">All categories</option>
                    {(categories.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
                <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={onlyAvailable} onChange={(e) => { setPage(1); setOnlyAvailable(e.target.checked); }} />
                    On the shelf now
                </label>
                <Button type="submit" variant="outline">Search</Button>
            </FilterBar>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load books. Please try again." onRetry={refetch} />
            ) : rows.length === 0 ? (
                <EmptyHint
                    title={search || category || onlyAvailable ? "No book matches." : "No books yet."}
                    hint={search || category || onlyAvailable ? "Try a different search." : "Add a title, then add its copies so it can be lent."}
                    action={!search && !category && !onlyAvailable && canEdit ? <Button onClick={() => setEditing(null)}>Add the first book</Button> : undefined}
                />
            ) : (
                <ResponsiveList
                    rows={rows}
                    rowKey={(r) => r.id}
                    columns={[
                        {
                            key: "title", header: "Title", primary: true,
                            cell: (r) => <>{r.title} {!r.is_active && <Pill className="ml-1 bg-slate-200 text-slate-600">Off</Pill>}</>,
                        },
                        { key: "author", header: "Author", hideOnMobile: true, className: "text-slate-500", cell: (r) => r.author || "-" },
                        { key: "category", header: "Category", hideOnMobile: true, className: "text-slate-500", cell: (r) => r.category_name || "-" },
                        { key: "shelf", header: "Shelf", hideOnMobile: true, className: "text-slate-500", cell: (r) => r.shelf_location || "-" },
                        {
                            key: "copies", header: "On the shelf", className: "font-bold",
                            cell: (r) => (r.copies_total === 0 ? <span className="text-amber-600">No copies</span> : `${r.copies_available} / ${r.copies_total}`),
                        },
                    ]}
                    actionsHeader="Actions"
                    actions={(r) => (
                        <div className="flex flex-wrap justify-end gap-1">
                            <Button size="sm" variant="outline" onClick={() => setCopiesOf(r)}>Copies</Button>
                            {canEdit && <Button size="sm" variant="ghost" onClick={() => setEditing(r)}>Edit</Button>}
                            {canEdit && <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setDeleting(r)}>Delete</Button>}
                        </div>
                    )}
                />
            )}
            <Pager data={data} page={page} onPage={setPage} />

            <BookDialog book={editing} onClose={() => setEditing(undefined)} />
            <CopiesDialog book={copiesOf} onClose={() => setCopiesOf(null)} />
            <ConfirmationDialog
                open={!!deleting}
                onOpenChange={(open) => !open && setDeleting(null)}
                title={`Delete ${deleting?.title ?? ""}?`}
                description="This only works if the book has no copies. Otherwise switch it off in the catalogue instead."
                confirmLabel="Delete"
                isLoading={remove.isPending}
                onConfirm={() => deleting && remove.mutate(deleting.id, { onSettled: () => setDeleting(null) })}
            />
        </div>
    );
}
