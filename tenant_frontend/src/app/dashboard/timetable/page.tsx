"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { LoaderCircle, Plus, Trash2 } from "lucide-react";
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

const WORKING_DAYS = [0, 1, 2, 3, 4, 5]; // Monday-Saturday shown by default; Sunday (6) is rare for school timetables

function currentYear() {
    return String(new Date().getFullYear());
}

export default function TimetablePage() {
    const { can, isOwner } = usePermissions();
    const canManage = isOwner || can("manage_timetable");
    const canView = isOwner || can("view_timetable");

    const [academicYear, setAcademicYear] = useState(currentYear());
    const [sectionId, setSectionId] = useState("");
    const { data: sections } = useSections();
    const { data: subjects } = useSubjects();
    const { data: periods, isLoading: loadingPeriods, isError: periodsError, refetch: refetchPeriods } = usePeriods(academicYear);
    const { data: rooms } = useRooms();
    const { data: assignments } = useQuery({
        queryKey: ["assignments", "all"],
        queryFn: async () => {
            const response = await axiosInstance.get("/academics/assignments/");
            return response.data as any[];
        },
    });
    const { data: entries, isLoading: loadingEntries, isError: entriesError, refetch: refetchEntries } = useSectionTimetable(
        sectionId || undefined,
        academicYear
    );

    const { mutate: createEntry, isPending: isCreating } = useCreateTimetableEntry();
    const { mutate: updateEntry, isPending: isUpdating } = useUpdateTimetableEntry();
    const { mutate: deleteEntry } = useDeleteTimetableEntry();

    const [dialogState, setDialogState] = useState<{ day: number; periodId: string; entry?: TimetableEntry } | null>(
        null
    );
    const [form, setForm] = useState<{ subject: string; instructor: string; room: string }>({
        subject: "", instructor: "", room: "",
    });

    const entryMap = useMemo(() => {
        const map: Record<string, TimetableEntry> = {};
        entries?.forEach((e) => {
            map[`${e.day_of_week}-${e.period}`] = e;
        });
        return map;
    }, [entries]);

    const sectionSubjects = useMemo(() => {
        const section = sections?.find((s) => s.id === sectionId);
        if (!section) return subjects ?? [];
        return (subjects ?? []).filter((subj: any) => subj.level === section.level);
    }, [sections, subjects, sectionId]);

    const availableInstructors = useMemo(() => {
        if (!form.subject) return [];
        return (assignments ?? []).filter(
            (a: any) => a.section === sectionId && a.subject === form.subject && a.instructor
        );
    }, [assignments, sectionId, form.subject]);

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
                { onSuccess: () => setDialogState(null) }
            );
        } else {
            createEntry(payload, { onSuccess: () => setDialogState(null) });
        }
    };

    const handleDelete = () => {
        if (!dialogState?.entry) return;
        deleteEntry(dialogState.entry.id, { onSuccess: () => setDialogState(null) });
    };

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Timetable</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Weekly recurring schedule per section
                </p>
            </div>

            <div className="flex flex-wrap gap-4 items-end">
                <div className="w-64">
                    <label className="text-xs font-medium text-slate-500 mb-1 block">Section</label>
                    <Select value={sectionId} onValueChange={setSectionId}>
                        <SelectTrigger>
                            <SelectValue placeholder="Select a section" />
                        </SelectTrigger>
                        <SelectContent>
                            {sections?.map((s) => (
                                <SelectItem key={s.id} value={s.id}>
                                    {s.level_name} - {s.name}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
                <div className="w-40">
                    <label className="text-xs font-medium text-slate-500 mb-1 block">Academic Year</label>
                    <Input value={academicYear} onChange={(e) => setAcademicYear(e.target.value)} />
                </div>
            </div>

            {!sectionId && (
                <EmptyState title="Choose a section above to view or edit its timetable." className="py-16 text-slate-500 text-sm" />
            )}

            {sectionId && (loadingPeriods || loadingEntries) && <LoadingState className="py-20" />}

            {sectionId && !loadingPeriods && !loadingEntries && (periodsError || entriesError) && (
                <ErrorState onRetry={periodsError ? refetchPeriods : refetchEntries} />
            )}

            {sectionId && !loadingPeriods && periods && periods.length === 0 && (
                <EmptyState
                    title={`No periods defined for ${academicYear} yet. Ask an administrator to add them.`}
                    className="py-16 text-slate-500 text-sm"
                />
            )}

            {sectionId && !loadingPeriods && periods && periods.length > 0 && (
                <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800">
                    <table className="w-full text-sm border-collapse">
                        <thead className="bg-slate-50 dark:bg-slate-900">
                            <tr>
                                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">Period</th>
                                {WORKING_DAYS.map((day) => (
                                    <th key={day} className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase">
                                        {DAY_LABELS[day]}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {periods.map((period) => (
                                <tr key={period.id} className="border-t border-slate-100 dark:border-slate-800">
                                    <td className="px-4 py-2 font-medium whitespace-nowrap">
                                        {period.name}
                                        <div className="text-xs text-slate-400">
                                            {period.start_time}-{period.end_time}
                                        </div>
                                    </td>
                                    {WORKING_DAYS.map((day) => {
                                        if (period.is_break) {
                                            return (
                                                <td key={day} className="px-4 py-2 text-center text-xs text-slate-400 bg-slate-50 dark:bg-slate-900">
                                                    Break
                                                </td>
                                            );
                                        }
                                        const entry = entryMap[`${day}-${period.id}`];
                                        return (
                                            <td
                                                key={day}
                                                className={`px-4 py-2 align-top ${canManage ? "cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/50" : ""}`}
                                                onClick={() => openCell(day, period.id, entry)}
                                            >
                                                {entry ? (
                                                    <div>
                                                        <p className="font-semibold text-slate-800 dark:text-slate-200">{entry.subject_name}</p>
                                                        <p className="text-xs text-slate-500">{entry.instructor_name || "—"}</p>
                                                        {entry.room_name && <p className="text-xs text-slate-400">{entry.room_name}</p>}
                                                    </div>
                                                ) : canManage ? (
                                                    <Plus className="h-4 w-4 text-slate-300" />
                                                ) : (
                                                    <span className="text-slate-300">—</span>
                                                )}
                                            </td>
                                        );
                                    })}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            <Dialog open={!!dialogState} onOpenChange={(open) => !open && setDialogState(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{dialogState?.entry ? "Edit" : "Add"} Timetable Entry</DialogTitle>
                        <DialogDescription>
                            {dialogState && `${DAY_LABELS[dialogState.day]} - ${periods?.find((p) => p.id === dialogState.periodId)?.name}`}
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4">
                        <div>
                            <label className="text-xs font-medium text-slate-500 mb-1 block">Subject</label>
                            <Select value={form.subject} onValueChange={(v) => setForm((f) => ({ ...f, subject: v }))}>
                                <SelectTrigger>
                                    <SelectValue placeholder="Select subject" />
                                </SelectTrigger>
                                <SelectContent>
                                    {sectionSubjects.map((s: any) => (
                                        <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div>
                            <label className="text-xs font-medium text-slate-500 mb-1 block">Instructor (optional)</label>
                            <Select
                                value={form.instructor || "__none__"}
                                onValueChange={(v) => setForm((f) => ({ ...f, instructor: v === "__none__" ? "" : v }))}
                                disabled={!form.subject}
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder={form.subject ? "No instructor" : "Select a subject first"} />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="__none__">No instructor</SelectItem>
                                    {availableInstructors.map((a: any) => (
                                        <SelectItem key={a.instructor} value={a.instructor}>
                                            {a.instructor_details?.staff_member_name || a.instructor}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            {form.subject && availableInstructors.length === 0 && (
                                <p className="text-xs text-slate-400 mt-1">
                                    No instructor is assigned to teach this subject for this section yet - assign one
                                    via Academics → Teaching Assignments first.
                                </p>
                            )}
                        </div>
                        <div>
                            <label className="text-xs font-medium text-slate-500 mb-1 block">Room (optional)</label>
                            <Select value={form.room || "__none__"} onValueChange={(v) => setForm((f) => ({ ...f, room: v === "__none__" ? "" : v }))}>
                                <SelectTrigger>
                                    <SelectValue placeholder="No room" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="__none__">No room</SelectItem>
                                    {rooms?.map((r) => (
                                        <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>

                    <div className="flex justify-between pt-2">
                        {dialogState?.entry ? (
                            <Button variant="outline" className="text-red-600 gap-2" onClick={handleDelete}>
                                <Trash2 className="h-4 w-4" />
                                Delete
                            </Button>
                        ) : <div />}
                        <Button onClick={handleSave} disabled={!form.subject || isCreating || isUpdating}>
                            {(isCreating || isUpdating) && <LoaderCircle className="h-4 w-4 animate-spin mr-2" />}
                            Save
                        </Button>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
}
