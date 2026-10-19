"use client";

import React from "react";
import { Printer, School, User, Calendar, Award, CheckCircle2, FileText, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { OfficialTranscript } from "@/types/Examinations";

interface PrintableTranscriptProps {
    transcript: OfficialTranscript;
    onBackToReportCard?: () => void;
}

export const PrintableTranscript: React.FC<PrintableTranscriptProps> = ({
    transcript,
    onBackToReportCard,
}) => {
    const {
        institution,
        student,
        years = [],
        cumulative_summary,
        issuance,
        generated_at,
    } = transcript;

    const handlePrint = () => {
        window.print();
    };

    return (
        <div className="space-y-6">
            {/* Action Bar (hidden when printing) */}
            <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-slate-50 dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 print:hidden">
                <div className="flex items-center gap-3">
                    {onBackToReportCard && (
                        <Button variant="ghost" size="sm" onClick={onBackToReportCard} className="gap-2 text-slate-600 dark:text-slate-300">
                            <ArrowLeft className="h-4 w-4" />
                            Back to Report Card
                        </Button>
                    )}
                    <span className="text-sm font-medium text-slate-600 dark:text-slate-300">
                        Official Transcript: <strong className="text-slate-900 dark:text-white">{student.full_name}</strong> ({student.enrollment_id})
                    </span>
                </div>
                <div className="flex items-center gap-3">
                    <Button onClick={handlePrint} size="sm" className="bg-indigo-600 hover:bg-indigo-700 text-white gap-2">
                        <Printer className="h-4 w-4" />
                        Print / Save as PDF
                    </Button>
                </div>
            </div>

            {/* Printable Transcript Document */}
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
                        .page-break-before {
                            page-break-before: always;
                        }
                        .avoid-break {
                            break-inside: avoid;
                            page-break-inside: avoid;
                        }
                    }
                `}</style>

                {/* Header: School Identity */}
                <div className="border-b-2 border-slate-900 pb-5 mb-6 text-center">
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

                    <div className="mt-4 pt-3 border-t border-slate-200">
                        <span className="text-sm font-black uppercase tracking-widest text-slate-900 bg-slate-100 border border-slate-300 px-4 py-1 rounded inline-block">
                            OFFICIAL ACADEMIC TRANSCRIPT
                        </span>
                    </div>
                </div>

                {/* Student Information Block */}
                <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 mb-6 text-sm">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-y-3 gap-x-4">
                        <div>
                            <span className="text-xs text-slate-500 uppercase block font-semibold">Student Full Name</span>
                            <span className="font-bold text-slate-900">{student.full_name}</span>
                        </div>
                        <div>
                            <span className="text-xs text-slate-500 uppercase block font-semibold">Enrollment ID</span>
                            <span className="font-semibold text-slate-800">{student.enrollment_id}</span>
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
                            <span className="text-xs text-slate-500 uppercase block font-semibold">Admission Date</span>
                            <span className="text-slate-800">{student.admission_date || "—"}</span>
                        </div>
                        <div>
                            <span className="text-xs text-slate-500 uppercase block font-semibold">Academic Status</span>
                            <span className="capitalize font-semibold text-slate-900">{student.status || "Active"}</span>
                        </div>
                        <div>
                            <span className="text-xs text-slate-500 uppercase block font-semibold">Total Years Recorded</span>
                            <span className="font-semibold text-slate-800">{years.length}</span>
                        </div>
                        <div>
                            <span className="text-xs text-slate-500 uppercase block font-semibold">Date of Issuance</span>
                            <span className="font-semibold text-slate-800">{issuance?.issued_date || "—"}</span>
                        </div>
                    </div>
                </div>

                {/* Chronological Academic Years */}
                {years.length === 0 ? (
                    <div className="text-center py-12 border border-dashed border-slate-300 rounded-xl my-6">
                        <FileText className="h-8 w-8 text-slate-400 mx-auto mb-2" />
                        <p className="font-medium text-slate-700">No academic years or examination records found for this student.</p>
                    </div>
                ) : (
                    <div className="space-y-6">
                        {years.map((yearBlock, yIdx) => (
                            <div key={yearBlock.academic_year || yIdx} className="avoid-break border border-slate-300 rounded-xl overflow-hidden">
                                <div className="bg-slate-100 px-4 py-2.5 border-b border-slate-300 flex flex-wrap items-center justify-between gap-2">
                                    <div className="flex items-center gap-2">
                                        <h3 className="font-bold text-slate-900 text-sm">
                                            Academic Year: {yearBlock.academic_year}
                                        </h3>
                                        <span className="text-xs text-slate-600 bg-white border border-slate-200 px-2 py-0.5 rounded font-medium">
                                            {yearBlock.level || "Unspecified Level"} {yearBlock.section ? `(${yearBlock.section})` : ""}
                                        </span>
                                    </div>
                                    <div className="flex items-center gap-2 text-xs">
                                        {yearBlock.summary?.gpa !== null && yearBlock.summary?.gpa !== undefined && (
                                            <span className="font-bold bg-indigo-100 text-indigo-900 px-2 py-0.5 rounded">
                                                GPA: {yearBlock.summary.gpa.toFixed(2)}
                                            </span>
                                        )}
                                        {yearBlock.summary?.percentage !== null && (
                                            <span className="font-bold text-slate-700">
                                                {yearBlock.summary.percentage}% ({yearBlock.summary.overall_grade || "—"})
                                            </span>
                                        )}
                                        <span className={`font-bold px-2 py-0.5 rounded ${yearBlock.summary?.is_pass ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"}`}>
                                            {yearBlock.summary?.is_pass ? "PASSED" : "FAILED"}
                                        </span>
                                    </div>
                                </div>

                                {yearBlock.examinations.length === 0 ? (
                                    <div className="p-4 text-xs text-slate-500 italic text-center">
                                        Enrolled in this academic year; no published examination results recorded.
                                    </div>
                                ) : (
                                    <div className="divide-y divide-slate-200">
                                        {yearBlock.examinations.map((exam, eIdx) => (
                                            <div key={exam.id || eIdx} className="p-3">
                                                <div className="flex items-center justify-between mb-2">
                                                    <span className="font-bold text-xs text-slate-800">{exam.examination_name}</span>
                                                    <span className="text-xs text-slate-500">
                                                        Marks: <strong>{exam.total_marks_obtained}/{exam.total_max_marks}</strong> ({exam.percentage}%) · Grade: <strong>{exam.overall_grade || "—"}</strong>
                                                        {exam.gpa !== null && ` · GPA: ${exam.gpa.toFixed(2)}`}
                                                    </span>
                                                </div>

                                                <table className="w-full text-[11px] text-left">
                                                    <thead className="bg-slate-50 border-y border-slate-200 text-slate-600 font-semibold uppercase">
                                                        <tr>
                                                            <th className="py-1 px-2">Subject</th>
                                                            <th className="py-1 px-2 text-center">Credits</th>
                                                            <th className="py-1 px-2 text-right">Max</th>
                                                            <th className="py-1 px-2 text-right">Obtained</th>
                                                            <th className="py-1 px-2 text-right">%</th>
                                                            <th className="py-1 px-2 text-center">Grade</th>
                                                            {exam.gpa !== null && <th className="py-1 px-2 text-center">GP</th>}
                                                            <th className="py-1 px-2 text-center">Status</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody className="divide-y divide-slate-100">
                                                        {exam.subject_breakdown.map((sub, sIdx) => (
                                                            <tr key={sub.subject || sIdx}>
                                                                <td className="py-1 px-2 font-medium text-slate-900">{sub.subject_name}</td>
                                                                <td className="py-1 px-2 text-center text-slate-600">{sub.credits ?? 1.0}</td>
                                                                <td className="py-1 px-2 text-right text-slate-600">{sub.max_marks}</td>
                                                                <td className="py-1 px-2 text-right font-medium text-slate-900">
                                                                    {sub.is_absent ? "Absent" : sub.marks_obtained === null ? "—" : sub.marks_obtained}
                                                                </td>
                                                                <td className="py-1 px-2 text-right text-slate-700">{sub.percentage !== null ? `${sub.percentage}%` : "—"}</td>
                                                                <td className="py-1 px-2 text-center font-bold text-slate-800">{sub.grade || "—"}</td>
                                                                {exam.gpa !== null && (
                                                                    <td className="py-1 px-2 text-center text-slate-700">
                                                                        {sub.grade_point !== null && sub.grade_point !== undefined ? sub.grade_point.toFixed(2) : "—"}
                                                                    </td>
                                                                )}
                                                                <td className="py-1 px-2 text-center">
                                                                    {sub.is_pass ? (
                                                                        <span className="text-emerald-700 font-medium">Pass</span>
                                                                    ) : (
                                                                        <span className="text-red-600 font-medium">Fail</span>
                                                                    )}
                                                                </td>
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {/* Year Footer Summary (Attendance & Promotion) */}
                                <div className="bg-slate-50 px-4 py-2 border-t border-slate-200 text-xs flex flex-wrap items-center justify-between gap-2 text-slate-600">
                                    <div>
                                        Attendance: <strong className="text-slate-800">
                                            {yearBlock.attendance?.percentage !== null && yearBlock.attendance?.percentage !== undefined
                                                ? `${yearBlock.attendance.percentage}% (${yearBlock.attendance.present_days}/${yearBlock.attendance.total_days} days)`
                                                : "—"}
                                        </strong>
                                    </div>
                                    {yearBlock.promotion && (
                                        <div>
                                            Progression: <strong className="text-indigo-800 uppercase">{yearBlock.promotion.action_display || yearBlock.promotion.action}</strong>
                                            {yearBlock.promotion.target_level && ` to ${yearBlock.promotion.target_level}`}
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {/* Cumulative Academic Record Summary */}
                {cumulative_summary && (
                    <div className="avoid-break mt-8 border-2 border-slate-900 rounded-xl p-5 bg-slate-50">
                        <h4 className="text-xs font-black uppercase tracking-wider text-slate-900 mb-3 text-center">
                            Cumulative Academic Achievement Summary
                        </h4>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center text-xs">
                            <div className="p-3 bg-white rounded-lg border border-slate-200">
                                <span className="text-slate-500 block uppercase font-bold text-[10px]">Grand Total Marks</span>
                                <span className="text-lg font-black text-slate-900">
                                    {cumulative_summary.total_marks_obtained} / {cumulative_summary.total_max_marks}
                                </span>
                            </div>
                            <div className="p-3 bg-white rounded-lg border border-slate-200">
                                <span className="text-slate-500 block uppercase font-bold text-[10px]">Overall Percentage</span>
                                <span className="text-lg font-black text-indigo-700">
                                    {cumulative_summary.cumulative_percentage !== null ? `${cumulative_summary.cumulative_percentage}%` : "—"}
                                </span>
                            </div>
                            <div className="p-3 bg-white rounded-lg border border-slate-200">
                                <span className="text-slate-500 block uppercase font-bold text-[10px]">Cumulative GPA (CGPA)</span>
                                <span className="text-lg font-black text-indigo-950">
                                    {cumulative_summary.cgpa !== null ? cumulative_summary.cgpa.toFixed(2) : "N/A"}
                                </span>
                            </div>
                            <div className="p-3 bg-white rounded-lg border border-slate-200">
                                <span className="text-slate-500 block uppercase font-bold text-[10px]">Credits Completed</span>
                                <span className="text-lg font-black text-emerald-700">
                                    {cumulative_summary.total_credits_earned} / {cumulative_summary.total_credits_attempted}
                                </span>
                            </div>
                        </div>

                        {/* Official Certification Statement */}
                        <div className="mt-4 pt-3 border-t border-slate-200 text-center text-xs text-slate-600 italic">
                            &ldquo;This is to certify that the above is a true and accurate official transcript of academic performance, attendance, and evaluation records maintained by {institution?.name || "the institution"}.&rdquo;
                        </div>
                    </div>
                )}

                {/* Signatures & Seal Block */}
                <div className="avoid-break mt-12 pt-8 border-t border-slate-300 grid grid-cols-3 gap-8 text-center text-xs">
                    <div>
                        <div className="border-b border-slate-400 h-12 mb-2"></div>
                        <p className="font-bold text-slate-900">Class Teacher</p>
                        <p className="text-[10px] text-slate-500">Signature</p>
                    </div>
                    <div>
                        <div className="border-b border-slate-400 h-12 mb-2"></div>
                        <p className="font-bold text-slate-900">Academic Coordinator</p>
                        <p className="text-[10px] text-slate-500">Verified By</p>
                    </div>
                    <div>
                        <div className="border-b border-slate-400 h-12 mb-2"></div>
                        <p className="font-bold text-slate-900">Principal / Head of Institution</p>
                        <p className="text-[10px] text-slate-500">Official Seal & Signature</p>
                    </div>
                </div>

                <div className="mt-8 text-[10px] text-slate-400 flex justify-between items-center border-t border-slate-100 pt-2">
                    <span>Generated on: {generated_at ? new Date(generated_at).toLocaleString() : new Date().toLocaleDateString()}</span>
                    <span>EduSekai SIS · Official Transcript Document</span>
                </div>
            </div>
        </div>
    );
};

export default PrintableTranscript;

