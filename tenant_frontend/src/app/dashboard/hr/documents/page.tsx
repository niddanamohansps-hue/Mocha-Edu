"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import {
    openDocumentFile,
    useAddDocumentType,
    useAddMemberDocument,
    useChecklistOverview,
    useDocumentTypes,
    useMemberDocuments,
    useUpdateDocumentItem,
    useUpdateDocumentType,
    useUploadDocumentFile,
} from "@/hooks/useStaffDocuments";
import { usePermissions } from "@/providers/PermissionProvider";
import type { ChecklistRow, DocumentItem } from "@/types/StaffDocuments";

const STATUS_LABEL = { pending: "Pending", received: "Received", waived: "Not needed" } as const;

export default function StaffDocumentsPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("view_staff")) return <Unauthorized />;
    return <Content canEdit={isOwner || can("change_staff")} />;
}

function Content({ canEdit }: { canEdit: boolean }) {
    const [outstanding, setOutstanding] = useState(true);
    const overview = useChecklistOverview(outstanding);
    const [openStaff, setOpenStaff] = useState<ChecklistRow | null>(null);

    return (
        <div className="max-w-5xl mx-auto space-y-8">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Joining documents</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    The documents every new staff member must hand in. Hiring someone through Recruitment starts their checklist
                    from the standard list below.
                </p>
            </div>

            {canEdit && <StandardList />}

            <section className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                    <h2 className="text-lg font-semibold">Staff checklists</h2>
                    <label className="flex items-center gap-2 text-sm">
                        <input type="checkbox" checked={outstanding} onChange={(e) => setOutstanding(e.target.checked)} />
                        Only staff with documents still to come
                    </label>
                </div>
                {overview.isLoading ? (
                    <LoadingState />
                ) : (overview.data ?? []).length === 0 ? (
                    <EmptyState
                        title={outstanding ? "Nobody is owing documents" : "No checklists yet"}
                        description="A checklist starts when you hire someone, or from a staff member's row once the standard list is set."
                    />
                ) : (
                    <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900">
                        {(overview.data ?? []).map((row) => (
                            <li key={row.staff} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                                <span>
                                    <span className="font-medium">{row.name}</span>{" "}
                                    <span className="text-xs text-slate-400">{row.employee_id}, {row.designation}</span>
                                </span>
                                <span className="flex items-center gap-2">
                                    {row.pending > 0 ? <Badge variant="destructive">{row.pending} to come</Badge> : <Badge>Complete</Badge>}
                                    <span className="text-xs text-slate-500">{row.received} of {row.total} received</span>
                                    <Button size="sm" variant="outline" onClick={() => setOpenStaff(row)}>Open</Button>
                                </span>
                            </li>
                        ))}
                    </ul>
                )}
            </section>

            {openStaff && <MemberDialog staff={openStaff} canEdit={canEdit} onClose={() => setOpenStaff(null)} />}
        </div>
    );
}

function StandardList() {
    const types = useDocumentTypes();
    const add = useAddDocumentType();
    const update = useUpdateDocumentType();
    const [name, setName] = useState("");
    return (
        <section className="space-y-3">
            <h2 className="text-lg font-semibold">Standard list</h2>
            <p className="text-xs text-slate-500">New hires get one pending item for each active document here. Turning one off does not remove it from existing checklists.</p>
            <div className="flex flex-wrap gap-2">
                {(types.data ?? []).map((t) => (
                    <button
                        key={t.id} type="button" disabled={update.isPending}
                        onClick={() => update.mutate({ id: t.id, is_active: !t.is_active })}
                        className={`rounded-full border px-3 py-1 text-sm ${t.is_active ? "border-indigo-300 bg-indigo-50 text-indigo-800" : "border-slate-200 text-slate-400 line-through"}`}
                        title={t.is_active ? "Click to turn off" : "Click to turn on"}
                    >
                        {t.name}
                    </button>
                ))}
                {(types.data ?? []).length === 0 && <span className="text-sm text-slate-500">Nothing yet. Add the documents you ask for, such as Aadhaar card or Degree certificate.</span>}
            </div>
            <div className="flex gap-2">
                <Input className="max-w-xs" placeholder="Add a document" value={name} onChange={(e) => setName(e.target.value)} />
                <Button disabled={!name.trim() || add.isPending} onClick={() => add.mutate(name, { onSuccess: () => setName("") })}>Add</Button>
            </div>
        </section>
    );
}

function MemberDialog({ staff, canEdit, onClose }: { staff: ChecklistRow; canEdit: boolean; onClose: () => void }) {
    const items = useMemberDocuments(staff.staff);
    const add = useAddMemberDocument();
    const [extra, setExtra] = useState("");
    return (
        <Dialog open onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>{staff.name}: joining documents</DialogTitle>
                </DialogHeader>
                {items.isLoading ? <LoadingState /> : (
                    <ul className="space-y-2">
                        {(items.data ?? []).map((item) => <Row key={item.id} item={item} canEdit={canEdit} />)}
                    </ul>
                )}
                {canEdit && (
                    <div className="space-y-2 border-t border-slate-100 pt-3 dark:border-slate-800">
                        <div className="flex gap-2">
                            <Input placeholder="Add a one-off document" value={extra} onChange={(e) => setExtra(e.target.value)} />
                            <Button
                                disabled={!extra.trim() || add.isPending}
                                onClick={() => add.mutate({ staff: staff.staff, name: extra }, { onSuccess: () => setExtra("") })}
                            >
                                Add
                            </Button>
                        </div>
                        <Button size="sm" variant="outline" disabled={add.isPending} onClick={() => add.mutate({ staff: staff.staff })}>
                            Add any missing standard documents
                        </Button>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}

function Row({ item, canEdit }: { item: DocumentItem; canEdit: boolean }) {
    const update = useUpdateDocumentItem();
    const upload = useUploadDocumentFile();
    return (
        <li className="space-y-2 rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-800">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-medium">{item.name}</span>
                <Badge variant={item.status === "received" ? "default" : item.status === "waived" ? "secondary" : "outline"}>
                    {STATUS_LABEL[item.status]}{item.received_on ? `, ${item.received_on}` : ""}
                </Badge>
            </div>
            {item.note && <p className="text-xs text-slate-500">{item.note}</p>}
            <div className="flex flex-wrap items-center gap-2">
                {item.has_file && <Button size="sm" variant="outline" onClick={() => openDocumentFile(item.id)}>View file</Button>}
                {canEdit && (
                    <>
                        {item.status !== "received" && (
                            <Button size="sm" disabled={update.isPending} onClick={() => update.mutate({ id: item.id, status: "received" })}>
                                Mark received
                            </Button>
                        )}
                        {item.status !== "waived" && (
                            <Button
                                size="sm" variant="ghost" disabled={update.isPending}
                                onClick={() => {
                                    const note = window.prompt(`Why is "${item.name}" not needed?`);
                                    if (note && note.trim()) update.mutate({ id: item.id, status: "waived", note: note.trim() });
                                }}
                            >
                                Not needed
                            </Button>
                        )}
                        {item.status !== "pending" && (
                            <Button size="sm" variant="ghost" disabled={update.isPending} onClick={() => update.mutate({ id: item.id, status: "pending" })}>
                                Back to pending
                            </Button>
                        )}
                        <label className="cursor-pointer text-xs text-indigo-700 underline">
                            {upload.isPending ? "Uploading..." : item.has_file ? "Replace file" : "Attach scan"}
                            <input
                                type="file" accept=".pdf,.jpg,.jpeg,.png" className="hidden"
                                onChange={(e) => { const file = e.target.files?.[0]; if (file) upload.mutate({ id: item.id, file }); e.target.value = ""; }}
                            />
                        </label>
                    </>
                )}
            </div>
        </li>
    );
}
