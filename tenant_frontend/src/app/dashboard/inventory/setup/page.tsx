"use client";

import { ConfigSection } from "@/components/dashboard/inventory/ConfigSection";
import { PageHeader } from "@/components/dashboard/inventory/shared";
import { ErrorState } from "@/components/feedback/ErrorState";
import { useLowStockAlertSetting, useUpdateLowStockAlertSetting } from "@/hooks/useInventory";
import { usePermissions } from "@/providers/PermissionProvider";

function LowStockAlertCard() {
    const { can } = usePermissions();
    const canManage = can("manage_notification_settings");
    const { data, isLoading, isError } = useLowStockAlertSetting(canManage);
    const update = useUpdateLowStockAlertSetting();
    if (!canManage) return null;
    return (
        <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-2">
            <h2 className="font-semibold text-slate-900 dark:text-white">Low-stock alerts</h2>
            <p className="text-xs text-slate-500">
                When an item&apos;s total falls to its reorder level, the owner and the people who can restock are notified once, in the app and by email.
            </p>
            {isError ? (
                <p className="text-sm text-red-600">Could not load the setting.</p>
            ) : (
                <label className="flex items-center gap-2 text-sm">
                    <input
                        type="checkbox"
                        disabled={isLoading || update.isPending}
                        checked={data?.low_stock_alerts_enabled ?? false}
                        onChange={(e) => update.mutate(e.target.checked)}
                    />
                    Send low-stock alerts
                </label>
            )}
        </section>
    );
}

export default function InventorySetupPage() {
    const { can } = usePermissions();
    if (!can("view_inventory")) return <ErrorState message="You do not have permission to view the inventory setup." />;
    const manageStock = can("manage_inventory_items");
    const manageAssets = can("manage_assets");

    return (
        <div className="space-y-6">
            <PageHeader title="Setup" description="The lists the rest of the inventory is built from." />
            <div className="grid lg:grid-cols-2 gap-6">
                <ConfigSection
                    resource="categories"
                    title="Item categories"
                    hint="Groups for stock items, e.g. Stationery or Cleaning."
                    fields={[{ name: "name", label: "Name", required: true, maxLength: 100 }, { name: "description", label: "Description", maxLength: 255 }]}
                    summary={(row) => String(row.description ?? "")}
                    canManage={manageStock}
                />
                <ConfigSection
                    resource="locations"
                    title="Stock locations"
                    hint="Stores, cupboards or rooms where stock is kept."
                    fields={[{ name: "name", label: "Name", required: true, maxLength: 100 }, { name: "description", label: "Description", maxLength: 255 }]}
                    summary={(row) => String(row.description ?? "")}
                    canManage={manageStock}
                    hasActive
                />
                <ConfigSection
                    resource="suppliers"
                    title="Suppliers"
                    hint="Who you buy from. Used when recording purchases and registering assets."
                    fields={[
                        { name: "name", label: "Name", required: true, maxLength: 200 },
                        { name: "contact_name", label: "Contact person", maxLength: 150 },
                        { name: "phone", label: "Phone", maxLength: 30 },
                        { name: "email", label: "Email", type: "email" },
                    ]}
                    summary={(row) => [row.contact_name, row.phone].filter(Boolean).join(" - ")}
                    canManage={manageStock}
                    hasActive
                />
                {can("view_assets") && (
                    <ConfigSection
                        resource="asset-categories"
                        title="Asset categories"
                        hint="Groups for assets, e.g. Computers or Furniture."
                        fields={[{ name: "name", label: "Name", required: true, maxLength: 100 }, { name: "description", label: "Description", maxLength: 255 }]}
                        summary={(row) => String(row.description ?? "")}
                        canManage={manageAssets}
                    />
                )}
            </div>
            <LowStockAlertCard />
        </div>
    );
}
