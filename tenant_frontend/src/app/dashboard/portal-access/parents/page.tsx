"use client";

import { usePermissions } from "@/providers/PermissionProvider";
import Unauthorized from "@/components/Unauthorized";
import ParentPortalActivationManager from "@/components/dashboard/families/portal-activation/ParentPortalActivationManager";

export default function CentralParentPortalPage() {
    const { can, isOwner } = usePermissions();

    const canManage = isOwner || can("change_family");

    if (!canManage) {
        return <Unauthorized />;
    }

    return (
        <ParentPortalActivationManager />
    );
}

