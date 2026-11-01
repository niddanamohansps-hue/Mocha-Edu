"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Printer } from "lucide-react";
import axiosInstance from "@/lib/axios";
import { Button } from "@/components/ui/button";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { useExamSchedules, useExaminations, useScheduleMarks } from "@/hooks/useExaminations";
import { useInstitutionProfile } from "@/hooks/useProfile";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { usePermissions } from "@/providers/PermissionProvider";

const selectClass =
    "h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";
const ATTENDANCE_LABEL: Record<string, string> = {
    absent: "Absent", medical: "Absent (medical)", malpractice: "Malpractice", exempt: "Exempt",
};

export default function MarkSheetsPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("view_examinations")) return <Unauthorized />;
    return <MarkSheetsContent />;
}

function MarkSheetsContent() {
    const { selectedYear } = useAcademicYear();
    const { data: examinations = [] } = useExaminations(selectedYear?.name || undefined);
    const { data: institution } = useInstitutionProfile();
    const [examinationId, setExaminationId] = useState("");
    const [scheduleId, setScheduleId] = useState("");
    const [filled, setFilled] = useState(false);
    const { data: schedules = [] } = useExamSchedules(examinationId || undefined);
    const schedule = schedules.find((s) => s.id === scheduleId);
    const examination = examinations.find((e) => e.id === examinationId);

    const { data: roster, isLoading } = useQuery({
        queryKey: ["examinations", "mark-sheet-roster", scheduleId],
        enabled: !!schedule,
        queryFn: async () =>
            (await axiosInstance.get(`/attendance/sections/${schedule?.section}/roster/`, { params: { date: schedule?.date } }))
                .data.students as { student: string; full_name: string; enrollment_id: string }[],
    });
    const saved = useScheduleMarks(filled && scheduleId ? scheduleId : undefined);
    const savedByStudent = Object.fromEntries((saved.data?.marks ?? []).map((m) => [m.student, m]));
    const parts = schedule?.components ?? [];

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <style jsx global>{`
                @media print {
                    @page { size: A4 portrait; margin: 12mm; }
                    body { background: white !important; color: black !important; }
                    nav, header, aside, .no-print { display: none !important; }
                }
            `}</style>
            <div className="space-y-2 no-print">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Mark sheets</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    Print a blank sheet for a teacher to write marks on, or an award list with the marks already entered.
                </p>
            </div>
            <div className="flex flex-wrap items-center gap-3 no-print">
                <select className={selectClass} value={examinationId} onChange={(e) => { setExaminationId(e.target.value); setScheduleId(""); }}>
                    <option value="">Choose an examination</option>
                    {examinations.map((exam) => <option key={exam.id} value={exam.id}>{exam.name}</option>)}
                </select>
                <select className={selectClass} value={scheduleId} onChange={(e) => setScheduleId(e.target.value)}>
                    <option value="">Choose a paper</option>
                    {schedules.map((s) => <option key={s.id} value={s.id}>{s.section_name} - {s.subject_name} ({s.date})</option>)}
                </select>
                <select className={selectClass} value={filled ? "filled" : "blank"} onChange={(e) => setFilled(e.target.value === "filled")}>
                    <option value="blank">Blank mark sheet</option>
                    <option value="filled">Award list (with marks)</option>
                </select>
                <Button variant="outline" disabled={!roster} onClick={() => window.print()}>
                    <Printer className="mr-2 h-4 w-4" /> Print
                </Button>
            </div>

            {!schedule || !examination ? (
                <EmptyState title="Choose an examination and a paper" description="The sheet will be shown here." />
            ) : isLoading || !roster || (filled && saved.isLoading) ? (
                <LoadingState />
            ) : (
                <article className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 text-slate-900">
                    <div className="border-b-2 border-slate-900 pb-2 text-center">
                        <h2 className="text-lg font-bold uppercase tracking-wide">{institution?.name || "School"}</h2>
                        <p className="text-sm font-semibold">
                            {filled ? "Award list" : "Mark sheet"} - {examination.name}
                        </p>
                    </div>
                    <div className="grid grid-cols-2 gap-x-6 text-sm">
                        <p><span className="text-slate-500">Class: </span><strong>{schedule.section_name}</strong></p>
                        <p><span className="text-slate-500">Subject: </span><strong>{schedule.subject_name}</strong></p>
                        <p><span className="text-slate-500">Date: </span><strong>{schedule.date}</strong></p>
                        <p><span className="text-slate-500">Maximum marks: </span><strong>{Number(schedule.max_marks)}</strong> (pass {Number(schedule.pass_marks)})</p>
                    </div>
                    <table className="w-full border-collapse text-sm">
                        <thead>
                            <tr className="border-b-2 border-slate-900 text-left">
                                <th className="py-1 pr-2">No.</th>
                                <th className="py-1 pr-2">Enrollment no.</th>
                                <th className="py-1 pr-2">Student</th>
                                {parts.length > 0
                                    ? parts.map((p) => <th key={p.id} className="py-1 pr-2 text-center">{p.code} ({Number(p.max_marks)})</th>)
                                    : null}
                                <th className="py-1 pr-2 text-center">{parts.length > 0 ? "Total" : "Marks"} ({Number(schedule.max_marks)})</th>
                                <th className="py-1 text-center">Absent</th>
                            </tr>
                        </thead>
                        <tbody>
                            {roster.map((student, index) => {
                                const mark = savedByStudent[student.student];
                                const status = mark ? ATTENDANCE_LABEL[mark.attendance] : undefined;
                                return (
                                    <tr key={student.student} className="border-b border-slate-300">
                                        <td className="py-1.5 pr-2">{index + 1}</td>
                                        <td className="py-1.5 pr-2">{student.enrollment_id}</td>
                                        <td className="py-1.5 pr-2">{student.full_name}</td>
                                        {parts.map((p) => {
                                            const cm = mark?.component_marks?.find((c) => c.component === p.id);
                                            return (
                                                <td key={p.id} className="h-8 py-1.5 pr-2 text-center">
                                                    {filled && cm?.marks_obtained != null ? Number(cm.marks_obtained) : ""}
                                                </td>
                                            );
                                        })}
                                        <td className="h-8 py-1.5 pr-2 text-center font-medium">
                                            {filled ? (status ?? (mark?.marks_obtained != null ? Number(mark.marks_obtained) : "")) : ""}
                                        </td>
                                        <td className="py-1.5 text-center">{filled ? (status ? "Yes" : "") : "[  ]"}</td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                    <div className="grid grid-cols-3 gap-6 pt-8 text-xs">
                        <span className="border-t border-slate-900 pt-1">Subject teacher</span>
                        <span className="border-t border-slate-900 pt-1">Checked by</span>
                        <span className="border-t border-slate-900 pt-1">Date</span>
                    </div>
                </article>
            )}
        </div>
    );
}
