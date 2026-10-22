"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ASSET_ACTION_LABELS, AssetActionDialog, AssetFormDialog } from "@/components/dashboard/inventory/AssetDialogs";
import { AssetStatusBadge, ConditionLabel, PageHeader, formatDate, formatDateTime, formatMoney } from "@/components/dashboard/inventory/shared";
import { useAsset, useAssetAssignments, useAssetHistory, useAssetMaintenance } from "@/hooks/useInventory";
import { usePermissions } from "@/providers/PermissionProvider";
import { AssetActionName, AssetStatus } from "@/types/Inventory";

// Which actions make sense in which state, and which permission each needs (mirrors the server's rules).
const ACTIONS: { action: AssetActionName; from: AssetStatus[]; permission: string }[] = [
    { action: "assign", from: ["available"], permission: "assign_assets" },
    { action: "return", from: ["assigned"], permission: "assign_assets" },
    { action: "move", from: ["available"], permission: "assign_assets" },
    { action: "repair", from: ["available", "assigned"], permission: "manage_assets" },
    { action: "complete-repair", from: ["in_repair"], permission: "manage_assets" },
    { action: "lost", from: ["available", "assigned"], permission: "manage_assets" },
    { action: "found", from: ["lost"], permission: "manage_assets" },
    { action: "dispose", from: ["available", "lost"], permission: "manage_assets" },
];

function Detail({ label, value }: { label: string; value: React.ReactNode }) {
    return (
        <div>
            <dt className="text-xs text-slate-500">{label}</dt>
            <dd className="text-sm font-medium text-slate-800 dark:text-slate-200">{value || "-"}</dd>
        </div>
    );
}

export default function AssetDetailPage() {
    const params = useParams<{ id: string }>();
    const id = Array.isArray(params.id) ? params.id[0] : params.id;
    const { can } = usePermissions();
    const { data: asset, isLoading, isError, refetch } = useAsset(id);
    const history = useAssetHistory(id);
    const assignments = useAssetAssignments(id);
    const maintenance = useAssetMaintenance(id);
    const [action, setAction] = useState<AssetActionName | null>(null);
    const [editing, setEditing] = useState(false);

    if (!can("view_assets")) return <ErrorState message="You do not have permission to view assets." />;
    if (isLoading) return <LoadingState className="py-20" />;
    if (isError || !asset) return <ErrorState message="Could not load this asset." onRetry={refetch} />;

    const available = ACTIONS.filter((a) => a.from.includes(asset.status) && can(a.permission));

    return (
        <div className="space-y-6">
            <PageHeader
                title={asset.name}
                description={`${asset.tag} - ${asset.category_name}`}
                actions={
                    <>
                        <Button asChild variant="outline"><Link href="/dashboard/inventory/assets">Back to assets</Link></Button>
                        {can("manage_assets") && asset.status !== "disposed" && (
                            <Button variant="outline" onClick={() => setEditing(true)}>Edit details</Button>
                        )}
                    </>
                }
            />

            <div className="flex flex-wrap items-center gap-3">
                <AssetStatusBadge status={asset.status} />
                {available.map((a) => (
                    <Button key={a.action} size="sm" variant={a.action === "dispose" || a.action === "lost" ? "outline" : "default"} onClick={() => setAction(a.action)}>
                        {ASSET_ACTION_LABELS[a.action]}
                    </Button>
                ))}
            </div>

            <dl className="grid grid-cols-2 md:grid-cols-4 gap-4 rounded-2xl border border-slate-200 dark:border-slate-800 p-5">
                <Detail label="Condition" value={<ConditionLabel condition={asset.condition} />} />
                <Detail label="Kept at" value={asset.location_name} />
                <Detail
                    label="Held by"
                    value={asset.current_assignment ? asset.current_assignment.staff_name || asset.current_assignment.location_name || asset.current_assignment.note : null}
                />
                <Detail label="Serial number" value={asset.serial_number} />
                <Detail label="Supplier" value={asset.supplier_name} />
                <Detail label="Purchase date" value={asset.purchase_date ? formatDate(asset.purchase_date) : null} />
                <Detail label="Purchase cost" value={asset.purchase_cost ? formatMoney(asset.purchase_cost) : null} />
                {asset.status === "disposed" && <Detail label="Disposed" value={`${formatDate(asset.disposed_at)} - ${asset.disposal_reason}`} />}
            </dl>
            {asset.description && <p className="text-sm text-slate-600 dark:text-slate-400">{asset.description}</p>}

            <section className="grid lg:grid-cols-3 gap-6">
                <div className="space-y-2">
                    <h2 className="font-semibold">History</h2>
                    <ul className="text-xs text-slate-600 dark:text-slate-400 space-y-1.5">
                        {(history.data?.results ?? []).map((e) => (
                            <li key={e.id}>
                                <span className="font-semibold">{e.kind.replace(/_/g, " ")}</span> - {formatDateTime(e.created_at)}
                                {e.note ? ` - ${e.note}` : ""}
                            </li>
                        ))}
                        {history.data && history.data.results.length === 0 && <li>No history.</li>}
                    </ul>
                </div>
                <div className="space-y-2">
                    <h2 className="font-semibold">Assignments</h2>
                    <ul className="text-xs text-slate-600 dark:text-slate-400 space-y-1.5">
                        {(assignments.data?.results ?? []).map((a) => (
                            <li key={a.id}>
                                {a.staff_name || a.location_name || a.note || "-"} - from {formatDate(a.assigned_at)}
                                {a.returned_at ? ` to ${formatDate(a.returned_at)}` : " (current)"}
                            </li>
                        ))}
                        {assignments.data && assignments.data.results.length === 0 && <li>Never assigned.</li>}
                    </ul>
                </div>
                <div className="space-y-2">
                    <h2 className="font-semibold">Repairs</h2>
                    <ul className="text-xs text-slate-600 dark:text-slate-400 space-y-1.5">
                        {(maintenance.data?.results ?? []).map((m) => (
                            <li key={m.id}>
                                {m.reason} - {formatDate(m.opened_at)}
                                {m.closed_at ? ` to ${formatDate(m.closed_at)}` : " (open)"}
                                {m.cost ? ` - cost ${formatMoney(m.cost)}` : ""}
                            </li>
                        ))}
                        {maintenance.data && maintenance.data.results.length === 0 && <li>No repairs.</li>}
                    </ul>
                </div>
            </section>

            <AssetActionDialog asset={asset} action={action} onClose={() => setAction(null)} />
            <AssetFormDialog asset={asset} open={editing} onClose={() => setEditing(false)} />
        </div>
    );
}
