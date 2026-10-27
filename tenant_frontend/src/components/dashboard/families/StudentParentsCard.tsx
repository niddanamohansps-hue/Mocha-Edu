"use client";

import React, { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    Users,
    UserPlus,
    Link as LinkIcon,
    Trash2,
    ShieldCheck,
    Star,
    Loader2,
} from "lucide-react";
import { useStudentParentRelations, useUnlinkChild, useLinkChild } from "@/hooks/useFamilies";
import { usePermissions } from "@/providers/PermissionProvider";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { LinkChildDialog } from "./LinkChildDialog";
import { ParentFormDialog } from "./ParentFormDialog";
import type { Parent } from "@/types/Families";

interface StudentParentsCardProps {
    studentId: string;
    studentName?: string;
}

export function StudentParentsCard({ studentId, studentName }: StudentParentsCardProps) {
    const { can, isOwner } = usePermissions();
    const canManage = isOwner || can("change_family") || can("change_student");

    const { data: relations, isLoading, refetch } = useStudentParentRelations({
        student: studentId,
    });
    const { mutate: unlinkChild, isPending: isUnlinking } = useUnlinkChild();
    const { mutate: linkChild } = useLinkChild();

    const [isLinkDialogOpen, setIsLinkDialogOpen] = useState(false);
    const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
    const [relationToUnlink, setRelationToUnlink] = useState<{
        id: number;
        parentName: string;
    } | null>(null);

    const handleParentCreated = (newParent: Parent) => {
        // Automatically link newly created parent to this student as father/mother/guardian
        linkChild(
            {
                student: studentId,
                parent: newParent.id,
                relation_type: "guardian",
                is_primary_contact: !relations || relations.length === 0,
                can_pickup: true,
            },
            {
                onSuccess: () => refetch(),
            }
        );
    };

    return (
        <Card className="rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
            <CardHeader className="bg-slate-50/50 dark:bg-slate-900/30 border-b border-slate-100 dark:border-slate-800 p-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="space-y-1">
                        <CardTitle className="text-xl font-bold flex items-center gap-2.5">
                            <Users className="h-5 w-5 text-sky-500" />
                            Parents & Guardians
                        </CardTitle>
                        <CardDescription>
                            Linked family members, primary emergency contacts, and campus pickup authorizations.
                        </CardDescription>
                    </div>

                    {canManage && (
                        <div className="flex items-center gap-2">
                            <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={() => setIsLinkDialogOpen(true)}
                                className="rounded-xl h-9"
                            >
                                <LinkIcon className="h-3.5 w-3.5 mr-1.5" />
                                Link Existing
                            </Button>
                            <Button
                                type="button"
                                size="sm"
                                onClick={() => setIsCreateDialogOpen(true)}
                                className="rounded-xl h-9"
                            >
                                <UserPlus className="h-3.5 w-3.5 mr-1.5" />
                                Add Parent
                            </Button>
                        </div>
                    )}
                </div>
            </CardHeader>

            <CardContent className="p-6">
                {isLoading ? (
                    <div className="py-10 text-center text-slate-400 flex items-center justify-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" /> Loading guardians...
                    </div>
                ) : !relations || relations.length === 0 ? (
                    <div className="py-10 text-center rounded-2xl border border-dashed border-slate-200 dark:border-slate-800 bg-slate-50/40 dark:bg-slate-900/20">
                        <Users className="h-10 w-10 mx-auto text-slate-300 mb-2" />
                        <p className="text-sm font-medium text-slate-600 dark:text-slate-400">
                            No parents or guardians linked yet.
                        </p>
                        <p className="text-xs text-slate-400 mt-1">
                            Link an existing parent profile or register a new one to enable emergency contact alerts.
                        </p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {relations.map((rel) => (
                            <div
                                key={rel.id}
                                className="p-4 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 flex flex-col justify-between gap-3 shadow-xs"
                            >
                                <div className="flex items-start justify-between gap-2">
                                    <div className="flex items-center gap-3">
                                        <div className="h-10 w-10 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 flex items-center justify-center font-bold text-sm shrink-0">
                                            {rel.parent_name?.[0] || "P"}
                                        </div>
                                        <div>
                                            <div className="font-semibold text-slate-900 dark:text-white">
                                                {rel.parent_name || "Parent Profile"}
                                            </div>
                                            <div className="flex items-center gap-1.5 mt-0.5">
                                                <Badge variant="outline" className="capitalize text-[11px] rounded-md px-1.5 py-0">
                                                    {rel.relation_type}
                                                </Badge>
                                                {rel.is_primary_contact && (
                                                    <Badge className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-0 text-[11px] rounded-md px-1.5 py-0 flex items-center gap-1">
                                                        <Star className="h-3 w-3 fill-current" /> Primary
                                                    </Badge>
                                                )}
                                                {rel.can_pickup && (
                                                    <Badge className="bg-sky-500/10 text-sky-600 dark:text-sky-400 border-0 text-[11px] rounded-md px-1.5 py-0 flex items-center gap-1">
                                                        <ShieldCheck className="h-3 w-3" /> Pickup
                                                    </Badge>
                                                )}
                                            </div>
                                        </div>
                                    </div>

                                    {canManage && (
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            size="icon"
                                            onClick={() =>
                                                setRelationToUnlink({
                                                    id: rel.id,
                                                    parentName: rel.parent_name || "this parent",
                                                })
                                            }
                                            className="h-8 w-8 text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/40 rounded-lg shrink-0"
                                            title="Unlink Parent"
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </Button>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </CardContent>

            {/* Unlink Confirmation */}
            <ConfirmationDialog
                open={Boolean(relationToUnlink)}
                onOpenChange={(open) => !open && setRelationToUnlink(null)}
                title="Unlink Parent?"
                description={`Are you sure you want to unlink ${relationToUnlink?.parentName} from ${studentName || "this student"}? The parent profile itself will not be deleted.`}
                confirmLabel="Unlink Parent"
                isLoading={isUnlinking}
                onConfirm={() => {
                    if (relationToUnlink) {
                        unlinkChild(relationToUnlink.id, {
                            onSuccess: () => {
                                setRelationToUnlink(null);
                                refetch();
                            },
                        });
                    }
                }}
                contentClassName="rounded-3xl"
            />

            {/* Link Existing Parent Modal */}
            <LinkChildDialog
                open={isLinkDialogOpen}
                onOpenChange={setIsLinkDialogOpen}
                studentId={studentId}
                studentName={studentName}
                onSuccess={() => refetch()}
            />

            {/* Create & Link Parent Modal */}
            <ParentFormDialog
                open={isCreateDialogOpen}
                onOpenChange={setIsCreateDialogOpen}
                onSuccess={handleParentCreated}
            />
        </Card>
    );
}

