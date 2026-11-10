"use client";

import React, { useState, useMemo, useRef } from "react";
import {
    Printer,
    GraduationCap,
    School,
    Users,
    CheckSquare,
    Square,
    RotateCw,
    Filter,
    Layers,
    Scissors,
    Sparkles,
} from "lucide-react";
import { useInstitutionProfile } from "@/hooks/useProfile";
import { useStudents, Student } from "@/hooks/useStudents";
import { useSections } from "@/hooks/useAcademics";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar } from "@/components/ui/avatar";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

const CARDS_PER_A4_PAGE = 8; // 2 columns x 4 rows (CR80: 85.6mm x 54.0mm)

function formatDate(dateStr?: string | null) {
    if (!dateStr) return "—";
    try {
        if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
            const [y, m, d] = dateStr.split("-").map(Number);
            const date = new Date(y, m - 1, d);
            return date.toLocaleDateString("en-IN", { month: "short", day: "numeric", year: "numeric" });
        }
        return new Date(dateStr).toLocaleDateString("en-IN", { month: "short", day: "numeric", year: "numeric" });
    } catch {
        return dateStr;
    }
}

export function BatchIdCardSheet() {
    const { data: institution } = useInstitutionProfile();
    const { data: sectionsData = [] } = useSections();
    const { data: studentsData, isLoading: loadingStudents } = useStudents({
        pageSize: 100,
        status: "active",
    });

    const [selectedLevel, setSelectedLevel] = useState<string>("all");
    const [selectedSection, setSelectedSection] = useState<string>("all");
    const [selectedStudentIds, setSelectedStudentIds] = useState<Set<string>>(new Set());
    const [side, setSide] = useState<"front" | "back">("front");
    const [layout, setLayout] = useState<"landscape" | "portrait">("landscape");

    const schoolName = institution?.name || "Sunrise Valley School";
    const schoolAddress = (institution as any)?.address || institution?.tagline || "Affiliated to CBSE, New Delhi";
    const schoolPhone = institution?.phone || "+91 (011) 2345-6789";

    const allStudents = useMemo(() => studentsData?.results || [], [studentsData]);

    // Unique levels for the filter dropdown
    const availableLevels = useMemo(() => {
        const set = new Set<string>();
        allStudents.forEach((s) => {
            if (s.level && s.level !== "N/A" && s.level !== "Unassigned") set.add(s.level);
        });
        return Array.from(set).sort();
    }, [allStudents]);

    // Filter students by level and section
    const filteredStudents = useMemo(() => {
        return allStudents.filter((s) => {
            if (selectedLevel !== "all" && s.level !== selectedLevel) return false;
            if (selectedSection !== "all" && s.section !== selectedSection) return false;
            return true;
        });
    }, [allStudents, selectedLevel, selectedSection]);

    // Initialize or reset selected IDs when class filter changes
    React.useEffect(() => {
        const ids = new Set<string>();
        filteredStudents.forEach((s) => ids.add(s.id));
        setSelectedStudentIds(ids);
    }, [filteredStudents]);

    const toggleSelectAll = () => {
        if (selectedStudentIds.size === filteredStudents.length) {
            setSelectedStudentIds(new Set());
        } else {
            const ids = new Set<string>();
            filteredStudents.forEach((s) => ids.add(s.id));
            setSelectedStudentIds(ids);
        }
    };

    const toggleStudent = (id: string) => {
        setSelectedStudentIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    // Filtered selected students
    const studentsToPrint = useMemo(() => {
        return filteredStudents.filter((s) => selectedStudentIds.has(s.id));
    }, [filteredStudents, selectedStudentIds]);

    // Split into A4 pages (8 cards per page)
    const pages = useMemo(() => {
        const chunks: Student[][] = [];
        for (let i = 0; i < studentsToPrint.length; i += CARDS_PER_A4_PAGE) {
            chunks.push(studentsToPrint.slice(i, i + CARDS_PER_A4_PAGE));
        }
        return chunks;
    }, [studentsToPrint]);

    const handlePrint = () => {
        window.print();
    };

    return (
        <div className="space-y-6">
            {/* Filter & Batch Controls Toolbar */}
            <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200/80 dark:border-slate-800 shadow-2xs space-y-4 print:hidden">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 dark:border-slate-800 pb-4">
                    <div>
                        <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                            <Layers className="h-4 w-4 text-indigo-600" />
                            <span>Batch Class Parameters &amp; Format</span>
                        </h3>
                        <p className="text-xs text-slate-400 mt-0.5">
                            Filter cohort, toggle cutting guides, and select layout orientation
                        </p>
                    </div>

                    {/* Batch Print Button */}
                    <Button
                        size="sm"
                        disabled={studentsToPrint.length === 0}
                        onClick={handlePrint}
                        className="gap-2 bg-indigo-600 hover:bg-indigo-500 text-white"
                    >
                        <Printer className="h-4 w-4" />
                        <span>Print Batch ({studentsToPrint.length} Cards • {pages.length} A4 Pages)</span>
                    </Button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 items-end">
                    {/* Grade / Level Filter */}
                    <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                            Grade Level
                        </label>
                        <Select value={selectedLevel} onValueChange={setSelectedLevel}>
                            <SelectTrigger className="h-9 text-xs rounded-lg border-slate-200 dark:border-slate-800">
                                <SelectValue placeholder="All Grades" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all" className="text-xs">All Grades</SelectItem>
                                {availableLevels.map((lvl) => (
                                    <SelectItem key={lvl} value={lvl} className="text-xs">{lvl}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Section Filter */}
                    <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                            Section
                        </label>
                        <Select value={selectedSection} onValueChange={setSelectedSection}>
                            <SelectTrigger className="h-9 text-xs rounded-lg border-slate-200 dark:border-slate-800">
                                <SelectValue placeholder="All Sections" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all" className="text-xs">All Sections</SelectItem>
                                <SelectItem value="A" className="text-xs">Section A</SelectItem>
                                <SelectItem value="B" className="text-xs">Section B</SelectItem>
                                <SelectItem value="C" className="text-xs">Section C</SelectItem>
                                <SelectItem value="D" className="text-xs">Section D</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Format Layout Toggle */}
                    <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                            Card Style
                        </label>
                        <div className="flex items-center gap-1">
                            <button
                                type="button"
                                onClick={() => setLayout("landscape")}
                                className={`flex-1 h-9 px-2 text-xs font-semibold rounded-lg border transition ${
                                    layout === "landscape"
                                        ? "bg-indigo-600 text-white border-indigo-600"
                                        : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700"
                                }`}
                            >
                                Landscape (8/A4)
                            </button>
                            <button
                                type="button"
                                onClick={() => setLayout("portrait")}
                                className={`flex-1 h-9 px-2 text-xs font-semibold rounded-lg border transition ${
                                    layout === "portrait"
                                        ? "bg-indigo-600 text-white border-indigo-600"
                                        : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700"
                                }`}
                            >
                                Portrait (8/A4)
                            </button>
                        </div>
                    </div>

                    {/* Front vs Back Face Toggle */}
                    <div className="space-y-1.5">
                        <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                            Face Side
                        </label>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setSide(side === "front" ? "back" : "front")}
                            className="w-full gap-1.5"
                        >
                            <RotateCw className="h-3.5 w-3.5 text-indigo-600" />
                            <span>Showing {side === "front" ? "Front Face" : "Back Face"}</span>
                        </Button>
                    </div>
                </div>

                {/* Selection Bar */}
                <div className="pt-2 flex flex-wrap items-center justify-between gap-3 text-xs border-t border-slate-100 dark:border-slate-800">
                    <button
                        type="button"
                        onClick={toggleSelectAll}
                        className="flex items-center gap-2 font-semibold text-slate-700 dark:text-slate-300 hover:text-indigo-600 cursor-pointer"
                    >
                        {selectedStudentIds.size === filteredStudents.length && filteredStudents.length > 0 ? (
                            <CheckSquare className="h-4 w-4 text-indigo-600" />
                        ) : (
                            <Square className="h-4 w-4 text-slate-400" />
                        )}
                        <span>
                            {selectedStudentIds.size === filteredStudents.length ? "Deselect All" : "Select All"}{" "}
                            ({filteredStudents.length} Students Available)
                        </span>
                    </button>

                    <div className="flex items-center gap-3 text-slate-400">
                        <span className="flex items-center gap-1 text-slate-600 dark:text-slate-300 font-medium">
                            <Scissors className="h-3.5 w-3.5 text-amber-500" />
                            <span>Includes cutting guides for paper trimmer</span>
                        </span>
                        <span>•</span>
                        <span className="font-mono text-indigo-600 dark:text-indigo-400 font-bold">
                            {studentsToPrint.length} Cards Selected
                        </span>
                    </div>
                </div>
            </div>

            {/* Empty State */}
            {studentsToPrint.length === 0 && !loadingStudents && (
                <div className="p-12 text-center bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 text-slate-400 print:hidden">
                    <GraduationCap className="h-12 w-12 mx-auto mb-2 opacity-30" />
                    <p className="font-semibold text-slate-700 dark:text-slate-300 text-sm">
                        No students selected for batch printing.
                    </p>
                    <p className="text-xs text-slate-400 mt-1">
                        Select students or adjust class filters to render A4 print sheets.
                    </p>
                </div>
            )}

            {/* Printable A4 Batch Sheets */}
            <div className="space-y-8 print:space-y-0">
                {pages.map((pageStudents, pageIdx) => (
                    <div
                        key={pageIdx}
                        className="a4-batch-page w-[210mm] min-h-[297mm] p-[10mm] mx-auto bg-white text-slate-900 border border-slate-300 dark:border-slate-800 shadow-xl print:shadow-none print:border-none print:p-[8mm] print:m-0 rounded-2xl print:rounded-none relative print-avoid-break"
                        style={{
                            pageBreakAfter: pageIdx < pages.length - 1 ? "always" : "auto",
                            breakAfter: pageIdx < pages.length - 1 ? "page" : "auto",
                        }}
                    >
                        {/* Page Header (Hidden when printing) */}
                        <div className="flex items-center justify-between text-[11px] font-semibold text-slate-400 border-b border-slate-200 pb-2 mb-4 print:hidden">
                            <span>
                                A4 BATCH SHEET • PAGE {pageIdx + 1} OF {pages.length}
                            </span>
                            <span>
                                {pageStudents.length} CARDS ON THIS SHEET (CR80: 85.6mm × 54.0mm)
                            </span>
                        </div>

                        {/* 2 x 4 Grid of 8 CR80 Cards */}
                        <div className="grid grid-cols-2 grid-rows-4 gap-[4mm] h-[264mm]">
                            {pageStudents.map((student) => {
                                const fullName = student.full_name || `${student.first_name || ""} ${student.last_name || ""}`.trim();

                                return (
                                    <div
                                        key={student.id}
                                        className="relative w-[92mm] h-[62mm] bg-white rounded-xl border border-dashed border-slate-400 p-2 flex flex-col justify-between overflow-hidden shadow-2xs print:shadow-none print:border-slate-400"
                                    >
                                        {/* Scissor Cutting Marks */}
                                        <div className="absolute top-0.5 right-1 text-[7px] text-slate-300 font-mono print:text-slate-400 select-none">
                                            ✂ cut
                                        </div>

                                        {side === "front" ? (
                                            /* FRONT FACE */
                                            <>
                                                {/* Header */}
                                                <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white px-2.5 py-1 rounded-t flex items-center justify-between">
                                                    <div className="flex items-center gap-1.5 min-w-0">
                                                        <School className="h-3 w-3 text-sky-300 shrink-0" />
                                                        <span className="text-[8px] font-black uppercase tracking-tight truncate max-w-[150px]">
                                                            {schoolName}
                                                        </span>
                                                    </div>
                                                    <span className="text-[7px] font-bold uppercase bg-white/20 px-1 py-0.2 rounded font-mono">
                                                        {student.enrollment_id}
                                                    </span>
                                                </div>

                                                {/* Card Content Body */}
                                                <div className="flex items-center gap-2.5 px-1 py-1 flex-1">
                                                    {/* Avatar */}
                                                    <Avatar
                                                        name={fullName}
                                                        src={student.photo}
                                                        size="xl"
                                                        shape="rounded"
                                                        className="h-14 w-14 rounded-xl shrink-0"
                                                    />

                                                    {/* Particulars */}
                                                    <div className="space-y-0.5 flex-1 min-w-0 text-[9px]">
                                                        <h5 className="font-black text-slate-900 text-[10px] truncate leading-tight">
                                                            {fullName}
                                                        </h5>
                                                        <div className="flex items-center gap-1 font-bold text-indigo-700">
                                                            <span>{student.level || "Grade"}</span>
                                                            {student.section && <span>• Sec {student.section}</span>}
                                                        </div>
                                                        <div className="text-[7.5px] text-slate-500 leading-tight">
                                                            <span>Guardian: {student.guardian_name || student.father_name || "—"}</span>
                                                        </div>
                                                        <div className="text-[7.5px] text-slate-500 leading-tight">
                                                            <span>Contact: {(student as any).phone || schoolPhone}</span>
                                                        </div>
                                                    </div>
                                                </div>

                                                {/* Card Footer with Barcode */}
                                                <div className="px-2 py-0.5 bg-slate-50 rounded-b border-t border-slate-200 flex items-center justify-between">
                                                    <div className="h-3 w-28 flex items-center gap-[1.5px] opacity-75">
                                                        {[2, 3, 1, 4, 1, 5, 2, 6, 3, 5, 1, 4, 2, 3, 6, 4, 2, 5].map((w, idx) => (
                                                            <div key={idx} style={{ width: `${(w % 2) + 1}px` }} className="h-full bg-slate-900" />
                                                        ))}
                                                    </div>
                                                    <span className="text-[7px] font-bold text-slate-400 uppercase tracking-wider">
                                                        Student Pass
                                                    </span>
                                                </div>
                                            </>
                                        ) : (
                                            /* BACK FACE */
                                            <div className="p-2 flex-1 flex flex-col justify-between text-[8px] space-y-1">
                                                <div className="text-center border-b border-slate-200 pb-1">
                                                    <span className="font-black uppercase text-[8.5px] text-slate-900 block">
                                                        {schoolName}
                                                    </span>
                                                    <span className="text-[7px] text-slate-500 block truncate">
                                                        {schoolAddress}
                                                    </span>
                                                </div>

                                                <p className="text-[7px] text-slate-600 leading-tight">
                                                    This card is institutional property. If found, return to school office or call: {schoolPhone}.
                                                </p>

                                                <div className="pt-2 flex items-end justify-between px-1">
                                                    <div className="text-center">
                                                        <div className="w-14 border-b border-slate-400 mb-0.5" />
                                                        <span className="text-[6.5px] uppercase font-bold text-slate-400">Student Sign</span>
                                                    </div>
                                                    <div className="text-center">
                                                        <div className="w-16 border-b border-slate-400 mb-0.5" />
                                                        <span className="text-[6.5px] uppercase font-bold text-slate-400">Principal Sign</span>
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
