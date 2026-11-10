"use client";

import { useMemo, useState, Suspense } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import {
    LoaderCircle,
    ArrowRight,
    RotateCcw,
    GraduationCap,
    CheckCheck,
    AlertTriangle,
    ShieldAlert,
    CheckCircle2,
    Calendar,
    Users,
    ArrowRightCircle,
    Layers,
    FileSpreadsheet,
    HelpCircle,
    Sparkles,
} from "lucide-react";
import { useAcademicLevels, useSections } from "@/hooks/useAcademics";
import {
    useExecutePromotion,
    usePreviewPromotion,
    usePromotionCandidates,
    usePromotionHistory,
    useReversePromotion,
} from "@/hooks/usePromotion";
import {
    PROMOTION_ACTION_LABELS,
    PromotionAction,
    PromotionEntryInput,
} from "@/types/Promotion";
import { usePermissions } from "@/providers/PermissionProvider";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
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
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import { Pagination } from "@/components/ui/pagination";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { toast } from "sonner";

const HISTORY_PAGE_SIZE = 15;

const ACTIONS: PromotionAction[] = ["promoted", "retained", "withdrawn", "transferred", "graduated"];

function PromotionDeskContent() {
    const { can, isOwner } = usePermissions();
    const { selectedYear, academicYears } = useAcademicYear();
    const canManage = isOwner || can("manage_student_promotion");

    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();

    const updateParams = (updates: Record<string, string | null>) => {
        const params = new URLSearchParams(searchParams.toString());
        for (const [key, value] of Object.entries(updates)) {
            if (value === null || value === "") {
                params.delete(key);
            } else {
                params.set(key, value);
            }
        }
        const query = params.toString();
        router.replace(query ? `${pathname}?${query}` : pathname);
    };

    // Source selection from URL
    const sourceYear = searchParams.get("sourceYear") || selectedYear?.name || "";
    const levelId = searchParams.get("levelId") || "";
    const sectionId = searchParams.get("sectionId") || "";
    const historyPageParam = Number(searchParams.get("historyPage"));
    const historyPage = Number.isInteger(historyPageParam) && historyPageParam >= 1 ? historyPageParam : 1;

    const { data: levels } = useAcademicLevels();
    const { data: sections } = useSections();
    const sectionsForLevel = useMemo(
        () => (sections || []).filter((s) => s.level === levelId),
        [sections, levelId]
    );

    // Candidates query
    const {
        data: candidates,
        isLoading: loadingCandidates,
        isError: candidatesError,
        refetch: refetchCandidates,
    } = usePromotionCandidates(sourceYear, levelId, sectionId || undefined);

    const [selected, setSelected] = useState<Record<string, boolean>>({});
    const [actionByStudent, setActionByStudent] = useState<Record<string, PromotionAction>>({});

    // Target parameters
    const [targetYear, setTargetYear] = useState("");
    const [targetLevelId, setTargetLevelId] = useState("");
    const [targetSectionId, setTargetSectionId] = useState("");
    const targetSectionsForLevel = useMemo(
        () => (sections || []).filter((s) => s.level === targetLevelId),
        [sections, targetLevelId]
    );

    // Mutations
    const { mutate: preview, data: previewResults, isPending: previewing } = usePreviewPromotion();
    const { mutate: execute, data: executeResponse, isPending: executing } = useExecutePromotion();
    const { mutate: reverse, isPending: reversing } = useReversePromotion();

    const [reverseRecordId, setReverseRecordId] = useState<string | null>(null);

    // History query
    const {
        data: historyData,
        isLoading: loadingHistory,
        isError: historyError,
        refetch: refetchHistory,
    } = usePromotionHistory({ academic_year: sourceYear }, historyPage, HISTORY_PAGE_SIZE);
    const history = historyData?.results;

    const [showPreview, setShowPreview] = useState(false);

    if (!canManage) {
        return <Unauthorized />;
    }

    const toggleAll = (checked: boolean) => {
        const next: Record<string, boolean> = {};
        (candidates || []).forEach((c) => (next[c.student_id] = checked));
        setSelected(next);
    };

    const setAllActions = (action: PromotionAction) => {
        if (!candidates) return;
        const next: Record<string, PromotionAction> = { ...actionByStudent };
        for (const c of candidates) {
            if (selected[c.student_id]) {
                next[c.student_id] = action;
            }
        }
        setActionByStudent(next);
        toast.info(`Set selected students to "${PROMOTION_ACTION_LABELS[action]}"`);
    };

    const buildEntries = (): PromotionEntryInput[] => {
        return (candidates || [])
            .filter((c) => selected[c.student_id])
            .map((c) => {
                const action = actionByStudent[c.student_id] || "promoted";
                const entry: PromotionEntryInput = { student: c.student_id, action };
                if (action === "promoted" || action === "retained") {
                    entry.target_academic_year = targetYear;
                    if (action === "promoted" && targetLevelId) entry.target_level = targetLevelId;
                    if (targetSectionId) entry.target_section = targetSectionId;
                }
                return entry;
            });
    };

    const handlePreview = () => {
        const entries = buildEntries();
        if (entries.length === 0) {
            toast.error("Please select at least one student candidate.");
            return;
        }
        if (!targetYear) {
            toast.error("Please select a target academic year.");
            return;
        }
        preview(
            { source_academic_year: sourceYear, entries },
            {
                onSuccess: () => {
                    setShowPreview(true);
                    toast.success("Progression eligibility verified successfully.");
                },
                onError: (err: any) => {
                    toast.error(err?.message || "Failed to preview promotion");
                },
            }
        );
    };

    const handleConfirm = () => {
        const entries = buildEntries();
        if (entries.length === 0) return;
        execute(
            { source_academic_year: sourceYear, entries },
            {
                onSuccess: () => {
                    setShowPreview(false);
                    setSelected({});
                    refetchCandidates();
                    refetchHistory();
                    toast.success("Batch promotion executed successfully!");
                },
                onError: (err: any) => {
                    toast.error(err?.message || "Promotion execution failed");
                },
            }
        );
    };

    const handleReverseConfirm = () => {
        if (!reverseRecordId) return;
        reverse(
            { recordId: reverseRecordId },
            {
                onSuccess: () => {
                    setReverseRecordId(null);
                    refetchHistory();
                    refetchCandidates();
                    toast.success("Promotion record reversed successfully.");
                },
                onError: (err: any) => {
                    toast.error(err?.message || "Reversal failed");
                },
            }
        );
    };

    const selectedCount = Object.values(selected).filter(Boolean).length;
    const currentLevelObj = levels?.find((l) => l.id === levelId);
    const targetLevelObj = levels?.find((l) => l.id === targetLevelId);

    return (
        <div className="space-y-7 max-w-7xl mx-auto pb-24 animate-in fade-in duration-500">
            {/* 1. Senior Executive Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <GraduationCap className="h-7 w-7 text-sky-600 dark:text-sky-400" />
                        <span>Student Promotion &amp; Progression Desk</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Batch promote students, advance academic cohorts, allocate sections, or process year-end transfers
                    </p>
                </div>

                {/* Status Counter Pill */}
                {candidates && candidates.length > 0 && (
                    <div className="flex items-center gap-2 shrink-0">
                        <Badge
                            variant="outline"
                            className="h-8 px-3 gap-1.5 border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 text-xs font-semibold shadow-2xs"
                        >
                            <Users className="h-3.5 w-3.5 text-sky-600" />
                            <span>{candidates.length} Cohort Candidates</span>
                        </Badge>
                    </div>
                )}
            </div>

            {/* 2. Directional Progression Pipeline Stepper Card */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-5 shadow-2xs space-y-4">
                <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800/80 pb-3">
                    <span className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider flex items-center gap-2">
                        <Sparkles className="w-3.5 h-3.5 text-sky-600" />
                        Progression Pipeline Setup
                    </span>
                    <span className="text-xs text-slate-400">
                        Step 1: Define Source &amp; Target Classes
                    </span>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-11 gap-4 items-center">
                    {/* Source Container (Left: 5 cols) */}
                    <div className="lg:col-span-5 bg-slate-50/70 dark:bg-slate-950/60 rounded-xl p-4 border border-slate-200/70 dark:border-slate-800 space-y-3">
                        <div className="flex items-center gap-2 text-xs font-bold text-slate-700 dark:text-slate-300">
                            <span className="h-5 w-5 rounded-full bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-[11px] flex items-center justify-center font-bold">
                                1
                            </span>
                            <span>Source Term (Current Cohort)</span>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                            {/* Academic Year */}
                            <div className="space-y-1">
                                <label className="text-[11px] font-semibold text-slate-500">Year</label>
                                {academicYears.length > 0 ? (
                                    <Select
                                        value={sourceYear}
                                        onValueChange={(v) => updateParams({ sourceYear: v || null, historyPage: null })}
                                    >
                                        <SelectTrigger className="h-9 text-xs bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-medium">
                                            <SelectValue placeholder="Select year" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {academicYears.map((y) => (
                                                <SelectItem key={y.id} value={y.name} className="text-xs">
                                                    {y.name} {y.is_current ? "(Current)" : ""}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                ) : (
                                    <Input
                                        value={sourceYear}
                                        onChange={(e) => updateParams({ sourceYear: e.target.value || null, historyPage: null })}
                                        className="h-9 text-xs bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800"
                                    />
                                )}
                            </div>

                            {/* Source Level */}
                            <div className="space-y-1">
                                <label className="text-[11px] font-semibold text-slate-500">Grade Level *</label>
                                <Select value={levelId} onValueChange={(v) => updateParams({ levelId: v, sectionId: null })}>
                                    <SelectTrigger className="h-9 text-xs bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-medium">
                                        <SelectValue placeholder="Select grade" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {levels?.map((l) => (
                                            <SelectItem key={l.id} value={l.id} className="text-xs">
                                                {l.name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            {/* Source Section */}
                            <div className="space-y-1">
                                <label className="text-[11px] font-semibold text-slate-500">Section</label>
                                <Select value={sectionId || "ALL"} onValueChange={(v) => updateParams({ sectionId: v === "ALL" ? null : v })}>
                                    <SelectTrigger className="h-9 text-xs bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-medium">
                                        <SelectValue placeholder="All Sections" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="ALL" className="text-xs">All Sections</SelectItem>
                                        {sectionsForLevel.map((s) => (
                                            <SelectItem key={s.id} value={s.id} className="text-xs">
                                                Section {s.name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                    </div>

                    {/* Directional Progression Arrow (Center: 1 col) */}
                    <div className="lg:col-span-1 flex items-center justify-center py-2 lg:py-0">
                        <div className="h-10 w-10 rounded-full bg-sky-50 dark:bg-sky-950/70 border border-sky-200 dark:border-sky-800 flex items-center justify-center text-sky-600 dark:text-sky-400 shadow-2xs">
                            <ArrowRight className="h-5 w-5" />
                        </div>
                    </div>

                    {/* Target Container (Right: 5 cols) */}
                    <div className="lg:col-span-5 bg-sky-50/40 dark:bg-sky-950/20 rounded-xl p-4 border border-sky-200/70 dark:border-sky-900/50 space-y-3">
                        <div className="flex items-center gap-2 text-xs font-bold text-sky-900 dark:text-sky-200">
                            <span className="h-5 w-5 rounded-full bg-sky-200 dark:bg-sky-900 text-sky-800 dark:text-sky-300 text-[11px] flex items-center justify-center font-bold">
                                2
                            </span>
                            <span>Target Term (Destination Grade)</span>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                            {/* Target Year */}
                            <div className="space-y-1">
                                <label className="text-[11px] font-semibold text-slate-500">Target Year *</label>
                                {academicYears.length > 0 ? (
                                    <Select value={targetYear} onValueChange={setTargetYear}>
                                        <SelectTrigger className="h-9 text-xs bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-medium">
                                            <SelectValue placeholder="Select target" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {academicYears.map((y) => (
                                                <SelectItem key={y.id} value={y.name} className="text-xs">
                                                    {y.name} {y.is_current ? "(Current)" : ""}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                ) : (
                                    <Input
                                        value={targetYear}
                                        onChange={(e) => setTargetYear(e.target.value)}
                                        className="h-9 text-xs bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800"
                                    />
                                )}
                            </div>

                            {/* Target Level */}
                            <div className="space-y-1">
                                <label className="text-[11px] font-semibold text-slate-500">Next Grade</label>
                                <Select
                                    value={targetLevelId}
                                    onValueChange={(v) => {
                                        setTargetLevelId(v);
                                        setTargetSectionId("");
                                    }}
                                >
                                    <SelectTrigger className="h-9 text-xs bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-medium">
                                        <SelectValue placeholder="Default (Next)" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {levels?.map((l) => (
                                            <SelectItem key={l.id} value={l.id} className="text-xs">
                                                {l.name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            {/* Target Section */}
                            <div className="space-y-1">
                                <label className="text-[11px] font-semibold text-slate-500">Target Section</label>
                                <Select value={targetSectionId || "UNASSIGNED"} onValueChange={(v) => setTargetSectionId(v === "UNASSIGNED" ? "" : v)}>
                                    <SelectTrigger className="h-9 text-xs bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-medium">
                                        <SelectValue placeholder="Unassigned" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="UNASSIGNED" className="text-xs">Unassigned</SelectItem>
                                        {targetSectionsForLevel.map((s) => (
                                            <SelectItem key={s.id} value={s.id} className="text-xs">
                                                Section {s.name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Step 3: Candidates Roster */}
            {!levelId ? (
                <EmptyState
                    title="Select a source academic year and grade level to load candidates"
                    description="Choose the academic session and class cohort from the controls above to inspect student records and configure progressions."
                    className="py-16 text-slate-500 text-sm"
                />
            ) : loadingCandidates ? (
                <LoadingState className="py-20" />
            ) : candidatesError ? (
                <ErrorState onRetry={refetchCandidates} />
            ) : !candidates || candidates.length === 0 ? (
                <EmptyState
                    title="No active students found in this cohort"
                    description={`No active student records matched ${sourceYear} • ${currentLevelObj?.name ?? "Selected Grade"}.`}
                    className="py-16 text-slate-500 text-sm"
                />
            ) : (
                <div className="space-y-4">
                    {/* Batch Actions Toolbar */}
                    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 p-3 shadow-2xs flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                        <div className="flex items-center gap-3">
                            <div className="flex items-center gap-2 pl-2">
                                <Checkbox
                                    id="select-all"
                                    checked={selectedCount === candidates.length && candidates.length > 0}
                                    onCheckedChange={(v) => toggleAll(Boolean(v))}
                                />
                                <label htmlFor="select-all" className="text-xs font-semibold text-slate-700 dark:text-slate-300 cursor-pointer">
                                    Select All ({candidates.length})
                                </label>
                            </div>
                            <span className="text-slate-300 dark:text-slate-700">|</span>
                            <span className="text-xs font-medium text-slate-500">
                                <span className="font-bold text-sky-600 dark:text-sky-400">{selectedCount}</span> selected
                            </span>
                        </div>

                        {/* Bulk Action Pill Triggers */}
                        {selectedCount > 0 && (
                            <div className="flex items-center gap-1.5 flex-wrap">
                                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mr-1">
                                    Set Selected:
                                </span>
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setAllActions("promoted")}
                                    className="h-8 px-2.5 text-xs font-semibold border-emerald-200 text-emerald-700 bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-950/40 dark:text-emerald-300"
                                >
                                    Promote
                                </Button>
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setAllActions("retained")}
                                    className="h-8 px-2.5 text-xs font-semibold border-amber-200 text-amber-700 bg-amber-50 hover:bg-amber-100 dark:bg-amber-950/40 dark:text-amber-300"
                                >
                                    Retain
                                </Button>
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setAllActions("graduated")}
                                    className="h-8 px-2.5 text-xs font-semibold border-indigo-200 text-indigo-700 bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-950/40 dark:text-indigo-300"
                                >
                                    Graduate
                                </Button>
                            </div>
                        )}
                    </div>

                    {/* High Density Candidates Table */}
                    <TableShell>
                        <Table>
                            <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                <TableRow className="hover:bg-transparent">
                                    <TableHead className="w-12 pl-4">
                                        <Checkbox
                                            checked={selectedCount === candidates.length && candidates.length > 0}
                                            onCheckedChange={(v) => toggleAll(Boolean(v))}
                                        />
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Student Candidate
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Current Placement
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Audit Warnings &amp; Flags
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider pr-4 min-w-[170px]">
                                        Progression Action
                                    </TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {candidates.map((c) => {
                                    const isRowSelected = Boolean(selected[c.student_id]);
                                    const action = actionByStudent[c.student_id] || "promoted";

                                    return (
                                        <TableRow
                                            key={c.student_id}
                                            className={`hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors border-b border-slate-100 dark:border-slate-800/70 ${
                                                isRowSelected ? "bg-sky-50/30 dark:bg-sky-950/20" : ""
                                            }`}
                                        >
                                            <TableCell className="pl-4">
                                                <Checkbox
                                                    checked={isRowSelected}
                                                    onCheckedChange={(v) =>
                                                        setSelected((s) => ({ ...s, [c.student_id]: Boolean(v) }))
                                                    }
                                                />
                                            </TableCell>

                                            {/* Student Details */}
                                            <TableCell className="py-3">
                                                <div className="flex items-center gap-2.5">
                                                    <Avatar name={c.full_name} size="sm" />
                                                    <div>
                                                        <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                            {c.full_name}
                                                        </div>
                                                        <div className="text-[10px] font-mono text-slate-400">
                                                            {c.enrollment_id}
                                                        </div>
                                                    </div>
                                                </div>
                                            </TableCell>

                                            {/* Current Class */}
                                            <TableCell className="py-3">
                                                <span className="font-semibold text-xs text-slate-800 dark:text-slate-200">
                                                    {c.current_level_name}
                                                </span>
                                                {c.current_section_name && (
                                                    <span className="text-xs text-slate-500 dark:text-slate-400">
                                                        {" "}• Section {c.current_section_name}
                                                    </span>
                                                )}
                                            </TableCell>

                                            {/* Warnings & Checks */}
                                            <TableCell className="py-3">
                                                <div className="flex flex-col gap-1 text-xs">
                                                    {c.fee_warning && (
                                                        <span className="inline-flex items-center gap-1 text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 px-2 py-0.5 rounded text-[11px] font-semibold w-fit">
                                                            <AlertTriangle className="h-3 w-3" />
                                                            Dues: ₹{c.fee_warning}
                                                        </span>
                                                    )}
                                                    {c.exam_warning && c.exam_warning.length > 0 && (
                                                        <span className="inline-flex items-center gap-1 text-rose-700 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 px-2 py-0.5 rounded text-[11px] font-semibold w-fit">
                                                            <ShieldAlert className="h-3 w-3" />
                                                            Failed: {c.exam_warning.join(", ")}
                                                        </span>
                                                    )}
                                                    {!c.fee_warning && (!c.exam_warning || c.exam_warning.length === 0) && (
                                                        <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-400 text-[11px] font-medium">
                                                            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                                                            Clear for Progression
                                                        </span>
                                                    )}
                                                </div>
                                            </TableCell>

                                            {/* Action Select */}
                                            <TableCell className="py-3 pr-4">
                                                <Select
                                                    value={action}
                                                    onValueChange={(v) =>
                                                        setActionByStudent((a) => ({
                                                            ...a,
                                                            [c.student_id]: v as PromotionAction,
                                                        }))
                                                    }
                                                >
                                                    <SelectTrigger className="h-8.5 text-xs bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-semibold w-40">
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {ACTIONS.map((a) => (
                                                            <SelectItem key={a} value={a} className="text-xs font-medium cursor-pointer">
                                                                {PROMOTION_ACTION_LABELS[a]}
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                            </TableBody>
                        </Table>
                    </TableShell>

                    {/* Preview Trigger Bar */}
                    <div className="flex items-center justify-between p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                        <div className="text-xs text-slate-500 font-medium">
                            Ready to audit {selectedCount} selected students against progression rules
                        </div>
                        <Button
                            onClick={handlePreview}
                            disabled={previewing || selectedCount === 0 || !sourceYear || !targetYear}
                            className="gap-2"
                        >
                            {previewing && <LoaderCircle className="h-4 w-4 animate-spin" />}
                            <span>Preview Promotion ({selectedCount} Selected)</span>
                            <ArrowRight className="h-3.5 w-3.5" />
                        </Button>
                    </div>
                </div>
            )}

            {/* Step 4: Preview Modal / Executive Verification Strip */}
            {showPreview && previewResults && (
                <div className="space-y-4 p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-lg animate-in fade-in duration-300">
                    <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800/80 pb-3">
                        <div>
                            <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                <CheckCheck className="w-5 h-5 text-emerald-600" />
                                <span>Progression Eligibility Verification</span>
                            </h2>
                            <p className="text-xs text-slate-500 mt-0.5">
                                Review conflicts and pre-flight checks before final academic record progression
                            </p>
                        </div>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setShowPreview(false)}
                            className="text-xs text-slate-500 hover:text-slate-900"
                        >
                            Dismiss
                        </Button>
                    </div>

                    <TableShell>
                        <Table>
                            <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                <TableRow>
                                    <TableHead className="py-3 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Student ID
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Assigned Action
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Target Academic Year
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Warnings / Conflicts
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider pr-4">
                                        Eligibility Status
                                    </TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {previewResults.map((r, i) => (
                                    <TableRow
                                        key={i}
                                        className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                    >
                                        <TableCell className="pl-4 font-mono text-xs font-bold text-slate-700 dark:text-slate-300">
                                            {r.student}
                                        </TableCell>
                                        <TableCell className="capitalize text-xs font-semibold text-slate-900 dark:text-white">
                                            {r.action}
                                        </TableCell>
                                        <TableCell className="text-xs text-slate-600 dark:text-slate-400">
                                            {r.target_academic_year || "—"}
                                        </TableCell>
                                        <TableCell className="text-xs text-amber-600 dark:text-amber-400">
                                            {r.warnings.join("; ") || "No warnings"}
                                        </TableCell>
                                        <TableCell className="pr-4">
                                            {r.eligible ? (
                                                <Badge
                                                    variant="outline"
                                                    className="bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 text-xs font-semibold"
                                                >
                                                    Ready to Progress
                                                </Badge>
                                            ) : (
                                                <Badge
                                                    variant="outline"
                                                    className="bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 text-xs font-semibold"
                                                >
                                                    {r.conflicts.join("; ") || "Conflict detected"}
                                                </Badge>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableShell>

                    <div className="flex items-center justify-end gap-3 pt-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setShowPreview(false)}
                            className="text-xs font-semibold"
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={handleConfirm}
                            disabled={executing}
                            className="bg-emerald-600 hover:bg-emerald-500 text-white gap-2"
                        >
                            {executing && <LoaderCircle className="h-4 w-4 animate-spin" />}
                            <ArrowRight className="h-4 w-4" />
                            <span>Confirm &amp; Execute Batch Progression</span>
                        </Button>
                    </div>
                </div>
            )}

            {/* Step 5: Execution Result Summary */}
            {executeResponse && (
                <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-2xs space-y-3">
                    <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                        <span>Execution Results</span>
                    </h2>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="p-3 rounded-xl bg-emerald-50/60 dark:bg-emerald-950/30 border border-emerald-200/60">
                            <span className="text-[11px] font-semibold text-emerald-600 uppercase tracking-wider block">
                                Successful
                            </span>
                            <span className="text-2xl font-black text-emerald-700 dark:text-emerald-300">
                                {executeResponse.results.filter((r) => r.status === "success").length}
                            </span>
                        </div>
                        <div className="p-3 rounded-xl bg-rose-50/60 dark:bg-rose-950/30 border border-rose-200/60">
                            <span className="text-[11px] font-semibold text-rose-600 uppercase tracking-wider block">
                                Skipped / Blocked
                            </span>
                            <span className="text-2xl font-black text-rose-700 dark:text-rose-300">
                                {executeResponse.results.filter((r) => r.status === "skipped").length}
                            </span>
                        </div>
                    </div>
                    {executeResponse.results.filter((r) => r.status === "skipped").length > 0 && (
                        <div className="text-xs text-rose-600 space-y-1 pt-1">
                            {executeResponse.results
                                .filter((r) => r.status === "skipped")
                                .map((r, i) => (
                                    <div key={i} className="font-mono">
                                        • {r.student}: {r.error}
                                    </div>
                                ))}
                        </div>
                    )}
                </div>
            )}

            {/* Step 6: Promotion Audit History for Current Term */}
            {loadingHistory && <LoadingState className="py-12" />}
            {!loadingHistory && historyError && <ErrorState onRetry={refetchHistory} />}

            {!loadingHistory && !historyError && history && history.length > 0 && (
                <div className="space-y-3 pt-6 border-t border-slate-200 dark:border-slate-800">
                    <div className="flex items-center justify-between">
                        <div>
                            <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                <RotateCcw className="w-4 h-4 text-sky-600" />
                                <span>Recent Promotion History ({sourceYear})</span>
                            </h2>
                            <p className="text-xs text-slate-500 mt-0.5">
                                Audit log of past grade advancements with one-click administrative reversal
                            </p>
                        </div>
                    </div>

                    <TableShell>
                        <Table>
                            <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                <TableRow>
                                    <TableHead className="py-3 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Student Candidate
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Action
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Academic Year Flow
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Grade Level Flow
                                    </TableHead>
                                    <TableHead className="text-right pr-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Actions
                                    </TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {history.map((r) => (
                                    <TableRow
                                        key={r.id}
                                        className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                    >
                                        <TableCell className="pl-4 py-3 font-semibold text-xs text-slate-900 dark:text-slate-100">
                                            {r.student_name}
                                        </TableCell>
                                        <TableCell className="py-3 capitalize text-xs font-medium text-slate-700 dark:text-slate-300">
                                            {r.action}
                                        </TableCell>
                                        <TableCell className="py-3 text-xs text-slate-600 dark:text-slate-400 font-mono">
                                            {r.source_academic_year} → {r.target_academic_year || "—"}
                                        </TableCell>
                                        <TableCell className="py-3 text-xs text-slate-600 dark:text-slate-400 font-medium">
                                            {r.source_level_name} → {r.target_level_name || "—"}
                                        </TableCell>
                                        <TableCell className="py-3 text-right pr-4">
                                            {(r.action === "promoted" || r.action === "retained") && !r.is_reversed && (
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    onClick={() => setReverseRecordId(r.id)}
                                                    className="h-8 px-2 text-xs text-rose-600 hover:text-rose-700 hover:bg-rose-50 dark:hover:bg-rose-950/40 font-semibold gap-1"
                                                >
                                                    <RotateCcw className="h-3 w-3" />
                                                    Reverse
                                                </Button>
                                            )}
                                            {r.is_reversed && (
                                                <span className="text-[11px] font-semibold text-slate-400">
                                                    Reversed
                                                </span>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                        {historyData && (
                            <Pagination
                                page={historyPage}
                                pageSize={HISTORY_PAGE_SIZE}
                                count={historyData.count}
                                onPageChange={(p) => updateParams({ historyPage: p <= 1 ? null : String(p) })}
                                className="border-t border-slate-200 dark:border-slate-800"
                            />
                        )}
                    </TableShell>
                </div>
            )}

            {/* Reversal Confirmation Dialog */}
            <ConfirmationDialog
                open={Boolean(reverseRecordId)}
                onOpenChange={(open) => !open && setReverseRecordId(null)}
                title="Reverse Promotion Record"
                description="Are you sure you want to revert this student's progression? This will restore their previous grade level and undo year-end transitions."
                confirmLabel="Yes, Reverse Progression"
                variant="destructive"
                isLoading={reversing}
                onConfirm={handleReverseConfirm}
            />
        </div>
    );
}

export default function PromotionPage() {
    return (
        <Suspense fallback={<LoadingState className="py-20" />}>
            <PromotionDeskContent />
        </Suspense>
    );
}
