"use client";

import { useState } from "react";
import { LoaderCircle, Plus, Lock, Unlock, Send } from "lucide-react";
import { useSections, useSubjects } from "@/hooks/useAcademics";
import { useRooms, usePeriods } from "@/hooks/useTimetable";
import {
    useCreateExamination,
    useCreateExamSchedule,
    useCreateExamType,
    useExaminations,
    useExamSchedules,
    useExamTypes,
    useLockExamSchedule,
    usePublishExamination,
    useExaminationSettings,
    useRequestPublication,
    useUpdateExaminationSettings,
} from "@/hooks/useExaminations";
import { usePermissions } from "@/providers/PermissionProvider";
import { useMe } from "@/hooks/useAuth";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
    Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";


export default function ExaminationsPage() {
    const { can, isOwner } = usePermissions();
    const { selectedYear } = useAcademicYear();
    const academicYear = selectedYear?.name || "";
    const canManage = isOwner || can("manage_examinations");
    const canView = isOwner || can("view_examinations");
    const canPublish = isOwner || can("publish_results");
    const { data: examTypes } = useExamTypes();
    const { data: examinations, isLoading: loadingExams, isError: examsError, refetch: refetchExams } = useExaminations(academicYear);
    const [selectedExamId, setSelectedExamId] = useState("");
    const { data: schedules, isLoading: loadingSchedules } = useExamSchedules(selectedExamId || undefined);

    const { data: sections } = useSections();
    const { data: subjects } = useSubjects();
    const { data: rooms } = useRooms();
    const { data: periods } = usePeriods(academicYear);

    const { mutate: createExamType } = useCreateExamType();
    const { mutate: createExamination, isPending: isCreatingExam } = useCreateExamination();
    const { mutate: createSchedule, isPending: isCreatingSchedule } = useCreateExamSchedule();
    const { mutate: lockSchedule } = useLockExamSchedule();
    const { mutate: publish, isPending: isPublishing } = usePublishExamination();
    const examSettings = useExaminationSettings();
    const updateSettings = useUpdateExaminationSettings();
    const requestPublication = useRequestPublication();
    const twoPerson = !!examSettings.data?.require_separate_publisher;
    const { data: me } = useMe();

    const [examDialogOpen, setExamDialogOpen] = useState(false);
    const [examForm, setExamForm] = useState({ name: "", exam_type: "", start_date: "", end_date: "" });
    const [newTypeName, setNewTypeName] = useState("");

    const [scheduleDialogOpen, setScheduleDialogOpen] = useState(false);
    const [scheduleForm, setScheduleForm] = useState({
        subject: "", section: "", date: "", start_time: "", end_time: "",
        period: "", room: "", max_marks: "100", pass_marks: "40",
    });

    const selectedExam = examinations?.find((e) => e.id === selectedExamId);

    const handleAddExamType = () => {
        if (!newTypeName.trim()) return;
        createExamType({ name: newTypeName, order: (examTypes?.length ?? 0) + 1 }, {
            onSuccess: () => setNewTypeName(""),
        });
    };

    const handleCreateExam = () => {
        createExamination(
            { ...examForm, academic_year: academicYear },
            { onSuccess: () => { setExamDialogOpen(false); setExamForm({ name: "", exam_type: "", start_date: "", end_date: "" }); } }
        );
    };

    const handleCreateSchedule = () => {
        if (!selectedExamId) return;
        createSchedule(
            {
                examination: selectedExamId, academic_year: academicYear,
                subject: scheduleForm.subject, section: scheduleForm.section,
                date: scheduleForm.date, start_time: scheduleForm.start_time, end_time: scheduleForm.end_time,
                period: scheduleForm.period || null, room: scheduleForm.room || null,
                max_marks: scheduleForm.max_marks, pass_marks: scheduleForm.pass_marks,
            },
            {
                onSuccess: () => {
                    setScheduleDialogOpen(false);
                    setScheduleForm({ subject: "", section: "", date: "", start_time: "", end_time: "", period: "", room: "", max_marks: "100", pass_marks: "40" });
                },
            }
        );
    };

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-8">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Examinations</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Create examinations, schedule subjects, and publish results
                </p>
            </div>

            <div className="flex flex-wrap gap-4 items-end">
                <div className="w-48">
                    <label className="text-xs font-medium text-slate-500 mb-1 block">Academic Year</label>
                    <div className="flex items-center gap-1.5 h-9 px-3 rounded-md border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-sm font-medium text-slate-700 dark:text-slate-300">
                        <span className="truncate">{academicYear || "No year selected"}</span>
                        {selectedYear?.is_current && (
                            <span className="text-[10px] bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 px-1 py-0.2 rounded font-medium ml-auto">Current</span>
                        )}
                    </div>
                </div>
                {canManage && (
                    <>
                        <div className="flex gap-2 items-end">
                            <div>
                                <label htmlFor="f-new-exam-type" className="text-xs font-medium text-slate-500 mb-1 block">New Exam Type</label>
                                <Input id="f-new-exam-type" value={newTypeName} onChange={(e) => setNewTypeName(e.target.value)} placeholder="e.g. Mid-Term" className="w-48" />
                            </div>
                            <Button variant="outline" onClick={handleAddExamType}>Add Type</Button>
                        </div>
                        <Button onClick={() => setExamDialogOpen(true)} className="gap-2">
                            <Plus className="h-4 w-4" /> New Examination
                        </Button>
                    </>
                )}
            </div>

            {loadingExams ? (
                <LoadingState className="py-10" />
            ) : examsError ? (
                <ErrorState onRetry={refetchExams} />
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {examinations?.map((exam) => (
                        <button
                            key={exam.id}
                            onClick={() => setSelectedExamId(exam.id)}
                            className={`text-left p-4 rounded-2xl border ${selectedExamId === exam.id ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-500/10" : "border-slate-200 dark:border-slate-800"}`}
                        >
                            <p className="font-bold">{exam.name}</p>
                            <p className="text-xs text-slate-500">{exam.exam_type_name} - {exam.start_date} to {exam.end_date}</p>
                            <p className="text-xs mt-1">{exam.is_published ? "✅ Published" : "Draft"}</p>
                        </button>
                    ))}
                    {examinations?.length === 0 && (
                        <EmptyState title={`No examinations for ${academicYear} yet.`} className="py-6 text-slate-500 text-sm" />
                    )}
                </div>
            )}

            {canManage && examSettings.data && (
                <label className="flex items-start gap-2 text-sm">
                    <input type="checkbox" className="mt-1" checked={twoPerson} disabled={updateSettings.isPending}
                        onChange={(e) => updateSettings.mutate(e.target.checked)} />
                    <span>A different person must publish results<span className="block text-xs text-slate-500">One person requests publication, someone else publishes. Recommended.</span></span>
                </label>
            )}

            {selectedExam && (
                <div className="space-y-4">
                    <div className="flex flex-wrap justify-between gap-2 items-center">
                        <h2 className="text-lg font-bold">{selectedExam.name} - Schedules</h2>
                        <div className="flex gap-2">
                            {canManage && !selectedExam.is_published && (
                                <Button variant="outline" onClick={() => setScheduleDialogOpen(true)} className="gap-2">
                                    <Plus className="h-4 w-4" /> Add Schedule
                                </Button>
                            )}
                            {twoPerson && canManage && !selectedExam.is_published && !selectedExam.publication_requested_by_user_id && (
                                <Button variant="outline" onClick={() => requestPublication.mutate(selectedExam.id)} disabled={requestPublication.isPending}>
                                    Request publication
                                </Button>
                            )}
                            {canPublish && !selectedExam.is_published && (!twoPerson || (selectedExam.publication_requested_by_user_id && selectedExam.publication_requested_by_user_id !== me?.id)) && (
                                <Button onClick={() => publish(selectedExam.id)} disabled={isPublishing} className="gap-2">
                                    {isPublishing && <LoaderCircle className="h-4 w-4 animate-spin" />}
                                    <Send className="h-4 w-4" /> Publish Results
                                </Button>
                            )}
                            {twoPerson && !selectedExam.is_published && selectedExam.publication_requested_by_user_id === me?.id && (
                                <span className="text-sm text-slate-500 self-center">You requested publication; someone else publishes.</span>
                            )}
                        </div>
                    </div>

                    {loadingSchedules ? (
                        <LoaderCircle className="h-6 w-6 animate-spin text-indigo-600" />
                    ) : (
                        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead className="bg-slate-50 dark:bg-slate-900">
                                    <tr className="text-left text-xs font-semibold text-slate-500 uppercase">
                                        <th className="px-4 py-3">Subject</th>
                                        <th className="px-4 py-3">Section</th>
                                        <th className="px-4 py-3">Date</th>
                                        <th className="px-4 py-3">Time</th>
                                        <th className="px-4 py-3">Room</th>
                                        <th className="px-4 py-3">Max/Pass</th>
                                        <th className="px-4 py-3">Lock</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {schedules?.map((s) => (
                                        <tr key={s.id} className="border-t border-slate-100 dark:border-slate-800">
                                            <td className="px-4 py-2 font-medium">{s.subject_name}</td>
                                            <td className="px-4 py-2">{s.section_name}</td>
                                            <td className="px-4 py-2">{s.date}</td>
                                            <td className="px-4 py-2 text-slate-500">{s.start_time}-{s.end_time}</td>
                                            <td className="px-4 py-2 text-slate-500">{s.room_name || "—"}</td>
                                            <td className="px-4 py-2 text-slate-500">{s.max_marks}/{s.pass_marks}</td>
                                            <td className="px-4 py-2">
                                                {canManage && (
                                                    <Button
                                                        size="sm" variant="ghost"
                                                        onClick={() => lockSchedule({ id: s.id, isLocked: !s.is_locked })}
                                                    >
                                                        {s.is_locked ? <Lock className="h-4 w-4 text-amber-600" /> : <Unlock className="h-4 w-4 text-slate-400" />}
                                                    </Button>
                                                )}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}

            <Dialog open={examDialogOpen} onOpenChange={setExamDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>New Examination</DialogTitle>
                        <DialogDescription>Academic year: {academicYear}</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4">
                        <Input aria-label="Name (e.g. Mid-Term 2026)" placeholder="Name (e.g. Mid-Term 2026)" value={examForm.name} onChange={(e) => setExamForm((f) => ({ ...f, name: e.target.value }))} />
                        <Select value={examForm.exam_type} onValueChange={(v) => setExamForm((f) => ({ ...f, exam_type: v }))}>
                            <SelectTrigger><SelectValue placeholder="Exam type" /></SelectTrigger>
                            <SelectContent>
                                {examTypes?.map((t) => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}
                            </SelectContent>
                        </Select>
                        <Input type="date" value={examForm.start_date} onChange={(e) => setExamForm((f) => ({ ...f, start_date: e.target.value }))} />
                        <Input type="date" value={examForm.end_date} onChange={(e) => setExamForm((f) => ({ ...f, end_date: e.target.value }))} />
                    </div>
                    <Button onClick={handleCreateExam} disabled={isCreatingExam || !examForm.name || !examForm.exam_type}>
                        Create
                    </Button>
                </DialogContent>
            </Dialog>

            <Dialog open={scheduleDialogOpen} onOpenChange={setScheduleDialogOpen}>
                <DialogContent>
                    <DialogHeader><DialogTitle>Add Schedule</DialogTitle></DialogHeader>
                    <div className="space-y-3">
                        <Select value={scheduleForm.section} onValueChange={(v) => setScheduleForm((f) => ({ ...f, section: v }))}>
                            <SelectTrigger><SelectValue placeholder="Section" /></SelectTrigger>
                            <SelectContent>{sections?.map((s) => <SelectItem key={s.id} value={s.id}>{s.level_name} - {s.name}</SelectItem>)}</SelectContent>
                        </Select>
                        <Select value={scheduleForm.subject} onValueChange={(v) => setScheduleForm((f) => ({ ...f, subject: v }))}>
                            <SelectTrigger><SelectValue placeholder="Subject" /></SelectTrigger>
                            <SelectContent>{subjects?.map((s: any) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}</SelectContent>
                        </Select>
                        <Input type="date" value={scheduleForm.date} onChange={(e) => setScheduleForm((f) => ({ ...f, date: e.target.value }))} />
                        <div className="grid grid-cols-2 gap-2">
                            <Input type="time" value={scheduleForm.start_time} onChange={(e) => setScheduleForm((f) => ({ ...f, start_time: e.target.value }))} />
                            <Input type="time" value={scheduleForm.end_time} onChange={(e) => setScheduleForm((f) => ({ ...f, end_time: e.target.value }))} />
                        </div>
                        <Select value={scheduleForm.period || "__none__"} onValueChange={(v) => setScheduleForm((f) => ({ ...f, period: v === "__none__" ? "" : v }))}>
                            <SelectTrigger><SelectValue placeholder="Period (optional)" /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="__none__">No period</SelectItem>
                                {periods?.map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
                            </SelectContent>
                        </Select>
                        <Select value={scheduleForm.room || "__none__"} onValueChange={(v) => setScheduleForm((f) => ({ ...f, room: v === "__none__" ? "" : v }))}>
                            <SelectTrigger><SelectValue placeholder="Room (optional)" /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value="__none__">No room</SelectItem>
                                {rooms?.map((r) => <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>)}
                            </SelectContent>
                        </Select>
                        <div className="grid grid-cols-2 gap-2">
                            <Input aria-label="Max marks" type="number" placeholder="Max marks" value={scheduleForm.max_marks} onChange={(e) => setScheduleForm((f) => ({ ...f, max_marks: e.target.value }))} />
                            <Input aria-label="Pass marks" type="number" placeholder="Pass marks" value={scheduleForm.pass_marks} onChange={(e) => setScheduleForm((f) => ({ ...f, pass_marks: e.target.value }))} />
                        </div>
                    </div>
                    <Button onClick={handleCreateSchedule} disabled={isCreatingSchedule || !scheduleForm.subject || !scheduleForm.section}>
                        {isCreatingSchedule && <LoaderCircle className="h-4 w-4 animate-spin mr-2" />}
                        Save Schedule
                    </Button>
                </DialogContent>
            </Dialog>
        </div>
    );
}
