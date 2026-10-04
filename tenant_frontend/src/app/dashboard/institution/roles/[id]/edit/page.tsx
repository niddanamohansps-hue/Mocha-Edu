"use client";

import { useRoles, useUpdateRole, usePermissionsList } from "@/hooks/useRoles";
import { usePermissions } from "@/providers/PermissionProvider";
import RoleForm from "@/components/dashboard/institution/RoleForm";
import { RoleFormData } from "@/types/roles";
import { useRouter, useParams } from "next/navigation";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import React from "react";

export default function EditRolePage() {
    const { id } = useParams();
    const { can, isOwner } = usePermissions();
    const { data: roles, isLoading: isRolesLoading, isError: rolesError, refetch: refetchRoles } = useRoles();
    const { data: permissionGroups, isLoading: isPermissionsLoading, isError: permsError, refetch: refetchPerms } = usePermissionsList();
    const { mutate: updateRole, isPending: isUpdating } = useUpdateRole();
    const router = useRouter();

    const role = roles?.find((r) => r.id === id);
    const canEdit = isOwner || can("change_role");

    if (isRolesLoading || isPermissionsLoading) {
        return <LoadingState className="h-[60vh]" />;
    }

    if (rolesError || permsError) {
        return <ErrorState onRetry={rolesError ? refetchRoles : refetchPerms} className="m-6" />;
    }

    if (!canEdit) {
        return <Unauthorized />;
    }

    if (!role) {
        return (
            <EmptyState
                title="Role not found"
                titleAs="h1"
                description="The role you are looking for does not exist or has been deleted."
                action={
                    <Button onClick={() => router.push("/dashboard/institution/roles")}>
                        Back to Roles
                    </Button>
                }
                className="h-[60vh]"
            />
        );
    }

    const handleSubmit = (data: RoleFormData) => {
        updateRole({ id: id as string, payload: data }, {
            onSuccess: () => {
                router.push("/dashboard/institution/roles");
            },
        });
    };

    return (
        <div className="max-w-7xl mx-auto py-6">
            <RoleForm
                initialData={role}
                permissionGroups={permissionGroups || []}
                onSubmit={handleSubmit}
                isSubmitting={isUpdating}
            />
        </div>
    );
}

// Helper Button import for the "not found" state
import { Button } from "@/components/ui/button";
