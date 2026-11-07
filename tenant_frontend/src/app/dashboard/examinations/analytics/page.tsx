"use client";

import { useState } from "react";
import { Download, Printer } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { useAcademicLevels, useSections } from "@/hooks/useAcademics";
import { useExaminations } from "@/hooks/useExaminations";
import { useExamAnalytics, useExamComparison, useWeakStudents } from "@/hooks/useExamAllocation";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { usePermissions } from "@/providers/PermissionProvider";
import { downloadCsv } from "@/lib/csv";

const selectClass =
    "h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "-" : `${v}%`);

export default function ExamAnalyticsPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("view_exam_reports")) return <Unauthorized />;
    return <AnalyticsContent />;
}

function AnalyticsContent() {
    const { selectedYear } = useAcademicYear();
    const { data: examinations = [] } = useExaminations(selectedYear?.name || undefined);
    const { data: sections = [] } = useSections();
    const { data: levels = [] } = useAcademicLevels();
    const [examinationId, setExaminationId] = useState("");
    const [otherId, setOtherId] = useState("");
    const [scope, setScope] = useState<"section" | "level">("level");
    const [target, setTarget] = useState("");
    const [margin, setMargin] = useState("5");
    const examination = examinations.find((e) => e.id === examinationId);
    const published = !!examination?.is_published;
    const other = examinations.find((e) => e.id === otherId);

    const analytics = useExamAnalytics(examinationId || undefined, scope, target || undefined, published);
    const comparison = useExamComparison(examinationId || undefined, otherId || undefined, scope, target || undefined, published && !!other?.is_published);
    const weak = useWeakStudents(examinationId || undefined, scope, target || undefined, Number(margin) || 5, published);

    return (
        <div className="max-w-5xl mx-auto space-y-6">
            <style jsx global>{`
                @media print {
                    @page { size: A4 landscape; margin: 10mm; }
                    body { background: white !important; color: black !important; }
                    nav, header, aside, .no-print { display: none !important; }
                }
            `}</style>
            <div className="space-y-2 no-print">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Exam analytics</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    How a class or section did, subject by subject, and who needs help. Figures come from the published results,
                    and a subject counts as passed using that paper&apos;s own pass mark.
                </p>
            </div>

            <div className="flex flex-wrap items-center gap-3 no-print">
                <select className={selectClass} value={examinationId} onChange={(e) => setExaminationId(e.target.value)}>
                    <option value="">Choose an examination</option>
                    {examinations.map((exam) => <option key={exam.id} value={exam.id}>{exam.name}</option>)}
                </select>
                <select className={selectClass} value={scope} onChange={(e) => { setScope(e.target.value as "section" | "level"); setTarget(""); }}>
                    <option value="level">Whole class</option>
                    <option value="section">One section</option>
                </select>
                <select className={selectClass} value={target} onChange={(e) => setTarget(e.target.value)}>
                    <option value="">{scope === "section" ? "Choose a section" : "Choose a class"}</option>
                    {scope === "section"
                        ? sections.map((s) => <option key={s.id} value={s.id}>{s.level_name} - {s.name}</option>)
                        : levels.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
                </select>
            </div>

            {!examinationId || !target ? (
                <EmptyState title="Choose an examination and a class" description="The analysis will be shown here." />
            ) : !published ? (
                <EmptyState title="Results not published yet" description="Analytics are available once the results are published." />
            ) : (
                <Tabs defaultValue="overview">
                    <TabsList className="no-print">
                        <TabsTrigger value="overview">Overview</TabsTrigger>
                        <TabsTrigger value="compare">Compare two exams</TabsTrigger>
                        <TabsTrigger value="weak">Students who need help</TabsTrigger>
                    </TabsList>

                    <TabsContent value="overview" className="space-y-6">
                        {analytics.isLoading || !analytics.data ? <LoadingState /> : analytics.data.overall.students === 0 ? (
                            <EmptyState title="No results" description="There are no published results for this class." />
                        ) : (
                            <Overview data={analytics.data} />
                        )}
                    </TabsContent>

                    <TabsContent value="compare" className="space-y-4">
                        <div className="flex items-center gap-3 no-print">
                            <Label>Compare with</Label>
                            <select className={selectClass} value={otherId} onChange={(e) => setOtherId(e.target.value)}>
                                <option value="">Choose another examination</option>
                                {examinations.filter((e) => e.id !== examinationId && e.is_published).map((exam) => (
                                    <option key={exam.id} value={exam.id}>{exam.name}</option>
                                ))}
                            </select>
                        </div>
                        {!otherId ? (
                            <EmptyState title="Choose a second examination" description="Only published examinations can be compared." />
                        ) : comparison.isLoading || !comparison.data ? <LoadingState /> : (
                            <Comparison data={comparison.data} />
                        )}
                    </TabsContent>

                    <TabsContent value="weak" className="space-y-4">
                        <div className="flex flex-wrap items-end gap-3 no-print">
                            <div className="grid gap-1.5">
                                <Label>Also list passes within (percentage points of the pass mark)</Label>
                                <Input className="w-28" type="number" min={0} max={30} value={margin} onChange={(e) => setMargin(e.target.value)} />
                            </div>
                            <Button variant="outline" disabled={!weak.data} onClick={() => window.print()}>
                                <Printer className="mr-2 h-4 w-4" /> Print
                            </Button>
                            <Button
                                variant="outline"
                                disabled={!weak.data}
                                onClick={() => weak.data && downloadCsv("students-who-need-help.csv", [
                                    ["Student", "Enrollment no.", "Class", "Overall %", "Attendance %", "Weak subjects"],
                                    ...weak.data.rows.map((r) => [
                                        r.name, r.enrollment_id, r.class, r.percentage, r.attendance_percentage,
                                        r.weak_subjects.map((w) => `${w.subject} (${w.status}${w.percentage !== null ? ` ${w.percentage}%` : ""})`).join("; "),
                                    ]),
                                ])}
                            >
                                <Download className="mr-2 h-4 w-4" /> Export CSV
                            </Button>
                        </div>
                        {weak.isLoading || !weak.data ? <LoadingState /> : weak.data.rows.length === 0 ? (
                            <EmptyState title="Nobody to list" description="Every student passed every paper by a safe margin." />
                        ) : (
                            <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800">
                                <table className="w-full text-sm">
                                    <thead className="bg-slate-50 dark:bg-slate-900">
                                        <tr className="text-left text-xs font-semibold uppercase text-slate-500">
                                            <th className="px-4 py-3">Student</th>
                                            <th className="px-4 py-3">Class</th>
                                            <th className="px-4 py-3">Overall</th>
                                            <th className="px-4 py-3">Attendance</th>
                                            <th className="px-4 py-3">Weak subjects</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {weak.data.rows.map((row) => (
                                            <tr key={row.student_id} className="border-t border-slate-100 dark:border-slate-800">
                                                <td className="px-4 py-2"><span className="font-medium">{row.name}</span> <span className="text-xs text-slate-400">{row.enrollment_id}</span></td>
                                                <td className="px-4 py-2">{row.class}</td>
                                                <td className="px-4 py-2">{pct(row.percentage)}</td>
                                                <td className="px-4 py-2">{pct(row.attendance_percentage)}</td>
                                                <td className="px-4 py-2">
                                                    <span className="flex flex-wrap gap-1.5">
                                                        {row.weak_subjects.map((w) => (
                                                            <Badge key={w.subject} variant={w.status === "failed" ? "destructive" : "outline"}>
                                                                {w.subject}: {w.status}{w.percentage !== null ? ` ${w.percentage}%` : ""}
                                                            </Badge>
                                                        ))}
                                                    </span>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </TabsContent>
                </Tabs>
            )}
        </div>
    );
}

function Tile({ label, value, tone }: { label: string; value: string | number; tone?: "good" | "bad" }) {
    const color = tone === "good" ? "text-emerald-600" : tone === "bad" ? "text-red-600" : "text-slate-900 dark:text-white";
    return (
        <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
            <div className={`text-2xl font-bold ${color}`}>{value}</div>
            <div className="text-xs text-slate-500">{label}</div>
        </div>
    );
}

function Overview({ data }: { data: import("@/types/ExamAllocation").ExamAnalytics }) {
    const o = data.overall;
    const widest = Math.max(1, ...data.distribution.map((b) => b.count));
    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between gap-3">
                <h2 className="text-xl font-semibold">{data.examination.name} - {data.title}</h2>
                <div className="flex gap-2 no-print">
                    <Button variant="outline" size="sm" onClick={() => window.print()}><Printer className="mr-2 h-4 w-4" /> Print</Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => downloadCsv("exam-analytics.csv", [
                            ["Subject", "Appeared", "Absent", "Passed", "Pass %", "Average %", "Highest %", "Lowest %"],
                            ...data.subjects.map((s) => [s.subject, s.appeared, s.absent, s.passed, s.pass_percentage, s.average_percentage, s.highest_percentage, s.lowest_percentage]),
                        ])}
                    >
                        <Download className="mr-2 h-4 w-4" /> Export CSV
                    </Button>
                </div>
            </div>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                <Tile label="Students" value={o.students} />
                <Tile label="Pass percentage" value={pct(o.pass_percentage)} tone={(o.pass_percentage ?? 0) >= 75 ? "good" : undefined} />
                <Tile label="Average" value={pct(o.average_percentage)} />
                <Tile label="Highest" value={pct(o.highest_percentage)} tone="good" />
                <Tile label="Lowest" value={pct(o.lowest_percentage)} tone={o.failed > 0 ? "bad" : undefined} />
            </div>

            <section className="space-y-2">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">How the marks are spread</h3>
                {data.distribution.map((band) => (
                    <div key={band.label} className="flex items-center gap-3 text-sm">
                        <span className="w-28 text-slate-600 dark:text-slate-300">{band.label}</span>
                        <div className="h-4 flex-1 overflow-hidden rounded bg-slate-100 dark:bg-slate-800">
                            <div className="h-full bg-indigo-500" style={{ width: `${(band.count / widest) * 100}%` }} />
                        </div>
                        <span className="w-10 text-right font-medium">{band.count}</span>
                    </div>
                ))}
            </section>

            <section className="space-y-2">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Subjects, weakest first</h3>
                <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800">
                    <table className="w-full text-sm">
                        <thead className="bg-slate-50 dark:bg-slate-900">
                            <tr className="text-left text-xs font-semibold uppercase text-slate-500">
                                <th className="px-4 py-3">Subject</th>
                                <th className="px-4 py-3">Appeared</th>
                                <th className="px-4 py-3">Passed</th>
                                <th className="px-4 py-3">Average</th>
                                <th className="px-4 py-3">Highest</th>
                                <th className="px-4 py-3">Lowest</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.subjects.map((s) => (
                                <tr key={s.subject_id} className="border-t border-slate-100 dark:border-slate-800">
                                    <td className="px-4 py-2 font-medium">{s.subject}{s.absent > 0 && <span className="ml-2 text-xs text-slate-400">{s.absent} absent</span>}</td>
                                    <td className="px-4 py-2">{s.appeared}</td>
                                    <td className="px-4 py-2">{s.passed} ({pct(s.pass_percentage)})</td>
                                    <td className="px-4 py-2">{pct(s.average_percentage)}</td>
                                    <td className="px-4 py-2">{pct(s.highest_percentage)}</td>
                                    <td className="px-4 py-2">{pct(s.lowest_percentage)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>

            {data.sections.length > 1 && (
                <section className="space-y-2">
                    <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Sections</h3>
                    <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800">
                        <table className="w-full text-sm">
                            <thead className="bg-slate-50 dark:bg-slate-900">
                                <tr className="text-left text-xs font-semibold uppercase text-slate-500">
                                    <th className="px-4 py-3">Section</th>
                                    <th className="px-4 py-3">Students</th>
                                    <th className="px-4 py-3">Passed</th>
                                    <th className="px-4 py-3">Average</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.sections.map((s) => (
                                    <tr key={s.section} className="border-t border-slate-100 dark:border-slate-800">
                                        <td className="px-4 py-2 font-medium">{s.section}</td>
                                        <td className="px-4 py-2">{s.students}</td>
                                        <td className="px-4 py-2">{s.passed} ({pct(s.pass_percentage)})</td>
                                        <td className="px-4 py-2">{pct(s.average_percentage)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>
            )}
        </div>
    );
}

function Comparison({ data }: { data: import("@/types/ExamAllocation").ExamComparison }) {
    return (
        <div className="space-y-4">
            <h2 className="text-xl font-semibold">{data.first.name} and {data.second.name} - {data.title}</h2>
            <div className="grid grid-cols-2 gap-3">
                {[data.first, data.second].map((side) => (
                    <div key={side.name} className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
                        <div className="text-sm font-semibold">{side.name}</div>
                        <div className="text-xs text-slate-500">{side.students} students</div>
                        <div className="mt-2 text-sm">Pass {pct(side.pass_percentage)} - average {pct(side.average_percentage)}</div>
                    </div>
                ))}
            </div>
            <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800">
                <table className="w-full text-sm">
                    <thead className="bg-slate-50 dark:bg-slate-900">
                        <tr className="text-left text-xs font-semibold uppercase text-slate-500">
                            <th className="px-4 py-3">Subject</th>
                            <th className="px-4 py-3">{data.first.name}</th>
                            <th className="px-4 py-3">{data.second.name}</th>
                            <th className="px-4 py-3">Change</th>
                        </tr>
                    </thead>
                    <tbody>
                        {data.subjects.map((row) => (
                            <tr key={row.subject} className="border-t border-slate-100 dark:border-slate-800">
                                <td className="px-4 py-2 font-medium">{row.subject}</td>
                                <td className="px-4 py-2">{pct(row.first_average)}</td>
                                <td className="px-4 py-2">{pct(row.second_average)}</td>
                                <td className={`px-4 py-2 font-medium ${row.change === null ? "" : row.change > 0 ? "text-emerald-600" : row.change < 0 ? "text-red-600" : ""}`}>
                                    {row.change === null ? "-" : `${row.change > 0 ? "+" : ""}${row.change}`}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
