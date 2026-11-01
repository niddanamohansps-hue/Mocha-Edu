"use client";

import { useState } from "react";
import { Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { useAcademicLevels, useSections } from "@/hooks/useAcademics";
import { useExaminations } from "@/hooks/useExaminations";
import { useRankList } from "@/hooks/useExamAllocation";
import { useInstitutionProfile } from "@/hooks/useProfile";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { usePermissions } from "@/providers/PermissionProvider";

const selectClass =
    "h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";

export default function RankListPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("view_results")) return <Unauthorized />;
    return <RankListContent />;
}

function RankListContent() {
    const { selectedYear } = useAcademicYear();
    const { data: examinations = [] } = useExaminations(selectedYear?.name || undefined);
    const { data: sections = [] } = useSections();
    const { data: levels = [] } = useAcademicLevels();
    const { data: institution } = useInstitutionProfile();
    const [examinationId, setExaminationId] = useState("");
    const [scope, setScope] = useState<"section" | "level">("section");
    const [target, setTarget] = useState("");
    const [includeFailed, setIncludeFailed] = useState(false);
    const examination = examinations.find((e) => e.id === examinationId);
    const published = !!examination?.is_published;
    const { data, isLoading } = useRankList(examinationId || undefined, scope, target || undefined, includeFailed, published);

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
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Rank list</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    Students ranked by their published result. Students on the same percentage share a rank. Students who did
                    not pass are listed after the ranked ones unless you choose to rank them too.
                </p>
            </div>
            <div className="flex flex-wrap items-center gap-3 no-print">
                <select className={selectClass} value={examinationId} onChange={(e) => setExaminationId(e.target.value)}>
                    <option value="">Choose an examination</option>
                    {examinations.map((exam) => <option key={exam.id} value={exam.id}>{exam.name}</option>)}
                </select>
                <select className={selectClass} value={scope} onChange={(e) => { setScope(e.target.value as "section" | "level"); setTarget(""); }}>
                    <option value="section">One section</option>
                    <option value="level">Whole class</option>
                </select>
                <select className={selectClass} value={target} onChange={(e) => setTarget(e.target.value)}>
                    <option value="">{scope === "section" ? "Choose a section" : "Choose a class"}</option>
                    {scope === "section"
                        ? sections.map((s) => <option key={s.id} value={s.id}>{s.level_name} - {s.name}</option>)
                        : levels.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
                </select>
                <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={includeFailed} onChange={(e) => setIncludeFailed(e.target.checked)} />
                    Rank everyone
                </label>
                <Button variant="outline" disabled={!data} onClick={() => window.print()}>
                    <Printer className="mr-2 h-4 w-4" /> Print
                </Button>
            </div>

            {!examinationId || !target ? (
                <EmptyState title="Choose an examination and a class" description="The ranking will be shown here." />
            ) : !published ? (
                <EmptyState title="Results not published yet" description="A rank list is available once the results are published." />
            ) : isLoading || !data ? (
                <LoadingState />
            ) : data.rows.length === 0 ? (
                <EmptyState title="No results" description="There are no published results for this class." />
            ) : (
                <article className="space-y-5 rounded-xl border border-slate-200 bg-white p-6 text-slate-900">
                    <div className="border-b-2 border-slate-900 pb-2 text-center">
                        <h2 className="text-lg font-bold uppercase tracking-wide">{institution?.name || "School"}</h2>
                        <p className="text-sm font-semibold">
                            Merit list - {data.examination.name} - {data.title}
                        </p>
                    </div>
                    {data.toppers.length > 0 && (
                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                            {data.toppers.map((t) => (
                                <div key={t.student_id} className="rounded-lg border border-slate-300 p-3 text-center">
                                    <div className="text-2xl font-bold">{t.rank}</div>
                                    <div className="font-medium">{t.name}</div>
                                    <div className="text-xs text-slate-500">{t.class} - {Number(t.percentage)}%</div>
                                </div>
                            ))}
                        </div>
                    )}
                    <table className="w-full border-collapse text-sm">
                        <thead>
                            <tr className="border-b-2 border-slate-900 text-left">
                                <th className="py-1 pr-2">Rank</th>
                                <th className="py-1 pr-2">Student</th>
                                <th className="py-1 pr-2">Enrollment no.</th>
                                <th className="py-1 pr-2">Class</th>
                                <th className="py-1 pr-2 text-right">Marks</th>
                                <th className="py-1 pr-2 text-right">%</th>
                                <th className="py-1">Grade</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.rows.map((row) => (
                                <tr key={row.student_id} className="border-b border-slate-300">
                                    <td className="py-1.5 pr-2 font-semibold">{row.rank ?? "-"}</td>
                                    <td className="py-1.5 pr-2">{row.name}{!row.is_pass && <span className="ml-2 text-xs text-red-600">did not pass</span>}</td>
                                    <td className="py-1.5 pr-2">{row.enrollment_id}</td>
                                    <td className="py-1.5 pr-2">{row.class}</td>
                                    <td className="py-1.5 pr-2 text-right">{Number(row.total_marks)}/{Number(row.max_marks)}</td>
                                    <td className="py-1.5 pr-2 text-right">{Number(row.percentage)}</td>
                                    <td className="py-1.5">{row.grade}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </article>
            )}
        </div>
    );
}
