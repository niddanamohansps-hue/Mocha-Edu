"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
    LoaderCircle,
    Plus,
    Trash2,
    Calendar,
    Clock,
    Printer,
    Users,
    BookOpen,
    Layers,
    MapPin,
    AlertCircle,
    Sparkles,
    CheckCircle2,
    Coffee,
    ArrowRight,
} from "lucide-react";
import Link from "next/link";
import axiosInstance from "@/lib/axios";
import { useSections, useSubjects } from "@/hooks/useAcademics";
import {
    useCreateTimetableEntry,
    useDeleteTimetableEntry,
    usePeriods,
    useRooms,
    useSectionTimetable,
    useUpdateTimetableEntry,
} from "@/hooks/useTimetable";
import { DAY_LABELS, TimetableEntry } from "@/types/Timetable";
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
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import Unauthorized from "@/components/Unauthorized";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { toast } from "sonner";

const WORKING_DAYS = [0, 1, 2, 3, 4, 5]; // Monday to Saturday

const SUBJECT_COLOR_PALETTES = [
    {
        bg: "bg-sky-50 dark:bg-sky-950/40",
        border: "border-sky-200 dark:border-sky-800",
        text: "text-sky-900 dark:text-sky-200",
        accent: "text-sky-600 dark:text-sky-400",
        badge: "bg-sky-100 text-sky-800 dark:bg-sky-900/60 dark:text-sky-300",
    },
    {
        bg: "bg-emerald-50 dark:bg-emerald-950/40",
        border: "border-emerald-200 dark:border-emerald-800",
        text: "text-emerald-900 dark:text-emerald-200",
        accent: "text-emerald-600 dark:text-emerald-400",
        badge: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-300",
    },
    {
        bg: "bg-indigo-50 dark:bg-indigo-950/40",
        border: "border-indigo-200 dark:border-indigo-800",
        text: "text-indigo-900 dark:text-indigo-200",
        accent: "text-indigo-600 dark:text-indigo-400",
        badge: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900/60 dark:text-indigo-300",
    },
    {
        bg: "bg-purple-50 dark:bg-purple-950/40",
        border: "border-purple-200 dark:border-purple-800",
        text: "text-purple-900 dark:text-purple-200",
        accent: "text-purple-600 dark:text-purple-400",
        badge: "bg-purple-100 text-purple-800 dark:bg-purple-900/60 dark:text-purple-300",
    },
    {
        bg: "bg-amber-50 dark:bg-amber-950/40",
        border: "border-amber-200 dark:border-amber-800",
        text: "text-amber-900 dark:text-amber-200",
        accent: "text-amber-600 dark:text-amber-400",
        badge: "bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-300",
    },
    {
        bg: "bg-rose-50 dark:bg-rose-950/40",
        border: "border-rose-200 dark:border-rose-800",
        text: "text-rose-900 dark:text-rose-200",
        accent: "text-rose-600 dark:text-rose-400",
        badge: "bg-rose-100 text-rose-800 dark:bg-rose-900/60 dark:text-rose-300",
    },
    {
        bg: "bg-teal-50 dark:bg-teal-950/40",
        border: "border-teal-200 dark:border-teal-800",
        text: "text-teal-900 dark:text-teal-200",
        accent: "text-teal-600 dark:text-teal-400",
        badge: "bg-teal-100 text-teal-800 dark:bg-teal-900/60 dark:text-teal-300",
    },
];

function getSubjectPalette(subjectName: string) {
    let hash = 0;
    for (let i = 0; i < subjectName.length; i++) {
        hash = subjectName.charCodeAt(i) + ((hash << 5) - hash);
    }
    const index = Math.abs(hash) % SUBJECT_COLOR_PALETTES.length;
    return SUBJECT_COLOR_PALETTES[index];
}

export default function TimetablePage() {
    const { can, isOwner } = usePermissions();
    const { selectedYear } = useAcademicYear();
    const academicYear = selectedYear?.name || "";
    const canManage = isOwner || can("manage_timetable");
    const canView = isOwner || can("view_timetable");

    const [sectionId, setSectionId] = useState("");
    const { data: sections } = useSections();
    const { data: subjects } = useSubjects();
    const {
        data: periods,
        isLoading: loadingPeriods,
        isError: periodsError,
        refetch: refetchPeriods,
    } = usePeriods(academicYear);
    const { data: rooms } = useRooms();

    const { data: assignments } = useQuery({
        queryKey: ["assignments", "all"],
        queryFn: async () => {
            const response = await axiosInstance.get("/academics/assignments/");
            return response.data as any[];
        },
    });

    const {
        data: entries,
        isLoading: loadingEntries,
        isError: entriesError,
        refetch: refetchEntries,
    } = useSectionTimetable(sectionId || undefined, academicYear);

    const { mutate: createEntry, isPending: isCreating } = useCreateTimetableEntry();
    const { mutate: updateEntry, isPending: isUpdating } = useUpdateTimetableEntry();
    const { mutate: deleteEntry, isPending: isDeleting } = useDeleteTimetableEntry();

    const [dialogState, setDialogState] = useState<{
        day: number;
        periodId: string;
        entry?: TimetableEntry;
    } | null>(null);

    const [form, setForm] = useState<{ subject: string; instructor: string; room: string }>({
        subject: "",
        instructor: "",
        room: "",
    });

    const entryMap = useMemo(() => {
        const map: Record<string, TimetableEntry> = {};
        entries?.forEach((e) => {
            map[`${e.day_of_week}-${e.period}`] = e;
        });
        return map;
    }, [entries]);

    const selectedSection = useMemo(() => {
        return sections?.find((s) => s.id === sectionId);
    }, [sections, sectionId]);

    const sectionSubjects = useMemo(() => {
        if (!selectedSection) return subjects ?? [];
        return (subjects ?? []).filter((subj: any) => subj.level === selectedSection.level);
    }, [selectedSection, subjects]);

    const availableInstructors = useMemo(() => {
        if (!form.subject) return [];
        return (assignments ?? []).filter(
            (a: any) => a.section === sectionId && a.subject === form.subject && a.instructor
        );
    }, [assignments, sectionId, form.subject]);

    // Timetable Summary Metrics
    const metrics = useMemo(() => {
        if (!entries || entries.length === 0) {
            return { totalPeriods: 0, uniqueSubjects: 0, uniqueTeachers: 0 };
        }
        const subjectsSet = new Set<string>();
        const teachersSet = new Set<string>();
        for (const e of entries) {
            if (e.subject) subjectsSet.add(e.subject);
            if (e.instructor) teachersSet.add(e.instructor);
        }
        return {
            totalPeriods: entries.length,
            uniqueSubjects: subjectsSet.size,
            uniqueTeachers: teachersSet.size,
        };
    }, [entries]);

    const openCell = (day: number, periodId: string, entry?: TimetableEntry) => {
        if (!canManage) return;
        const period = periods?.find((p) => p.id === periodId);
        if (period?.is_break) return;
        setForm({
            subject: entry?.subject ?? "",
            instructor: entry?.instructor ?? "",
            room: entry?.room ?? "",
        });
        setDialogState({ day, periodId, entry });
    };

    const handleSave = () => {
        if (!dialogState || !form.subject) return;
        const payload = {
            academic_year: academicYear,
            section: sectionId,
            subject: form.subject,
            instructor: form.instructor || null,
            room: form.room || null,
            day_of_week: dialogState.day,
            period: dialogState.periodId,
        };
        if (dialogState.entry) {
            updateEntry(
                { id: dialogState.entry.id, data: payload },
                {
                    onSuccess: () => {
                        toast.success("Schedule slot updated");
                        setDialogState(null);
                    },
                }
            );
        } else {
            createEntry(payload, {
                onSuccess: () => {
                    toast.success("Period allocated successfully");
                    setDialogState(null);
                },
            });
        }
    };

    const handleDelete = () => {
        if (!dialogState?.entry) return;
        deleteEntry(dialogState.entry.id, {
            onSuccess: () => {
                toast.info("Slot removed from schedule");
                setDialogState(null);
            },
        });
    };

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-6 max-w-7xl mx-auto pb-24 animate-in fade-in duration-500">
            {/* 1. Header with Actions Strip */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800 print:hidden">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Calendar className="h-7 w-7 text-sky-600 dark:text-sky-400" />
                        <span>Master Timetable &amp; Schedule</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Weekly recurring academic schedule matrix, period allocations, faculty assignments, and rooms
                    </p>
                </div>

                <div className="flex items-center gap-2.5 shrink-0">
                    <Button
                        asChild
                        variant="outline"
                        size="sm"
                        className="h-9 px-3 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 cursor-pointer shadow-2xs"
                    >
                        <Link href="/dashboard/timetable/substitutions">
                            <Users className="h-3.5 w-3.5 text-slate-500" />
                            <span>Substitution Desk</span>
                        </Link>
                    </Button>
                    {sectionId && (
                        <Button
                            onClick={() => window.print()}
                            variant="outline"
                            size="sm"
                            className="h-9 px-3 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 cursor-pointer shadow-2xs"
                        >
                            <Printer className="h-3.5 w-3.5 text-slate-500" />
                            <span>Print Schedule</span>
                        </Button>
                    )}
                </div>
            </div>

            {/* 2. Control Card: Section Selector & Status Badges */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-5 shadow-2xs space-y-4 print:hidden">
                <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
                    <div className="md:col-span-6 space-y-1.5">
                        <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                            <Layers className="h-3.5 w-3.5 text-slate-500" />
                            Academic Class &amp; Section <span className="text-rose-500">*</span>
                        </label>
                        <Select value={sectionId} onValueChange={setSectionId}>
                            <SelectTrigger className="h-10 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium">
                                <SelectValue placeholder="Select class section..." />
                            </SelectTrigger>
                            <SelectContent>
                                {sections?.map((s) => (
                                    <SelectItem key={s.id} value={s.id} className="text-xs">
                                        <div className="flex items-center gap-2">
                                            <span className="font-semibold text-slate-900 dark:text-white">
                                                {s.level_name}
                                            </span>
                                            <span className="text-slate-400">• Section {s.name}</span>
                                        </div>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="md:col-span-6 flex items-center justify-between md:justify-end gap-3 pt-2">
                        <div className="flex items-center gap-2 text-xs">
                            <span className="text-slate-400">Academic Session:</span>
                            <Badge
                                variant="outline"
                                className="bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/60 dark:text-sky-300 font-semibold"
                            >
                                {academicYear || "No term selected"}
                            </Badge>
                        </div>
                    </div>
                </div>

                {/* Section Summary Strip */}
                {selectedSection && (
                    <div className="grid grid-cols-3 gap-3 pt-3 border-t border-slate-100 dark:border-slate-800">
                        <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-950/50 border border-slate-100 dark:border-slate-800 text-center">
                            <span className="text-[10px] uppercase font-bold text-slate-400 block">
                                Weekly Periods
                            </span>
                            <span className="text-lg font-bold text-slate-900 dark:text-white">
                                {metrics.totalPeriods} Slots
                            </span>
                        </div>
                        <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-950/50 border border-slate-100 dark:border-slate-800 text-center">
                            <span className="text-[10px] uppercase font-bold text-slate-400 block">
                                Subjects
                            </span>
                            <span className="text-lg font-bold text-indigo-600 dark:text-indigo-400">
                                {metrics.uniqueSubjects} Subjects
                            </span>
                        </div>
                        <div className="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-950/50 border border-slate-100 dark:border-slate-800 text-center">
                            <span className="text-[10px] uppercase font-bold text-slate-400 block">
                                Faculty Assigned
                            </span>
                            <span className="text-lg font-bold text-emerald-600 dark:text-emerald-400">
                                {metrics.uniqueTeachers} Teachers
                            </span>
                        </div>
                    </div>
                )}
            </div>

            {/* Empty, Loading, and Error States */}
            {!sectionId && (
                <EmptyState
                    title="Choose an academic section to load its weekly timetable"
                    description="Select a class and section from the dropdown above to view or configure weekly periods."
                    className="py-16 text-slate-500 text-sm print:hidden"
                />
            )}

            {sectionId && (loadingPeriods || loadingEntries) && <LoadingState className="py-20" />}

            {sectionId && !loadingPeriods && !loadingEntries && (periodsError || entriesError) && (
                <ErrorState onRetry={periodsError ? refetchPeriods : refetchEntries} />
            )}

            {sectionId && !loadingPeriods && periods && periods.length === 0 && (
                <EmptyState
                    title={`No period structure defined for ${academicYear} yet`}
                    description="Ask an institution administrator to configure daily period bells and durations."
                    className="py-16 text-slate-500 text-sm"
                />
            )}

            {/* 3. High-Density Weekly Schedule Matrix */}
            {sectionId && !loadingPeriods && periods && periods.length > 0 && (
                <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 shadow-2xs overflow-hidden">
                    {/* Print Only Header Banner */}
                    <div className="hidden print:block p-4 border-b border-slate-200 text-center space-y-1">
                        <h2 className="text-xl font-bold">Class Timetable: {selectedSection?.level_name} - {selectedSection?.name}</h2>
                        <p className="text-xs text-slate-500">Academic Session: {academicYear}</p>
                    </div>

                    <div className="overflow-x-auto">
                        <table className="w-full text-xs border-collapse">
                            <thead>
                                <tr className="bg-slate-50/90 dark:bg-slate-800/80 border-b border-slate-200/80 dark:border-slate-800">
                                    <th className="py-3 px-4 text-left font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider w-32 border-r border-slate-200/60 dark:border-slate-800">
                                        Period
                                    </th>
                                    {WORKING_DAYS.map((day) => (
                                        <th
                                            key={day}
                                            className="py-3 px-3 text-left font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider min-w-[150px] border-r border-slate-200/60 dark:border-slate-800 last:border-0"
                                        >
                                            {DAY_LABELS[day]}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                {periods.map((period) => (
                                    <tr key={period.id} className="hover:bg-slate-50/40 dark:hover:bg-slate-800/20">
                                        {/* Period Time Column */}
                                        <td className="py-3 px-4 font-medium whitespace-nowrap bg-slate-50/40 dark:bg-slate-900/40 border-r border-slate-200/60 dark:border-slate-800">
                                            <div className="font-bold text-slate-900 dark:text-white text-xs">
                                                {period.name}
                                            </div>
                                            <div className="text-[10px] text-slate-400 font-mono mt-0.5 flex items-center gap-1">
                                                <Clock className="w-3 h-3" />
                                                <span>
                                                    {period.start_time.slice(0, 5)} - {period.end_time.slice(0, 5)}
                                                </span>
                                            </div>
                                        </td>

                                        {/* Days Cells */}
                                        {WORKING_DAYS.map((day) => {
                                            if (period.is_break) {
                                                return (
                                                    <td
                                                        key={day}
                                                        className="p-2 text-center bg-slate-100/60 dark:bg-slate-800/40 border-r border-slate-200/60 dark:border-slate-800 last:border-0"
                                                    >
                                                        <div className="flex items-center justify-center gap-1.5 text-slate-400 font-semibold text-[11px]">
                                                            <Coffee className="w-3.5 h-3.5" />
                                                            <span>Recess Break</span>
                                                        </div>
                                                    </td>
                                                );
                                            }

                                            const entry = entryMap[`${day}-${period.id}`];
                                            const palette = entry ? getSubjectPalette(entry.subject_name) : null;

                                            return (
                                                <td
                                                    key={day}
                                                    onClick={() => openCell(day, period.id, entry)}
                                                    className={`p-2 align-top border-r border-slate-200/60 dark:border-slate-800 last:border-0 transition-colors ${
                                                        canManage ? "cursor-pointer" : ""
                                                    }`}
                                                >
                                                    {entry && palette ? (
                                                        <div
                                                            className={`p-2.5 rounded-xl border ${palette.bg} ${palette.border} space-y-1.5 shadow-2xs hover:shadow-xs transition`}
                                                        >
                                                            <div className="flex items-center justify-between gap-1">
                                                                <span
                                                                    className={`font-bold text-xs truncate ${palette.text}`}
                                                                >
                                                                    {entry.subject_name}
                                                                </span>
                                                            </div>
                                                            <div className="flex items-center gap-1.5 text-[11px] text-slate-600 dark:text-slate-300">
                                                                <Users className="w-3 h-3 text-slate-400 shrink-0" />
                                                                <span className="truncate">
                                                                    {entry.instructor_name || "Unassigned"}
                                                                </span>
                                                            </div>
                                                            {entry.room_name && (
                                                                <div className="flex items-center gap-1 text-[10px] text-slate-400 font-medium">
                                                                    <MapPin className="w-2.5 h-2.5 shrink-0" />
                                                                    <span>{entry.room_name}</span>
                                                                </div>
                                                            )}
                                                        </div>
                                                    ) : canManage ? (
                                                        <div className="h-20 rounded-xl border border-dashed border-slate-200 dark:border-slate-800 hover:border-sky-400 dark:hover:border-sky-600 flex flex-col items-center justify-center gap-1 text-slate-300 hover:text-sky-600 dark:hover:text-sky-400 transition-colors group">
                                                            <Plus className="h-4 w-4 transition group-hover:scale-110" />
                                                            <span className="text-[10px] font-semibold opacity-0 group-hover:opacity-100 transition">
                                                                Assign Slot
                                                            </span>
                                                        </div>
                                                    ) : (
                                                        <div className="h-20 flex items-center justify-center text-slate-300 dark:text-slate-700">
                                                            —
                                                        </div>
                                                    )}
                                                </td>
                                            );
                                        })}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* 4. Slot Configuration Modal */}
            <Dialog open={Boolean(dialogState)} onOpenChange={(open) => !open && setDialogState(null)}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle className="text-base font-bold flex items-center gap-2">
                            <Clock className="w-5 h-5 text-sky-600" />
                            <span>
                                {dialogState?.entry ? "Edit Schedule Slot" : "Allocate Schedule Slot"}
                            </span>
                        </DialogTitle>
                        <DialogDescription className="text-xs">
                            {dialogState &&
                                `${DAY_LABELS[dialogState.day]} • ${
                                    periods?.find((p) => p.id === dialogState.periodId)?.name
                                }`}
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 pt-2">
                        {/* Subject */}
                        <div className="space-y-1.5">
                            <Label htmlFor="slot-subject" className="text-xs font-semibold">
                                Subject <span className="text-rose-500">*</span>
                            </Label>
                            <Select
                                value={form.subject}
                                onValueChange={(v) =>
                                    setForm((f) => ({ ...f, subject: v, instructor: "" }))
                                }
                            >
                                <SelectTrigger className="h-9 text-xs">
                                    <SelectValue placeholder="Select subject..." />
                                </SelectTrigger>
                                <SelectContent>
                                    {sectionSubjects.map((s: any) => (
                                        <SelectItem key={s.id} value={s.id} className="text-xs">
                                            {s.name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        {/* Faculty */}
                        <div className="space-y-1.5">
                            <Label htmlFor="slot-faculty" className="text-xs font-semibold">
                                Assigned Instructor
                            </Label>
                            <Select
                                value={form.instructor}
                                onValueChange={(v) => setForm((f) => ({ ...f, instructor: v }))}
                            >
                                <SelectTrigger className="h-9 text-xs">
                                    <SelectValue
                                        placeholder={
                                            availableInstructors.length > 0
                                                ? "Select assigned teacher..."
                                                : "Choose teacher (optional)"
                                        }
                                    />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="" className="text-xs text-slate-400">
                                        No instructor assigned
                                    </SelectItem>
                                    {availableInstructors.map((a: any) => (
                                        <SelectItem
                                            key={a.instructor}
                                            value={a.instructor}
                                            className="text-xs"
                                        >
                                            {a.instructor_name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        {/* Room */}
                        <div className="space-y-1.5">
                            <Label htmlFor="slot-room" className="text-xs font-semibold">
                                Classroom / Laboratory
                            </Label>
                            <Select
                                value={form.room}
                                onValueChange={(v) => setForm((f) => ({ ...f, room: v }))}
                            >
                                <SelectTrigger className="h-9 text-xs">
                                    <SelectValue placeholder="Select room..." />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="" className="text-xs text-slate-400">
                                        Unassigned room
                                    </SelectItem>
                                    {rooms?.map((r) => (
                                        <SelectItem key={r.id} value={r.id} className="text-xs">
                                            {r.name} (Cap: {r.capacity})
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <DialogFooter className="pt-2 gap-2 flex items-center justify-between">
                            {dialogState?.entry && (
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    onClick={handleDelete}
                                    disabled={isDeleting}
                                    className="text-xs text-rose-600 hover:text-rose-700 hover:bg-rose-50 mr-auto"
                                >
                                    <Trash2 className="w-3.5 h-3.5 mr-1" />
                                    Delete Slot
                                </Button>
                            )}
                            <div className="flex items-center gap-2">
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setDialogState(null)}
                                >
                                    Cancel
                                </Button>
                                <Button
                                    type="button"
                                    size="sm"
                                    disabled={!form.subject || isCreating || isUpdating}
                                    onClick={handleSave}
                                    className="bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs"
                                >
                                    {(isCreating || isUpdating) && (
                                        <LoaderCircle className="h-4 w-4 animate-spin mr-1.5" />
                                    )}
                                    Save Slot
                                </Button>
                            </div>
                        </DialogFooter>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
}
