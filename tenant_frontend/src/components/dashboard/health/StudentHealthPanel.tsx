"use client";

import { useState } from "react";
import { AlertTriangle, HeartPulse, LoaderCircle, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/feedback/EmptyState";
import { LoadingState } from "@/components/feedback/LoadingState";
import {
    HealthProfile,
    INCIDENT_KINDS,
    IncidentKind,
    useRecordIncident,
    useSaveHealthProfile,
    useStudentHealth,
    useUpdateIncident,
} from "@/hooks/useHealth";

const selectClass =
    "h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";

const FIELDS: { key: keyof HealthProfile; label: string; long?: boolean; placeholder?: string }[] = [
    { key: "allergies", label: "Allergies", long: true, placeholder: "Peanuts (severe, carries an EpiPen)" },
    { key: "medical_conditions", label: "Medical conditions", long: true, placeholder: "Asthma, uses an inhaler" },
    { key: "medications", label: "Regular medicines", long: true },
    { key: "dietary_notes", label: "Diet", long: true },
    { key: "doctor_name", label: "Family doctor" },
    { key: "doctor_phone", label: "Doctor's phone" },
    { key: "notes", label: "Other notes", long: true },
];

const when = (iso: string) =>
    new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });

/** A student's health information and incidents. Editable only with manage_health_records. */
export function StudentHealthPanel({ studentId }: { studentId: string }) {
    const { data, isLoading, isError } = useStudentHealth(studentId);
    const [editing, setEditing] = useState(false);
    const [recording, setRecording] = useState(false);

    if (isLoading) return <LoadingState />;
    if (isError || !data) return <EmptyState title="Health information is not available" description="You may not have access to health records." />;
    const p = data.profile;

    return (
        <div className="space-y-6">
            {p.has_alert && (
                <div role="alert" className="flex gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800 dark:border-rose-900 dark:bg-rose-950/40 dark:text-rose-200">
                    <AlertTriangle className="h-5 w-5 shrink-0" />
                    <div>
                        {p.allergies && <p><strong>Allergies:</strong> {p.allergies}</p>}
                        {p.medical_conditions && <p><strong>Conditions:</strong> {p.medical_conditions}</p>}
                    </div>
                </div>
            )}

            <section className="rounded-xl border border-slate-200 p-5 dark:border-slate-800">
                <div className="mb-4 flex items-center justify-between">
                    <h3 className="flex items-center gap-2 font-semibold"><HeartPulse className="h-4 w-4 text-rose-500" /> Health information</h3>
                    {data.can_manage && !editing && <Button variant="outline" size="sm" onClick={() => setEditing(true)}>Edit</Button>}
                </div>
                {editing ? (
                    <ProfileForm studentId={studentId} profile={p} onDone={() => setEditing(false)} />
                ) : (
                    <dl className="grid gap-4 text-sm md:grid-cols-2">
                        <Item label="Blood group" value={p.blood_group} />
                        {FIELDS.map((f) => <Item key={f.key} label={f.label} value={String(p[f.key] ?? "")} />)}
                    </dl>
                )}
            </section>

            <section className="rounded-xl border border-slate-200 p-5 dark:border-slate-800">
                <div className="mb-4 flex items-center justify-between">
                    <h3 className="font-semibold">Incidents at school</h3>
                    {data.can_manage && !recording && (
                        <Button size="sm" onClick={() => setRecording(true)}><Plus className="h-4 w-4" /> Record incident</Button>
                    )}
                </div>
                {recording && <IncidentForm studentId={studentId} onDone={() => setRecording(false)} />}
                {data.incidents.length === 0 ? (
                    <p className="text-sm text-slate-500">No incidents recorded.</p>
                ) : (
                    <ul className="space-y-3">
                        {data.incidents.map((i) => <IncidentRow key={i.id} incident={i} canManage={data.can_manage} />)}
                    </ul>
                )}
            </section>
        </div>
    );
}

function Item({ label, value }: { label: string; value: string }) {
    return (
        <div>
            <dt className="text-xs text-slate-500">{label}</dt>
            <dd className="mt-0.5 whitespace-pre-line">{value || <span className="text-slate-400">Not given</span>}</dd>
        </div>
    );
}

function ProfileForm({ studentId, profile, onDone }: { studentId: string; profile: HealthProfile; onDone: () => void }) {
    const save = useSaveHealthProfile(studentId);
    const [form, setForm] = useState(() => Object.fromEntries(FIELDS.map((f) => [f.key, String(profile[f.key] ?? "")])));
    return (
        <form
            className="space-y-4"
            onSubmit={(e) => { e.preventDefault(); save.mutate(form, { onSuccess: onDone }); }}
        >
            <div className="grid gap-4 md:grid-cols-2">
                {FIELDS.map((f) => (
                    <div key={f.key} className="grid gap-1.5">
                        <Label htmlFor={`hp-${f.key}`}>{f.label}</Label>
                        {f.long ? (
                            <Textarea id={`hp-${f.key}`} rows={2} value={form[f.key]} placeholder={f.placeholder} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} />
                        ) : (
                            <Input id={`hp-${f.key}`} value={form[f.key]} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} />
                        )}
                    </div>
                ))}
            </div>
            <p className="text-xs text-slate-500">Blood group is set on the student&apos;s personal details.</p>
            <div className="flex gap-2">
                <Button type="submit" disabled={save.isPending}>{save.isPending && <LoaderCircle className="h-4 w-4 animate-spin" />} Save</Button>
                <Button type="button" variant="outline" onClick={onDone}>Cancel</Button>
            </div>
        </form>
    );
}

function nowLocal() {
    const d = new Date();
    d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
    return d.toISOString().slice(0, 16);
}

function IncidentForm({ studentId, onDone }: { studentId: string; onDone: () => void }) {
    const record = useRecordIncident(studentId);
    const [form, setForm] = useState({
        occurred_at: nowLocal(), kind: "illness" as IncidentKind, description: "", action_taken: "", sent_home: false, parent_informed: false,
    });
    return (
        <form
            className="mb-5 space-y-4 rounded-lg bg-slate-50 p-4 dark:bg-slate-900"
            onSubmit={(e) => {
                e.preventDefault();
                record.mutate({ ...form, occurred_at: new Date(form.occurred_at).toISOString() }, { onSuccess: onDone });
            }}
        >
            <div className="grid gap-4 md:grid-cols-2">
                <div className="grid gap-1.5">
                    <Label htmlFor="inc-when">When</Label>
                    <Input id="inc-when" type="datetime-local" value={form.occurred_at} onChange={(e) => setForm({ ...form, occurred_at: e.target.value })} />
                </div>
                <div className="grid gap-1.5">
                    <Label htmlFor="inc-kind">Type</Label>
                    <select id="inc-kind" className={selectClass} value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as IncidentKind })}>
                        {INCIDENT_KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
                    </select>
                </div>
            </div>
            <div className="grid gap-1.5">
                <Label htmlFor="inc-what">What happened</Label>
                <Textarea id="inc-what" rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
            <div className="grid gap-1.5">
                <Label htmlFor="inc-action">What was done</Label>
                <Textarea id="inc-action" rows={2} value={form.action_taken} onChange={(e) => setForm({ ...form, action_taken: e.target.value })} />
            </div>
            <div className="flex flex-wrap gap-6 text-sm">
                <label className="flex items-center gap-2"><input type="checkbox" checked={form.sent_home} onChange={(e) => setForm({ ...form, sent_home: e.target.checked })} /> Sent home</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={form.parent_informed} onChange={(e) => setForm({ ...form, parent_informed: e.target.checked })} /> Parent informed</label>
            </div>
            <div className="flex gap-2">
                <Button type="submit" disabled={!form.description.trim() || record.isPending}>{record.isPending && <LoaderCircle className="h-4 w-4 animate-spin" />} Save incident</Button>
                <Button type="button" variant="outline" onClick={onDone}>Cancel</Button>
            </div>
        </form>
    );
}

function IncidentRow({ incident: i, canManage }: { incident: import("@/hooks/useHealth").HealthIncident; canManage: boolean }) {
    const update = useUpdateIncident();
    return (
        <li className="rounded-lg border border-slate-100 p-3 text-sm dark:border-slate-800">
            <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{i.kind_display}</Badge>
                <span className="text-xs text-slate-500">{when(i.occurred_at)}{i.recorded_by_name ? ` · ${i.recorded_by_name}` : ""}</span>
                {i.sent_home && <Badge variant="outline">Sent home</Badge>}
                {i.parent_informed ? (
                    <Badge variant="outline">Parent informed</Badge>
                ) : canManage ? (
                    <Button variant="outline" size="sm" className="h-6 text-xs" disabled={update.isPending} onClick={() => update.mutate({ id: i.id, parent_informed: true })}>
                        Mark parent informed
                    </Button>
                ) : null}
            </div>
            <p className="mt-2">{i.description}</p>
            {i.action_taken && <p className="mt-1 text-slate-500">Action: {i.action_taken}</p>}
        </li>
    );
}
