"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { useAdmissionsReport, useSeats, useSetSeatLimit, type SeatRow } from "@/hooks/useAdmissions";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { usePermissions } from "@/providers/PermissionProvider";

export default function SeatsPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("view_admissions")) return <Unauthorized />;
    return <Content canEdit={isOwner || can("manage_admission_applications")} />;
}

function Content({ canEdit }: { canEdit: boolean }) {
    const { selectedYear } = useAcademicYear();
    const year = selectedYear?.name || "";
    const seats = useSeats(year);
    const report = useAdmissionsReport(year);

    if (!year) return <EmptyState title="Choose an academic year" description="Pick the year at the top of the page." />;

    return (
        <div className="max-w-5xl mx-auto space-y-10">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Seats and admissions report</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    Academic year {year}. A class with no limit set can take any number. Approving past a limit asks for confirmation.
                </p>
            </div>

            <section className="space-y-3">
                <h2 className="text-lg font-semibold">Seats by class</h2>
                {seats.isLoading ? <LoadingState /> : (
                    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
                        <table className="w-full text-sm">
                            <thead className="border-b border-slate-200 text-left text-xs uppercase text-slate-500 dark:border-slate-800">
                                <tr>
                                    <th className="px-4 py-2">Class</th>
                                    <th className="px-4 py-2">Seats</th>
                                    <th className="px-4 py-2 text-right">Taken</th>
                                    <th className="px-4 py-2 text-right">Free</th>
                                    <th className="px-4 py-2 text-right">Waiting list</th>
                                    <th className="px-4 py-2 text-right">In progress</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                {(seats.data ?? []).map((row) => (
                                    <SeatLine key={`${row.level}-${row.seats}`} row={row} year={year} canEdit={canEdit} />
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </section>

            <section className="space-y-4">
                <h2 className="text-lg font-semibold">Enquiries to enrolment</h2>
                {report.isLoading || !report.data ? <LoadingState /> : report.data.totals.enquiries + report.data.totals.applications === 0 ? (
                    <EmptyState title="Nothing to report yet" description="Enquiries and applications for this year will be counted here." />
                ) : (
                    <>
                        <p className="text-sm text-slate-600 dark:text-slate-300">
                            {report.data.totals.enquiries} enquiries, {report.data.totals.applications} applications, {report.data.totals.enrolled} enrolled.
                            {report.data.average_days_to_enrol !== null
                                ? ` Families who started as an enquiry took ${report.data.average_days_to_enrol} days on average to enrol (${report.data.enrolled_with_enquiry} children).`
                                : ""}
                        </p>
                        <Table
                            title="Where enquiries come from"
                            heads={["Source", "Enquiries", "Applied", "Lost", "Enrolled"]}
                            rows={report.data.by_source.map((r) => [r.label, r.enquiries, r.applied, r.lost, r.enrolled])}
                        />
                        <Table
                            title="By class"
                            heads={["Class", "Enquiries", "Applications", "Approved", "Enrolled"]}
                            rows={report.data.by_level.map((r) => [r.level_name, r.enquiries, r.applications, r.approved, r.enrolled])}
                        />
                    </>
                )}
            </section>
        </div>
    );
}

function SeatLine({ row, year, canEdit }: { row: SeatRow; year: string; canEdit: boolean }) {
    const save = useSetSeatLimit();
    const [value, setValue] = useState(row.seats === null ? "" : String(row.seats));
    return (
        <tr>
            <td className="px-4 py-2 font-medium">{row.level_name}</td>
            <td className="px-4 py-2">
                {canEdit ? (
                    <span className="flex items-center gap-2">
                        <Input
                            type="number" min={0} className="h-8 w-24" placeholder="No limit" value={value}
                            onChange={(e) => setValue(e.target.value)}
                        />
                        <Button
                            size="sm" variant="outline"
                            disabled={save.isPending || value === "" || Number(value) === row.seats}
                            onClick={() => save.mutate({ academic_year: year, level: row.level, seats: Number(value) })}
                        >
                            Save
                        </Button>
                    </span>
                ) : row.seats ?? "No limit"}
            </td>
            <td className="px-4 py-2 text-right">
                {row.taken}
                {row.over_by > 0 && <Badge variant="destructive" className="ml-2">{row.over_by} over</Badge>}
            </td>
            <td className="px-4 py-2 text-right">{row.free ?? "-"}</td>
            <td className="px-4 py-2 text-right">{row.waitlisted}</td>
            <td className="px-4 py-2 text-right">{row.in_progress}</td>
        </tr>
    );
}

function Table({ title, heads, rows }: { title: string; heads: string[]; rows: (string | number)[][] }) {
    return (
        <div className="space-y-2">
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">{title}</h3>
            <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
                <table className="w-full text-sm">
                    <thead className="border-b border-slate-200 text-left text-xs uppercase text-slate-500 dark:border-slate-800">
                        <tr>{heads.map((h, i) => <th key={h} className={`px-4 py-2 ${i > 0 ? "text-right" : ""}`}>{h}</th>)}</tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {rows.map((r) => (
                            <tr key={String(r[0])}>
                                {r.map((cell, i) => <td key={i} className={`px-4 py-2 ${i > 0 ? "text-right" : "font-medium"}`}>{cell}</td>)}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
