"use client";

import { useCreateRole, usePermissionsList } from "@/hooks/useRoles";
import { usePermissions } from "@/providers/PermissionProvider";
import RoleForm from "@/components/dashboard/institution/RoleForm";
import { RoleFormData } from "@/types/roles";
import { useRouter } from "next/navigation";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";

export default function CreateRolePage() {
    const { can, isOwner } = usePermissions();
    const { data: permissionGroups, isLoading, isError, refetch } = usePermissionsList();
    const { mutate: createRole, isPending } = useCreateRole();
    const router = useRouter();

    const canCreate = isOwner || can("add_role");

    if (isLoading) {
        return <LoadingState className="h-[60vh]" />;
    }

    if (isError) {
        return <ErrorState onRetry={refetch} className="m-6" />;
    }

    if (!canCreate) {
        return <Unauthorized />;
    }

    const handleSubmit = (data: RoleFormData) => {
        createRole(data, {
            onSuccess: () => {
                router.push("/dashboard/institution/roles");
            },
        });
    };

    return (
        <div>
            <RoleForm
                permissionGroups={permissionGroups || []}
                onSubmit={handleSubmit}
                isSubmitting={isPending}
            />
        </div>
    );
}
