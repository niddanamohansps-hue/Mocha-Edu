"use client";

import { Suspense, useMemo, useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
    LoaderCircle,
    Plus,
    Receipt as ReceiptIcon,
    XCircle,
    Search,
    User,
    CheckCircle2,
    CreditCard,
    DollarSign,
    Calendar,
    ArrowRight,
    Zap,
    X,
    RotateCcw,
    Sparkles,
    AlertCircle,
    Building2,
    Printer,
} from "lucide-react";
import { ReceiptModal } from "@/components/dashboard/fees/ReceiptModal";
import {
    useAssignStudentFee,
    useCancelStudentFee,
    useFeeHeads,
    useRecordPayment,
    useReversePayment,
    useStudentFees,
    useStudentPayments,
} from "@/hooks/useFees";
import { useStudents, Student } from "@/hooks/useStudents";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { PAYMENT_METHOD_CHOICES, PaymentMethod, StudentFee } from "@/types/Fees";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Avatar } from "@/components/ui/avatar";
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
    TableHeadNumeric,
    TableHeader,
    TableRow,
    TableCellNumeric,
    TableCellAction,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import Unauthorized from "@/components/Unauthorized";
import { formatIndianCurrency, CURRENCY } from "@/lib/currency";
import { toast } from "sonner";

function formatDate(dateStr?: string | null) {
    if (!dateStr) return "—";
    try {
        if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
            const [y, m, d] = dateStr.split("-").map(Number);
            const date = new Date(y, m - 1, d);
            return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
        }
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr.split("T")[0];
        return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    } catch {
        return dateStr.split("T")[0];
    }
}

function CollectPaymentContent() {
    const { can, isOwner } = usePermissions();
    const canView = isOwner || can("view_fees");
    const canManage = isOwner || can("manage_fee_structures");
    const canCollect = isOwner || can("collect_payments");

    const searchParams = useSearchParams();
    const router = useRouter();

    const { selectedYear, currentYear } = useAcademicYear();
    const activeYear = selectedYear || currentYear;
    const academicYear = activeYear?.name || "2026-27";

    // Student Search & Selection State
    const [studentSearchInput, setStudentSearchInput] = useState(searchParams.get("search") || "");
    const [debouncedStudentSearch, setDebouncedStudentSearch] = useState(searchParams.get("search") || "");
    const [selectedStudent, setSelectedStudent] = useState<Student | null>(null);
    const [studentId, setStudentId] = useState<string>(searchParams.get("studentId") || "");
    const [isSearchOpen, setIsSearchOpen] = useState(false);

    // Debounce student search input
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedStudentSearch(studentSearchInput);
        }, 250);
        return () => clearTimeout(timer);
    }, [studentSearchInput]);

    // Query matching students
    const { data: studentResults } = useStudents({
        search: debouncedStudentSearch,
        pageSize: 6,
    });
    const candidateStudents = studentResults?.results || [];

    // Auto-select student if single exact match from URL search param
    useEffect(() => {
        const initialSearch = searchParams.get("search");
        if (initialSearch && candidateStudents.length > 0 && !selectedStudent) {
            const exact = candidateStudents.find(
                (s) =>
                    s.enrollment_id.toLowerCase() === initialSearch.toLowerCase() ||
                    s.id === initialSearch
            );
            if (exact) {
                handleSelectStudent(exact);
            }
        }
    }, [candidateStudents, searchParams, selectedStudent]);

    // Fees & Payments Queries
    const { data: feesData, isLoading: loadingFees } = useStudentFees(
        studentId || undefined,
        academicYear
    );
    const { data: payments = [], isLoading: loadingPayments } = useStudentPayments(
        studentId || undefined
    );
    const { data: heads = [] } = useFeeHeads();

    const { mutate: assignFee, isPending: assigning } = useAssignStudentFee();
    const { mutate: cancelFee, isPending: cancelling } = useCancelStudentFee();
    const { mutate: recordPayment, isPending: recording } = useRecordPayment();

    // Payment Form State
    const [assignForm, setAssignForm] = useState({
        fee_head: "",
        amount_due: "",
        due_date: new Date().toISOString().split("T")[0],
    });
    const [selectedAllocations, setSelectedAllocations] = useState<Record<string, string>>({});
    const [method, setMethod] = useState<PaymentMethod>("cash");
    const [referenceNote, setReferenceNote] = useState("");
    const [cancelReason, setCancelReason] = useState<Record<string, string>>({});
    // A payment recorded by mistake is reversed (never deleted): the reversal is its own receipt row.
    const [reverseReason, setReverseReason] = useState<Record<string, string>>({});
    const { mutate: reversePayment, isPending: reversing } = useReversePayment();
    const [isAssignOpen, setIsAssignOpen] = useState(false);
    const [receiptToPrint, setReceiptToPrint] = useState<string | null>(null);

    const activeFees = useMemo(
        () => feesData?.fees.filter((f) => f.status === "active") ?? [],
        [feesData]
    );

    const totalAllocated = useMemo(
        () =>
            Object.values(selectedAllocations).reduce(
                (sum, v) => sum + (parseFloat(v) || 0),
                0
            ),
        [selectedAllocations]
    );

    const totalPaidToDate = useMemo(() => {
        return (feesData?.fees || []).reduce(
            (sum, f) => sum + (parseFloat(f.amount_paid) || 0),
            0
        );
    }, [feesData]);

    const handleSelectStudent = (student: Student) => {
        setSelectedStudent(student);
        setStudentId(student.id);
        setStudentSearchInput(`${student.first_name} ${student.last_name}`);
        setIsSearchOpen(false);
        setSelectedAllocations({});
    };

    const handleClearStudent = () => {
        setSelectedStudent(null);
        setStudentId("");
        setStudentSearchInput("");
        setSelectedAllocations({});
    };

    const handleAutoAllocateAll = () => {
        const next: Record<string, string> = {};
        activeFees.forEach((fee) => {
            const outstanding = parseFloat(fee.outstanding_balance);
            if (outstanding > 0) {
                next[fee.id] = fee.outstanding_balance;
            }
        });
        setSelectedAllocations(next);
        toast.success("Auto-allocated exact dues for all active fee heads");
    };

    const handleAssign = (e: React.FormEvent) => {
        e.preventDefault();
        if (!studentId || !assignForm.fee_head || !assignForm.amount_due) return;
        assignFee(
            {
                studentId,
                data: {
                    fee_head: assignForm.fee_head,
                    academic_year: academicYear,
                    amount_due: assignForm.amount_due,
                    due_date: assignForm.due_date || undefined,
                },
            },
            {
                onSuccess: () => {
                    setAssignForm({
                        fee_head: "",
                        amount_due: "",
                        due_date: new Date().toISOString().split("T")[0],
                    });
                    setIsAssignOpen(false);
                },
            }
        );
    };

    const handleCancel = (feeId: string) => {
        const reason = cancelReason[feeId];
        if (!studentId || !reason) {
            toast.error("Please enter a cancellation reason first");
            return;
        }
        cancelFee({ studentId, feeId, cancellationReason: reason });
    };

    const handleReverse = (paymentId: string, receipt: string) => {
        const reason = (reverseReason[paymentId] ?? "").trim();
        if (!reason) {
            toast.error("Enter why this payment is being reversed first");
            return;
        }
        if (!window.confirm(`Reverse payment ${receipt}? Its amount goes back to the student's dues. This cannot be undone.`)) return;
        reversePayment(
            { paymentId, reason },
            { onSuccess: () => setReverseReason((prev) => ({ ...prev, [paymentId]: "" })) }
        );
    };

    const handleRecordPayment = () => {
        if (!studentId) return;
        const allocations = Object.entries(selectedAllocations)
            .filter(([, amount]) => parseFloat(amount) > 0)
            .map(([student_fee, amount]) => ({ student_fee, amount }));
        if (allocations.length === 0) {
            toast.error("Please allocate a payment amount to at least one fee head");
            return;
        }

        recordPayment(
            {
                student: studentId,
                amount: totalAllocated.toFixed(2),
                method,
                reference_note: referenceNote.trim() || undefined,
                allocations,
            },
            {
                onSuccess: (data: any) => {
                    setSelectedAllocations({});
                    setReferenceNote("");
                    if (data?.id) {
                        setReceiptToPrint(data.id);
                    }
                },
            }
        );
    };

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-4">
            {/* 1. Header Banner */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1">
                <div>
                    <div className="flex items-center gap-2.5">
                        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                            Fee Collection Desk
                        </h1>
                        <Badge
                            variant="secondary"
                            className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300/80 font-semibold text-xs px-2 py-0.5"
                        >
                            Cashier Operations
                        </Badge>
                    </div>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-0.5">
                        Search student enrollment, review outstanding fee balances, record collections, and issue official receipts.
                    </p>
                </div>

                <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
                    <Badge className="bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700 text-xs py-1">
                        Academic Year: {academicYear}
                    </Badge>
                </div>
            </div>

            {/* 2. Interactive Student Search & Selection Bar */}
            <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs space-y-3">
                <div className="flex items-center justify-between">
                    <Label className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
                        <Search className="w-3.5 h-3.5 text-sky-600" />
                        <span>Search Student / Enrollment ID</span>
                    </Label>
                    {selectedStudent && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleClearStudent}
                            className="h-7 px-2 text-xs text-rose-600 hover:text-rose-700 hover:bg-rose-50 dark:hover:bg-rose-950/40"
                        >
                            <X className="w-3 h-3 mr-1" />
                            <span>Change Student</span>
                        </Button>
                    )}
                </div>

                {!selectedStudent ? (
                    <div className="relative">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                            <Input
                                placeholder="Type student name, enrollment ID (e.g. SV/2026/0189), or roll number..."
                                value={studentSearchInput}
                                onChange={(e) => {
                                    setStudentSearchInput(e.target.value);
                                    setIsSearchOpen(true);
                                }}
                                onFocus={() => setIsSearchOpen(true)}
                                className="pl-9 pr-8 h-10 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                            />
                            {studentSearchInput && (
                                <button
                                    onClick={() => {
                                        setStudentSearchInput("");
                                        setIsSearchOpen(false);
                                    }}
                                    className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-400 hover:text-slate-600"
                                >
                                    <X className="h-3.5 w-3.5" />
                                </button>
                            )}
                        </div>

                        {/* Search Results Dropdown */}
                        {isSearchOpen && debouncedStudentSearch && (
                            <div className="absolute top-full left-0 right-0 z-30 mt-1.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-xl overflow-hidden max-h-72 overflow-y-auto">
                                {candidateStudents.length > 0 ? (
                                    <div className="p-1 divide-y divide-slate-100 dark:divide-slate-800">
                                        {candidateStudents.map((s) => {
                                            return (
                                                <div
                                                    key={s.id}
                                                    onClick={() => handleSelectStudent(s)}
                                                    className="flex items-center justify-between p-2.5 hover:bg-slate-50 dark:hover:bg-slate-800/60 rounded-lg cursor-pointer transition-colors"
                                                >
                                                    <div className="flex items-center gap-3">
                                                        <Avatar name={s.full_name} size="sm" />
                                                        <div>
                                                            <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                                {s.full_name}
                                                            </div>
                                                            <div className="text-[10px] text-slate-400 font-mono">
                                                                {s.enrollment_id} • {s.level || "Grade Not Set"} {s.section ? `(${s.section})` : ""}
                                                            </div>
                                                        </div>
                                                    </div>
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        className="h-7 text-xs font-semibold px-2.5 rounded-lg border-sky-300 text-sky-600 hover:bg-sky-50"
                                                    >
                                                        Select
                                                    </Button>
                                                </div>
                                            );
                                        })}
                                    </div>
                                ) : (
                                    <div className="p-6 text-center text-xs text-slate-500">
                                        No enrolled students matched &quot;{debouncedStudentSearch}&quot;.
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                ) : (
                    /* Selected Student Profile Banner */
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 bg-slate-50 dark:bg-slate-800/50 border border-slate-200/80 dark:border-slate-700/80 rounded-xl">
                        <div className="flex items-center gap-3">
                            <Avatar
                                name={selectedStudent.full_name}
                                src={selectedStudent.photo}
                                size="lg"
                            />
                            <div>
                                <div className="flex items-center gap-2">
                                    <h4 className="font-bold text-xs sm:text-sm text-slate-900 dark:text-white">
                                        {selectedStudent.full_name}
                                    </h4>
                                    <Badge className="bg-sky-50 text-sky-700 border border-sky-200 text-[10px] font-mono py-0">
                                        {selectedStudent.enrollment_id}
                                    </Badge>
                                </div>
                                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                                    Class: <span className="font-semibold text-slate-700 dark:text-slate-200">{selectedStudent.level || "Grade Unassigned"}</span>
                                    {selectedStudent.section ? ` • Section ${selectedStudent.section}` : ""}
                                    {selectedStudent.father_name ? ` • Father: ${selectedStudent.father_name}` : ""}
                                </p>
                            </div>
                        </div>

                        <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
                            <Badge
                                className={`text-xs px-2.5 py-1 font-bold ${
                                    parseFloat(feesData?.total_outstanding || "0") > 0
                                        ? "bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-300"
                                        : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300"
                                }`}
                            >
                                {parseFloat(feesData?.total_outstanding || "0") > 0
                                    ? `Outstanding: ${formatIndianCurrency(feesData?.total_outstanding)}`
                                    : "All Fees Cleared ✓"}
                            </Badge>
                        </div>
                    </div>
                )}
            </div>

            {/* When No Student Selected */}
            {!studentId && (
                <div className="p-16 text-center bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs space-y-3">
                    <div className="w-12 h-12 mx-auto rounded-xl bg-sky-50 dark:bg-sky-900/30 flex items-center justify-center text-sky-600 dark:text-sky-400">
                        <CreditCard className="w-6 h-6" />
                    </div>
                    <h3 className="text-sm font-bold text-slate-800 dark:text-white">
                        No Student Selected
                    </h3>
                    <p className="text-xs text-slate-500 max-w-sm mx-auto">
                        Search and select a student above by name or enrollment ID to view fee ledgers, allocate receipts, and collect payments.
                    </p>
                </div>
            )}

            {/* Loading Fees State */}
            {studentId && loadingFees && (
                <div className="p-16 flex flex-col items-center justify-center gap-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs">
                    <LoaderCircle className="w-7 h-7 animate-spin text-sky-600" />
                    <span className="text-xs text-slate-500 font-medium">Loading student fee ledger...</span>
                </div>
            )}

            {/* 3. Loaded Student Fee Dashboard */}
            {studentId && feesData && !loadingFees && (
                <div className="space-y-4">
                    {/* Financial Metric Cards (3-card high density grid) */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
                        <div className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                            <span className="text-xs font-semibold text-slate-500">Total Outstanding Balance</span>
                            <div className="text-2xl font-black text-rose-600 dark:text-rose-400 mt-1">
                                {formatIndianCurrency(feesData.total_outstanding)}
                            </div>
                            <span className="text-[10px] text-slate-400 mt-0.5 block">
                                Across {activeFees.length} active fee items
                            </span>
                        </div>

                        <div className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                            <span className="text-xs font-semibold text-slate-500">Total Fees Paid to Date</span>
                            <div className="text-2xl font-black text-emerald-600 dark:text-emerald-400 mt-1">
                                {formatIndianCurrency(totalPaidToDate)}
                            </div>
                            <span className="text-[10px] text-slate-400 mt-0.5 block">
                                Realized in current academic session
                            </span>
                        </div>

                        <div className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                            <span className="text-xs font-semibold text-slate-500">Payment Allocation Status</span>
                            <div className="text-2xl font-black text-slate-800 dark:text-slate-100 mt-1">
                                {formatIndianCurrency(totalAllocated)}
                            </div>
                            <span className="text-[10px] text-slate-400 mt-0.5 block">
                                Ready for checkout in this receipt
                            </span>
                        </div>
                    </div>

                    {/* 4. Active Fees & Payment Allocation Table */}
                    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-2xs overflow-hidden">
                        <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50/50 dark:bg-slate-800/30">
                            <div>
                                <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                    <span>Assigned Fee Heads &amp; Dues</span>
                                    <Badge variant="outline" className="text-[10px] py-0 font-semibold">
                                        {activeFees.length} Active
                                    </Badge>
                                </h3>
                                <p className="text-xs text-slate-500">
                                    Enter amounts to allocate for this collection receipt or click &quot;Pay All Dues&quot;.
                                </p>
                            </div>

                            <div className="flex items-center gap-2">
                                {activeFees.length > 0 && parseFloat(feesData.total_outstanding) > 0 && (
                                    <Button
                                        size="sm"
                                        onClick={handleAutoAllocateAll}
                                        className="bg-emerald-600 hover:bg-emerald-500 text-white gap-1.5"
                                    >
                                        <Zap className="w-3.5 h-3.5" />
                                        <span>Auto-Allocate All Dues</span>
                                    </Button>
                                )}

                                {canManage && (
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={() => setIsAssignOpen(!isAssignOpen)}
                                        className="h-8 px-3 text-xs font-semibold gap-1.5 border-slate-200 dark:border-slate-700 rounded-lg cursor-pointer"
                                    >
                                        <Plus className="w-3.5 h-3.5" />
                                        <span>{isAssignOpen ? "Close Assign" : "Assign Fee"}</span>
                                    </Button>
                                )}
                            </div>
                        </div>

                        {/* Collapsible Assign Fee Form */}
                        {isAssignOpen && canManage && (
                            <form onSubmit={handleAssign} className="p-4 bg-sky-50/40 dark:bg-sky-950/20 border-b border-sky-100 dark:border-sky-900/40 grid grid-cols-1 sm:grid-cols-4 gap-3 items-end">
                                <div className="space-y-1.5">
                                    <Label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                        Fee Head <span className="text-rose-500">*</span>
                                    </Label>
                                    <Select
                                        value={assignForm.fee_head}
                                        onValueChange={(v) => setAssignForm((f) => ({ ...f, fee_head: v }))}
                                    >
                                        <SelectTrigger className="h-[42px] text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                                            <SelectValue placeholder="Select fee type" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {heads.filter((h) => h.is_active).map((h) => (
                                                <SelectItem key={h.id} value={h.id} className="text-xs">
                                                    {h.name}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>

                                <div className="space-y-1.5">
                                    <Label htmlFor="assign_amount" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                        Amount Due ({CURRENCY}) <span className="text-rose-500">*</span>
                                    </Label>
                                    <Input
                                        id="assign_amount"
                                        type="number"
                                        step="0.01"
                                        placeholder="0.00"
                                        value={assignForm.amount_due}
                                        onChange={(e) => setAssignForm((f) => ({ ...f, amount_due: e.target.value }))}
                                        className="h-[42px] text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                                    />
                                </div>

                                <div className="space-y-1.5">
                                    <Label htmlFor="assign_due_date" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                        Due Date
                                    </Label>
                                    <Input
                                        id="assign_due_date"
                                        type="date"
                                        value={assignForm.due_date}
                                        onChange={(e) => setAssignForm((f) => ({ ...f, due_date: e.target.value }))}
                                        className="h-[42px] text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                                    />
                                </div>

                                <Button
                                    type="submit"
                                    disabled={assigning || !assignForm.fee_head || !assignForm.amount_due}
                                    className="h-[42px]"
                                >
                                    {assigning ? <LoaderCircle className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Plus className="w-3.5 h-3.5 mr-1.5" />}
                                    Assign to Student
                                </Button>
                            </form>
                        )}

                        {/* Fee Table */}
                        <TableShell>
                            <Table>
                                <TableHeader>
                                    <TableRow className="hover:bg-transparent">
                                        <TableHead className="pl-5">Fee Head &amp; Schedule</TableHead>
                                        <TableHeadNumeric>Amount Due</TableHeadNumeric>
                                        <TableHeadNumeric>Paid</TableHeadNumeric>
                                        <TableHeadNumeric>Outstanding</TableHeadNumeric>
                                        <TableHead className="text-center">Status</TableHead>
                                        <TableHead className="w-44">Collect Amount ({CURRENCY})</TableHead>
                                        <TableHead className="text-right pr-5">Cancel</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {feesData.fees.length > 0 ? (
                                        feesData.fees.map((fee) => {
                                            const outstanding = parseFloat(fee.outstanding_balance);
                                            const isCollectable = fee.status === "active" && outstanding > 0;

                                            return (
                                                <TableRow
                                                    key={fee.id}
                                                    className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors border-b border-slate-100 dark:border-slate-800/70"
                                                >
                                                    <TableCell className="py-3 pl-5">
                                                        <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                            {fee.fee_head_name}
                                                        </div>
                                                        <div className="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5">
                                                            <Calendar className="w-3 h-3 text-slate-400" />
                                                            <span>Due: {formatDate(fee.due_date)}</span>
                                                        </div>
                                                    </TableCell>

                                                    <TableCell className="py-3 text-right text-xs font-mono tabular-nums text-slate-700 dark:text-slate-300">
                                                        {formatIndianCurrency(fee.amount_due)}
                                                    </TableCell>

                                                    <TableCell className="py-3 text-right text-xs font-mono tabular-nums font-semibold text-emerald-600 dark:text-emerald-400">
                                                        {formatIndianCurrency(fee.amount_paid)}
                                                    </TableCell>

                                                    <TableCell className="py-3 text-right text-xs font-mono tabular-nums font-bold text-slate-900 dark:text-slate-100">
                                                        {outstanding > 0 ? (
                                                            <span className="text-rose-600 dark:text-rose-400">
                                                                {formatIndianCurrency(fee.outstanding_balance)}
                                                            </span>
                                                        ) : (
                                                            <span className="text-emerald-600 dark:text-emerald-400">
                                                                Paid in Full
                                                            </span>
                                                        )}
                                                    </TableCell>

                                                    <TableCell className="py-3 text-center">
                                                        {fee.status === "active" ? (
                                                            outstanding === 0 ? (
                                                                <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300/80 font-semibold text-[10px]">
                                                                    Cleared
                                                                </Badge>
                                                            ) : (
                                                                <Badge className="bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300/80 font-semibold text-[10px]">
                                                                    Pending
                                                                </Badge>
                                                            )
                                                        ) : (
                                                            <Badge className="bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-300/80 font-semibold text-[10px]">
                                                                Cancelled
                                                            </Badge>
                                                        )}
                                                    </TableCell>

                                                    {/* Collection Allocation Input */}
                                                    <TableCell className="py-3">
                                                        {isCollectable && canCollect ? (
                                                            <div className="flex items-center gap-1.5">
                                                                <Input
                                                                    type="number"
                                                                    step="0.01"
                                                                    min="0"
                                                                    max={fee.outstanding_balance}
                                                                    placeholder="0.00"
                                                                    value={selectedAllocations[fee.id] ?? ""}
                                                                    onChange={(e) =>
                                                                        setSelectedAllocations((prev) => ({
                                                                            ...prev,
                                                                            [fee.id]: e.target.value,
                                                                        }))
                                                                    }
                                                                    className="h-8 text-xs font-mono w-28 rounded-lg border-slate-200 dark:border-slate-800"
                                                                />
                                                                <Button
                                                                    type="button"
                                                                    size="sm"
                                                                    variant="ghost"
                                                                    onClick={() =>
                                                                        setSelectedAllocations((prev) => ({
                                                                            ...prev,
                                                                            [fee.id]: fee.outstanding_balance,
                                                                        }))
                                                                    }
                                                                    className="h-8 px-1.5 text-[10px] font-bold text-sky-600 hover:bg-sky-50"
                                                                    title="Allocate full balance"
                                                                >
                                                                    Full
                                                                </Button>
                                                            </div>
                                                        ) : (
                                                            <span className="text-xs text-slate-400">—</span>
                                                        )}
                                                    </TableCell>

                                                    {/* Cancellation Action */}
                                                    <TableCell className="text-right pr-5 py-3">
                                                        {fee.status === "active" && canManage ? (
                                                            <div className="flex items-center justify-end gap-1.5">
                                                                <Input
                                                                    placeholder="Reason"
                                                                    value={cancelReason[fee.id] ?? ""}
                                                                    onChange={(e) =>
                                                                        setCancelReason((prev) => ({
                                                                            ...prev,
                                                                            [fee.id]: e.target.value,
                                                                        }))
                                                                    }
                                                                    className="h-7 text-[11px] w-24 rounded-md border-slate-200 dark:border-slate-800"
                                                                />
                                                                <Button
                                                                    size="sm"
                                                                    variant="ghost"
                                                                    disabled={cancelling}
                                                                    onClick={() => handleCancel(fee.id)}
                                                                    className="h-7 w-7 p-0 text-rose-500 hover:text-rose-700 hover:bg-rose-50"
                                                                    title="Cancel fee item"
                                                                >
                                                                    <XCircle className="w-4 h-4" />
                                                                </Button>
                                                            </div>
                                                        ) : (
                                                            <span className="text-xs text-slate-400">—</span>
                                                        )}
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        })
                                    ) : (
                                        <TableRow>
                                            <TableCell colSpan={7} className="h-32 text-center text-xs text-slate-500">
                                                No fee items have been assigned to this student yet.
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </TableBody>
                            </Table>
                        </TableShell>
                    </div>

                    {/* 5. Checkout & Payment Recording Card */}
                    {canCollect && (
                        <div className="p-5 bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-2xs space-y-4">
                            <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                                <div className="flex items-center gap-2">
                                    <div className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
                                        <ReceiptIcon className="w-4 h-4" />
                                    </div>
                                    <div>
                                        <h3 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                                            Payment Processing &amp; Receipt Generation
                                        </h3>
                                        <p className="text-[11px] text-slate-400">Select payment channel, note transaction reference, and issue receipt</p>
                                    </div>
                                </div>

                                <div className="text-right">
                                    <span className="text-[10px] text-slate-400 uppercase font-semibold">Total Collection</span>
                                    <div className="text-lg font-black text-slate-900 dark:text-white font-mono">
                                        {formatIndianCurrency(totalAllocated)}
                                    </div>
                                </div>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 items-end">
                                <div className="space-y-1.5">
                                    <Label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                        Payment Method <span className="text-rose-500">*</span>
                                    </Label>
                                    <Select value={method} onValueChange={(v) => setMethod(v as PaymentMethod)}>
                                        <SelectTrigger className="h-[42px] text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="cash" className="text-xs">Cash Desk</SelectItem>
                                            <SelectItem value="upi" className="text-xs">UPI / Dynamic QR</SelectItem>
                                            <SelectItem value="bank_transfer" className="text-xs">Bank Transfer / NEFT</SelectItem>
                                            <SelectItem value="cheque" className="text-xs">Cheque / Demand Draft</SelectItem>
                                            <SelectItem value="online" className="text-xs">Online Payment Gateway</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>

                                <div className="space-y-1.5">
                                    <Label htmlFor="pay_ref" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                        Transaction Reference / Cheque No <span className="text-slate-400 font-normal">(Optional)</span>
                                    </Label>
                                    <Input
                                        id="pay_ref"
                                        placeholder="e.g. UPI Ref #893412 or Cheque #102938"
                                        value={referenceNote}
                                        onChange={(e) => setReferenceNote(e.target.value)}
                                        className="h-[42px] text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                                    />
                                </div>

                                <Button
                                    onClick={handleRecordPayment}
                                    disabled={recording || totalAllocated <= 0}
                                    className="h-[42px] bg-emerald-600 hover:bg-emerald-500 text-white gap-2"
                                >
                                    {recording ? (
                                        <>
                                            <LoaderCircle className="w-4 h-4 animate-spin" />
                                            <span>Recording Payment...</span>
                                        </>
                                    ) : (
                                        <>
                                            <CheckCircle2 className="w-4 h-4" />
                                            <span>Record Payment ({formatIndianCurrency(totalAllocated)})</span>
                                        </>
                                    )}
                                </Button>
                            </div>
                        </div>
                    )}

                    {/* 6. Payment History & Official Receipts */}
                    <TableShell
                        header={
                            <div className="p-3.5 sm:px-4 sm:py-3 flex items-center justify-between">
                                <h3 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider flex items-center gap-2">
                                    <span>Collection Receipts History</span>
                                    <Badge variant="outline" className="text-[10px] py-0 font-semibold">
                                        {payments.length} Receipts
                                    </Badge>
                                </h3>
                            </div>
                        }
                    >
                        <Table>
                            <TableHeader>
                                <TableRow className="hover:bg-transparent">
                                    <TableHead className="pl-5">Receipt #</TableHead>
                                    <TableHead>Date</TableHead>
                                    <TableHeadNumeric>Amount Paid</TableHeadNumeric>
                                    <TableHead>Payment Channel</TableHead>
                                    <TableHead>Reference Note</TableHead>
                                    <TableHead className="text-right">Status</TableHead>
                                    <TableHead className="text-right pr-5">Action</TableHead>
                                </TableRow>
                            </TableHeader>
                                <TableBody>
                                    {payments && payments.length > 0 ? (
                                        payments.map((p) => (
                                            <TableRow
                                                key={p.id}
                                                className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors border-b border-slate-100 dark:border-slate-800/70"
                                            >
                                                <TableCell className="py-3 pl-5">
                                                    <code className="text-xs font-mono font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-200 dark:border-emerald-800">
                                                        {p.receipt_number}
                                                    </code>
                                                </TableCell>

                                                <TableCell className="py-3 text-xs text-slate-600 dark:text-slate-400">
                                                    {formatDate(p.created_at)}
                                                </TableCell>

                                                <TableCell className="py-3 text-right text-xs font-bold text-slate-900 dark:text-white font-mono tabular-nums">
                                                    {formatIndianCurrency(p.amount)}
                                                </TableCell>

                                                <TableCell className="py-3 text-xs capitalize text-slate-700 dark:text-slate-300">
                                                    {p.method.replace("_", " ")}
                                                </TableCell>

                                                <TableCell className="py-3 text-xs text-slate-500 font-mono">
                                                    {p.reference_note || "—"}
                                                </TableCell>

                                                <TableCell className="text-right py-3">
                                                    <Badge
                                                        className={`text-[10px] font-semibold ${
                                                            p.status === "completed"
                                                                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300/80"
                                                                : "bg-rose-50 text-rose-700 border border-rose-300"
                                                        }`}
                                                    >
                                                        {p.status === "completed" ? "Verified" : "Reversed"}
                                                    </Badge>
                                                </TableCell>

                                                <TableCell className="text-right pr-5 py-3">
                                                    <div className="flex items-center justify-end gap-1.5">
                                                    {canCollect && p.status === "completed" && !p.reverses && !p.is_reversed && p.paid_via_gateway && (
                                                        <span className="text-[11px] text-slate-500 dark:text-slate-400" title={`Refund this in ${p.paid_via_gateway}; it cannot be reversed here.`}>
                                                            Paid via {p.paid_via_gateway}
                                                        </span>
                                                    )}
                                                    {canCollect && p.status === "completed" && !p.reverses && !p.is_reversed && !p.paid_via_gateway && (
                                                        <>
                                                            <Input
                                                                placeholder="Reason"
                                                                aria-label={`Reason for reversing ${p.receipt_number}`}
                                                                value={reverseReason[p.id] ?? ""}
                                                                onChange={(e) => setReverseReason((prev) => ({ ...prev, [p.id]: e.target.value }))}
                                                                className="h-7 text-[11px] w-24 rounded-md border-slate-200 dark:border-slate-800"
                                                            />
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                disabled={reversing}
                                                                onClick={() => handleReverse(p.id, p.receipt_number)}
                                                                className="h-7 text-xs font-semibold px-2 rounded-lg gap-1 text-rose-600 border-rose-200 hover:bg-rose-50 hover:text-rose-700"
                                                                title="Reverse this payment"
                                                            >
                                                                <RotateCcw className="h-3 w-3" />
                                                                <span>Reverse</span>
                                                            </Button>
                                                        </>
                                                    )}
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        onClick={() => setReceiptToPrint(p.id)}
                                                        className="h-7 text-xs font-semibold px-2 rounded-lg gap-1 border-slate-200 dark:border-slate-800 hover:text-indigo-600 hover:border-indigo-300"
                                                    >
                                                        <Printer className="h-3 w-3" />
                                                        <span>Receipt</span>
                                                    </Button>
                                                    </div>
                                                </TableCell>
                                            </TableRow>
                                        ))
                                    ) : (
                                        <TableRow>
                                            <TableCell colSpan={7} className="h-28 text-center text-xs text-slate-500">
                                                No payment receipts have been recorded for this student yet.
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </TableBody>
                            </Table>
                        </TableShell>
                </div>
            )}

            {/* Official Fee Receipt Modal */}
            <ReceiptModal
                isOpen={Boolean(receiptToPrint)}
                onClose={() => setReceiptToPrint(null)}
                paymentId={receiptToPrint}
            />
        </div>
    );
}

export default function CollectPaymentPage() {
    return (
        <Suspense fallback={<div className="h-64 animate-pulse bg-slate-100 dark:bg-slate-800 rounded-xl" />}>
            <CollectPaymentContent />
        </Suspense>
    );
}
