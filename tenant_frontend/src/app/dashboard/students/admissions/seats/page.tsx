"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { PageHeader } from "@/components/common/PageLayout";
import {
    Table as SharedTable,
    TableHeader,
    TableHead,
    TableRow,
    TableCell,
    TableCellNumeric,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import {
    useAdmissionsReport,
    useRequiredDocuments,
    useSeats,
    useSetRequiredDocuments,
    useSetSeatLimit,
    type SeatRow,
} from "@/hooks/useAdmissions";
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
        <div className="max-w-7xl mx-auto space-y-6">
            <PageHeader
                title="Seats and Admissions Report"
                description={`Academic year ${year}. A class with no limit set can take any number. Approving past a limit asks for confirmation.`}
                badge={<Badge variant="outline" className="text-xs font-semibold bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-300">{year}</Badge>}
            />

            <section className="space-y-3">
                <h2 className="text-lg font-semibold">Seats by class</h2>
                {seats.isLoading ? <LoadingState /> : (seats.data ?? []).length === 0 ? (
                    <EmptyState
                        title="No classes configured for this academic year"
                        description="Academic levels and class sections need to be configured in Academics before assigning seat quotas."
                        hint="Go to Academics › Academic Structure to add your grades and sections."
                        className="py-12"
                    />
                ) : (
                    <TableShell>
                        <SharedTable className="min-w-[34rem]">
                            <TableHeader>
                                <TableRow>
                                    <TableHead className="sticky left-0 bg-white dark:bg-slate-900 z-10 border-r border-slate-100 dark:border-slate-800 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)] pl-4">Class</TableHead>
                                    <TableHead>Seats</TableHead>
                                    <TableHead className="text-right">Taken</TableHead>
                                    <TableHead className="text-right">Free</TableHead>
                                    <TableHead className="text-right">Waiting list</TableHead>
                                    <TableHead className="text-right pr-4">In progress</TableHead>
                                </TableRow>
                            </TableHeader>
                            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                {(seats.data ?? []).map((row) => (
                                    <SeatLine key={`${row.level}-${row.seats}`} row={row} year={year} canEdit={canEdit} />
                                ))}
                            </tbody>
                        </SharedTable>
                    </TableShell>
                )}
            </section>

            {canEdit && <RequiredDocumentsSection />}

            <section className="space-y-4">
                <h2 className="text-lg font-semibold">Enquiries to enrolment</h2>
                {report.isLoading || !report.data ? <LoadingState /> : report.data.totals.enquiries + report.data.totals.applications === 0 ? (
                    <EmptyState title="Nothing to report yet" description="Enquiries and applications for this year will be counted here." />
                ) : (
                    <>
                        <div className="grid grid-cols-3 gap-2 sm:gap-4 p-3 sm:p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs">
                            <div>
                                <span className="block text-[11px] sm:text-xs text-slate-500 uppercase font-medium">Enquiries</span>
                                <span className="text-base sm:text-2xl font-bold text-slate-900 dark:text-white">{report.data.totals.enquiries}</span>
                            </div>
                            <div>
                                <span className="block text-[11px] sm:text-xs text-slate-500 uppercase font-medium">Applications</span>
                                <span className="text-base sm:text-2xl font-bold text-slate-900 dark:text-white">{report.data.totals.applications}</span>
                            </div>
                            <div>
                                <span className="block text-[11px] sm:text-xs text-slate-500 uppercase font-medium">Enrolled</span>
                                <span className="text-base sm:text-2xl font-bold text-emerald-600 dark:text-emerald-400">{report.data.totals.enrolled}</span>
                            </div>
                        </div>
                        {report.data.average_days_to_enrol !== null && (
                            <p className="text-xs text-slate-500 dark:text-slate-400">
                                Families who started as an enquiry took {report.data.average_days_to_enrol} days on average to enrol ({report.data.enrolled_with_enquiry} children).
                            </p>
                        )}
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

function Picker({
    title, hint, types, chosen, pending, onSave,
}: {
    title: string; hint?: string; types: { value: string; label: string }[]; chosen: string[]; pending: boolean; onSave: (next: string[]) => void;
}) {
    const [picked, setPicked] = useState<string[]>(chosen);
    const changed = picked.length !== chosen.length || picked.some((p) => !chosen.includes(p));
    return (
        <div className="space-y-2 rounded-xl border border-slate-200 p-3 dark:border-slate-800">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-medium">{title}{hint && <span className="ml-2 text-xs font-normal text-slate-500">{hint}</span>}</span>
                <Button size="sm" variant="outline" className="min-h-[38px] sm:min-h-0 px-4 font-semibold" disabled={pending || !changed} onClick={() => onSave(picked)}>Save</Button>
            </div>
            <div className="flex flex-wrap gap-2 text-sm">
                {types.map((t) => (
                    <label key={t.value} className="flex items-center gap-2 py-1.5 px-2.5 rounded-lg border border-transparent hover:border-slate-200 dark:hover:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/60 transition cursor-pointer select-none">
                        <input
                            type="checkbox"
                            className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 cursor-pointer"
                            checked={picked.includes(t.value)}
                            onChange={(e) => setPicked((cur) => (e.target.checked ? [...cur, t.value] : cur.filter((v) => v !== t.value)))}
                        />
                        <span>{t.label}</span>
                    </label>
                ))}
            </div>
        </div>
    );
}

function RequiredDocumentsSection() {
    const required = useRequiredDocuments();
    const save = useSetRequiredDocuments();
    if (required.isLoading || !required.data) return <LoadingState />;
    const data = required.data;
    return (
        <section className="space-y-3">
            <h2 className="text-lg font-semibold">Documents applicants must hand in</h2>
            <p className="text-xs text-slate-500">
                Choose what every applicant needs, then anything extra for a class. A class with nothing chosen only gets the
                general reminder. Families are reminded of exactly what is still missing.
            </p>
            {data.types.length === 0 ? (
                <EmptyState
                    title="No admission document types defined yet"
                    description="Configure required document types (such as Birth Certificate, Transfer Certificate, Report Card) to request them from applying families."
                    hint="Choose what every applicant needs, then add any class-specific requirements."
                    className="py-10"
                />
            ) : (
                <>
                    <Picker
                        key={`all-${data.all_classes.join(",")}`} title="Every class" types={data.types} chosen={data.all_classes}
                        pending={save.isPending} onSave={(next) => save.mutate({ level: null, document_types: next })}
                    />
                    {data.by_level.map((row) => (
                        <Picker
                            key={`${row.level}-${row.document_types.join(",")}`} title={row.level_name} hint="extra for this class" types={data.types}
                            chosen={row.document_types} pending={save.isPending}
                            onSave={(next) => save.mutate({ level: row.level, document_types: next })}
                        />
                    ))}
                </>
            )}
        </section>
    );
}

function SeatLine({ row, year, canEdit }: { row: SeatRow; year: string; canEdit: boolean }) {
    const save = useSetSeatLimit();
    const [value, setValue] = useState(row.seats === null ? "" : String(row.seats));
    return (
        <tr>
            <td className="whitespace-nowrap px-4 py-2.5 sm:py-2 font-medium sticky left-0 bg-white dark:bg-slate-900 z-10 border-r border-slate-100 dark:border-slate-800 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)]">{row.level_name}</td>
            <td className="px-4 py-2.5 sm:py-2">
                {canEdit ? (
                    <span className="flex items-center gap-2">
                        <Input
                            type="number" min={0} className="h-9 sm:h-8 w-28 sm:w-24 text-sm" placeholder="No limit" value={value}
                            onChange={(e) => setValue(e.target.value)}
                        />
                        <Button
                            size="sm" variant="outline"
                            className="min-h-[38px] sm:min-h-0 px-3.5 font-semibold"
                            disabled={save.isPending || value === "" || Number(value) === row.seats}
                            onClick={() => save.mutate({ academic_year: year, level: row.level, seats: Number(value) })}
                        >
                            Save
                        </Button>
                    </span>
                ) : row.seats ?? "No limit"}
            </td>
            <td className="px-4 py-2.5 sm:py-2 text-right">
                {row.taken}
                {row.over_by > 0 && <Badge variant="destructive" className="ml-2">{row.over_by} over</Badge>}
            </td>
            <td className="px-4 py-2.5 sm:py-2 text-right">{row.free ?? "-"}</td>
            <td className="px-4 py-2.5 sm:py-2 text-right">{row.waitlisted}</td>
            <td className="px-4 py-2.5 sm:py-2 text-right">{row.in_progress}</td>
        </tr>
    );
}

function Table({ title, heads, rows }: { title: string; heads: string[]; rows: (string | number)[][] }) {
    return (
        <div className="space-y-2">
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">{title}</h3>
            <TableShell>
                <SharedTable className="min-w-[34rem]">
                    <TableHeader>
                        <TableRow>
                            {heads.map((h, i) => (
                                <TableHead
                                    key={h}
                                    className={`${i === 0 ? "sticky left-0 bg-white dark:bg-slate-900 z-10 border-r border-slate-100 dark:border-slate-800 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)] pl-4" : ""} ${i > 0 ? "text-right" : ""}`}
                                >
                                    {h}
                                </TableHead>
                            ))}
                        </TableRow>
                    </TableHeader>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {rows.map((r) => (
                            <tr key={String(r[0])} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40">
                                {r.map((cell, i) => (
                                    <td
                                        key={i}
                                        className={`px-4 py-2.5 sm:py-2 ${i === 0 ? "sticky left-0 bg-white dark:bg-slate-900 z-10 border-r border-slate-100 dark:border-slate-800 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.06)] font-medium" : "text-right font-mono tabular-nums"}`}
                                    >
                                        {cell}
                                    </td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                </SharedTable>
            </TableShell>
        </div>
    );
}
