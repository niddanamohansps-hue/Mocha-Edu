"use client";

import { useState } from "react";
import { BadgePercent, LoaderCircle, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import { StudentPicker } from "@/components/common/StudentPicker";
import Unauthorized from "@/components/Unauthorized";
import { EmptyState } from "@/components/feedback/EmptyState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { usePermissions } from "@/providers/PermissionProvider";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { useFeeHeads } from "@/hooks/useFees";
import type { Student } from "@/hooks/useStudents";
import { formatIndianCurrency } from "@/lib/currency";
import {
    ConcessionKind,
    ConcessionType,
    useConcessionTypes,
    useGrantConcession,
    useSaveConcessionType,
    useSetConcessionActive,
    useStudentConcessions,
} from "@/hooks/useFeeCharging";

const selectClass =
    "h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";

const describe = (t: { kind: ConcessionKind; value: string }) =>
    t.kind === "percent" ? `${Number(t.value)}% off` : `${formatIndianCurrency(t.value)} off`;

export default function ConcessionsPage() {
    const { can } = usePermissions();
    const canManage = can("manage_fee_structures");
    const { selectedYear } = useAcademicYear();
    const academicYear = selectedYear?.name || "";
    const types = useConcessionTypes();
    const grants = useStudentConcessions(academicYear);
    if (!canManage && !can("view_fees")) return <Unauthorized />;

    return (
        <div className="space-y-8 p-4 md:p-6">
            <div>
                <h1 className="text-2xl font-bold flex items-center gap-2">
                    <BadgePercent className="h-6 w-6 text-sky-600" /> Concessions &amp; Scholarships
                </h1>
                <p className="mt-1 max-w-3xl text-sm text-slate-500">
                    Set up the concessions your school gives, such as a sibling discount or a merit scholarship, then give them to
                    students. A concession is taken off automatically when a fee structure is charged to the student&apos;s class.
                    Fees already charged keep their amounts.
                </p>
            </div>

            <section className="space-y-3">
                <h2 className="text-lg font-semibold">Concession types</h2>
                {canManage && <NewTypeForm />}
                {types.isLoading ? (
                    <LoadingState />
                ) : !types.data?.length ? (
                    <EmptyState title="No concessions set up yet" description="Add one above, for example Sibling at 10%." />
                ) : (
                    <TableShell>
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Name</TableHead>
                                    <TableHead>Discount</TableHead>
                                    <TableHead>Applies to</TableHead>
                                    <TableHead>Status</TableHead>
                                    {canManage && <TableHead className="text-right">Action</TableHead>}
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {types.data.map((t) => <TypeRow key={t.id} type={t} canManage={canManage} />)}
                            </TableBody>
                        </Table>
                    </TableShell>
                )}
            </section>

            <section className="space-y-3">
                <h2 className="text-lg font-semibold">Given for {academicYear}</h2>
                {canManage && academicYear && <GrantForm academicYear={academicYear} types={(types.data ?? []).filter((t) => t.is_active)} />}
                <GrantList canManage={canManage} loading={grants.isLoading} rows={grants.data ?? []} />
            </section>
        </div>
    );
}

function NewTypeForm() {
    const heads = useFeeHeads();
    const save = useSaveConcessionType();
    const [form, setForm] = useState({ name: "", kind: "percent" as ConcessionKind, value: "", fee_head: "" });
    return (
        <form
            className="grid gap-3 rounded-xl border border-slate-200 p-4 dark:border-slate-800 md:grid-cols-[2fr_1fr_1fr_1.5fr_auto] md:items-end"
            onSubmit={(e) => {
                e.preventDefault();
                save.mutate(
                    { name: form.name.trim(), kind: form.kind, value: form.value, fee_head: form.fee_head || null },
                    { onSuccess: () => setForm({ name: "", kind: "percent", value: "", fee_head: "" }) },
                );
            }}
        >
            <div className="grid gap-1.5">
                <Label htmlFor="ct-name">Name</Label>
                <Input id="ct-name" value={form.name} placeholder="Sibling discount" onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="grid gap-1.5">
                <Label htmlFor="ct-kind">Type</Label>
                <select id="ct-kind" className={selectClass} value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as ConcessionKind })}>
                    <option value="percent">Percentage</option>
                    <option value="fixed">Fixed amount (₹)</option>
                </select>
            </div>
            <div className="grid gap-1.5">
                <Label htmlFor="ct-value">{form.kind === "percent" ? "Percent" : "Amount (₹)"}</Label>
                <Input id="ct-value" type="number" inputMode="decimal" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} />
            </div>
            <div className="grid gap-1.5">
                <Label htmlFor="ct-head">Fee head</Label>
                <select id="ct-head" className={selectClass} value={form.fee_head} onChange={(e) => setForm({ ...form, fee_head: e.target.value })}>
                    <option value="">Every fee head</option>
                    {(heads.data ?? []).map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
                </select>
            </div>
            <Button type="submit" disabled={!form.name.trim() || !(Number(form.value) > 0) || save.isPending}>
                {save.isPending ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Add
            </Button>
        </form>
    );
}

function TypeRow({ type, canManage }: { type: ConcessionType; canManage: boolean }) {
    const save = useSaveConcessionType();
    return (
        <TableRow>
            <TableCell className="font-medium">{type.name}</TableCell>
            <TableCell>{describe(type)}</TableCell>
            <TableCell>{type.fee_head_name || "Every fee head"}</TableCell>
            <TableCell><Badge variant={type.is_active ? "default" : "outline"}>{type.is_active ? "In use" : "Switched off"}</Badge></TableCell>
            {canManage && (
                <TableCell className="text-right">
                    <Button variant="outline" size="sm" disabled={save.isPending} onClick={() => save.mutate({ id: type.id, is_active: !type.is_active })}>
                        {type.is_active ? "Switch off" : "Switch on"}
                    </Button>
                </TableCell>
            )}
        </TableRow>
    );
}

function GrantForm({ academicYear, types }: { academicYear: string; types: ConcessionType[] }) {
    const grant = useGrantConcession();
    const [student, setStudent] = useState<Student | null>(null);
    const [typeId, setTypeId] = useState("");
    const [note, setNote] = useState("");
    return (
        <form
            className="grid gap-3 rounded-xl border border-slate-200 p-4 dark:border-slate-800 md:grid-cols-[2fr_1.5fr_2fr_auto] md:items-end"
            onSubmit={(e) => {
                e.preventDefault();
                if (!student) return;
                grant.mutate(
                    { student: student.id, concession_type: typeId, academic_year: academicYear, note: note.trim() },
                    { onSuccess: () => { setStudent(null); setTypeId(""); setNote(""); } },
                );
            }}
        >
            <div className="grid gap-1.5">
                <Label htmlFor="cg-student">Student</Label>
                <StudentPicker id="cg-student" value={student} onChange={setStudent} />
            </div>
            <div className="grid gap-1.5">
                <Label htmlFor="cg-type">Concession</Label>
                <select id="cg-type" className={selectClass} value={typeId} onChange={(e) => setTypeId(e.target.value)}>
                    <option value="">Choose</option>
                    {types.map((t) => <option key={t.id} value={t.id}>{t.name} ({describe(t)})</option>)}
                </select>
            </div>
            <div className="grid gap-1.5">
                <Label htmlFor="cg-note">Reason</Label>
                <Input id="cg-note" value={note} placeholder="Elder brother in Class 7" onChange={(e) => setNote(e.target.value)} />
            </div>
            <Button type="submit" disabled={!student || !typeId || grant.isPending}>
                {grant.isPending && <LoaderCircle className="h-4 w-4 animate-spin" />} Give
            </Button>
        </form>
    );
}

function GrantList({ rows, loading, canManage }: { rows: ReturnType<typeof useStudentConcessions>["data"] & object; loading: boolean; canManage: boolean }) {
    const setActive = useSetConcessionActive();
    if (loading) return <LoadingState />;
    if (!rows.length) return <EmptyState title="No concessions given this year" description="Give one above; it applies to fees charged afterwards." />;
    return (
        <TableShell>
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead>Student</TableHead>
                        <TableHead>Concession</TableHead>
                        <TableHead>Reason</TableHead>
                        <TableHead>Status</TableHead>
                        {canManage && <TableHead className="text-right">Action</TableHead>}
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {rows.map((g) => (
                        <TableRow key={g.id}>
                            <TableCell className="font-medium">{g.student_name}</TableCell>
                            <TableCell>{g.concession_name} · {describe(g)}</TableCell>
                            <TableCell className="text-slate-500">{g.note || "—"}</TableCell>
                            <TableCell><Badge variant={g.is_active ? "default" : "outline"}>{g.is_active ? "Active" : "Withdrawn"}</Badge></TableCell>
                            {canManage && (
                                <TableCell className="text-right">
                                    <Button variant="outline" size="sm" disabled={setActive.isPending} onClick={() => setActive.mutate({ id: g.id, is_active: !g.is_active })}>
                                        {g.is_active ? "Withdraw" : "Restore"}
                                    </Button>
                                </TableCell>
                            )}
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </TableShell>
    );
}
