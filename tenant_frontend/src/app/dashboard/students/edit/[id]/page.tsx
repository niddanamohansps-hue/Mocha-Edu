"use client";

import { use, useMemo } from 'react';
import AdmissionWizard from '@/components/dashboard/students/AdmissionWizard';
import { StudentParentsCard } from '@/components/dashboard/families/StudentParentsCard';
import { usePermissions } from "@/providers/PermissionProvider";
import Unauthorized from "@/components/Unauthorized";

interface EditStudentPageProps {
    params: Promise<{ id: string }>;
}

export default function EditStudentPage({ params }: EditStudentPageProps) {
    const { can, isOwner } = usePermissions();
    // In Next 15, params is a Promise. Unwrap it with use()
    const resolvedParams = use(params);
    const { id } = resolvedParams;

    const canEdit = isOwner || can("change_student");

    if (!canEdit) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-6">
            <AdmissionWizard studentId={id} />
            <StudentParentsCard studentId={id} />
        </div>
    );
}
