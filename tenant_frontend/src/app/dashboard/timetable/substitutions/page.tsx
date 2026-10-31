"use client";

import { useState } from "react";
import {
    LoaderCircle,
    UserCheck,
    Calendar,
    Users,
    Clock,
    BookOpen,
    Plus,
    CheckCircle2,
    RotateCcw,
    AlertCircle,
    ArrowLeft,
} from "lucide-react";
import Link from "next/link";
import { useSections } from "@/hooks/useAcademics";
import { useInstructors } from "@/hooks/useStaff";
import {
    useCreateSubstitution,
    useSectionTimetable,
    useSubstitutions,
} from "@/hooks/useTimetable";
import { DAY_LABELS } from "@/types/Timetable";
import { usePermissions } from "@/providers/PermissionProvider";
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
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { toast } from "sonner";

function todayISO() {
    return new Date().toISOString().slice(0, 10);
}

export default function SubstitutionsPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("manage_substitutions")) {
        return <Unauthorized />;
    }
    return <SubstitutionsPageContent />;
}

function SubstitutionsPageContent() {
    const { data: sections } = useSections();
    const [sectionId, setSectionId] = useState("");
    const { data: entries } = useSectionTimetable(sectionId || undefined);
    const {
        data: substitutions,
        isLoading: loadingSubs,
        isError: subsError,
        refetch: refetchSubs,
    } = useSubstitutions();

    const [entryId, setEntryId] = useState("");
    const [date, setDate] = useState(todayISO());
    const [substituteInstructor, setSubstituteInstructor] = useState("");
    const [reason, setReason] = useState("");

    const { data: instructorsData } = useInstructors();
    const instructors = instructorsData?.results;

    const { mutate: createSubstitution, isPending } = useCreateSubstitution();

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!entryId || !date || !substituteInstructor) {
            toast.error("Please fill in all required substitution fields.");
            return;
        }
        createSubstitution(
            { entryId, data: { date, substitute_instructor: substituteInstructor, reason } },
            {
                onSuccess: () => {
                    toast.success("Teacher substitution allocated successfully!");
                    setEntryId("");
                    setSubstituteInstructor("");
                    setReason("");
                    refetchSubs();
                },
                onError: (err: any) => {
                    toast.error(err?.message || "Failed to record substitution");
                },
            }
        );
    };

    return (
        <div className="space-y-7 max-w-7xl mx-auto pb-24 animate-in fade-in duration-500">
            {/* 1. Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <div className="flex items-center gap-2 mb-1">
                        <Link
                            href="/dashboard/timetable"
                            className="text-xs text-sky-600 dark:text-sky-400 hover:underline flex items-center gap-1 font-semibold"
                        >
                            <ArrowLeft className="w-3.5 h-3.5" /> Back to Master Timetable
                        </Link>
                    </div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <UserCheck className="h-7 w-7 text-sky-600 dark:text-sky-400" />
                        <span>Teacher Substitution Desk</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Assign proxy faculty, manage temporary teacher replacements, and track coverage logs
                    </p>
                </div>
            </div>

            {/* 2. Create Substitution Card */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-6 shadow-2xs space-y-4">
                <div className="border-b border-slate-100 dark:border-slate-800/80 pb-3">
                    <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                        <Plus className="w-4 h-4 text-sky-600" />
                        <span>Schedule New Teacher Replacement</span>
                    </h2>
                    <p className="text-xs text-slate-400 mt-0.5">
                        Select the affected class period, date of absence, and substitute educator
                    </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        {/* Section */}
                        <div className="space-y-1.5">
                            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                Class Section <span className="text-rose-500">*</span>
                            </label>
                            <Select
                                value={sectionId}
                                onValueChange={(v) => {
                                    setSectionId(v);
                                    setEntryId("");
                                }}
                            >
                                <SelectTrigger className="h-10 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium">
                                    <SelectValue placeholder="Select class section..." />
                                </SelectTrigger>
                                <SelectContent>
                                    {sections?.map((s) => (
                                        <SelectItem key={s.id} value={s.id} className="text-xs">
                                            {s.level_name} - {s.name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        {/* Slot */}
                        <div className="space-y-1.5">
                            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                Timetable Slot <span className="text-rose-500">*</span>
                            </label>
                            <Select
                                value={entryId}
                                onValueChange={setEntryId}
                                disabled={!sectionId}
                            >
                                <SelectTrigger className="h-10 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium">
                                    <SelectValue
                                        placeholder={
                                            sectionId
                                                ? "Select period slot..."
                                                : "Choose section first"
                                        }
                                    />
                                </SelectTrigger>
                                <SelectContent>
                                    {entries?.map((e) => (
                                        <SelectItem key={e.id} value={e.id} className="text-xs">
                                            {DAY_LABELS[e.day_of_week]} • {e.period_name} ({e.subject_name})
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        {/* Date */}
                        <div className="space-y-1.5">
                            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                Absence Date <span className="text-rose-500">*</span>
                            </label>
                            <Input
                                type="date"
                                value={date}
                                onChange={(e) => setDate(e.target.value)}
                                className="h-10 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium"
                            />
                        </div>

                        {/* Substitute Teacher */}
                        <div className="space-y-1.5">
                            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                Substitute Instructor <span className="text-rose-500">*</span>
                            </label>
                            <Select
                                value={substituteInstructor}
                                onValueChange={setSubstituteInstructor}
                            >
                                <SelectTrigger className="h-10 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium">
                                    <SelectValue placeholder="Select faculty..." />
                                </SelectTrigger>
                                <SelectContent>
                                    {instructors?.map((i: any) => (
                                        <SelectItem key={i.id} value={i.id} className="text-xs">
                                            {i.staff_member_name || i.id}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>

                    {/* Reason & Submit Bar */}
                    <div className="flex flex-col sm:flex-row items-stretch sm:items-end justify-between gap-3 pt-2">
                        <div className="flex-1 max-w-md space-y-1.5">
                            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                Administrative Reason (Optional)
                            </label>
                            <Input
                                value={reason}
                                onChange={(e) => setReason(e.target.value)}
                                placeholder="e.g. Medical leave / official duty / conference"
                                className="h-9 text-xs border-slate-200 dark:border-slate-800"
                            />
                        </div>

                        <Button
                            type="submit"
                            disabled={!entryId || !date || !substituteInstructor || isPending}
                            className="h-9 px-5 gap-2 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95 shrink-0"
                        >
                            {isPending && <LoaderCircle className="h-4 w-4 animate-spin" />}
                            <span>Commit Substitution</span>
                        </Button>
                    </div>
                </form>
            </div>

            {/* 3. Existing Substitutions Table */}
            <div className="space-y-3">
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                            <Clock className="w-4 h-4 text-sky-600" />
                            <span>Recent Teacher Substitutions</span>
                        </h2>
                        <p className="text-xs text-slate-500 mt-0.5">
                            Historical coverage logs and active proxy faculty allocations
                        </p>
                    </div>
                </div>

                {loadingSubs ? (
                    <LoadingState className="py-16" />
                ) : subsError ? (
                    <ErrorState onRetry={refetchSubs} />
                ) : !substitutions || substitutions.length === 0 ? (
                    <EmptyState
                        title="No substitutions recorded yet"
                        description="Temporary faculty replacements and coverage periods will appear here once assigned."
                        className="py-16 text-slate-500 text-sm"
                    />
                ) : (
                    <TableShell>
                        <Table>
                            <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                <TableRow>
                                    <TableHead className="py-3 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Date
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Timetable Slot Reference
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Substitute Faculty ID
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider pr-4">
                                        Reason &amp; Remarks
                                    </TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {substitutions.map((s) => (
                                    <TableRow
                                        key={String(s.id)}
                                        className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                    >
                                        <TableCell className="py-3 pl-4 font-semibold text-xs text-slate-900 dark:text-slate-100">
                                            {s.date}
                                        </TableCell>
                                        <TableCell className="py-3 font-mono text-xs text-slate-500">
                                            {s.timetable_entry}
                                        </TableCell>
                                        <TableCell className="py-3 font-mono text-xs text-slate-600 dark:text-slate-400">
                                            {s.substitute_instructor || "—"}
                                        </TableCell>
                                        <TableCell className="py-3 pr-4 text-xs text-slate-600 dark:text-slate-400">
                                            {s.reason || "—"}
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
