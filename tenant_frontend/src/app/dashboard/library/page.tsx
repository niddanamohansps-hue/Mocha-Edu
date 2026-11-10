"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
    BookOpen,
    Plus,
    Search,
    X,
    Bookmark,
    Layers,
    MapPin,
    AlertCircle,
    CheckCircle2,
    Clock,
    Library,
    ArrowRight,
    Copy,
    Edit3,
    Trash2,
    Calendar,
    Coins,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import { Pagination } from "@/components/ui/pagination";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { BookDialog, CopiesDialog } from "@/components/dashboard/library/BookDialogs";
import {
    useBooks,
    useCategories,
    useDeleteBook,
    useLibrarySummary,
} from "@/hooks/useLibrary";
import { usePermissions } from "@/providers/PermissionProvider";
import { Book } from "@/types/Library";
import { toast } from "sonner";

const PAGE_SIZE = 20;

function LibraryPulseMetrics() {
    const { data } = useLibrarySummary();
    if (!data) return null;

    return (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl p-3.5 shadow-2xs">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                    Catalog Titles
                </span>
                <div className="text-xl font-bold text-slate-900 dark:text-white mt-1">
                    {data.titles}
                </div>
                <span className="text-[10px] text-slate-400 font-medium">Distinct books</span>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-emerald-200/60 dark:border-emerald-900/60 rounded-xl p-3.5 shadow-2xs">
                <span className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider block">
                    Available on Shelf
                </span>
                <div className="text-xl font-bold text-emerald-700 dark:text-emerald-300 mt-1">
                    {data.copies.available} <span className="text-xs text-slate-400 font-normal">/ {data.copies.total} copies</span>
                </div>
                <span className="text-[10px] text-emerald-600/80 font-medium">Ready for lending</span>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-indigo-200/60 dark:border-indigo-900/60 rounded-xl p-3.5 shadow-2xs">
                <span className="text-[11px] font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider block">
                    Active Loans
                </span>
                <div className="text-xl font-bold text-indigo-700 dark:text-indigo-300 mt-1">
                    {data.open_loans}
                </div>
                <span className="text-[10px] text-indigo-600/80 font-medium">Out with borrowers</span>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-rose-200/60 dark:border-rose-900/60 rounded-xl p-3.5 shadow-2xs">
                <span className="text-[11px] font-semibold text-rose-600 dark:text-rose-400 uppercase tracking-wider block">
                    Overdue Copies
                </span>
                <div className="text-xl font-bold text-rose-700 dark:text-rose-300 mt-1">
                    {data.overdue_loans}
                </div>
                <span className="text-[10px] text-rose-600/80 font-medium">Late returns</span>
            </div>

            <div className="bg-white dark:bg-slate-900 border border-amber-200/60 dark:border-amber-900/60 rounded-xl p-3.5 shadow-2xs">
                <span className="text-[11px] font-semibold text-amber-600 dark:text-amber-400 uppercase tracking-wider block">
                    Pending Fines
                </span>
                <div className="text-xl font-bold text-amber-700 dark:text-amber-300 mt-1">
                    {data.pending_fines}
                </div>
                <span className="text-[10px] text-amber-600/80 font-medium">Uncollected penalties</span>
            </div>
        </div>
    );
}

export default function LibraryBooksPage() {
    const { can } = usePermissions();
    const canEdit = can("manage_library");
    const [page, setPage] = useState(1);
    const [searchInput, setSearchInput] = useState("");
    const [debouncedSearch, setDebouncedSearch] = useState("");
    const [category, setCategory] = useState("");
    const [onlyAvailable, setOnlyAvailable] = useState(false);

    // Debounce search query by 300ms
    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedSearch(searchInput.trim());
        }, 300);
        return () => clearTimeout(handler);
    }, [searchInput]);

    const { data, isLoading, isError, refetch } = useBooks({
        page,
        search: debouncedSearch,
        category,
        available: onlyAvailable,
    });

    const categories = useCategories();
    const remove = useDeleteBook();
    const [editing, setEditing] = useState<Book | null | undefined>(undefined);
    const [copiesOf, setCopiesOf] = useState<Book | null>(null);
    const [deleting, setDeleting] = useState<Book | null>(null);

    if (!can("view_library")) {
        return <ErrorState message="You do not have permission to view the library." />;
    }

    const rows = data?.results ?? [];
    const totalCount = data?.count ?? 0;

    return (
        <div className="space-y-6 max-w-7xl mx-auto pb-24 animate-in fade-in duration-500">
            {/* 1. Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Library className="h-7 w-7 text-indigo-600 dark:text-indigo-400" />
                        <span>Library Catalog &amp; Book Inventory</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Catalog of library books, accession barcodes, shelf coordinates, and copy availability
                    </p>
                </div>

                <div className="flex items-center gap-2.5 shrink-0">
                    <Button
                        asChild
                        variant="outline"
                        size="sm"
                        className="h-9 px-3 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 cursor-pointer shadow-2xs"
                    >
                        <Link href="/dashboard/library/loans">
                            <Clock className="h-3.5 w-3.5 text-slate-500" />
                            <span>Circulation Loans</span>
                        </Link>
                    </Button>
                    <Button
                        asChild
                        variant="outline"
                        size="sm"
                        className="h-9 px-3 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 cursor-pointer shadow-2xs"
                    >
                        <Link href="/dashboard/library/fines">
                            <Coins className="h-3.5 w-3.5 text-amber-500" />
                            <span>Fine Registry</span>
                        </Link>
                    </Button>
                    {canEdit && (
                        <Button
                            onClick={() => setEditing(null)}
                            size="sm"
                            className="h-9 px-4 gap-1.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95"
                        >
                            <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                            <span>Add New Book</span>
                        </Button>
                    )}
                </div>
            </div>

            {/* 2. Library Circulation Pulse Strip */}
            <LibraryPulseMetrics />

            {/* 3. Filter Bar */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-4 shadow-2xs space-y-3">
                <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
                    {/* Live Search Input */}
                    <div className="relative flex-1 max-w-md">
                        <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                        <Input
                            placeholder="Search by title, author, ISBN or accession number..."
                            value={searchInput}
                            onChange={(e) => {
                                setPage(1);
                                setSearchInput(e.target.value);
                            }}
                            className="h-9 pl-8.5 pr-8 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium"
                        />
                        {searchInput && (
                            <button
                                type="button"
                                onClick={() => {
                                    setPage(1);
                                    setSearchInput("");
                                }}
                                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5 cursor-pointer"
                            >
                                <X className="w-3 h-3" />
                            </button>
                        )}
                    </div>

                    {/* Category Filter */}
                    <div className="w-full md:w-56 shrink-0">
                        <Select
                            value={category || "all"}
                            onValueChange={(val) => {
                                setPage(1);
                                setCategory(val === "all" ? "" : val);
                            }}
                        >
                            <SelectTrigger className="h-9 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium">
                                <SelectValue placeholder="All Categories" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all" className="text-xs">
                                    All Categories
                                </SelectItem>
                                {(categories.data ?? []).map((c) => (
                                    <SelectItem key={c.id} value={c.id} className="text-xs">
                                        {c.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Only Available Toggle */}
                    <label className="flex items-center gap-2 text-xs font-semibold text-slate-700 dark:text-slate-300 cursor-pointer select-none shrink-0 pl-1">
                        <input
                            type="checkbox"
                            checked={onlyAvailable}
                            onChange={(e) => {
                                setPage(1);
                                setOnlyAvailable(e.target.checked);
                            }}
                            className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 h-3.5 w-3.5"
                        />
                        <span>Only available copies on shelf</span>
                    </label>
                </div>
            </div>

            {/* 4. Books Table Desk */}
            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load books. Please try again." onRetry={refetch} />
            ) : rows.length === 0 ? (
                <EmptyState
                    title={
                        debouncedSearch || category || onlyAvailable
                            ? "No books match your search filters"
                            : "No books in the library catalog yet"
                    }
                    description="Add titles and accession numbers to establish your school library inventory."
                    className="py-16 text-slate-500"
                />
            ) : (
                <TableShell
                    footer={
                        totalCount > PAGE_SIZE ? (
                            <Pagination
                                page={page}
                                pageSize={PAGE_SIZE}
                                count={totalCount}
                                onPageChange={setPage}
                            />
                        ) : undefined
                    }
                >
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead className="pl-4 min-w-[240px]">
                                    Book Title &amp; Details
                                </TableHead>
                                <TableHead>
                                    Author
                                </TableHead>
                                <TableHead>
                                    Category
                                </TableHead>
                                <TableHead>
                                    Shelf Location
                                </TableHead>
                                <TableHead className="text-center">
                                    On Shelf Stock
                                </TableHead>
                                <TableHead className="text-right pr-4">
                                    Actions
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody striped>
                            {rows.map((r) => {
                                const hasCopies = r.copies_total > 0;
                                const hasAvailable = r.copies_available > 0;

                                return (
                                    <TableRow
                                        key={r.id}
                                    >
                                        {/* Book Title */}
                                        <TableCell className="pl-4">
                                            <div className="flex items-start gap-2.5">
                                                <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5">
                                                    <BookOpen className="w-4 h-4" />
                                                </div>
                                                <div>
                                                    <div className="font-bold text-xs text-slate-900 dark:text-white flex items-center gap-1.5">
                                                        <span>{r.title}</span>
                                                        {!r.is_active && (
                                                            <Badge
                                                                variant="outline"
                                                                className="bg-slate-100 text-slate-500 text-[10px]"
                                                            >
                                                                Inactive
                                                            </Badge>
                                                        )}
                                                    </div>
                                                    {r.isbn && (
                                                        <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                                                            ISBN: {r.isbn}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        </TableCell>

                                        {/* Author */}
                                        <TableCell className="text-xs text-slate-600 dark:text-slate-300 font-medium">
                                            {r.author || "—"}
                                        </TableCell>

                                        {/* Category */}
                                        <TableCell>
                                            <Badge
                                                variant="outline"
                                                className="bg-slate-50 dark:bg-slate-900 text-slate-700 dark:text-slate-300 text-xs font-medium"
                                            >
                                                {r.category_name || "General"}
                                            </Badge>
                                        </TableCell>

                                        {/* Shelf */}
                                        <TableCell>
                                            <div className="flex items-center gap-1 text-xs text-slate-500 font-mono">
                                                <MapPin className="w-3 h-3 text-slate-400 shrink-0" />
                                                <span>{r.shelf_location || "—"}</span>
                                            </div>
                                        </TableCell>

                                        {/* Copies On Shelf */}
                                        <TableCell className="text-center">
                                            {!hasCopies ? (
                                                <Badge
                                                    variant="outline"
                                                    className="bg-amber-50 text-amber-700 border-amber-300 text-[11px] font-bold"
                                                >
                                                    0 Copies
                                                </Badge>
                                            ) : (
                                                <div className="flex items-center justify-center gap-1.5">
                                                    <span
                                                        className={`font-bold text-xs ${
                                                            hasAvailable
                                                                ? "text-emerald-600 dark:text-emerald-400"
                                                                : "text-rose-600"
                                                        }`}
                                                    >
                                                        {r.copies_available}
                                                    </span>
                                                    <span className="text-slate-400 text-xs">/ {r.copies_total}</span>
                                                </div>
                                            )}
                                        </TableCell>

                                        {/* Actions */}
                                        <TableCell className="pr-4 text-right">
                                            <div className="flex items-center justify-end gap-1">
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    onClick={() => setCopiesOf(r)}
                                                    className="h-8 px-2.5 text-xs font-semibold gap-1"
                                                >
                                                    <Copy className="w-3.5 h-3.5 text-slate-500" />
                                                    <span>Copies ({r.copies_total})</span>
                                                </Button>
                                                {canEdit && (
                                                    <>
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            onClick={() => setEditing(r)}
                                                            className="h-8 px-2 text-xs text-slate-600 hover:text-indigo-600"
                                                        >
                                                            <Edit3 className="w-3.5 h-3.5" />
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            onClick={() => setDeleting(r)}
                                                            className="h-8 px-2 text-xs text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                                                        >
                                                            <Trash2 className="w-3.5 h-3.5" />
                                                        </Button>
                                                    </>
                                                )}
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                );
                            })}
                        </TableBody>
                    </Table>
                </TableShell>
            )}

            {/* Book Form & Copies Modals */}
            <BookDialog book={editing} onClose={() => setEditing(undefined)} />
            <CopiesDialog book={copiesOf} onClose={() => setCopiesOf(null)} />
            <ConfirmationDialog
                open={Boolean(deleting)}
                onOpenChange={(open) => !open && setDeleting(null)}
                title={`Delete Catalog Entry: ${deleting?.title ?? ""}?`}
                description="This book can only be deleted if zero physical copies are linked to it. Otherwise, mark it inactive in the catalog."
                confirmLabel="Yes, Delete Book"
                variant="destructive"
                isLoading={remove.isPending}
                onConfirm={() =>
                    deleting &&
                    remove.mutate(deleting.id, {
                        onSuccess: () => {
                            toast.success("Book deleted from catalog");
                            setDeleting(null);
                        },
                        onSettled: () => setDeleting(null),
                    })
                }
            />
        </div>
    );
}
