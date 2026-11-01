"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { useSections } from "@/hooks/useAcademics";
import {
    useBulkSubmitCoScholasticGrades,
    useCoScholasticActivities,
    useCoScholasticGrades,
    useCreateCoScholasticActivity,
    useExaminations,
} from "@/hooks/useExaminations";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { usePermissions } from "@/providers/PermissionProvider";

const GRADES = ["A", "B", "C", "D", "E"];
const selectClass =
    "h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";

export default function CoScholasticPage() {
    const { can, isOwner } = usePermissions();
    const canSetUp = isOwner || can("manage_examinations");
    const canEnter = isOwner || can("enter_marks");
    if (!canSetUp && !canEnter && !can("view_examinations")) return <Unauthorized />;
    return <CoScholasticContent canSetUp={canSetUp} canEnter={canEnter} />;
}

function CoScholasticContent({ canSetUp, canEnter }: { canSetUp: boolean; canEnter: boolean }) {
    return (
        <div className="max-w-5xl mx-auto space-y-6">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Co-scholastic grades</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    Grades for areas that are not marked out of a number, such as art, work education, sports and discipline.
                    They appear on the report card.
                </p>
            </div>
            <Tabs defaultValue="grades">
                <TabsList>
                    <TabsTrigger value="grades">Enter grades</TabsTrigger>
                    <TabsTrigger value="activities">Activities</TabsTrigger>
                </TabsList>
                <TabsContent value="grades"><GradeEntry canEnter={canEnter} /></TabsContent>
                <TabsContent value="activities"><Activities canSetUp={canSetUp} /></TabsContent>
            </Tabs>
        </div>
    );
}

function Activities({ canSetUp }: { canSetUp: boolean }) {
    const { data: activities = [], isLoading } = useCoScholasticActivities();
    const create = useCreateCoScholasticActivity();
    const [name, setName] = useState("");
    const [code, setCode] = useState("");
    return (
        <section className="space-y-4 pt-4">
            {isLoading ? <LoadingState /> : activities.length === 0 ? (
                <EmptyState title="No activities yet" description="Add the areas your board asks you to grade." />
            ) : (
                <div className="space-y-2">
                    {activities.map((a) => (
                        <div key={a.id} className="rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-800">
                            <span className="font-medium">{a.name}</span>
                            {a.code && <span className="ml-2 text-slate-500">({a.code})</span>}
                        </div>
                    ))}
                </div>
            )}
            {canSetUp && (
                <div className="flex flex-wrap items-end gap-3 border-t border-slate-200 pt-4 dark:border-slate-800">
                    <div className="grid gap-1.5">
                        <Label>Activity</Label>
                        <Input placeholder="Art Education" value={name} onChange={(e) => setName(e.target.value)} />
                    </div>
                    <div className="grid gap-1.5">
                        <Label>Short code (optional)</Label>
                        <Input className="w-32" value={code} onChange={(e) => setCode(e.target.value)} />
                    </div>
                    <Button
                        disabled={create.isPending || !name.trim()}
                        onClick={() =>
                            create.mutate(
                                { name: name.trim(), code: code.trim(), order: activities.length + 1, is_active: true },
                                { onSuccess: () => { setName(""); setCode(""); } },
                            )
                        }
                    >
                        Add activity
                    </Button>
                </div>
            )}
        </section>
    );
}

function GradeEntry({ canEnter }: { canEnter: boolean }) {
    const { selectedYear } = useAcademicYear();
    const { data: examinations = [] } = useExaminations(selectedYear?.name || undefined);
    const { data: sections = [] } = useSections();
    const { data: activities = [] } = useCoScholasticActivities();
    const [examinationId, setExaminationId] = useState("");
    const [sectionId, setSectionId] = useState("");
    const examination = examinations.find((e) => e.id === examinationId);
    const active = activities.filter((a) => a.is_active);

    const { data: roster, isLoading } = useQuery({
        queryKey: ["examinations", "co-scholastic", "roster", sectionId, examination?.end_date],
        enabled: !!sectionId && !!examination,
        queryFn: async () =>
            (await axiosInstance.get(`/attendance/sections/${sectionId}/roster/`, { params: { date: examination?.end_date } }))
                .data.students as { student: string; full_name: string; enrollment_id: string }[],
    });
    const saved = useCoScholasticGrades(examinationId || undefined);
    const submit = useBulkSubmitCoScholasticGrades();

    // "student|activity" -> grade letter: what is saved, with the teacher's unsaved changes on top.
    const [edits, setEdits] = useState<Record<string, string>>({});
    const grades = useMemo(() => {
        const base: Record<string, string> = {};
        for (const g of saved.data ?? []) base[`${g.student}|${g.activity}`] = g.grade;
        return { ...base, ...edits };
    }, [saved.data, edits]);

    const records = useMemo(
        () =>
            Object.entries(grades)
                .filter(([, grade]) => grade !== "")
                .map(([key, grade]) => {
                    const [student, activity] = key.split("|");
                    return { student, activity, grade };
                })
                .filter((r) => roster?.some((s) => s.student === r.student)),
        [grades, roster],
    );

    return (
        <section className="space-y-4 pt-4">
            <div className="flex flex-wrap gap-3">
                <select className={selectClass} value={examinationId} onChange={(e) => { setExaminationId(e.target.value); setEdits({}); }}>
                    <option value="">Choose an examination</option>
                    {examinations.map((exam) => <option key={exam.id} value={exam.id}>{exam.name}</option>)}
                </select>
                <select className={selectClass} value={sectionId} onChange={(e) => setSectionId(e.target.value)}>
                    <option value="">Choose a class and section</option>
                    {sections.map((s) => <option key={s.id} value={s.id}>{s.level_name} - {s.name}</option>)}
                </select>
            </div>

            {active.length === 0 ? (
                <EmptyState title="Add activities first" description="Use the Activities tab." />
            ) : !examinationId || !sectionId ? (
                <EmptyState title="Choose an examination and a section" description="Its students will be listed here." />
            ) : isLoading || !roster ? (
                <LoadingState />
            ) : (
                <>
                    <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800">
                        <table className="w-full text-sm">
                            <thead className="bg-slate-50 dark:bg-slate-900">
                                <tr className="text-left text-xs font-semibold uppercase text-slate-500">
                                    <th className="px-4 py-3">Student</th>
                                    {active.map((a) => <th key={a.id} className="px-4 py-3">{a.name}</th>)}
                                </tr>
                            </thead>
                            <tbody>
                                {roster.map((student) => (
                                    <tr key={student.student} className="border-t border-slate-100 dark:border-slate-800">
                                        <td className="px-4 py-2">
                                            <span className="font-medium">{student.full_name}</span>{" "}
                                            <span className="text-xs text-slate-400">{student.enrollment_id}</span>
                                        </td>
                                        {active.map((a) => (
                                            <td key={a.id} className="px-4 py-2">
                                                <select
                                                    disabled={!canEnter}
                                                    className="h-9 w-20 rounded-md border border-slate-200 bg-white px-2 text-sm dark:border-slate-800 dark:bg-slate-950"
                                                    value={grades[`${student.student}|${a.id}`] ?? ""}
                                                    onChange={(e) => setEdits((g) => ({ ...g, [`${student.student}|${a.id}`]: e.target.value }))}
                                                >
                                                    <option value="">-</option>
                                                    {GRADES.map((g) => <option key={g} value={g}>{g}</option>)}
                                                </select>
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    {canEnter && (
                        <Button
                            disabled={submit.isPending || records.length === 0}
                            onClick={() => submit.mutate({ examination: examinationId, records }, { onSuccess: () => setEdits({}) })}
                        >
                            {submit.isPending ? "Saving..." : `Save ${records.length} grades`}
                        </Button>
                    )}
                </>
            )}
        </section>
    );
}
