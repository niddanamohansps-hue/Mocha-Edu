"use client";

import { useState } from "react";
import { BookOpen, CheckCircle2, Circle, Eye, Paperclip, Plus, Users } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Pager, FormDialog, Field, SELECT_CLASS } from "@/components/dashboard/inventory/shared";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { EmptyState } from "@/components/feedback/EmptyState";
import Unauthorized from "@/components/Unauthorized";
import ChildSwitcher from "@/components/parent-portal/ChildSwitcher";
import { useLinkedChildren } from "@/hooks/useParentPortal";
import {
    Homework,
    downloadAttachment,
    useCancelHomework,
    useHomeworkList,
    useHomeworkOptions,
    useHomeworkOverview,
    useHomeworkProgress,
    useMarkHomework,
    useMyHomework,
    useSetHomework,
} from "@/hooks/useHomework";
import { usePermissions } from "@/providers/PermissionProvider";

const TEXTAREA = "w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-transparent px-3 py-2 text-sm min-h-[90px]";
const today = () => new Date().toISOString().slice(0, 10);
const nice = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });

function dueLabel(due: string) {
    const days = Math.round((new Date(due).setHours(0, 0, 0, 0) - new Date().setHours(0, 0, 0, 0)) / 86_400_000);
    if (days < 0) return { text: `Was due ${nice(due)}`, tone: "text-red-600 dark:text-red-400" };
    if (days === 0) return { text: "Due today", tone: "text-amber-600 dark:text-amber-400" };
    if (days === 1) return { text: "Due tomorrow", tone: "text-amber-600 dark:text-amber-400" };
    return { text: `Due ${nice(due)}`, tone: "text-slate-500" };
}

function Attachments({ homework, studentId }: { homework: Homework; studentId?: string }) {
    if (!homework.attachments.length) return null;
    return (
        <div className="flex flex-wrap gap-2 mt-2">
            {homework.attachments.map((a) => (
                <button key={a.id} type="button" className="inline-flex items-center gap-1 rounded-lg border border-slate-200 dark:border-slate-700 px-2 py-1 text-xs hover:bg-slate-50 dark:hover:bg-slate-800"
                    onClick={() => downloadAttachment(homework.id, a, studentId).catch(() => toast.error("Could not download the file."))}>
                    <Paperclip className="h-3 w-3" /> {a.original_name}
                </button>
            ))}
        </div>
    );
}

/* ---------- students and parents ---------- */

function Diary({ isParent }: { isParent: boolean }) {
    const { data: children = [], isLoading: loadingChildren } = useLinkedChildren();
    const [childId, setChildId] = useState<string | undefined>();
    const studentId = isParent ? childId ?? children[0]?.student_id : undefined;
    const { data, isLoading, isError, refetch } = useMyHomework(studentId, !isParent || !!studentId);
    const markHomework = useMarkHomework();

    if (isParent && loadingChildren) return <LoadingState className="py-16" />;
    if (isParent && children.length === 0) return <EmptyState title="No children are linked to your account." className="py-12 text-slate-500 text-sm" />;

    const items = data?.homework ?? [];
    const pending = items.filter((h) => !h.done_at);
    const done = items.filter((h) => h.done_at);

    return (
        <div className="space-y-5">
            {isParent && <ChildSwitcher childOptions={children} selectedId={studentId} onChange={setChildId} />}
            {isLoading ? <LoadingState className="py-16" /> : isError ? <ErrorState onRetry={refetch} /> : items.length === 0 ? (
                <EmptyState title="No homework right now." className="py-12 text-slate-500 text-sm" />
            ) : (
                <>
                    {[{ title: `To do (${pending.length})`, list: pending }, { title: `Done (${done.length})`, list: done }].map((group) => group.list.length > 0 && (
                        <div key={group.title} className="space-y-3">
                            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">{group.title}</h2>
                            {group.list.map((h) => {
                                const due = dueLabel(h.due_date);
                                return (
                                    <div key={h.id} className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 flex gap-3">
                                        <button type="button" aria-label={h.done_at ? "Mark not done" : "Mark done"} disabled={markHomework.isPending}
                                            onClick={() => markHomework.mutate({ id: h.id, student: studentId, done: !h.done_at })}
                                            className="mt-0.5 shrink-0">
                                            {h.done_at ? <CheckCircle2 className="h-6 w-6 text-emerald-600" /> : <Circle className="h-6 w-6 text-slate-300" />}
                                        </button>
                                        <div className="min-w-0 flex-1">
                                            <div className="flex flex-wrap items-baseline justify-between gap-2">
                                                <p className={`font-semibold ${h.done_at ? "text-slate-400 line-through" : "text-slate-900 dark:text-white"}`}>
                                                    <span className="text-sky-700 dark:text-sky-400">{h.subject_name}</span> · {h.title}
                                                </p>
                                                <span className={`text-xs font-medium ${h.done_at ? "text-slate-400" : due.tone}`}>{due.text}</span>
                                            </div>
                                            {h.details && <p className="text-sm text-slate-600 dark:text-slate-300 mt-1 whitespace-pre-line">{h.details}</p>}
                                            <p className="text-xs text-slate-400 mt-1">Set {nice(h.assigned_on)}{h.created_by_name ? ` by ${h.created_by_name}` : ""}</p>
                                            <Attachments homework={h} studentId={studentId} />
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    ))}
                </>
            )}
        </div>
    );
}

/* ---------- teachers and the school ---------- */

function SetHomeworkDialog({ onClose }: { onClose: () => void }) {
    const { data: options = [], isLoading } = useHomeworkOptions(true);
    const setHomework = useSetHomework();
    // One entry per class section, in the order the server gives (by class, then section).
    const sections = options.filter((o, i) => options.findIndex((x) => x.section === o.section) === i);
    const [section, setSection] = useState("");
    const [subject, setSubject] = useState("");
    const [title, setTitle] = useState("");
    const [details, setDetails] = useState("");
    const [due, setDue] = useState(() => new Date(Date.now() + 86_400_000).toISOString().slice(0, 10));
    const [files, setFiles] = useState<File[]>([]);
    const [error, setError] = useState<string | null>(null);

    return (
        <FormDialog open onOpenChange={(o) => !o && onClose()} title="Set homework"
            description="Students and parents of the class are told straight away." submitLabel="Set homework"
            pending={setHomework.isPending} error={error}
            onSubmit={() => {
                const choice = options.find((o) => o.section === section && o.subject === subject);
                if (!section) return setError("Choose the class and section.");
                if (!choice) return setError("Choose the subject.");
                if (!title.trim()) return setError("Give the homework a title.");
                if (files.length > 3) return setError("At most 3 files.");
                setError(null);
                setHomework.mutate({ section: choice.section, subject: choice.subject, title: title.trim(), details: details.trim(), due_date: due, files },
                    { onSuccess: onClose });
            }}>
            {isLoading ? <LoadingState className="py-6" /> : options.length === 0 ? (
                <p className="text-sm text-amber-700">You are not assigned to any class yet. Ask the school to assign your subjects in Academics.</p>
            ) : (
                <>
                    <Field label="Class and section" htmlFor="hw-section">
                        <select id="hw-section" className={SELECT_CLASS} value={section}
                            onChange={(e) => { setSection(e.target.value); setSubject(""); }}>
                            <option value="">Choose the class</option>
                            {sections.map((o) => <option key={o.section} value={o.section}>{o.section_name}</option>)}
                        </select>
                    </Field>
                    <Field label="Subject" htmlFor="hw-subject">
                        <select id="hw-subject" className={SELECT_CLASS} value={subject} disabled={!section}
                            onChange={(e) => setSubject(e.target.value)}>
                            <option value="">{section ? "Choose the subject" : "Choose the class first"}</option>
                            {options.filter((o) => o.section === section).map((o) => <option key={o.subject} value={o.subject}>{o.subject_name}</option>)}
                        </select>
                    </Field>
                    {section && (
                        <p className="text-xs text-slate-500 -mt-2">
                            Only students of <b>{sections.find((o) => o.section === section)?.section_name}</b> will see this homework.
                        </p>
                    )}
                    <Field label="Title" htmlFor="hw-title"><Input id="hw-title" value={title} maxLength={200} placeholder="e.g. Exercise 4.2, questions 1-10" onChange={(e) => setTitle(e.target.value)} /></Field>
                    <Field label="Details (optional)" htmlFor="hw-details"><textarea id="hw-details" className={TEXTAREA} value={details} onChange={(e) => setDetails(e.target.value)} /></Field>
                    <Field label="Due date" htmlFor="hw-due"><Input id="hw-due" type="date" min={today()} value={due} onChange={(e) => setDue(e.target.value)} /></Field>
                    <Field label="Files (optional, up to 3, 10 MB each)" htmlFor="hw-files">
                        <input id="hw-files" type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt" className="text-sm"
                            onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
                    </Field>
                </>
            )}
        </FormDialog>
    );
}

function ProgressDialog({ homework, onClose }: { homework: Homework; onClose: () => void }) {
    const { data, isLoading } = useHomeworkProgress(homework.id);
    return (
        <FormDialog open onOpenChange={(o) => !o && onClose()} title={`${homework.subject_name}: ${homework.title}`}
            description={data ? `${homework.section_name} · ${data.done} of ${data.students.length} done, ${data.seen} have seen it` : homework.section_name}
            submitLabel="Close" onSubmit={onClose} pending={false} error={null}>
            {isLoading || !data ? <LoadingState className="py-6" /> : (
                <div className="max-h-80 overflow-auto divide-y divide-slate-100 dark:divide-slate-800">
                    {data.students.map((s) => (
                        <div key={s.student} className="flex items-center justify-between py-2 text-sm">
                            <span>{s.name} <span className="text-xs text-slate-400">{s.enrollment_id}</span></span>
                            <span className={s.done_at ? "text-emerald-600" : s.seen_at ? "text-sky-600" : "text-slate-400"}>
                                {s.done_at ? "Done" : s.seen_at ? "Seen" : "Not seen"}
                            </span>
                        </div>
                    ))}
                </div>
            )}
        </FormDialog>
    );
}

function Overview() {
    const [date, setDate] = useState(today());
    const { data, isLoading } = useHomeworkOverview(date, true);
    return (
        <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
                <Input type="date" value={date} max={today()} onChange={(e) => setDate(e.target.value)} className="w-44" />
                {data && <span className="text-sm text-slate-500">{data.without_homework} of {data.sections.length} classes got no homework.</span>}
            </div>
            {isLoading || !data ? <LoadingState className="py-10" /> : (
                <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-4">
                    {data.sections.map((s) => (
                        <div key={s.section} className={`rounded-xl border px-3 py-2 text-sm ${s.homework ? "border-emerald-200 bg-emerald-50 dark:bg-emerald-500/10 dark:border-emerald-900" : "border-slate-200 dark:border-slate-800"}`}>
                            <p className="font-medium">{s.name}</p>
                            <p className="text-xs text-slate-500">{s.homework ? `${s.homework} homework` : "None"}</p>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

function StaffView({ canSet, canOverview }: { canSet: boolean; canOverview: boolean }) {
    const [tab, setTab] = useState<"list" | "overview">("list");
    const [page, setPage] = useState(1);
    const [setting, setSetting] = useState(false);
    const [showing, setShowing] = useState<Homework | null>(null);
    const { data, isLoading, isError, refetch } = useHomeworkList({ page });
    const cancel = useCancelHomework();

    return (
        <div className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
                {canOverview ? (
                    <div className="flex gap-2">
                        {(["list", "overview"] as const).map((t) => (
                            <Button key={t} size="sm" variant={tab === t ? "default" : "outline"} onClick={() => setTab(t)}>
                                {t === "list" ? "Homework" : "Classes today"}
                            </Button>
                        ))}
                    </div>
                ) : <span />}
                {canSet && <Button onClick={() => setSetting(true)}><Plus className="h-4 w-4 mr-2" /> Set homework</Button>}
            </div>

            {tab === "overview" ? <Overview /> : isLoading ? <LoadingState className="py-16" /> : isError || !data ? <ErrorState onRetry={refetch} /> : data.results.length === 0 ? (
                <EmptyState title="No homework yet." className="py-12 text-slate-500 text-sm" />
            ) : (
                <div className="space-y-3">
                    {data.results.map((h) => (
                        <div key={h.id} className={`rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-4 ${h.status === "cancelled" ? "opacity-60" : ""}`}>
                            <div className="flex flex-wrap items-start justify-between gap-3">
                                <div className="min-w-0">
                                    <p className="font-semibold text-slate-900 dark:text-white">
                                        <span className="text-sky-700 dark:text-sky-400">{h.section_name} · {h.subject_name}</span> · {h.title}
                                        {h.status === "cancelled" && <span className="ml-2 text-xs text-red-600">Cancelled</span>}
                                    </p>
                                    {h.details && <p className="text-sm text-slate-600 dark:text-slate-300 mt-1 whitespace-pre-line">{h.details}</p>}
                                    <p className="text-xs text-slate-400 mt-1">Set {nice(h.assigned_on)} · {dueLabel(h.due_date).text}{h.created_by_name ? ` · ${h.created_by_name}` : ""}</p>
                                    <Attachments homework={h} />
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    <Button size="sm" variant="outline" onClick={() => setShowing(h)}>
                                        <Users className="h-4 w-4 mr-1" /> {h.done_count ?? 0} done · <Eye className="h-4 w-4 mx-1" />{h.seen_count ?? 0}
                                    </Button>
                                    {canSet && h.status === "active" && (
                                        <Button size="sm" variant="ghost" disabled={cancel.isPending}
                                            onClick={() => window.confirm("Cancel this homework? Students will no longer see it.") && cancel.mutate(h.id)}>
                                            Cancel
                                        </Button>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}
                    <Pager data={data} page={page} onPage={setPage} />
                </div>
            )}
            {setting && <SetHomeworkDialog onClose={() => setSetting(false)} />}
            {showing && <ProgressDialog homework={showing} onClose={() => setShowing(null)} />}
        </div>
    );
}

export default function HomeworkPage() {
    const { can, isOwner, activeRole } = usePermissions();
    const staff = isOwner || can("manage_homework") || can("view_homework");
    const isParent = can("view_child_homework") && activeRole === "parent";
    const isStudent = can("view_own_homework") && activeRole === "student";
    if (!staff && !isParent && !isStudent) return <Unauthorized />;

    return (
        <div className="space-y-6 max-w-5xl">
            <div className="flex items-center gap-3">
                <BookOpen className="h-6 w-6 text-sky-600" />
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Homework</h1>
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                        {staff ? "Set homework for your classes and see who has done it." : "Homework to do, and what is already done."}
                    </p>
                </div>
            </div>
            {staff && !isParent && !isStudent
                ? <StaffView canSet={isOwner || can("manage_homework")} canOverview={isOwner || can("view_homework")} />
                : <Diary isParent={isParent} />}
        </div>
    );
}
