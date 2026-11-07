"use client";

import React from "react";
import { Printer, School, User, Calendar, Award, CheckCircle2, XCircle, AlertCircle, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/common/StatusBadge";
import type { ReportCard } from "@/types/Examinations";

interface PrintableReportCardProps {
    reportCard: ReportCard;
    onViewTranscript?: () => void;
}

export const PrintableReportCard: React.FC<PrintableReportCardProps> = ({
    reportCard,
    onViewTranscript,
}) => {
    const {
        institution,
        student,
        academic_year,
        examinations = [],
        summary,
        attendance,
        promotion,
        remarks = [],
        generated_at,
    } = reportCard;

    const handlePrint = () => {
        window.print();
    };

    return (
        <div className="space-y-6">
            {/* Action Bar (hidden when printing) */}
            <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-slate-50 dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 print:hidden">
                <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-600 dark:text-slate-300">
                        Academic Year: <strong className="text-slate-900 dark:text-white">{academic_year || "Current"}</strong>
                    </span>
                    <span className="text-slate-300 dark:text-slate-700">|</span>
                    <span className="text-sm font-medium text-slate-600 dark:text-slate-300">
                        Student: <strong className="text-slate-900 dark:text-white">{student.full_name}</strong> ({student.enrollment_id})
                    </span>
                </div>
                <div className="flex items-center gap-3">
                    {onViewTranscript && (
                        <Button variant="outline" size="sm" onClick={onViewTranscript}>
                            View Full Transcript
                        </Button>
                    )}
                    <Button onClick={handlePrint} size="sm" className="bg-indigo-600 hover:bg-indigo-700 text-white gap-2">
                        <Printer className="h-4 w-4" />
                        Print / Save as PDF
                    </Button>
                </div>
            </div>

            {/* Printable Document Container */}
            <div className="print-document bg-white text-slate-900 p-8 sm:p-12 border border-slate-200 shadow-lg rounded-2xl print:border-none print:shadow-none print:p-0 print:m-0 print:rounded-none max-w-[210mm] mx-auto">
                <style jsx global>{`
                    @media print {
                        @page {
                            size: A4 portrait;
                            margin: 12mm 15mm;
                        }
                        body {
                            -webkit-print-color-adjust: exact !important;
                            print-color-adjust: exact !important;
                            background: white !important;
                            color: black !important;
                        }
                        .print-hidden, nav, header, aside, .no-print {
                            display: none !important;
                        }
                        .print-document {
                            border: none !important;
                            box-shadow: none !important;
                            padding: 0 !important;
                            margin: 0 !important;
                            max-width: 100% !important;
                        }
                        .page-break {
                            page-break-after: always;
                        }
                    }
                `}</style>

                {/* Header: School Identity */}
                <div className="border-b-2 border-slate-900 pb-5 mb-6 text-center relative">
                    {institution?.logo_url ? (
                        <div className="mb-2 flex justify-center">
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img src={institution.logo_url} alt={institution.name} className="h-16 w-auto object-contain" />
                        </div>
                    ) : (
                        <div className="flex justify-center mb-2">
                            <div className="p-2 bg-indigo-50 text-indigo-700 rounded-full">
                                <School className="h-8 w-8" />
                            </div>
                        </div>
                    )}
                    <h1 className="text-2xl font-black uppercase tracking-wider text-slate-950">
                        {institution?.name || "EduSekai Academy"}
                    </h1>
                    {institution?.tagline && (
                        <p className="text-xs italic text-slate-600 mt-0.5">{institution.tagline}</p>
                    )}
                    <div className="flex flex-wrap justify-center items-center gap-x-4 gap-y-1 text-xs text-slate-600 mt-2">
                        {institution?.address && <span>{institution.address}</span>}
                        {institution?.phone && <span>Tel: {institution.phone}</span>}
                        {institution?.email && <span>Email: {institution.email}</span>}
                        {institution?.website && <span>{institution.website}</span>}
                    </div>

                    <div className="mt-4 pt-3 border-t border-slate-200 flex items-center justify-between">
                        <span className="text-xs font-bold uppercase tracking-widest text-indigo-800 bg-indigo-50 px-3 py-1 rounded">
                            Official Student Report Card
                        </span>
                        <span className="text-xs font-semibold text-slate-600">
                            Academic Year: <strong className="text-slate-900">{academic_year || "—"}</strong>
                        </span>
                    </div>
                </div>

                {/* Student Info Card */}
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 mb-6 text-sm">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-y-3 gap-x-4">
                        <div>
                            <span className="text-xs text-slate-500 uppercase block font-semibold">Student Name</span>
                            <span className="font-bold text-slate-900">{student.full_name}</span>
                        </div>
                        <div>
                            <span className="text-xs text-slate-500 uppercase block font-semibold">Enrollment ID</span>
                            <span className="font-semibold text-slate-800">{student.enrollment_id}</span>
                        </div>
                        <div>
                            <span className="text-xs text-slate-500 uppercase block font-semibold">Grade / Level</span>
                            <span className="font-semibold text-slate-800">{student.level || "—"}</span>
                        </div>
                        <div>
                            <span className="text-xs text-slate-500 uppercase block font-semibold">Section</span>
                            <span className="font-semibold text-slate-800">{student.section || "—"}</span>
                        </div>
                        <div>
                            <span className="text-xs text-slate-500 uppercase block font-semibold">Date of Birth</span>
                            <span className="text-slate-800">{student.date_of_birth || "—"}</span>
                        </div>
                        <div>
                            <span className="text-xs text-slate-500 uppercase block font-semibold">Gender</span>
                            <span className="capitalize text-slate-800">{student.gender || "—"}</span>
                        </div>
                        <div>
                            <span className="text-xs text-slate-500 uppercase block font-semibold">Attendance</span>
                            <span className="font-semibold text-slate-900">
                                {attendance?.percentage !== null && attendance?.percentage !== undefined
                                    ? `${attendance.percentage}% (${attendance.present_days}/${attendance.total_days} days)`
                                    : "Not Recorded"}
                            </span>
                        </div>
                        <div>
                            <span className="text-xs text-slate-500 uppercase block font-semibold">Enrollment Status</span>
                            <span className="capitalize font-semibold text-slate-800">{student.status || "Active"}</span>
                        </div>
                    </div>
                </div>

                {/* Examination Results */}
                {examinations.length === 0 ? (
                    <div className="text-center py-10 border border-dashed border-slate-300 rounded-xl my-6">
                        <AlertCircle className="h-8 w-8 text-amber-500 mx-auto mb-2" />
                        <p className="font-medium text-slate-700">No published examination results found for this academic year.</p>
                        <p className="text-xs text-slate-500 mt-1">Results will appear here once officially published by the administration.</p>
                    </div>
                ) : (
                    <div className="space-y-6">
                        {examinations.map((exam, idx) => (
                            <div key={exam.id || idx} className="border border-slate-300 rounded-xl overflow-hidden">
                                <div className="bg-slate-100 px-4 py-2.5 border-b border-slate-300 flex items-center justify-between">
                                    <div>
                                        <h3 className="font-bold text-slate-900 text-sm tracking-wide">
                                            {exam.examination_name}
                                        </h3>
                                        {exam.exam_type && (
                                            <span className="text-xs text-slate-500 font-medium">Type: {exam.exam_type}</span>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-3">
                                        {reportCard.ranks?.[exam.examination] && (
                                            <span className="text-xs font-bold bg-amber-100 text-amber-800 px-2.5 py-0.5 rounded">
                                                Rank {reportCard.ranks[exam.examination].rank} of {reportCard.ranks[exam.examination].of}
                                            </span>
                                        )}
                                        {exam.gpa !== null && exam.gpa !== undefined && (
                                            <span className="text-xs font-bold bg-indigo-100 text-indigo-800 px-2.5 py-0.5 rounded">
                                                GPA: {exam.gpa.toFixed(2)}
                                            </span>
                                        )}
                                        <span className={`text-xs font-bold px-2.5 py-0.5 rounded ${exam.is_pass ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"}`}>
                                            {exam.is_pass ? "PASSED" : "FAILED"}
                                        </span>
                                    </div>
                                </div>

                                <div className="w-full overflow-x-auto"><table className="w-full text-xs text-left">
                                    <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider">
                                        <tr>
                                            <th className="py-2 px-3">#</th>
                                            <th className="py-2 px-3">Subject</th>
                                            <th className="py-2 px-3 text-center">Credits</th>
                                            <th className="py-2 px-3 text-right">Max Marks</th>
                                            <th className="py-2 px-3 text-right">Obtained</th>
                                            <th className="py-2 px-3 text-right">Percentage</th>
                                            <th className="py-2 px-3 text-center">Grade</th>
                                            {exam.gpa !== null && <th className="py-2 px-3 text-center">Grade Point</th>}
                                            <th className="py-2 px-3 text-center">Status</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-200">
                                        {exam.subject_breakdown.map((sub, sIdx) => (
                                            <tr key={sub.subject || sIdx} className={sIdx % 2 === 1 ? "bg-slate-50/50" : ""}>
                                                <td className="py-2 px-3 text-slate-400">{sIdx + 1}</td>
                                                <td className="py-2 px-3 font-semibold text-slate-900">
                                                    <div>{sub.subject_name}</div>
                                                    {sub.components && sub.components.length > 0 && (
                                                        <div className="flex flex-wrap gap-1.5 mt-1 text-[11px] font-normal text-slate-600">
                                                            {sub.components.map((c, cIdx) => (
                                                                <span
                                                                    key={c.component_id || cIdx}
                                                                    className={`inline-flex items-center px-1.5 py-0.5 rounded border ${
                                                                        c.requires_separate_pass && !c.is_pass
                                                                            ? "bg-red-50 text-red-700 border-red-200"
                                                                            : "bg-slate-100 text-slate-700 border-slate-200"
                                                                    }`}
                                                                >
                                                                    <span className="font-semibold mr-1">{c.code}:</span>
                                                                    {c.is_absent ? (
                                                                        <span className="text-red-600 font-semibold">Ab</span>
                                                                    ) : (
                                                                        <span>
                                                                            {c.marks_obtained !== null ? c.marks_obtained : "—"}/{c.max_marks}
                                                                        </span>
                                                                    )}
                                                                    {c.requires_separate_pass && !c.is_pass && (
                                                                        <span className="ml-1 text-[9px] uppercase font-bold text-red-600">
                                                                            (Fail)
                                                                        </span>
                                                                    )}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    )}
                                                </td>
                                                <td className="py-2 px-3 text-center text-slate-600">{sub.credits ?? 1.0}</td>
                                                <td className="py-2 px-3 text-right text-slate-600">{sub.max_marks}</td>
                                                <td className="py-2 px-3 text-right font-medium text-slate-900">
                                                    {sub.is_absent ? (
                                                        <span className="text-red-600 font-semibold">Absent</span>
                                                    ) : sub.marks_obtained === null ? (
                                                        <span className="text-slate-400">—</span>
                                                    ) : (
                                                        sub.marks_obtained
                                                    )}
                                                </td>
                                                <td className="py-2 px-3 text-right text-slate-700">
                                                    {sub.percentage !== null ? `${sub.percentage}%` : "—"}
                                                </td>
                                                <td className="py-2 px-3 text-center font-bold text-slate-800">
                                                    {sub.grade || "—"}
                                                </td>
                                                {exam.gpa !== null && (
                                                    <td className="py-2 px-3 text-center text-slate-700">
                                                        {sub.grade_point !== null && sub.grade_point !== undefined ? sub.grade_point.toFixed(2) : "—"}
                                                    </td>
                                                )}
                                                <td className="py-2 px-3 text-center">
                                                    {sub.is_pass ? (
                                                        <span className="text-emerald-700 font-semibold">Pass</span>
                                                    ) : (
                                                        <span className="text-red-600 font-semibold">Fail</span>
                                                    )}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                    <tfoot className="bg-slate-100 font-bold border-t-2 border-slate-300 text-slate-900">
                                        <tr>
                                            <td colSpan={3} className="py-2.5 px-3 uppercase text-xs tracking-wider">
                                                Exam Aggregate
                                            </td>
                                            <td className="py-2.5 px-3 text-right">{exam.total_max_marks}</td>
                                            <td className="py-2.5 px-3 text-right">{exam.total_marks_obtained}</td>
                                            <td className="py-2.5 px-3 text-right">{exam.percentage}%</td>
                                            <td className="py-2.5 px-3 text-center">{exam.overall_grade || "—"}</td>
                                            {exam.gpa !== null && (
                                                <td className="py-2.5 px-3 text-center text-indigo-900">
                                                    {exam.gpa.toFixed(2)}
                                                </td>
                                            )}
                                            <td className="py-2.5 px-3 text-center">
                                                {exam.is_pass ? "PASS" : "FAIL"}
                                            </td>
                                        </tr>
                                    </tfoot>
                                </table></div>
                            </div>
                        ))}
                    </div>
                )}

                {/* Annual Academic Summary & Promotion Decision */}
                {summary && examinations.length > 0 && (
                    <div className="mt-6 border-2 border-slate-900 rounded-xl p-4 bg-slate-50">
                        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900 mb-3 flex items-center gap-2">
                            <TrendingUp className="h-4 w-4 text-indigo-700" />
                            Academic Year Performance Summary
                        </h4>
                        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-center text-xs">
                            <div className="p-2 bg-white rounded border border-slate-200">
                                <span className="text-slate-500 block">Total Marks</span>
                                <span className="text-base font-black text-slate-900">
                                    {summary.total_marks_obtained} / {summary.total_max_marks}
                                </span>
                            </div>
                            <div className="p-2 bg-white rounded border border-slate-200">
                                <span className="text-slate-500 block">Overall Percentage</span>
                                <span className="text-base font-black text-indigo-700">
                                    {summary.percentage !== null ? `${summary.percentage}%` : "—"}
                                </span>
                            </div>
                            <div className="p-2 bg-white rounded border border-slate-200">
                                <span className="text-slate-500 block">Overall Grade</span>
                                <span className="text-base font-black text-slate-900">
                                    {summary.overall_grade || "—"}
                                </span>
                            </div>
                            <div className="p-2 bg-white rounded border border-slate-200">
                                <span className="text-slate-500 block">Cumulative GPA</span>
                                <span className="text-base font-black text-indigo-900">
                                    {summary.gpa !== null ? summary.gpa.toFixed(2) : "N/A"}
                                </span>
                            </div>
                            <div className="p-2 bg-white rounded border border-slate-200">
                                <span className="text-slate-500 block">Year Result</span>
                                <span className={`text-base font-black ${summary.is_pass ? "text-emerald-700" : "text-red-600"}`}>
                                    {summary.is_pass ? "PASSED" : "FAILED"}
                                </span>
                            </div>
                        </div>

                        {/* Promotion Status */}
                        {promotion && (
                            <div className="mt-3 pt-3 border-t border-slate-200 flex flex-wrap items-center justify-between text-xs">
                                <div>
                                    <span className="font-bold text-slate-700">Academic Progression / Promotion: </span>
                                    <span className="font-black text-indigo-800 uppercase px-2 py-0.5 bg-indigo-50 rounded">
                                        {promotion.action_display || promotion.action}
                                    </span>
                                    {promotion.target_level && (
                                        <span className="ml-2 text-slate-600">
                                            to <strong>{promotion.target_level}</strong>
                                            {promotion.target_academic_year && ` (${promotion.target_academic_year})`}
                                        </span>
                                    )}
                                </div>
                                {promotion.date && (
                                    <span className="text-slate-500">Decision Date: {promotion.date}</span>
                                )}
                            </div>
                        )}
                    </div>
                )}

                {/* Term Weightage Consolidated Breakdown */}
                {reportCard.term_weightage && reportCard.term_weightage.terms && reportCard.term_weightage.terms.length > 0 && (
                    <div className="mt-6 border border-slate-300 rounded-xl overflow-hidden bg-white">
                        <div className="bg-slate-100 px-4 py-2 border-b border-slate-300">
                            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900">
                                Consolidated Term Evaluation & Weightage Breakdown
                            </h4>
                        </div>
                        <div className="w-full overflow-x-auto">
                            <table className="w-full text-xs text-left">
                                <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase font-semibold">
                                    <tr>
                                        <th className="py-2 px-3">Evaluation Term</th>
                                        <th className="py-2 px-3 text-right">Prescribed Weight</th>
                                        <th className="py-2 px-3 text-right">Term Percentage</th>
                                        <th className="py-2 px-3 text-right">Weighted Contribution</th>
                                        <th className="py-2 px-3 text-center">Status</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-200">
                                    {reportCard.term_weightage.terms.map((t, tIdx) => (
                                        <tr key={t.examination_id || tIdx}>
                                            <td className="py-2 px-3 font-semibold text-slate-900">
                                                {t.examination_name}
                                            </td>
                                            <td className="py-2 px-3 text-right text-slate-600">
                                                {t.weightage_percentage}%
                                            </td>
                                            <td className="py-2 px-3 text-right font-medium text-slate-900">
                                                {t.percentage !== null ? `${t.percentage}%` : "—"}
                                            </td>
                                            <td className="py-2 px-3 text-right font-bold text-indigo-700">
                                                {t.weighted_contribution !== null ? `${t.weighted_contribution}%` : "—"}
                                            </td>
                                            <td className="py-2 px-3 text-center">
                                                <span className={`font-semibold ${t.is_pass ? "text-emerald-700" : "text-red-600"}`}>
                                                    {t.is_pass ? "Pass" : "Fail"}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                                <tfoot className="bg-slate-100 font-bold border-t-2 border-slate-300 text-slate-900">
                                    <tr>
                                        <td className="py-2 px-3 uppercase text-xs">Composite Score</td>
                                        <td className="py-2 px-3 text-right">{reportCard.term_weightage.total_weightage}%</td>
                                        <td className="py-2 px-3 text-right">—</td>
                                        <td className="py-2 px-3 text-right text-indigo-800">
                                            {reportCard.term_weightage.composite_score !== null ? `${reportCard.term_weightage.composite_score}%` : "—"}
                                        </td>
                                        <td className="py-2 px-3 text-center text-indigo-900">
                                            Grade: {reportCard.term_weightage.overall_grade || "—"}
                                        </td>
                                    </tr>
                                </tfoot>
                            </table>
                        </div>
                    </div>
                )}

                {/* Co-Scholastic Activities Section (CBSE 8-Point Scale) */}
                {reportCard.co_scholastic && reportCard.co_scholastic.length > 0 && (
                    <div className="mt-6 border border-slate-300 rounded-xl overflow-hidden bg-white">
                        <div className="bg-slate-100 px-4 py-2 border-b border-slate-300 flex items-center justify-between">
                            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900">
                                Co-Scholastic Activities & Domain Assessment
                            </h4>
                            <span className="text-[10px] font-semibold text-slate-500 uppercase">Graded on Direct Letter Scale</span>
                        </div>
                        <div className="w-full overflow-x-auto">
                            <table className="w-full text-xs text-left">
                                <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase font-semibold">
                                    <tr>
                                        <th className="py-2 px-3 w-12">#</th>
                                        <th className="py-2 px-3">Activity / Assessment Domain</th>
                                        <th className="py-2 px-3 text-center w-24">Grade Awarded</th>
                                        <th className="py-2 px-3">Descriptive Indicators / Remarks</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-200">
                                    {reportCard.co_scholastic.map((act, aIdx) => (
                                        <tr key={act.activity_id || aIdx} className={aIdx % 2 === 1 ? "bg-slate-50/50" : ""}>
                                            <td className="py-2 px-3 text-slate-400">{aIdx + 1}</td>
                                            <td className="py-2 px-3 font-semibold text-slate-900">
                                                {act.activity_name}
                                                {act.activity_code && (
                                                    <span className="text-slate-400 font-normal ml-1">({act.activity_code})</span>
                                                )}
                                            </td>
                                            <td className="py-2 px-3 text-center font-black text-indigo-700 text-sm">
                                                <span className="inline-block px-2.5 py-0.5 rounded bg-indigo-50 border border-indigo-200">
                                                    {act.grade}
                                                </span>
                                            </td>
                                            <td className="py-2 px-3 text-slate-700 italic">
                                                {act.remarks || "Satisfactory participation and conduct."}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {/* Remarks Block */}
                {remarks.length > 0 && (
                    <div className="mt-4 border border-slate-200 rounded-xl p-3 bg-white text-xs">
                        <span className="font-bold text-slate-800 block mb-1">Instructor / Class Teacher Remarks:</span>
                        <ul className="list-disc list-inside space-y-0.5 text-slate-700">
                            {remarks.map((r, rIdx) => (
                                <li key={rIdx}>
                                    <strong>{r.subject} ({r.examination}):</strong> {r.remarks}
                                </li>
                            ))}
                        </ul>
                    </div>
                )}

                {/* Signatures & Validation Footer */}
                <div className="mt-12 pt-8 border-t border-slate-300 grid grid-cols-3 gap-8 text-center text-xs">
                    <div>
                        <div className="border-b border-slate-400 h-10 mb-2"></div>
                        <p className="font-bold text-slate-800">Class Teacher</p>
                        <p className="text-[10px] text-slate-500">Signature & Date</p>
                    </div>
                    <div>
                        <div className="border-b border-slate-400 h-10 mb-2"></div>
                        <p className="font-bold text-slate-800">Academic Coordinator</p>
                        <p className="text-[10px] text-slate-500">Signature & Date</p>
                    </div>
                    <div>
                        <div className="border-b border-slate-400 h-10 mb-2"></div>
                        <p className="font-bold text-slate-800">Principal / Head of School</p>
                        <p className="text-[10px] text-slate-500">Official Seal & Signature</p>
                    </div>
                </div>

                <div className="mt-8 text-[10px] text-slate-400 flex justify-between items-center border-t border-slate-100 pt-2">
                    <span>Generated on: {generated_at ? new Date(generated_at).toLocaleString() : new Date().toLocaleDateString()}</span>
                    <span>EduSekai Student Information System · Official Document</span>
                </div>
            </div>
        </div>
    );
};

export default PrintableReportCard;

