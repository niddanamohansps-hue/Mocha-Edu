"use client";

import { LoaderCircle } from "lucide-react";
import { useLinkedChildren } from "@/hooks/useParentPortal";
import { usePermissions } from "@/providers/PermissionProvider";
import { Card, CardContent } from "@/components/ui/card";
import Unauthorized from "@/components/Unauthorized";

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

    const { data: children, isLoading } = useLinkedChildren();

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
                <div className="flex items-center justify-center py-20">
                    <LoaderCircle className="h-8 w-8 animate-spin text-indigo-600" />
                </div>
            ) : !children || children.length === 0 ? (
                <div className="py-16 text-center text-sm text-slate-500">
                    No children are linked to your account yet.
                </div>
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {children.map((child) => (
                        <Card key={child.student_id} className="border-none shadow-md">
                            <CardContent className="p-5 space-y-2">
                                <div className="flex items-start justify-between">
                                    <p className="text-lg font-bold text-slate-900 dark:text-white">
                                        {child.full_name}
                                    </p>
                                    {child.is_primary_contact && (
                                        <span className="text-xs font-semibold px-2 py-1 rounded-full bg-sky-100 text-sky-700">
                                            Primary
                                        </span>
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
