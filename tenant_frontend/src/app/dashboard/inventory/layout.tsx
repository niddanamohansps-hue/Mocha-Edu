"use client";

import { ReactNode } from "react";
import { ErrorState } from "@/components/feedback/ErrorState";
import { InventoryNav } from "@/components/dashboard/inventory/shared";
import { usePermissions } from "@/providers/PermissionProvider";

export default function InventoryLayout({ children }: { children: ReactNode }) {
    const { can } = usePermissions();
    if (!can("view_inventory") && !can("view_assets")) {
        return <ErrorState message="You do not have permission to view the inventory." />;
    }
    return (
        <div className="space-y-6">
            <InventoryNav />
            {children}
        </div>
    );
}
