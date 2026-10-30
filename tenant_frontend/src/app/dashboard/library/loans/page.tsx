"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
    BookOpen,
    Clock,
    Plus,
    Search,
    X,
    CheckCircle2,
    AlertCircle,
    RotateCcw,
    BookmarkCheck,
    Coins,
    Calendar,
    User,
    ArrowLeft,
    Check,
    AlertTriangle,
    ShieldAlert,
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
import { IssueDialog } from "@/components/dashboard/library/IssueDialog";
import {
    useLoans,
    useRenewLoan,
    useReportLost,
    useReturnBook,
} from "@/hooks/useLibrary";
import { usePermissions } from "@/providers/PermissionProvider";
import { ClosedLoanResult, Loan, LoanState } from "@/types/Library";
import { formatIndianCurrency } from "@/lib/currency";
import { toast } from "sonner";

const PAGE_SIZE = 20;

const AVATAR_PALETTES = [
    { bg: "bg-sky-100 dark:bg-sky-950/70", text: "text-sky-700 dark:text-sky-300", border: "border-sky-300/60 dark:border-sky-800" },
    { bg: "bg-emerald-100 dark:bg-emerald-950/70", text: "text-emerald-700 dark:text-emerald-300", border: "border-emerald-300/60 dark:border-emerald-800" },
    { bg: "bg-indigo-100 dark:bg-indigo-950/70", text: "text-indigo-700 dark:text-indigo-300", border: "border-indigo-300/60 dark:border-indigo-800" },
    { bg: "bg-purple-100 dark:bg-purple-950/70", text: "text-purple-700 dark:text-purple-300", border: "border-purple-300/60 dark:border-purple-800" },
    { bg: "bg-amber-100 dark:bg-amber-950/70", text: "text-amber-700 dark:text-amber-300", border: "border-amber-300/60 dark:border-amber-800" },
    { bg: "bg-rose-100 dark:bg-rose-950/70", text: "text-rose-700 dark:text-rose-300", border: "border-rose-300/60 dark:border-rose-800" },
    { bg: "bg-teal-100 dark:bg-teal-950/70", text: "text-teal-700 dark:text-teal-300", border: "border-teal-300/60 dark:border-teal-800" },
];

function getAvatarStyle(name: string) {
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    const index = Math.abs(hash) % AVATAR_PALETTES.length;
    return AVATAR_PALETTES[index];
}

function getInitials(name: string) {
    if (!name) return "ST";
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    return name.slice(0, 2).toUpperCase();
}

function formatDateDisplay(iso: string | null) {
    if (!iso) return "—";
    try {
        const d = new Date(iso);
        return d.toLocaleDateString("en-IN", {
            day: "numeric",
            month: "short",
            year: "numeric",
        });
    } catch {
        return iso;
    }
}

function LoanStatusBadge({ loan }: { loan: Loan }) {
    if (!loan.is_open) {
        return loan.outcome === "lost" ? (
            <Badge
                variant="outline"
                className="bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 font-bold text-xs"
            >
                Lost
            </Badge>
        ) : (
            <Badge
                variant="outline"
                className="bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 font-medium text-xs"
            >
                Returned
            </Badge>
        );
    }

    return loan.is_overdue ? (
        <Badge
            variant="outline"
            className="bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 font-bold text-xs"
        >
            {loan.days_overdue} day{loan.days_overdue === 1 ? "" : "s"} overdue
        </Badge>
    ) : (
        <Badge
            variant="outline"
            className="bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 font-semibold text-xs"
        >
            On Loan
        </Badge>
    );
}

export default function LoansPage() {
    const { can } = usePermissions();
    const canLend = can("lend_library_books");
    const [page, setPage] = useState(1);
    const [searchInput, setSearchInput] = useState("");
    const [debouncedSearch, setDebouncedSearch] = useState("");
    const [state, setState] = useState<LoanState>("open");

    // Debounce search query by 300ms
    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedSearch(searchInput.trim());
        }, 300);
        return () => clearTimeout(handler);
    }, [searchInput]);

    const { data, isLoading, isError, refetch } = useLoans({
        page,
        search: debouncedSearch,
        state,
    });

    const giveBack = useReturnBook();
    const lose = useReportLost();
    const renew = useRenewLoan();

    const [issuing, setIssuing] = useState(false);
    const [losing, setLosing] = useState<Loan | null>(null);
    const [result, setResult] = useState<ClosedLoanResult | null>(null);

    if (!can("view_library")) {
        return <ErrorState message="You do not have permission to view the library." />;
    }

    const rows = data?.results ?? [];
    const totalCount = data?.count ?? 0;

    const handleReturn = (loanId: string) => {
        giveBack.mutate(loanId, {
            onSuccess: (data) => {
                setResult(data);
                toast.success("Book successfully marked as returned!");
                refetch();
            },
            onError: (err: any) => {
                toast.error(err?.message || "Failed to return book");
            },
        });
    };

    const handleRenew = (loanId: string) => {
        renew.mutate(loanId, {
            onSuccess: () => {
                toast.success("Loan period renewed successfully!");
                refetch();
            },
            onError: (err: any) => {
                toast.error(err?.message || "Failed to renew loan");
            },
        });
    };

    const handleReportLostConfirm = () => {
        if (!losing) return;
        lose.mutate(losing.id, {
            onSuccess: (data) => {
                setResult(data);
                setLosing(null);
                toast.info("Book recorded as lost.");
                refetch();
            },
            onError: (err: any) => {
                toast.error(err?.message || "Failed to report lost book");
            },
        });
    };

    return (
        <div className="space-y-6 max-w-7xl mx-auto pb-24 animate-in fade-in duration-500">
            {/* 1. Senior Executive Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <div className="flex items-center gap-2 mb-1">
                        <Link
                            href="/dashboard/library"
                            className="text-xs text-sky-600 dark:text-sky-400 hover:underline flex items-center gap-1 font-semibold"
                        >
                            <ArrowLeft className="w-3.5 h-3.5" /> Back to Books Catalog
                        </Link>
                    </div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Clock className="h-7 w-7 text-indigo-600 dark:text-indigo-400" />
                        <span>Circulation &amp; Book Lending Desk</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Issue library copies to students and faculty, handle check-in returns, and monitor overdue items
                    </p>
                </div>

                <div className="flex items-center gap-2.5 shrink-0">
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
                    {canLend && (
                        <Button
                            onClick={() => setIssuing(true)}
                            size="sm"
                            className="h-9 px-4 gap-1.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95"
                        >
                            <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                            <span>Issue Book to Borrower</span>
                        </Button>
                    )}
                </div>
            </div>

            {/* 2. Closed / Returned Notice Banner */}
            {result && (
                <div
                    className={`rounded-2xl border p-4 text-xs space-y-2 shadow-2xs flex items-start justify-between gap-3 ${
                        result.fine
                            ? "border-amber-300 bg-amber-50 dark:bg-amber-950/40 dark:border-amber-800 text-amber-900 dark:text-amber-200"
                            : "border-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 dark:border-emerald-800 text-emerald-900 dark:text-emerald-200"
                    }`}
                >
                    <div className="space-y-1">
                        <p className="font-bold text-sm flex items-center gap-2">
                            <CheckCircle2 className="w-4 h-4" />
                            <span>
                                {result.outcome === "lost"
                                    ? `"${result.book_title}" has been recorded as lost.`
                                    : `"${result.book_title}" has been checked in and returned to the shelf.`}
                            </span>
                        </p>
                        {result.fine ? (
                            <p className="text-xs">
                                Overdue fine of <span className="font-bold">{formatIndianCurrency(result.fine.amount)}</span> was levied for{" "}
                                <span className="font-bold">{result.borrower_name}</span>
                                {result.fine.kind === "overdue"
                                    ? ` (${result.fine.days_overdue} days overdue)`
                                    : " (lost item penalty)"}
                                .{" "}
                                <Link href="/dashboard/library/fines" className="underline font-bold">
                                    Open Fines Desk
                                </Link>{" "}
                                to collect or waive it.
                            </p>
                        ) : (
                            <p className="text-xs">No overdue penalties incurred for this loan.</p>
                        )}
                    </div>
                    <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setResult(null)}
                        className="text-xs h-7 px-2 shrink-0"
                    >
                        Dismiss
                    </Button>
                </div>
            )}

            {/* 3. Filter Bar */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-4 shadow-2xs space-y-3">
                <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
                    {/* Live Search */}
                    <div className="relative flex-1 max-w-md">
                        <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                        <Input
                            placeholder="Search borrower name, book title or barcode..."
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
                                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5"
                            >
                                <X className="w-3 h-3" />
                            </button>
                        )}
                    </div>

                    {/* Status Select */}
                    <div className="w-full md:w-56 shrink-0">
                        <Select
                            value={state || "all"}
                            onValueChange={(val) => {
                                setPage(1);
                                setState(val === "all" ? ("" as LoanState) : (val as LoanState));
                            }}
                        >
                            <SelectTrigger className="h-9 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium">
                                <SelectValue placeholder="All Circulation States" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="open" className="text-xs">
                                    On Loan (Active)
                                </SelectItem>
                                <SelectItem value="overdue" className="text-xs">
                                    Overdue Returns
                                </SelectItem>
                                <SelectItem value="closed" className="text-xs">
                                    Returned or Lost
                                </SelectItem>
                                <SelectItem value="all" className="text-xs">
                                    All Circulation Records
                                </SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                </div>
            </div>

            {/* 4. Loans Table Desk */}
            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load loan records. Please try again." onRetry={refetch} />
            ) : rows.length === 0 ? (
                <EmptyState
                    title={
                        debouncedSearch || state
                            ? "No loan records match your search filters"
                            : "No books currently out on loan"
                    }
                    description="Issue a book copy to a student or staff member using the button above."
                    className="py-16 text-slate-500"
                />
            ) : (
                <div className="space-y-3">
                    <TableShell>
                        <Table>
                            <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                <TableRow>
                                    <TableHead className="py-3 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider min-w-[220px]">
                                        Book Title &amp; Barcode
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider min-w-[180px]">
                                        Borrower
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Issue Date
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Due Date
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Circulation Status
                                    </TableHead>
                                    <TableHead className="text-right pr-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Actions
                                    </TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {rows.map((loan) => {
                                    const borrowerName = loan.borrower_name || "—";
                                    const avatarStyle = getAvatarStyle(borrowerName);
                                    const initials = getInitials(borrowerName);

                                    return (
                                        <TableRow
                                            key={loan.id}
                                            className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                        >
                                            {/* Book Title */}
                                            <TableCell className="py-3 pl-4">
                                                <div className="font-bold text-xs text-slate-900 dark:text-white">
                                                    {loan.book_title}
                                                </div>
                                                <div className="text-[10px] font-mono text-slate-400 flex items-center gap-1 mt-0.5">
                                                    <span>Accession:</span>
                                                    <code className="text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-950/60 px-1 py-0.2 rounded font-bold">
                                                        {loan.accession_number}
                                                    </code>
                                                </div>
                                            </TableCell>

                                            {/* Borrower Details with Avatar */}
                                            <TableCell className="py-3">
                                                <div className="flex items-center gap-2.5">
                                                    <div
                                                        className={`h-8 w-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 border ${avatarStyle.bg} ${avatarStyle.text} ${avatarStyle.border}`}
                                                    >
                                                        {initials}
                                                    </div>
                                                    <div>
                                                        <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                            {borrowerName}
                                                        </div>
                                                        <div className="text-[10px] font-mono text-slate-400 capitalize">
                                                            {loan.borrower_type}
                                                        </div>
                                                    </div>
                                                </div>
                                            </TableCell>

                                            {/* Issued Date */}
                                            <TableCell className="py-3 text-xs text-slate-600 dark:text-slate-300 font-medium">
                                                {formatDateDisplay(loan.issued_on)}
                                            </TableCell>

                                            {/* Due Date */}
                                            <TableCell className="py-3">
                                                <span
                                                    className={`text-xs font-semibold ${
                                                        loan.is_overdue
                                                            ? "text-rose-600 dark:text-rose-400 font-bold"
                                                            : "text-slate-700 dark:text-slate-300"
                                                    }`}
                                                >
                                                    {formatDateDisplay(loan.due_on)}
                                                </span>
                                            </TableCell>

                                            {/* Status Badge */}
                                            <TableCell className="py-3">
                                                <LoanStatusBadge loan={loan} />
                                            </TableCell>

                                            {/* Actions */}
                                            <TableCell className="py-3 pr-4 text-right">
                                                {loan.is_open && canLend ? (
                                                    <div className="flex items-center justify-end gap-1.5">
                                                        <Button
                                                            size="sm"
                                                            onClick={() => handleReturn(loan.id)}
                                                            disabled={giveBack.isPending}
                                                            className="h-8 px-2.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white gap-1 rounded-lg"
                                                        >
                                                            <Check className="w-3.5 h-3.5" />
                                                            <span>Return</span>
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => handleRenew(loan.id)}
                                                            disabled={renew.isPending}
                                                            className="h-8 px-2 text-xs font-semibold text-slate-600 gap-1"
                                                        >
                                                            <RotateCcw className="w-3 h-3" />
                                                            <span>Renew</span>
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            onClick={() => setLosing(loan)}
                                                            className="h-8 px-2 text-xs font-semibold text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                                                        >
                                                            Lost
                                                        </Button>
                                                    </div>
                                                ) : (
                                                    <span className="text-xs text-slate-400 font-medium">
                                                        Closed
                                                    </span>
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                            </TableBody>
                        </Table>
                    </TableShell>

                    {/* Pagination */}
                    {totalCount > PAGE_SIZE && (
                        <div className="pt-2">
                            <Pagination
                                page={page}
                                pageSize={PAGE_SIZE}
                                count={totalCount}
                                onPageChange={setPage}
                            />
                        </div>
                    )}
                </div>
            )}

            {/* Modals */}
            <IssueDialog
                open={issuing}
                onClose={() => {
                    setIssuing(false);
                    refetch();
                }}
            />
            <ConfirmationDialog
                open={Boolean(losing)}
                onOpenChange={(open) => !open && setLosing(null)}
                title={`Report "${losing?.book_title}" as Lost?`}
                description="This will close the active loan, deduct the copy from available inventory, and calculate any replacement fine."
                confirmLabel="Yes, Record as Lost"
                variant="destructive"
                isLoading={lose.isPending}
                onConfirm={handleReportLostConfirm}
            />
        </div>
    );
}
