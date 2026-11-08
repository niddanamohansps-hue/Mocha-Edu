"use client";

import { useState } from "react";
import Link from "next/link";
import { Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { useDutyRoster, useMyDuties } from "@/hooks/useExamAllocation";
import { useExaminations } from "@/hooks/useExaminations";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { usePermissions } from "@/providers/PermissionProvider";
import type { DutyRow } from "@/types/ExamAllocation";

const time = (t: string) => t.slice(0, 5);

export default function ExamDutiesPage() {
    const { can, isOwner } = usePermissions();
    const canSeeRoster = isOwner || can("view_examinations");
    return (
        <div className="max-w-5xl mx-auto space-y-8">
            <style jsx global>{`
                @media print {
                    @page { size: A4 landscape; margin: 12mm; }
                    nav, header, aside, .no-print { display: none !important; }
                }
            `}</style>
            <MyDuties />
            {canSeeRoster && <Roster />}
        </div>
    );
}

function DutyTable({ rows, withStaff, attendance = false }: { rows: DutyRow[]; withStaff: boolean; attendance?: boolean }) {
    return (
        <Table>
            <TableHeader>
                <TableRow>
                    {withStaff && <TableHead>Staff</TableHead>}
                    <TableHead>Date</TableHead>
                    <TableHead>Time</TableHead>
                    <TableHead>Examination</TableHead>
                    <TableHead>Room</TableHead>
                    <TableHead>Role</TableHead>
                    {attendance && <TableHead />}
                </TableRow>
            </TableHeader>
            <TableBody>
                {rows.map((row) => (
                    <TableRow key={row.id}>
                        {withStaff && <TableCell className="font-medium">{row.staff} <span className="text-xs text-slate-400">{row.employee_id}</span></TableCell>}
                        <TableCell>{row.date}</TableCell>
                        <TableCell>{time(row.start_time)} - {time(row.end_time)}</TableCell>
                        <TableCell>{row.examination}</TableCell>
                        <TableCell>{row.room}</TableCell>
                        <TableCell>{row.role === "chief" ? "Chief invigilator" : "Invigilator"}</TableCell>
                        {attendance && (
                            <TableCell className="no-print">
                                <Button asChild size="sm" variant="outline">
                                    <Link href={`/dashboard/examinations/hall-attendance?sitting=${row.sitting}&room=${row.room_id}`}>Take attendance</Link>
                                </Button>{" "}
                                <Button asChild size="sm" variant="outline">
                                    <Link href={`/dashboard/examinations/room-report?sitting=${row.sitting}&room=${row.room_id}`}>Room report</Link>
                                </Button>
                            </TableCell>
                        )}
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    );
}

function MyDuties() {
    const { data: duties = [], isLoading } = useMyDuties();
    return (
        <section className="space-y-3">
            <h1 className="text-3xl font-bold text-slate-900 dark:text-white">My exam duties</h1>
            {isLoading ? (
                <LoadingState />
            ) : duties.length === 0 ? (
                <EmptyState title="No duties" description="You have not been put on any invigilation duty." />
            ) : (
                <DutyTable rows={duties} withStaff={false} attendance />
            )}
        </section>
    );
}

function Roster() {
    const { selectedYear } = useAcademicYear();
    const { data: examinations = [] } = useExaminations(selectedYear?.name || undefined);
    const [examination, setExamination] = useState("");
    const { data: rows = [], isLoading } = useDutyRoster(examination || undefined);
    return (
        <section className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3 no-print">
                <h2 className="text-xl font-semibold">Duty roster</h2>
                <div className="flex gap-2">
                    <select
                        className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950"
                        value={examination}
                        onChange={(e) => setExamination(e.target.value)}
                    >
                        <option value="">Choose an examination</option>
                        {examinations.map((exam) => (
                            <option key={exam.id} value={exam.id}>{exam.name}</option>
                        ))}
                    </select>
                    <Button variant="outline" disabled={rows.length === 0} onClick={() => window.print()}>
                        <Printer className="mr-2 h-4 w-4" /> Print
                    </Button>
                </div>
            </div>
            {!examination ? null : isLoading ? (
                <LoadingState />
            ) : rows.length === 0 ? (
                <EmptyState title="No duties allocated" description="Allocate rooms and invigilators first." />
            ) : (
                <DutyTable rows={rows} withStaff />
            )}
        </section>
    );
}
