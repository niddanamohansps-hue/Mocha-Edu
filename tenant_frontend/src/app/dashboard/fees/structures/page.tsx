"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import {
    LoaderCircle,
    Plus,
    Receipt,
    Coins,
    Calendar,
    ArrowRight,
    TrendingDown,
    Layers,
    FileSpreadsheet,
    CheckCircle2,
    Clock,
    Tag,
    IndianRupee,
} from "lucide-react";
import {
    useCreateFeeHead,
    useCreateFeeStructure,
    useFeeHeads,
    useFeeStructures,
} from "@/hooks/useFees";
import { FEE_FREQUENCY_CHOICES } from "@/types/Fees";
import { usePermissions } from "@/providers/PermissionProvider";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
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
import Unauthorized from "@/components/Unauthorized";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { formatIndianCurrency } from "@/lib/currency";
import { toast } from "sonner";

function getFrequencyBadge(frequency: string) {
    switch (frequency) {
        case "one_time":
            return (
                <Badge
                    variant="outline"
                    className="bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 font-semibold text-[11px]"
                >
                    One-Time
                </Badge>
            );
        case "monthly":
            return (
                <Badge
                    variant="outline"
                    className="bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-300 font-semibold text-[11px]"
                >
                    Monthly
                </Badge>
            );
        case "term":
        case "quarterly":
            return (
                <Badge
                    variant="outline"
                    className="bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 font-semibold text-[11px]"
                >
                    Term / Quarterly
                </Badge>
            );
        case "annual":
            return (
                <Badge
                    variant="outline"
                    className="bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 font-semibold text-[11px]"
                >
                    Annual
                </Badge>
            );
        default:
            return (
                <Badge variant="outline" className="text-[11px] capitalize">
                    {frequency.replace("_", " ")}
                </Badge>
            );
    }
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

export default function FeeStructuresPage() {
    const { can, isOwner } = usePermissions();
    const { selectedYear } = useAcademicYear();
    const academicYear = selectedYear?.name || "";
    const canManage = isOwner || can("manage_fee_structures");
    const canView = canManage || can("view_fees");

    const {
        data: heads,
        isLoading: loadingHeads,
        isError: headsError,
        refetch: refetchHeads,
    } = useFeeHeads();

    const {
        data: structures,
        isLoading: loadingStructures,
        isError: structuresError,
        refetch: refetchStructures,
    } = useFeeStructures(academicYear);

    const { mutate: createHead, isPending: creatingHead } = useCreateFeeHead();
    const { mutate: createStructure, isPending: creatingStructure } = useCreateFeeStructure();

    const [newHeadName, setNewHeadName] = useState("");
    const [form, setForm] = useState({
        fee_head: "",
        amount: "",
        frequency: "one_time",
        due_date: "",
    });

    const handleCreateHead = (e: React.FormEvent) => {
        e.preventDefault();
        if (!newHeadName.trim()) return;
        createHead(
            { name: newHeadName.trim() },
            {
                onSuccess: () => {
                    toast.success(`Fee category "${newHeadName.trim()}" added!`);
                    setNewHeadName("");
                    refetchHeads();
                },
                onError: (err: any) => {
                    toast.error(err?.message || "Failed to add fee type");
                },
            }
        );
    };

    const handleCreateStructure = (e: React.FormEvent) => {
        e.preventDefault();
        if (!form.fee_head || !form.amount) {
            toast.error("Please choose a fee type and set the amount.");
            return;
        }
        createStructure(
            {
                fee_head: form.fee_head,
                academic_year: academicYear,
                amount: form.amount,
                frequency: form.frequency as any,
                due_date: form.due_date || null,
            } as any,
            {
                onSuccess: () => {
                    toast.success("Fee structure definition saved!");
                    setForm({ fee_head: "", amount: "", frequency: "one_time", due_date: "" });
                    refetchStructures();
                },
                onError: (err: any) => {
                    toast.error(err?.message || "Failed to create fee structure");
                },
            }
        );
    };

    // Calculate total annual fees per student in this structure
    const totalStructureSum = useMemo(() => {
        if (!structures || structures.length === 0) return 0;
        return structures.reduce((sum, s) => sum + parseFloat(s.amount || "0"), 0);
    }, [structures]);

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-7 max-w-7xl mx-auto pb-24 animate-in fade-in duration-500">
            {/* 1. Senior Executive Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Receipt className="h-7 w-7 text-sky-600 dark:text-sky-400" />
                        <span>Fee Structures &amp; Heads Setup</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Configure institutional fee categories, schedule payment slabs, due dates, and term charges
                    </p>
                </div>

                {/* Right Action Navigation */}
                <div className="flex items-center gap-2.5 shrink-0">
                    <Button
                        asChild
                        variant="outline"
                        size="sm"
                        className="h-9 px-3 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 cursor-pointer shadow-2xs"
                    >
                        <Link href="/dashboard/fees/reports">
                            <TrendingDown className="h-3.5 w-3.5 text-rose-500" />
                            <span>Defaulters Report</span>
                        </Link>
                    </Button>
                    <Button
                        asChild
                        size="sm"
                        className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95"
                    >
                        <Link href="/dashboard/fees/collect">
                            <Coins className="h-3.5 w-3.5" />
                            <span>Cashier Desk</span>
                        </Link>
                    </Button>
                </div>
            </div>

            {/* 2. Top Summary & Academic Session Card */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-5 shadow-2xs space-y-1">
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                        Academic Session
                    </span>
                    <div className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2 mt-1">
                        <span>{academicYear || "No term selected"}</span>
                        {selectedYear?.is_current && (
                            <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 text-[10px] font-bold">
                                Current
                            </Badge>
                        )}
                    </div>
                    <span className="text-xs text-slate-500">Active session for fee charging</span>
                </div>

                <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-5 shadow-2xs space-y-1">
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                        Active Fee Heads
                    </span>
                    <div className="text-xl font-bold text-indigo-600 dark:text-indigo-400 mt-1">
                        {heads?.filter((h) => h.is_active).length ?? 0} Categories
                    </div>
                    <span className="text-xs text-slate-500">Tuition, Transport, Lab, etc.</span>
                </div>

                <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-5 shadow-2xs space-y-1">
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                        Standard Slabs Total
                    </span>
                    <div className="text-xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                        {formatIndianCurrency(totalStructureSum)}
                    </div>
                    <span className="text-xs text-slate-500">Total defined yearly charges</span>
                </div>
            </div>

            {/* 3. Fee Heads / Categories Library Card */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-6 shadow-2xs space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 dark:border-slate-800 pb-3">
                    <div>
                        <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                            <Tag className="w-4 h-4 text-sky-600" />
                            <span>Institutional Fee Categories</span>
                        </h2>
                        <p className="text-xs text-slate-400 mt-0.5">
                            Predefined billable heads used across standard fee structures and ad-hoc student dues
                        </p>
                    </div>

                    {/* Quick Add Fee Type Input */}
                    {canManage && (
                        <form onSubmit={handleCreateHead} className="flex items-center gap-2">
                            <Input
                                placeholder="New fee head (e.g. Science Lab)..."
                                value={newHeadName}
                                onChange={(e) => setNewHeadName(e.target.value)}
                                className="h-9 w-60 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50"
                            />
                            <Button
                                type="submit"
                                size="sm"
                                disabled={creatingHead || !newHeadName.trim()}
                                className="h-9 px-3 gap-1 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg shadow-2xs"
                            >
                                {creatingHead ? (
                                    <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                    <Plus className="h-3.5 w-3.5" />
                                )}
                                <span>Add</span>
                            </Button>
                        </form>
                    )}
                </div>

                {/* Available Fee Heads Pills */}
                {loadingHeads ? (
                    <LoadingState className="py-6" />
                ) : headsError ? (
                    <ErrorState onRetry={refetchHeads} />
                ) : (
                    <div className="flex flex-wrap gap-2 pt-1">
                        {heads?.map((h) => (
                            <div
                                key={h.id}
                                className={`px-3 py-1.5 rounded-xl border text-xs font-semibold flex items-center gap-1.5 ${
                                    h.is_active
                                        ? "bg-slate-50 text-slate-800 border-slate-200/80 dark:bg-slate-800/60 dark:text-slate-200 dark:border-slate-700"
                                        : "bg-rose-50 text-rose-600 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300"
                                }`}
                            >
                                <span className={`h-2 w-2 rounded-full ${h.is_active ? "bg-emerald-500" : "bg-rose-500"}`} />
                                <span>{h.name}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* 4. Create Fee Structure Matrix Card */}
            {canManage && (
                <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-6 shadow-2xs space-y-4">
                    <div className="border-b border-slate-100 dark:border-slate-800 pb-3">
                        <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                            <Plus className="w-4 h-4 text-emerald-600" />
                            <span>Add Fee Structure Slab ({academicYear})</span>
                        </h2>
                        <p className="text-xs text-slate-400 mt-0.5">
                            Set up annual charges, recurring monthly fees, or one-off admission components
                        </p>
                    </div>

                    <form onSubmit={handleCreateStructure} className="space-y-4">
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 items-end">
                            {/* Fee Head */}
                            <div className="space-y-1.5">
                                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                    Fee Category <span className="text-rose-500">*</span>
                                </label>
                                <Select
                                    value={form.fee_head}
                                    onValueChange={(v) => setForm((f) => ({ ...f, fee_head: v }))}
                                >
                                    <SelectTrigger className="h-10 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium">
                                        <SelectValue placeholder="Select fee type..." />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {heads
                                            ?.filter((h) => h.is_active)
                                            .map((h) => (
                                                <SelectItem key={h.id} value={h.id} className="text-xs">
                                                    {h.name}
                                                </SelectItem>
                                            ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            {/* Amount in INR */}
                            <div className="space-y-1.5">
                                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                    Charge Amount (₹) <span className="text-rose-500">*</span>
                                </label>
                                <div className="relative">
                                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs font-bold text-slate-400">
                                        ₹
                                    </span>
                                    <Input
                                        type="number"
                                        inputMode="decimal"
                                        placeholder="0.00"
                                        value={form.amount}
                                        onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
                                        className="h-10 pl-7 text-xs font-bold border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50"
                                    />
                                </div>
                            </div>

                            {/* Frequency */}
                            <div className="space-y-1.5">
                                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                    Billing Frequency <span className="text-rose-500">*</span>
                                </label>
                                <Select
                                    value={form.frequency}
                                    onValueChange={(v) => setForm((f) => ({ ...f, frequency: v }))}
                                >
                                    <SelectTrigger className="h-10 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {FEE_FREQUENCY_CHOICES.map((freq) => (
                                            <SelectItem key={freq} value={freq} className="text-xs capitalize">
                                                {freq.replace("_", " ")}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            {/* Due Date */}
                            <div className="space-y-1.5">
                                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                    Due Date (Optional)
                                </label>
                                <Input
                                    type="date"
                                    value={form.due_date}
                                    onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
                                    className="h-10 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium"
                                />
                            </div>
                        </div>

                        <div className="flex justify-end pt-2">
                            <Button
                                type="submit"
                                disabled={creatingStructure || !form.fee_head || !form.amount}
                                className="h-9 px-5 gap-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95"
                            >
                                {creatingStructure && <LoaderCircle className="h-4 w-4 animate-spin" />}
                                <Plus className="h-4 w-4" />
                                <span>Create Fee Structure Slab</span>
                            </Button>
                        </div>
                    </form>
                </div>
            )}

            {/* 5. Existing Fee Structures Table Card */}
            <div className="space-y-3">
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                            <FileSpreadsheet className="w-4 h-4 text-sky-600" />
                            <span>Defined Slabs for {academicYear}</span>
                        </h2>
                        <p className="text-xs text-slate-500 mt-0.5">
                            Standard tuition, infrastructure, and auxiliary charges configured for this academic year
                        </p>
                    </div>
                </div>

                {loadingStructures ? (
                    <LoadingState className="py-16" />
                ) : structuresError ? (
                    <ErrorState onRetry={refetchStructures} />
                ) : !structures || structures.length === 0 ? (
                    <EmptyState
                        icon={<Receipt className="h-6 w-6 stroke-[1.75]" />}
                        title={`No fee structures defined for ${academicYear} yet`}
                        description="Add your first fee slab using the form above to establish student billing rules."
                        hint="Create recurring monthly fees or one-time annual charges using the slab form above."
                        className="py-16"
                    />
                ) : (
                    <TableShell>
                        <Table>
                            <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                <TableRow>
                                    <TableHead className="py-3 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Fee Category
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Rate / Amount
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Billing Cycle
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Payment Due Date
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider pr-4">
                                        Applicable Level
                                    </TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {structures.map((s) => (
                                    <TableRow
                                        key={s.id}
                                        className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                    >
                                        <TableCell className="py-3 pl-4">
                                            <div className="font-semibold text-xs text-slate-900 dark:text-white">
                                                {s.fee_head_name}
                                            </div>
                                        </TableCell>

                                        <TableCell className="py-3">
                                            <span className="font-bold text-xs text-slate-900 dark:text-white">
                                                {formatIndianCurrency(s.amount)}
                                            </span>
                                        </TableCell>

                                        <TableCell className="py-3">
                                            {getFrequencyBadge(s.frequency)}
                                        </TableCell>

                                        <TableCell className="py-3 text-xs text-slate-500 font-medium">
                                            {formatDateDisplay(s.due_date)}
                                        </TableCell>

                                        <TableCell className="py-3 pr-4">
                                            <span className="text-xs font-medium text-slate-600 dark:text-slate-400">
                                                {s.level_name || "All Grade Levels"}
                                            </span>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableShell>
                )}
            </div>
        </div>
    );
}
