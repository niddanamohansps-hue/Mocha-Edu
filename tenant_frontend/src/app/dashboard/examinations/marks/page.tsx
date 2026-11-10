"use client";

import { useEffect, useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
    History,
    LoaderCircle,
    Lock,
    Upload,
    CheckCircle2,
    AlertCircle,
    Award,
    FileSpreadsheet,
    HelpCircle,
    RotateCcw,
    Sparkles,
    Search,
    X,
    Clock,
    User,
    Users,
    GraduationCap,
    Save,
    FileText,
    ArrowRight,
    TrendingUp,
} from "lucide-react";
import axiosInstance from "@/lib/axios";
import {
    importErrors,
    useExaminations,
    useExamSchedules,
    useImportMarks,
    useMarksHistory,
    useRequestRecheck,
    useScheduleMarks,
    useSetGrace,
    useSubmitExamMarks,
} from "@/hooks/useExaminations";
import {
    ATTENDANCE_LABELS,
    MarkAttendance,
    MarksImportResult,
    SavedMark,
} from "@/types/Examinations";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/avatar";
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
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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

type Row = {
    marks_obtained: string;
    attendance: MarkAttendance;
    remarks: string;
    components?: Record<string, string>;
};

function formatDateTime(iso: string | null) {
    if (!iso) return "—";
    try {
        const d = new Date(iso);
        return d.toLocaleDateString("en-IN", {
            day: "numeric",
            month: "short",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    } catch {
        return iso;
    }
}

// -------------------------------------------------------------
// Grace Marks Dialog
// -------------------------------------------------------------
function GraceDialog({
    mark,
    max,
    onClose,
}: {
    mark: SavedMark;
    max: string;
    onClose: () => void;
}) {
    const setGrace = useSetGrace();
    const [grace, setGraceValue] = useState(
        Number(mark.grace_marks) ? String(Number(mark.grace_marks)) : ""
    );
    const [reason, setReason] = useState("");
    const [error, setError] = useState<string | null>(null);

    const maxNum = Number(max);
    const currentNum = Number(mark.marks_obtained ?? 0);
    const room = Math.max(0, maxNum - currentNum);

    const handleSave = (e: React.FormEvent) => {
        e.preventDefault();
        if (!/^\d+(\.\d{1,2})?$/.test(grace.trim())) {
            return setError("Enter grace marks as a valid positive number.");
        }
        if (Number(grace) > room) {
            return setError(`At most ${room} grace marks fit under the maximum score (${maxNum}).`);
        }
        if (!reason.trim()) {
            return setError("Please provide a reason; it will be preserved in the audit log.");
        }
        setError(null);
        setGrace.mutate(
            { markId: mark.id, grace_marks: grace.trim(), reason: reason.trim() },
            {
                onSuccess: () => {
                    toast.success(`Grace marks awarded to ${mark.student_name}`);
                    onClose();
                },
                onError: (err: any) => {
                    setError(err?.message || "Failed to save grace marks");
                },
            }
        );
    };

    return (
        <Dialog open onOpenChange={(o) => !o && onClose()}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle className="text-base font-bold flex items-center gap-2">
                        <Award className="h-5 w-5 text-amber-500" />
                        <span>Award Grace Marks: {mark.student_name}</span>
                    </DialogTitle>
                    <DialogDescription className="text-xs">
                        Current score is {currentNum} of {maxNum} max marks. Headroom available:{" "}
                        <span className="font-bold text-slate-800 dark:text-slate-200">
                            +{room} marks
                        </span>
                        . Setting 0 removes grace.
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={handleSave} className="space-y-4 pt-2">
                    {error && (
                        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300">
                            {error}
                        </div>
                    )}

                    <div className="space-y-1.5">
                        <Label htmlFor="gr-marks" className="text-xs font-semibold">
                            Grace Marks to Award <span className="text-rose-500">*</span>
                        </Label>
                        <Input
                            id="gr-marks"
                            type="number"
                            inputMode="decimal"
                            step="any"
                            value={grace}
                            onChange={(e) => setGraceValue(e.target.value)}
                            placeholder={`0 to ${room}`}
                            className="h-9 text-xs"
                        />
                    </div>

                    <div className="space-y-1.5">
                        <Label htmlFor="gr-reason" className="text-xs font-semibold">
                            Administrative Justification <span className="text-rose-500">*</span>
                        </Label>
                        <Textarea
                            id="gr-reason"
                            rows={3}
                            maxLength={500}
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                            placeholder="e.g. Approved condonation for sports attendance / borderline moderation"
                            className="text-xs"
                        />
                    </div>

                    <DialogFooter className="pt-2 gap-2">
                        <Button type="button" variant="outline" size="sm" onClick={onClose}>
                            Cancel
                        </Button>
                        <Button
                            type="submit"
                            size="sm"
                            disabled={setGrace.isPending}
                            className="bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs"
                        >
                            {setGrace.isPending && <LoaderCircle className="h-4 w-4 animate-spin mr-1.5" />}
                            Apply Grace Marks
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

// -------------------------------------------------------------
// Ask for Recheck Dialog
// -------------------------------------------------------------
function RecheckDialog({ mark, onClose }: { mark: SavedMark; onClose: () => void }) {
    const ask = useRequestRecheck();
    const [reason, setReason] = useState("");
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!reason.trim()) {
            return setError("Please state specifically what should be re-evaluated.");
        }
        setError(null);
        ask.mutate(
            { mark: mark.id, reason: reason.trim() },
            {
                onSuccess: () => {
                    toast.success(`Recheck request submitted for ${mark.student_name}`);
                    onClose();
                },
                onError: (err: any) => setError(err?.message || "Failed to submit request"),
            }
        );
    };

    return (
        <Dialog open onOpenChange={(o) => !o && onClose()}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle className="text-base font-bold flex items-center gap-2">
                        <RotateCcw className="h-5 w-5 text-sky-600" />
                        <span>Request Paper Re-evaluation</span>
                    </DialogTitle>
                    <DialogDescription className="text-xs">
                        Initiate a formal re-check of answer script for{" "}
                        <span className="font-semibold text-slate-800 dark:text-slate-200">
                            {mark.student_name}
                        </span>
                        . An examination administrator will audit the paper.
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={handleSubmit} className="space-y-4 pt-2">
                    {error && (
                        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 text-xs text-rose-700">
                            {error}
                        </div>
                    )}

                    <div className="space-y-1.5">
                        <Label htmlFor="rc-reason" className="text-xs font-semibold">
                            Scope of Re-evaluation <span className="text-rose-500">*</span>
                        </Label>
                        <Textarea
                            id="rc-reason"
                            rows={3}
                            maxLength={1000}
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                            placeholder="e.g. Question 4(b) unchecked on page 5 or mark totalling mismatch"
                            className="text-xs"
                        />
                    </div>

                    <DialogFooter className="pt-2 gap-2">
                        <Button type="button" variant="outline" size="sm" onClick={onClose}>
                            Cancel
                        </Button>
                        <Button
                            type="submit"
                            size="sm"
                            disabled={ask.isPending}
                            className="bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs"
                        >
                            {ask.isPending && <LoaderCircle className="h-4 w-4 animate-spin mr-1.5" />}
                            Submit Recheck Request
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

// -------------------------------------------------------------
// Import Marks Dialog
// -------------------------------------------------------------
function ImportDialog({
    scheduleId,
    needsReason,
    onClose,
}: {
    scheduleId: string;
    needsReason: boolean;
    onClose: () => void;
}) {
    const run = useImportMarks();
    const [file, setFile] = useState<File | null>(null);
    const [preview, setPreview] = useState<MarksImportResult | null>(null);
    const [errors, setErrors] = useState<string[]>([]);
    const [reason, setReason] = useState("");

    const send = (dryRun: boolean) => {
        if (!file) return setErrors(["Please choose a CSV file."]);
        if (!dryRun && needsReason && !reason.trim()) {
            return setErrors(["This schedule is locked. Provide a justification for updating marks."]);
        }
        setErrors([]);
        run.mutate(
            { scheduleId, file, dryRun, reason: reason.trim() },
            {
                onSuccess: (data) => {
                    if (dryRun) {
                        setPreview(data);
                        toast.info(`Verified ${data.total} rows successfully.`);
                    } else {
                        toast.success("Marks imported successfully!");
                        onClose();
                    }
                },
                onError: (e) => {
                    setPreview(null);
                    setErrors(importErrors(e));
                },
            }
        );
    };

    return (
        <Dialog open onOpenChange={(o) => !o && onClose()}>
            <DialogContent className="sm:max-w-xl">
                <DialogHeader>
                    <DialogTitle className="text-base font-bold flex items-center gap-2">
                        <FileSpreadsheet className="h-5 w-5 text-emerald-600" />
                        <span>Batch Import Marks from CSV</span>
                    </DialogTitle>
                    <DialogDescription className="text-xs leading-relaxed">
                        Expected columns: <code className="font-mono font-bold text-sky-600">enrollment_id</code>,{" "}
                        <code className="font-mono font-bold text-sky-600">marks</code>, and optionally{" "}
                        <code className="font-mono">attendance</code> (present, absent, medical, malpractice, exempt) and{" "}
                        <code className="font-mono">remarks</code>. Pre-flight checks will run before saving.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 pt-2">
                    {errors.length > 0 && (
                        <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 text-xs text-rose-700 whitespace-pre-line max-h-36 overflow-y-auto">
                            {errors.slice(0, 6).join("\n")}
                            {errors.length > 6 && `\n...and ${errors.length - 6} more errors`}
                        </div>
                    )}

                    <div className="space-y-1.5">
                        <Label htmlFor="im-file" className="text-xs font-semibold">
                            Select CSV Spreadsheet <span className="text-rose-500">*</span>
                        </Label>
                        <Input
                            id="im-file"
                            type="file"
                            accept=".csv,text/csv"
                            className="h-10 text-xs cursor-pointer"
                            onChange={(e) => {
                                setFile(e.target.files?.[0] ?? null);
                                setPreview(null);
                                setErrors([]);
                            }}
                        />
                    </div>

                    {needsReason && (
                        <div className="space-y-1.5">
                            <Label htmlFor="im-reason" className="text-xs font-semibold">
                                Reason for modifying locked schedule <span className="text-rose-500">*</span>
                            </Label>
                            <Input
                                id="im-reason"
                                maxLength={500}
                                value={reason}
                                onChange={(e) => setReason(e.target.value)}
                                placeholder="Audit justification..."
                                className="h-9 text-xs"
                            />
                        </div>
                    )}

                    {preview?.rows && (
                        <div className="space-y-2">
                            <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                                Pre-flight Validation Preview ({preview.total} Rows)
                            </span>
                            <div className="max-h-48 overflow-y-auto rounded-xl border border-slate-200 dark:border-slate-800 text-xs divide-y divide-slate-100 dark:divide-slate-800">
                                {preview.rows.map((r) => (
                                    <div key={r.line} className="flex items-center justify-between p-2">
                                        <div>
                                            <span className="font-semibold text-slate-900 dark:text-white">
                                                {r.student_name}
                                            </span>
                                            <span className="text-[10px] font-mono text-slate-400 ml-1.5">
                                                ({r.enrollment_id})
                                            </span>
                                        </div>
                                        <Badge
                                            variant="outline"
                                            className="text-[11px] font-bold bg-slate-50 dark:bg-slate-900"
                                        >
                                            {r.attendance === "present"
                                                ? `${r.marks ?? "Not marked"} marks`
                                                : ATTENDANCE_LABELS[r.attendance]}
                                        </Badge>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    <DialogFooter className="pt-2 gap-2">
                        <Button type="button" variant="outline" size="sm" onClick={onClose}>
                            Cancel
                        </Button>
                        <Button
                            type="button"
                            size="sm"
                            disabled={run.isPending || !file}
                            onClick={() => send(!preview)}
                            className="bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs"
                        >
                            {run.isPending && <LoaderCircle className="h-4 w-4 animate-spin mr-1.5" />}
                            {preview ? `Commit Import (${preview.total} Rows)` : "Check CSV Format"}
                        </Button>
                    </DialogFooter>
                </div>
            </DialogContent>
        </Dialog>
    );
}

// -------------------------------------------------------------
// History Timeline Panel
// -------------------------------------------------------------
function HistoryPanel({ scheduleId }: { scheduleId: string }) {
    const { data, isLoading, isError } = useMarksHistory(scheduleId, true);
    if (isLoading) return <LoadingState className="py-6" />;
    if (isError) return <ErrorState message="Could not load the history." />;
    if (!data?.length) return <p className="text-xs text-slate-500">No marks entered yet.</p>;

    const show = (marks: string | null, attendance: string, grace?: string) =>
        attendance && attendance !== "present"
            ? ATTENDANCE_LABELS[attendance as MarkAttendance] ?? attendance
            : marks === null
            ? "blank"
            : `${Number(marks)}${grace && Number(grace) ? ` +${Number(grace)}` : ""}`;

    return (
        <ul className="text-xs space-y-2.5 max-h-72 overflow-y-auto pr-1">
            {data.map((c) => (
                <li
                    key={c.id}
                    className="p-2.5 rounded-lg bg-slate-50 dark:bg-slate-950/50 border border-slate-100 dark:border-slate-800 space-y-1"
                >
                    <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-900 dark:text-white">
                            {c.student_name}{" "}
                            <span className="text-[10px] font-mono text-slate-400 font-normal">
                                ({c.enrollment_id})
                            </span>
                        </span>
                        <Badge variant="outline" className="text-[10px] capitalize">
                            {c.kind}
                        </Badge>
                    </div>
                    <div className="text-slate-600 dark:text-slate-300">
                        {c.kind === "entry"
                            ? `Entered ${show(c.new_marks, c.new_attendance)}`
                            : c.kind === "grace"
                            ? `Grace ${Number(c.old_grace)} → ${Number(c.new_grace)}`
                            : `${c.kind === "recheck" ? "Recheck" : c.kind === "import" ? "Import" : c.kind === "moderation" ? "Moderated" : "Changed"} ${show(
                                  c.old_marks,
                                  c.old_attendance
                              )} → ${show(c.new_marks, c.new_attendance)}`}
                    </div>
                    <div className="text-[10px] text-slate-400">
                        {c.changed_by || "Staff"}, {formatDateTime(c.created_at)}
                        {c.reason ? ` • Justification: ${c.reason}` : ""}
                    </div>
                </li>
            ))}
        </ul>
    );
}

// -------------------------------------------------------------
// Main Marks Entry Desk Component
// -------------------------------------------------------------
export default function MarksEntryPage() {
    const { can, isOwner } = usePermissions();
    const canEnter = isOwner || can("enter_marks");
    const canManage = isOwner || can("manage_marks");

    const { data: examinations } = useExaminations();
    const [examinationId, setExaminationId] = useState("");
    const { data: schedules } = useExamSchedules(examinationId || undefined);
    const [scheduleId, setScheduleId] = useState("");

    const schedule = schedules?.find((s) => s.id === scheduleId);

    const {
        data: roster,
        isLoading: loadingRoster,
        isError: rosterError,
        refetch: refetchRoster,
    } = useQuery({
        queryKey: ["examinations", "roster", scheduleId],
        queryFn: async () => {
            const response = await axiosInstance.get(
                `/attendance/sections/${schedule?.section}/roster/?date=${schedule?.date}`
            );
            const students = response.data.students as {
                student: string;
                full_name: string;
                enrollment_id: string;
            }[];
            // A supplementary paper takes marks only for the students entitled to re-sit this subject.
            if (!examinations?.find((e) => e.id === examinationId)?.supplementary_of) return students;
            const entitled = await axiosInstance.get<{ rows: { student_id: string; subject_id: string }[] }>(
                "/examinations/supplementary/",
                { params: { examination: examinationId } },
            );
            const allowed = new Set(entitled.data.rows.filter((r) => r.subject_id === schedule?.subject).map((r) => r.student_id));
            return students.filter((s) => allowed.has(s.student));
        },
        enabled: Boolean(schedule),
    });

    const saved = useScheduleMarks(scheduleId || undefined);

    const [marks, setMarks] = useState<Record<string, Row>>({});
    const [reason, setReason] = useState("");
    const [studentSearch, setStudentSearch] = useState("");
    const [grace, setGrace] = useState<SavedMark | null>(null);
    const [recheck, setRecheck] = useState<SavedMark | null>(null);
    const [importing, setImporting] = useState(false);
    const [showHistory, setShowHistory] = useState(false);
    const { mutate: submitMarks, isPending } = useSubmitExamMarks();

    const savedByStudent = useMemo(() => {
        return Object.fromEntries((saved.data?.marks ?? []).map((m) => [m.student, m]));
    }, [saved.data?.marks]);

    useEffect(() => {
        if (!roster || !saved.data) return;
        const byStudent = Object.fromEntries(saved.data.marks.map((m) => [m.student, m]));
        const initial: Record<string, Row> = {};
        for (const s of roster) {
            const m = byStudent[s.student];
            const compMarksMap: Record<string, string> = {};
            if (m?.component_marks) {
                for (const cm of m.component_marks) {
                    compMarksMap[cm.component] =
                        cm.marks_obtained === null ? "" : String(Number(cm.marks_obtained));
                }
            }
            initial[s.student] = m
                ? {
                      marks_obtained:
                          m.marks_obtained === null ? "" : String(Number(m.marks_obtained)),
                      attendance: m.attendance,
                      remarks: m.remarks,
                      components: compMarksMap,
                  }
                : {
                      marks_obtained: "",
                      attendance: "present",
                      remarks: "",
                      components: compMarksMap,
                  };
        }
        setMarks(initial);
        setReason("");
    }, [roster, saved.data]);

    const published = Boolean(saved.data?.is_published);
    const locked = Boolean(schedule?.is_locked);
    const editable = !published && (!locked || canManage);
    const needsReason = locked && canManage && !published;

    const update = (student: string, patch: Partial<Row>) =>
        setMarks((prev) => ({ ...prev, [student]: { ...prev[student], ...patch } }));

    const updateComponent = (student: string, componentId: string, val: string) => {
        setMarks((prev) => {
            const studentRow = prev[student] || {
                marks_obtained: "",
                attendance: "present",
                remarks: "",
                components: {},
            };
            const updatedComps = { ...(studentRow.components || {}), [componentId]: val };
            const sum = Object.values(updatedComps).reduce((acc, curr) => {
                const num = parseFloat(curr);
                return isNaN(num) ? acc : acc + num;
            }, 0);
            return {
                ...prev,
                [student]: {
                    ...studentRow,
                    components: updatedComps,
                    marks_obtained: Object.values(updatedComps).some((v) => v !== "")
                        ? String(sum)
                        : "",
                },
            };
        });
    };

    // Live Grade Statistics & Pass/Fail Calculations
    const passMarks = Number(schedule?.pass_marks ?? 0);
    const maxMarks = Number(schedule?.max_marks ?? 100);

    const stats = useMemo(() => {
        if (!roster || roster.length === 0) {
            return { total: 0, graded: 0, present: 0, absent: 0, passed: 0, failed: 0, avg: 0, top: 0 };
        }
        const total = roster.length;
        let graded = 0;
        let present = 0;
        let absent = 0;
        let passed = 0;
        let failed = 0;
        let sumMarks = 0;
        let top = 0;

        for (const s of roster) {
            const m = marks[s.student];
            const att = m?.attendance ?? "present";
            const val = parseFloat(m?.marks_obtained ?? "");

            if (att === "present") {
                present++;
                if (!isNaN(val)) {
                    graded++;
                    sumMarks += val;
                    if (val > top) top = val;
                    if (val >= passMarks) passed++;
                    else failed++;
                }
            } else {
                absent++;
            }
        }

        const avg = graded > 0 ? Math.round((sumMarks / graded) * 10) / 10 : 0;
        return { total, graded, present, absent, passed, failed, avg, top };
    }, [roster, marks, passMarks]);

    // Filtered student roster by search input
    const filteredRoster = useMemo(() => {
        if (!roster) return [];
        return roster.filter((s) => {
            if (!studentSearch) return true;
            const q = studentSearch.toLowerCase();
            return s.full_name.toLowerCase().includes(q) || s.enrollment_id.toLowerCase().includes(q);
        });
    }, [roster, studentSearch]);

    const handleSubmit = () => {
        if (!schedule || !editable) return;
        const records = Object.entries(marks).map(([student, m]) => ({
            student,
            marks_obtained:
                m.attendance !== "present" || m.marks_obtained === "" ? null : Number(m.marks_obtained),
            is_absent: ["absent", "medical", "malpractice"].includes(m.attendance),
            attendance: m.attendance,
            remarks: m.remarks,
            components:
                schedule.components && schedule.components.length > 0 && m.components
                    ? Object.entries(m.components).map(([cid, score]) => ({
                          component: cid,
                          marks_obtained: score === "" ? null : Number(score),
                          is_absent: ["absent", "medical", "malpractice"].includes(m.attendance),
                      }))
                    : undefined,
        }));
        submitMarks(
            { scheduleId: schedule.id, records, reason: reason.trim() },
            {
                onSuccess: () => {
                    toast.success("Examination marks committed successfully!");
                },
                onError: (err: any) => {
                    toast.error(err?.message || "Failed to submit marks");
                },
            }
        );
    };

    if (!canEnter) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-6 max-w-7xl mx-auto pb-24 animate-in fade-in duration-500">
            {/* 1. Senior Executive Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Award className="h-7 w-7 text-indigo-600 dark:text-indigo-400" />
                        <span>Examinations &amp; Marks Entry Desk</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        High-density gradebook, component scoring (Theory / Practical), moderation headroom, and CSV batch imports
                    </p>
                </div>

                {/* Right Action Strip */}
                {schedule && (
                    <div className="flex items-center gap-2 shrink-0">
                        {editable && (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setImporting(true)}
                                className="h-9 px-3 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 cursor-pointer shadow-2xs"
                            >
                                <Upload className="h-3.5 w-3.5 text-slate-500" />
                                <span>Import CSV</span>
                            </Button>
                        )}
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setShowHistory((v) => !v)}
                            className="h-9 px-3 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 cursor-pointer shadow-2xs"
                        >
                            <History className="h-3.5 w-3.5 text-slate-500" />
                            <span>{showHistory ? "Hide History" : "Audit History"}</span>
                        </Button>
                    </div>
                )}
            </div>

            {/* 2. Control Card: Examination & Subject Schedule Selectors */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-5 shadow-2xs space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
                    {/* Examination Selector */}
                    <div className="md:col-span-5 space-y-1.5">
                        <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                            <GraduationCap className="h-3.5 w-3.5 text-slate-500" />
                            Examination Term <span className="text-rose-500">*</span>
                        </label>
                        <Select
                            value={examinationId}
                            onValueChange={(v) => {
                                setExaminationId(v);
                                setScheduleId("");
                            }}
                        >
                            <SelectTrigger className="h-10 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium">
                                <SelectValue placeholder="Select examination..." />
                            </SelectTrigger>
                            <SelectContent>
                                {examinations?.map((e) => (
                                    <SelectItem key={e.id} value={e.id} className="text-xs">
                                        {e.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Schedule Selector */}
                    <div className="md:col-span-7 space-y-1.5">
                        <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                            <FileText className="h-3.5 w-3.5 text-slate-500" />
                            Assigned Subject &amp; Section Schedule <span className="text-rose-500">*</span>
                        </label>
                        <Select
                            value={scheduleId}
                            onValueChange={(v) => {
                                setScheduleId(v);
                                setShowHistory(false);
                            }}
                            disabled={!examinationId}
                        >
                            <SelectTrigger className="h-10 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium">
                                <SelectValue
                                    placeholder={
                                        schedules?.length
                                            ? "Select subject & section..."
                                            : "No schedules assigned for this exam"
                                    }
                                />
                            </SelectTrigger>
                            <SelectContent>
                                {schedules?.map((s) => (
                                    <SelectItem key={s.id} value={s.id} className="text-xs">
                                        <div className="flex items-center gap-2">
                                            <span className="font-semibold text-slate-900 dark:text-white">
                                                {s.subject_name}
                                            </span>
                                            <span className="text-slate-400">• Section {s.section_name}</span>
                                            <span className="text-[10px] text-slate-400">
                                                ({s.date || "Date not set"})
                                            </span>
                                        </div>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                </div>

                {/* Schedule Criteria Strip */}
                {schedule && (
                    <div className="flex items-center gap-2 text-xs flex-wrap pt-2 border-t border-slate-100 dark:border-slate-800">
                        <Badge
                            variant="outline"
                            className="bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-300"
                        >
                            Max Score: {maxMarks}
                        </Badge>
                        <Badge
                            variant="outline"
                            className="bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300"
                        >
                            Passing Benchmark: {passMarks}
                        </Badge>
                        {schedule.components && schedule.components.length > 0 && (
                            <span className="text-[11px] text-slate-500">
                                Components:{" "}
                                {schedule.components.map((c) => `${c.name} (${Number(c.max_marks)})`).join(" + ")}
                            </span>
                        )}
                    </div>
                )}
            </div>

            {/* Status Banners */}
            {published && (
                <div className="flex items-center gap-2 bg-sky-50 dark:bg-sky-950/40 text-sky-800 dark:text-sky-300 text-xs font-semibold px-4 py-3 rounded-xl border border-sky-200 dark:border-sky-800 shadow-2xs">
                    <Lock className="h-4 w-4 shrink-0 text-sky-600" />
                    <span>
                        Examination results have been published to the student portal. Marks modification is restricted to administrative recheck approvals and grace moderation.
                    </span>
                </div>
            )}
            {!published && locked && (
                <div className="flex items-center gap-2 bg-amber-50 dark:bg-amber-950/40 text-amber-800 dark:text-amber-300 text-xs font-semibold px-4 py-3 rounded-xl border border-amber-200 dark:border-amber-800 shadow-2xs">
                    <Lock className="h-4 w-4 shrink-0 text-amber-600" />
                    <span>
                        {canManage
                            ? "This schedule is locked for auditing. Administrators can correct scores by submitting an audit reason below."
                            : "This schedule is locked by the exam department. Marks entry is in read-only mode."}
                    </span>
                </div>
            )}

            {/* Audit History Timeline Drawer */}
            {showHistory && scheduleId && (
                <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 p-5 shadow-2xs space-y-3 animate-in fade-in duration-300">
                    <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
                        <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                            <History className="w-4 h-4 text-sky-600" />
                            <span>Marks Audit Trail</span>
                        </h2>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setShowHistory(false)}
                            className="text-xs text-slate-400 hover:text-slate-700"
                        >
                            Close
                        </Button>
                    </div>
                    <HistoryPanel scheduleId={scheduleId} />
                </div>
            )}

            {/* Empty, Loading, and Error States */}
            {!scheduleId && (
                <EmptyState
                    title="Select an examination and assigned schedule"
                    description="Choose your subject examination from the dropdown above to open the grading roster."
                    className="py-16 text-slate-500"
                />
            )}

            {scheduleId && (loadingRoster || saved.isLoading) && <LoadingState className="py-20" />}

            {scheduleId && (rosterError || saved.isError) && !loadingRoster && (
                <ErrorState
                    onRetry={() => {
                        refetchRoster();
                        saved.refetch();
                    }}
                />
            )}

            {scheduleId && roster && roster.length === 0 && (
                <EmptyState
                    title="No students are currently enrolled in this section"
                    className="py-16 text-slate-500 text-sm"
                />
            )}

            {/* 3. Main Gradebook Desk View */}
            {scheduleId && roster && roster.length > 0 && schedule && saved.data && (
                <div className="space-y-4">
                    {/* 3A. Real-Time Grade Pulse & Performance Strip */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
                        <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl p-3 shadow-2xs">
                            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                                Cohort Size
                            </span>
                            <div className="text-xl font-bold text-slate-900 dark:text-white mt-1">
                                {stats.total}
                            </div>
                            <span className="text-[10px] text-slate-400 font-medium">Students</span>
                        </div>

                        <div className="bg-white dark:bg-slate-900 border border-indigo-200/60 dark:border-indigo-900/60 rounded-xl p-3 shadow-2xs">
                            <span className="text-[11px] font-semibold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider block">
                                Graded
                            </span>
                            <div className="text-xl font-bold text-indigo-700 dark:text-indigo-300 mt-1">
                                {stats.graded}
                            </div>
                            <span className="text-[10px] text-indigo-600/80 dark:text-indigo-400/80 font-medium">
                                {Math.round((stats.graded / (stats.total || 1)) * 100)}% scored
                            </span>
                        </div>

                        <div className="bg-white dark:bg-slate-900 border border-emerald-200/60 dark:border-emerald-900/60 rounded-xl p-3 shadow-2xs">
                            <span className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider block">
                                Passed
                            </span>
                            <div className="text-xl font-bold text-emerald-700 dark:text-emerald-300 mt-1">
                                {stats.passed}
                            </div>
                            <span className="text-[10px] text-emerald-600/80 dark:text-emerald-400/80 font-medium">
                                &gt;= {passMarks} Marks
                            </span>
                        </div>

                        <div className="bg-white dark:bg-slate-900 border border-rose-200/60 dark:border-rose-900/60 rounded-xl p-3 shadow-2xs">
                            <span className="text-[11px] font-semibold text-rose-600 dark:text-rose-400 uppercase tracking-wider block">
                                Below Passing
                            </span>
                            <div className="text-xl font-bold text-rose-700 dark:text-rose-300 mt-1">
                                {stats.failed}
                            </div>
                            <span className="text-[10px] text-rose-600/80 dark:text-rose-400/80 font-medium">
                                Attention required
                            </span>
                        </div>

                        <div className="bg-white dark:bg-slate-900 border border-amber-200/60 dark:border-amber-900/60 rounded-xl p-3 shadow-2xs">
                            <span className="text-[11px] font-semibold text-amber-600 dark:text-amber-400 uppercase tracking-wider block">
                                Absent / Exempt
                            </span>
                            <div className="text-xl font-bold text-amber-700 dark:text-amber-300 mt-1">
                                {stats.absent}
                            </div>
                            <span className="text-[10px] text-amber-600/80 dark:text-amber-400/80 font-medium">
                                Non-present
                            </span>
                        </div>

                        <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl p-3 shadow-2xs">
                            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                                Class Average
                            </span>
                            <div className="text-xl font-bold text-slate-900 dark:text-white mt-1">
                                {stats.avg}
                            </div>
                            <span className="text-[10px] text-slate-400 font-medium">Out of {maxMarks}</span>
                        </div>

                        <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl p-3 shadow-2xs">
                            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                                Class Highest
                            </span>
                            <div className="text-xl font-bold text-indigo-600 dark:text-indigo-400 mt-1">
                                {stats.top}
                            </div>
                            <span className="text-[10px] text-slate-400 font-medium">Top score</span>
                        </div>
                    </div>

                    {/* 3B. Student Quick Search */}
                    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 p-3 shadow-2xs flex items-center justify-between gap-3">
                        <div className="relative flex-1 max-w-sm">
                            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                            <Input
                                placeholder="Search student by name or enrollment ID..."
                                value={studentSearch}
                                onChange={(e) => setStudentSearch(e.target.value)}
                                className="h-9 pl-8.5 pr-8 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium"
                            />
                            {studentSearch && (
                                <button
                                    type="button"
                                    onClick={() => setStudentSearch("")}
                                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5"
                                >
                                    <X className="w-3 h-3" />
                                </button>
                            )}
                        </div>

                        <span className="text-xs text-slate-400 font-medium">
                            Showing {filteredRoster.length} of {roster.length} students
                        </span>
                    </div>

                    {/* 3C. High-Density Gradebook Table */}
                    <TableShell>
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead className="pl-4 w-14">
                                        #
                                    </TableHead>
                                    <TableHead className="min-w-[200px]">
                                        Student Candidate
                                    </TableHead>
                                    <TableHead className="w-36">
                                        Attendance
                                    </TableHead>
                                    {schedule.components && schedule.components.length > 0 &&
                                        schedule.components.map((c) => (
                                            <TableHead
                                                key={c.id}
                                                className="w-24 text-center"
                                            >
                                                {c.name} ({Number(c.max_marks)})
                                            </TableHead>
                                        ))}
                                    <TableHead className="w-28 text-center">
                                        Total Marks ({maxMarks})
                                    </TableHead>
                                    <TableHead className="w-28">
                                        Grace Marks
                                    </TableHead>
                                    <TableHead className="pr-4 min-w-[180px]">
                                        Teacher Remarks
                                    </TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody striped>
                                {filteredRoster.length === 0 ? (
                                    <TableRow>
                                        <TableCell
                                            colSpan={6 + (schedule.components?.length || 0)}
                                            className="h-28 text-center text-xs text-slate-500"
                                        >
                                            No students match your search filter.
                                        </TableCell>
                                    </TableRow>
                                ) : (
                                    filteredRoster.map((s, idx) => {
                                        const m = marks[s.student] || {
                                            marks_obtained: "",
                                            attendance: "present",
                                            remarks: "",
                                            components: {},
                                        };
                                        const savedMark = savedByStudent[s.student];
                                        const numScore = parseFloat(m.marks_obtained);
                                        const isScored = !isNaN(numScore);
                                        const isPassed = isScored && numScore >= passMarks;
                                        const g = Number(savedMark?.grace_marks ?? 0);
                                        const canGrace =
                                            canManage &&
                                            savedMark &&
                                            savedMark.attendance === "present" &&
                                            savedMark.marks_obtained !== null;

                                        return (
                                            <TableRow
                                                key={s.student}
                                                className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors border-b border-slate-100 dark:border-slate-800/70"
                                            >
                                                {/* Roll Number Index */}
                                                <TableCell className="py-3 pl-4 font-mono text-xs text-slate-400 font-medium">
                                                    #{String(idx + 1).padStart(2, "0")}
                                                </TableCell>

                                                {/* Student with Colorful Avatar */}
                                                <TableCell className="py-3">
                                                    <div className="flex items-center gap-2.5">
                                                        <Avatar name={s.full_name} size="sm" />
                                                        <div>
                                                            <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                                {s.full_name}
                                                            </div>
                                                            <div className="text-[10px] font-mono text-slate-400">
                                                                {s.enrollment_id}
                                                            </div>
                                                        </div>
                                                    </div>
                                                </TableCell>

                                                {/* Attendance Selector */}
                                                <TableCell className="py-3">
                                                    <Select
                                                        value={m.attendance}
                                                        disabled={!editable}
                                                        onValueChange={(val) =>
                                                            update(s.student, {
                                                                attendance: val as MarkAttendance,
                                                            })
                                                        }
                                                    >
                                                        <SelectTrigger className="h-8.5 text-xs font-semibold bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                                                            <SelectValue />
                                                        </SelectTrigger>
                                                        <SelectContent>
                                                            {(
                                                                Object.keys(
                                                                    ATTENDANCE_LABELS
                                                                ) as MarkAttendance[]
                                                            ).map((a) => (
                                                                <SelectItem
                                                                    key={a}
                                                                    value={a}
                                                                    className="text-xs"
                                                                >
                                                                    {ATTENDANCE_LABELS[a]}
                                                                </SelectItem>
                                                            ))}
                                                        </SelectContent>
                                                    </Select>
                                                </TableCell>

                                                {/* Component Scores */}
                                                {schedule.components &&
                                                    schedule.components.length > 0 &&
                                                    schedule.components.map((c) => (
                                                        <TableCell key={c.id} className="py-3 text-center">
                                                            <Input
                                                                type="number"
                                                                inputMode="decimal"
                                                                disabled={
                                                                    !editable || m.attendance !== "present"
                                                                }
                                                                value={m.components?.[c.id] ?? ""}
                                                                onChange={(e) =>
                                                                    updateComponent(
                                                                        s.student,
                                                                        c.id,
                                                                        e.target.value
                                                                    )
                                                                }
                                                                className="h-8.5 w-20 text-center mx-auto text-xs font-bold bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800"
                                                                placeholder="0"
                                                            />
                                                        </TableCell>
                                                    ))}

                                                {/* Total Score with Pass/Fail Pill */}
                                                <TableCell className="py-3 text-center">
                                                    <div className="flex items-center justify-center gap-1.5">
                                                        <Input
                                                            type="number"
                                                            inputMode="decimal"
                                                            disabled={
                                                                !editable ||
                                                                m.attendance !== "present" ||
                                                                Boolean(
                                                                    schedule.components &&
                                                                        schedule.components.length > 0
                                                                )
                                                            }
                                                            value={m.marks_obtained}
                                                            onChange={(e) =>
                                                                update(s.student, {
                                                                    marks_obtained: e.target.value,
                                                                })
                                                            }
                                                            className={`h-8.5 w-20 text-center text-xs font-bold border-slate-200 dark:border-slate-800 ${
                                                                Boolean(
                                                                    schedule.components &&
                                                                        schedule.components.length > 0
                                                                )
                                                                    ? "bg-slate-100 dark:bg-slate-800 cursor-not-allowed"
                                                                    : "bg-white dark:bg-slate-900"
                                                            }`}
                                                            placeholder="0"
                                                        />
                                                        {isScored && m.attendance === "present" && (
                                                            <span
                                                                className={`h-2.5 w-2.5 rounded-full shrink-0 ${
                                                                    isPassed
                                                                        ? "bg-emerald-500"
                                                                        : "bg-rose-500"
                                                                }`}
                                                                title={isPassed ? "Passing" : "Below passing"}
                                                            />
                                                        )}
                                                    </div>
                                                </TableCell>

                                                {/* Grace Marks */}
                                                <TableCell className="py-3">
                                                    <div className="flex items-center gap-1.5 text-xs">
                                                        {g > 0 ? (
                                                            <Badge
                                                                variant="outline"
                                                                className="bg-amber-50 text-amber-700 border-amber-300 font-mono font-bold text-[11px]"
                                                            >
                                                                +{g}
                                                            </Badge>
                                                        ) : (
                                                            <span className="text-slate-300 dark:text-slate-700">
                                                                —
                                                            </span>
                                                        )}
                                                        {canGrace && (
                                                            <Button
                                                                size="sm"
                                                                variant="ghost"
                                                                onClick={() => setGrace(savedMark)}
                                                                className="h-7 px-1.5 text-[11px] text-amber-600 hover:text-amber-700 hover:bg-amber-50"
                                                            >
                                                                {g > 0 ? "Edit" : "Grace"}
                                                            </Button>
                                                        )}
                                                        {published &&
                                                            savedMark &&
                                                            savedMark.attendance === "present" &&
                                                            savedMark.marks_obtained !== null && (
                                                                <Button
                                                                    size="sm"
                                                                    variant="ghost"
                                                                    onClick={() => setRecheck(savedMark)}
                                                                    className="h-7 px-1.5 text-[11px] text-sky-600 hover:text-sky-700 hover:bg-sky-50"
                                                                >
                                                                    Recheck
                                                                </Button>
                                                            )}
                                                    </div>
                                                </TableCell>

                                                {/* Teacher Remarks */}
                                                <TableCell className="py-3 pr-4">
                                                    <Input
                                                        disabled={!editable}
                                                        placeholder="Add note..."
                                                        value={m.remarks}
                                                        onChange={(e) =>
                                                            update(s.student, { remarks: e.target.value })
                                                        }
                                                        className="h-8.5 text-xs bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800"
                                                    />
                                                </TableCell>
                                            </TableRow>
                                        );
                                    })
                                )}
                            </TableBody>
                        </Table>
                    </TableShell>

                    {/* 3D. Sticky Bottom Docked Action Bar */}
                    {editable && (
                        <div className="sticky bottom-4 z-20 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md rounded-2xl border border-slate-200/90 dark:border-slate-800 p-4 shadow-lg flex flex-col md:flex-row items-center justify-between gap-3">
                            <div className="flex items-center gap-3 text-xs w-full md:w-auto">
                                <div className="flex items-center gap-1.5 font-semibold text-slate-700 dark:text-slate-300">
                                    <Award className="w-4 h-4 text-indigo-600" />
                                    <span>
                                        {schedule.subject_name} • Section {schedule.section_name}
                                    </span>
                                </div>
                                <span className="text-slate-300 dark:text-slate-700">|</span>
                                <div className="flex items-center gap-2">
                                    <span className="text-indigo-600 font-semibold">
                                        {stats.graded} of {stats.total} Graded
                                    </span>
                                    <span className="text-slate-300 dark:text-slate-700">•</span>
                                    <span className="text-emerald-600 font-semibold">
                                        {stats.passed} Passed
                                    </span>
                                </div>
                            </div>

                            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 w-full md:w-auto justify-end">
                                <div className="w-full sm:w-72">
                                    <Input
                                        id="marks-reason"
                                        maxLength={500}
                                        value={reason}
                                        onChange={(e) => setReason(e.target.value)}
                                        placeholder={
                                            needsReason
                                                ? "Audit justification required..."
                                                : "Optional reason for change..."
                                        }
                                        className="h-9 text-xs border-slate-200 dark:border-slate-800"
                                    />
                                </div>

                                <Button
                                    onClick={handleSubmit}
                                    disabled={isPending || (needsReason && !reason.trim())}
                                    className="bg-indigo-600 hover:bg-indigo-500 text-white gap-2 shrink-0"
                                >
                                    {isPending ? (
                                        <LoaderCircle className="h-4 w-4 animate-spin" />
                                    ) : (
                                        <Save className="h-4 w-4" />
                                    )}
                                    <span>Commit Examination Marks</span>
                                </Button>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Modals */}
            {grace && schedule && (
                <GraceDialog
                    mark={grace}
                    max={schedule.max_marks}
                    onClose={() => setGrace(null)}
                />
            )}
            {recheck && <RecheckDialog mark={recheck} onClose={() => setRecheck(null)} />}
            {importing && scheduleId && (
                <ImportDialog
                    scheduleId={scheduleId}
                    needsReason={needsReason}
                    onClose={() => setImporting(false)}
                />
            )}
        </div>
    );
}
