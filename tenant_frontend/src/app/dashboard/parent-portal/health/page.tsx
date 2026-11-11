"use client";

import { useState } from "react";
import { HeartPulse } from "lucide-react";
import { useLinkedChildren } from "@/hooks/useParentPortal";
import { usePermissions } from "@/providers/PermissionProvider";
import Unauthorized from "@/components/Unauthorized";
import ChildSwitcher from "@/components/parent-portal/ChildSwitcher";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { StudentHealthPanel } from "@/components/dashboard/health/StudentHealthPanel";
import { StudentHostelCard } from "@/components/dashboard/hostel/StudentHostelCard";

export default function ParentHealthPage() {
    const { can } = usePermissions();
    const { data: children, isLoading } = useLinkedChildren();
    const [selectedChildId, setSelectedChildId] = useState<string | undefined>(undefined);
    if (!can("view_own_children")) return <Unauthorized />;
    const childId = selectedChildId || children?.[0]?.student_id;

    return (
        <div className="space-y-6 p-4 md:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h1 className="flex items-center gap-2 text-2xl font-bold">
                        <HeartPulse className="h-6 w-6 text-rose-500" /> Health
                    </h1>
                    <p className="mt-1 text-sm text-slate-500">
                        What the school knows about your child&apos;s health, and anything that happened at school. To change it,
                        contact the school office.
                    </p>
                </div>
                {children && children.length > 1 && (
                    <ChildSwitcher childOptions={children} selectedId={childId} onChange={setSelectedChildId} />
                )}
            </div>
            {isLoading ? (
                <LoadingState />
            ) : childId ? (
                <div key={childId} className="space-y-6">
                    <StudentHostelCard studentId={childId} />
                    <StudentHealthPanel studentId={childId} />
                </div>
            ) : (
                <EmptyState title="No children linked" description="Ask the school to link your child to your account." />
            )}
        </div>
    );
}
