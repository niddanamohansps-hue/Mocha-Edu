"use client";

import { useLinkedChildren } from "@/hooks/useParentPortal";
import { usePermissions } from "@/providers/PermissionProvider";
import { Card, CardContent } from "@/components/ui/card";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { StatusBadge } from "@/components/common/StatusBadge";

const RELATION_LABELS: Record<string, string> = {
    father: "Father",
    mother: "Mother",
    guardian: "Guardian",
    brother: "Brother",
    sister: "Sister",
    other: "Other",
};

export default function ParentPortalChildrenPage() {
    const { can, isOwner } = usePermissions();
    const canView = isOwner || can("view_own_children");

    const { data: children, isLoading, isError, refetch } = useLinkedChildren();

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">My Children</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Children linked to your account
                </p>
            </div>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState onRetry={refetch} />
            ) : !children || children.length === 0 ? (
                <EmptyState title="No children are linked to your account yet." className="py-16 text-slate-500 text-sm" />
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {children.map((child) => (
                        <Card key={child.student_id} className="border-none shadow-md">
                            <CardContent className="p-5 space-y-2">
                                <div className="flex flex-wrap items-start justify-between gap-2">
                                    <p className="text-lg font-bold text-slate-900 dark:text-white">
                                        {child.full_name}
                                    </p>
                                    {child.is_primary_contact && (
                                        <StatusBadge label="Primary" className="bg-sky-100 text-sky-700" />
                                    )}
                                </div>
                                <p className="text-xs text-slate-500">{child.enrollment_id}</p>
                                <p className="text-sm text-slate-600 dark:text-slate-300">
                                    {child.level || "—"} {child.section ? `· Section ${child.section}` : ""}
                                </p>
                                <p className="text-xs text-slate-500">
                                    Relation: {RELATION_LABELS[child.relation_type] || child.relation_type}
                                </p>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
