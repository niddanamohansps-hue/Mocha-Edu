"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertTriangle, HeartPulse } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Pagination } from "@/components/ui/pagination";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import Unauthorized from "@/components/Unauthorized";
import { EmptyState } from "@/components/feedback/EmptyState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { usePermissions } from "@/providers/PermissionProvider";
import { useHealthAlerts, useIncidentLog } from "@/hooks/useHealth";
import { useSections } from "@/hooks/useAcademics";

const selectClass =
    "h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";

export default function HealthRecordsPage() {
    const { can } = usePermissions();
    const [section, setSection] = useState("");
    const [from, setFrom] = useState("");
    const [to, setTo] = useState("");
    const [page, setPage] = useState(1);
    const sections = useSections();
    const alerts = useHealthAlerts(section || undefined);
    const log = useIncidentLog(from, to, page);
    if (!can("view_health_records") && !can("manage_health_records")) return <Unauthorized />;

    return (
        <div className="space-y-8 p-4 md:p-6">
            <div>
                <h1 className="flex items-center gap-2 text-2xl font-bold">
                    <HeartPulse className="h-6 w-6 text-rose-500" /> Health Records
                </h1>
                <p className="mt-1 max-w-3xl text-sm text-slate-500">
                    Students with allergies or medical conditions, and every health incident at school. To see or change a
                    student&apos;s full information, or record an incident, open their page and the Health tab.
                </p>
            </div>

            <section className="space-y-3">
                <div className="flex flex-wrap items-end justify-between gap-3">
                    <h2 className="flex items-center gap-2 text-lg font-semibold">
                        <AlertTriangle className="h-5 w-5 text-rose-500" /> Students to know about
                    </h2>
                    <div className="grid w-64 gap-1.5">
                        <Label htmlFor="hr-section">Class and section</Label>
                        <select id="hr-section" className={selectClass} value={section} onChange={(e) => setSection(e.target.value)}>
                            <option value="">Whole school</option>
                            {(sections.data ?? []).map((s) => (
                                <option key={s.id} value={s.id}>{`${s.level_name} ${s.name}`}</option>
                            ))}
                        </select>
                    </div>
                </div>
                {alerts.isLoading ? (
                    <LoadingState />
                ) : !alerts.data?.length ? (
                    <EmptyState
                        title="No allergies or conditions recorded"
                        description={section ? "No student in this section has one." : "Add them from a student's Health tab."}
                    />
                ) : (
                    <TableShell>
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Student</TableHead>
                                    <TableHead>Allergies</TableHead>
                                    <TableHead>Conditions</TableHead>
                                    <TableHead>Medicines</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {alerts.data.map((a) => (
                                    <TableRow key={a.student}>
                                        <TableCell className="font-medium">
                                            <Link className="hover:underline" href={`/dashboard/students/${a.student}`}>{a.student_name}</Link>
                                        </TableCell>
                                        <TableCell className="whitespace-pre-line">{a.allergies || "—"}</TableCell>
                                        <TableCell className="whitespace-pre-line">{a.medical_conditions || "—"}</TableCell>
                                        <TableCell className="whitespace-pre-line">{a.medications || "—"}</TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableShell>
                )}
            </section>

            <section className="space-y-3">
                <div className="flex flex-wrap items-end justify-between gap-3">
                    <h2 className="text-lg font-semibold">Incident log</h2>
                    <div className="flex gap-3">
                        <div className="grid gap-1.5">
                            <Label htmlFor="hr-from">From</Label>
                            <Input id="hr-from" type="date" value={from} onChange={(e) => { setFrom(e.target.value); setPage(1); }} />
                        </div>
                        <div className="grid gap-1.5">
                            <Label htmlFor="hr-to">To</Label>
                            <Input id="hr-to" type="date" value={to} onChange={(e) => { setTo(e.target.value); setPage(1); }} />
                        </div>
                    </div>
                </div>
                {log.isLoading ? (
                    <LoadingState />
                ) : !log.data?.results.length ? (
                    <EmptyState title="No incidents" description="Incidents recorded on a student's Health tab appear here." />
                ) : (
                    <>
                        <TableShell>
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead>When</TableHead>
                                        <TableHead>Student</TableHead>
                                        <TableHead>Type</TableHead>
                                        <TableHead>What happened</TableHead>
                                        <TableHead>Follow-up</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {log.data.results.map((i) => (
                                        <TableRow key={i.id}>
                                            <TableCell className="whitespace-nowrap text-xs">
                                                {new Date(i.occurred_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
                                            </TableCell>
                                            <TableCell className="font-medium">
                                                <Link className="hover:underline" href={`/dashboard/students/${i.student}`}>{i.student_name}</Link>
                                            </TableCell>
                                            <TableCell><Badge variant="outline">{i.kind_display}</Badge></TableCell>
                                            <TableCell className="max-w-md">{i.description}</TableCell>
                                            <TableCell className="text-xs">
                                                {[i.sent_home && "Sent home", i.parent_informed ? "Parent informed" : "Parent not yet informed"]
                                                    .filter(Boolean)
                                                    .join(" · ")}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableShell>
                        <Pagination page={page} pageSize={20} count={log.data.count} onPageChange={setPage} />
                    </>
                )}
            </section>
        </div>
    );
}
