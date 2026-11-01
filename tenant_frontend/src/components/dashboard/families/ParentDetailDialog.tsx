"use client";

import React, { useState } from "react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    GraduationCap,
    Phone,
    Mail,
    MapPin,
    Briefcase,
    Building2,
    Plus,
    Pencil,
    Trash2,
    Lock,
    UserCheck,
} from "lucide-react";
import { useParent, useUnlinkChild } from "@/hooks/useFamilies";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { LinkChildDialog } from "./LinkChildDialog";
import { ParentFormDialog } from "./ParentFormDialog";
import type { Parent } from "@/types/Families";

interface ParentDetailDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    parentId?: string | null;
    canEdit?: boolean;
    onActivatePortal?: (parent: Parent) => void;
}

export function ParentDetailDialog({
    open,
    onOpenChange,
    parentId,
    canEdit = false,
    onActivatePortal,
}: ParentDetailDialogProps) {
    const { data: parent, isLoading } = useParent(parentId, open);
    const { mutate: unlinkChild, isPending: isUnlinking } = useUnlinkChild();

    const [relationToUnlink, setRelationToUnlink] = useState<{
        id: number;
        studentName: string;
    } | null>(null);

    const [isLinkChildOpen, setIsLinkChildOpen] = useState(false);
    const [isEditOpen, setIsEditOpen] = useState(false);

    if (!parentId) return null;

    const profile = parent?.profile_details;
    const fullName = `${profile?.first_name || ""} ${profile?.middle_name ? profile.middle_name + " " : ""}${profile?.last_name || ""}`.trim();
    const hasAccount = Boolean(profile?.user_id);
    const children = parent?.children || [];

    return (
        <>
            <Dialog open={open} onOpenChange={onOpenChange}>
                <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto rounded-3xl">
                    <DialogHeader>
                        <div className="flex items-start justify-between gap-4">
                            <div>
                                <DialogTitle className="text-2xl font-bold flex items-center gap-2">
                                    {fullName || "Parent Details"}
                                </DialogTitle>
                                <DialogDescription className="mt-1">
                                    Overview of profile, contact channels, and enrolled children.
                                </DialogDescription>
                            </div>
                            {canEdit && parent && (
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setIsEditOpen(true)}
                                    className="rounded-xl h-9"
                                >
                                    <Pencil className="h-3.5 w-3.5 mr-1.5" />
                                    Edit
                                </Button>
                            )}
                        </div>
                    </DialogHeader>

                    {isLoading ? (
                        <div className="py-16 text-center text-slate-400">Loading parent details...</div>
                    ) : parent ? (
                        <div className="space-y-6 pt-2">
                            {/* Account Status Banner */}
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 dark:bg-slate-900/40">
                                <div className="flex items-center gap-3">
                                    <div
                                        className={`h-10 w-10 rounded-xl flex items-center justify-center shrink-0 ${
                                            hasAccount
                                                ? "bg-emerald-100 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400"
                                                : "bg-amber-100 text-amber-600 dark:bg-amber-950/60 dark:text-amber-400"
                                        }`}
                                    >
                                        {hasAccount ? <UserCheck className="h-5 w-5" /> : <Lock className="h-5 w-5" />}
                                    </div>
                                    <div>
                                        <div className="text-sm font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                                            {hasAccount ? "Portal Account Activated" : "No Portal Access"}
                                            <Badge
                                                variant="outline"
                                                className={`text-[11px] font-medium border-0 ${
                                                    hasAccount
                                                        ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300"
                                                        : "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300"
                                                }`}
                                            >
                                                {hasAccount ? "Active" : "Unenrolled"}
                                            </Badge>
                                        </div>
                                        <div className="text-xs text-slate-400">
                                            {hasAccount
                                                ? `Username: ${profile?.local_username || profile?.username || "Configured"}`
                                                : "Parent cannot log into the family portal until credentials are created."}
                                        </div>
                                    </div>
                                </div>
                                {!hasAccount && canEdit && onActivatePortal && (
                                    <Button
                                        size="sm"
                                        onClick={() => {
                                            onOpenChange(false);
                                            onActivatePortal(parent);
                                        }}
                                        className="rounded-xl shrink-0"
                                    >
                                        <Lock className="h-3.5 w-3.5 mr-1.5" />
                                        Activate Portal
                                    </Button>
                                )}
                            </div>

                            {/* Contact & Personal Info Grid */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="p-4 rounded-2xl border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3">
                                    <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                                        Contact Information
                                    </h4>
                                    <div className="space-y-2 text-sm">
                                        <div className="flex items-center gap-2.5 text-slate-700 dark:text-slate-300">
                                            <Phone className="h-4 w-4 text-slate-400 shrink-0" />
                                            <span>{profile?.phone || "No phone number"}</span>
                                        </div>
                                        <div className="flex items-center gap-2.5 text-slate-700 dark:text-slate-300">
                                            <Mail className="h-4 w-4 text-slate-400 shrink-0" />
                                            <span className="truncate">{profile?.email || "No email recorded"}</span>
                                        </div>
                                        <div className="flex items-start gap-2.5 text-slate-700 dark:text-slate-300">
                                            <MapPin className="h-4 w-4 text-slate-400 shrink-0 mt-0.5" />
                                            <span>{profile?.address || "No residential address"}</span>
                                        </div>
                                    </div>
                                </div>

                                <div className="p-4 rounded-2xl border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-3">
                                    <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                                        Employment & Details
                                    </h4>
                                    <div className="space-y-2 text-sm">
                                        <div className="flex items-center gap-2.5 text-slate-700 dark:text-slate-300">
                                            <Briefcase className="h-4 w-4 text-slate-400 shrink-0" />
                                            <span>{parent.occupation || "Not specified"}</span>
                                        </div>
                                        <div className="flex items-start gap-2.5 text-slate-700 dark:text-slate-300">
                                            <Building2 className="h-4 w-4 text-slate-400 shrink-0 mt-0.5" />
                                            <span>{parent.office_address || "No office address"}</span>
                                        </div>
                                        <div className="flex items-center gap-2.5 text-slate-700 dark:text-slate-300">
                                            <span className="text-xs text-slate-400 font-semibold uppercase">Income:</span>
                                            <span>{parent.income_level || "Not disclosed"}</span>
                                        </div>
                                        <div className="flex items-center gap-2.5 text-slate-700 dark:text-slate-300">
                                            <span className="text-xs text-slate-400 font-semibold uppercase">WhatsApp:</span>
                                            <span>
                                                {parent.whatsapp_opt_in
                                                    ? `Agreed${parent.whatsapp_opt_in_at ? ` on ${new Date(parent.whatsapp_opt_in_at).toLocaleDateString()}` : ""}`
                                                    : "Not agreed"}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Children Section */}
                            <div className="space-y-3">
                                <div className="flex items-center justify-between">
                                    <h4 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                        <GraduationCap className="h-5 w-5 text-sky-500" />
                                        Enrolled Children ({children.length})
                                    </h4>
                                    {canEdit && (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => setIsLinkChildOpen(true)}
                                            className="rounded-xl h-8 px-3 text-xs"
                                        >
                                            <Plus className="h-3.5 w-3.5 mr-1" />
                                            Link Child
                                        </Button>
                                    )}
                                </div>

                                {children.length === 0 ? (
                                    <div className="p-8 text-center rounded-2xl border border-dashed border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/30">
                                        <GraduationCap className="h-10 w-10 mx-auto text-slate-300 mb-2" />
                                        <p className="text-sm font-medium text-slate-600 dark:text-slate-400">
                                            No children currently linked to this parent.
                                        </p>
                                        <p className="text-xs text-slate-400 mt-1">
                                            Use the &quot;Link Child&quot; button to attach an enrolled student.
                                        </p>
                                    </div>
                                ) : (
                                    <div className="divide-y divide-slate-100 dark:divide-slate-800 rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden bg-white dark:bg-slate-900">
                                        {children.map((child) => (
                                            <div
                                                key={child.relation_id}
                                                className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition-colors"
                                            >
                                                <div className="flex items-center gap-3">
                                                    <div className="h-10 w-10 rounded-full bg-sky-100 dark:bg-sky-900/30 text-sky-600 flex items-center justify-center font-bold text-sm shrink-0">
                                                        {child.student?.full_name?.[0] || "S"}
                                                    </div>
                                                    <div>
                                                        <div className="font-semibold text-slate-900 dark:text-white">
                                                            {child.student?.full_name || "Unknown Student"}
                                                        </div>
                                                        <div className="text-xs text-slate-400 font-mono">
                                                            ID: {child.student?.enrollment_id}
                                                        </div>
                                                    </div>
                                                </div>

                                                <div className="flex items-center gap-2 flex-wrap">
                                                    <Badge variant="outline" className="capitalize text-xs rounded-lg">
                                                        {child.relation_type}
                                                    </Badge>
                                                    {child.is_primary && (
                                                        <Badge className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20 text-xs rounded-lg">
                                                            Primary Contact
                                                        </Badge>
                                                    )}
                                                    {child.can_pickup && (
                                                        <Badge className="bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20 text-xs rounded-lg">
                                                            Pickup Authorized
                                                        </Badge>
                                                    )}
                                                    {canEdit && (
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() =>
                                                                setRelationToUnlink({
                                                                    id: child.relation_id,
                                                                    studentName: child.student?.full_name || "this student",
                                                                })
                                                            }
                                                            className="h-8 w-8 text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/40 rounded-lg"
                                                            title="Unlink Child"
                                                        >
                                                            <Trash2 className="h-4 w-4" />
                                                        </Button>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    ) : null}

                    <DialogFooter className="pt-4">
                        <Button
                            variant="outline"
                            onClick={() => onOpenChange(false)}
                            className="rounded-xl w-full sm:w-auto"
                        >
                            Close
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Unlink Confirmation */}
            <ConfirmationDialog
                open={Boolean(relationToUnlink)}
                onOpenChange={(open) => !open && setRelationToUnlink(null)}
                title="Unlink Student?"
                description={`Are you sure you want to remove the link between ${fullName} and ${relationToUnlink?.studentName}? The student profile will remain intact.`}
                confirmLabel="Unlink Student"
                isLoading={isUnlinking}
                onConfirm={() => {
                    if (relationToUnlink) {
                        unlinkChild(relationToUnlink.id, {
                            onSuccess: () => setRelationToUnlink(null),
                        });
                    }
                }}
                contentClassName="rounded-3xl"
            />

            {/* Link Child Modal */}
            <LinkChildDialog
                open={isLinkChildOpen}
                onOpenChange={setIsLinkChildOpen}
                parentId={parent?.id}
                parentName={fullName}
            />

            {/* Edit Parent Modal */}
            {parent && (
                <ParentFormDialog
                    open={isEditOpen}
                    onOpenChange={setIsEditOpen}
                    parent={parent}
                />
            )}
        </>
    );
}

