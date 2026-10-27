"use client";

import { useState } from "react";
import { useParents, useActivateParent } from "@/hooks/useFamilies";
import { Button } from "@/components/ui/button";
import {
    Users,
    Key,
    ShieldCheck,
    TriangleAlert,
    LoaderCircle,
    Plus,
    CircleCheck,
    Trash2,
    RefreshCw,
} from "lucide-react";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/feedback/ErrorState";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import type { Parent, ParentPortalActivationData } from "@/types/Families";

interface ParentActivationTabProps {
    onSuccess: () => void;
}

function generateUniquePassword() {
    const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%^&*";
    let password = "";
    for (let i = 0; i < 10; i++) {
        password += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return password;
}

function generateCredentials(parent: Parent): ParentPortalActivationData {
    const firstName = (parent.profile_details?.first_name || "parent").toLowerCase().replace(/[^a-z0-9]/g, "");
    const lastName = (parent.profile_details?.last_name || "").toLowerCase().replace(/[^a-z0-9]/g, "");
    const randomPin = Math.floor(1000 + Math.random() * 9000);
    const username = `p_${firstName}${lastName ? `_${lastName}` : ""}_${randomPin}`;

    return {
        parent_id: parent.id,
        username,
        password: generateUniquePassword(),
        email: parent.profile_details?.email || undefined,
    };
}

export default function ParentActivationTab({ onSuccess }: ParentActivationTabProps) {
    const { data: parentsData, isLoading: loadingParents, isError: parentsError, refetch: refetchParents } = useParents({
        pageSize: 100,
    });
    const allParents = parentsData?.results || [];
    const { mutateAsync: activatePortal, isPending } = useActivateParent();

    // Filter for parents without an active user_id
    const unactivatedParents = allParents.filter((p) => !p.profile_details?.user_id);

    const [selections, setSelections] = useState<ParentPortalActivationData[]>([]);
    const [errors, setErrors] = useState<Array<{ id: string; error: string }>>([]);

    const addParent = (parent: Parent) => {
        if (selections.find((s) => s.parent_id === parent.id)) return;
        setSelections((prev) => [...prev, generateCredentials(parent)]);
    };

    const addAllParents = () => {
        const newSelections = unactivatedParents
            .filter((p) => !selections.some((s) => s.parent_id === p.id))
            .map(generateCredentials);

        setSelections((prev) => [...prev, ...newSelections]);
    };

    const removeSelection = (parentId: string) => {
        setSelections((prev) => prev.filter((s) => s.parent_id !== parentId));
        setErrors((prev) => prev.filter((e) => e.id !== parentId));
    };

    const updateField = (parentId: string, field: keyof ParentPortalActivationData, value: string) => {
        setSelections((prev) =>
            prev.map((s) => (s.parent_id === parentId ? { ...s, [field]: value } : s))
        );
    };

    const regeneratePassword = (parentId: string) => {
        updateField(parentId, "password", generateUniquePassword());
    };

    const handleBulkActivation = async () => {
        if (selections.length === 0) return;

        setErrors([]);
        let successCount = 0;
        const newErrors: Array<{ id: string; error: string }> = [];

        for (const data of selections) {
            try {
                await activatePortal(data);
                successCount++;
            } catch (err: unknown) {
                let errorMsg = "Activation failed";
                if (typeof err === "object" && err !== null && "response" in err) {
                    const resp = (err as { response?: { data?: Record<string, unknown> | string } }).response;
                    if (typeof resp?.data === "string") errorMsg = resp.data;
                    else if (typeof resp?.data === "object" && resp.data !== null) {
                        const firstVal = Object.values(resp.data)[0];
                        if (Array.isArray(firstVal)) errorMsg = String(firstVal[0]);
                        else if (typeof firstVal === "string") errorMsg = firstVal;
                    }
                }
                newErrors.push({ id: data.parent_id, error: errorMsg });
            }
        }

        if (successCount > 0) {
            toast.success(`Successfully activated ${successCount} parent account(s)!`);
            refetchParents();
            if (newErrors.length === 0) {
                setSelections([]);
                onSuccess();
            } else {
                setSelections((prev) => prev.filter((s) => newErrors.some((e) => e.id === s.parent_id)));
                setErrors(newErrors);
            }
        } else {
            setErrors(newErrors);
            toast.error("Failed to activate selected parent accounts.");
        }
    };

    return (
        <div className="space-y-6">
            {/* Context Card */}
            <Card className="border border-slate-200 dark:border-slate-800 rounded-3xl bg-white dark:bg-slate-900 shadow-xs">
                <CardHeader className="bg-slate-50/50 dark:bg-slate-900/30 border-b border-slate-100 dark:border-slate-800 p-8">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <div className="space-y-1">
                            <CardTitle className="text-2xl font-bold flex items-center gap-2.5">
                                <Key className="h-6 w-6 text-sky-500" />
                                Parent Account Provisioning
                            </CardTitle>
                            <CardDescription className="text-base">
                                Setup login identities for parents to view student academic performance, attendance, and fee invoices.
                            </CardDescription>
                        </div>

                        {unactivatedParents.length > 0 && (
                            <Button
                                onClick={addAllParents}
                                disabled={selections.length === unactivatedParents.length}
                                variant="outline"
                                className="rounded-xl h-11 px-5 border-sky-200 dark:border-sky-800 text-sky-600 dark:text-sky-400"
                            >
                                <Plus className="h-4 w-4 mr-2" />
                                Select All ({unactivatedParents.length})
                            </Button>
                        )}
                    </div>
                </CardHeader>

                <CardContent className="p-8">
                    {/* Unactivated Parents Selector */}
                    <div className="space-y-3 mb-8">
                        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                            Unenrolled Parents ({unactivatedParents.length})
                        </h4>

                        {loadingParents ? (
                            <div className="py-8 text-center text-slate-400 flex items-center justify-center gap-2">
                                <LoaderCircle className="h-4 w-4 animate-spin" /> Loading parents...
                            </div>
                        ) : parentsError ? (
                            <ErrorState onRetry={refetchParents} className="py-6" />
                        ) : unactivatedParents.length === 0 ? (
                            <div className="p-6 rounded-2xl bg-emerald-50/60 dark:bg-emerald-950/20 border border-emerald-100 dark:border-emerald-900/30 text-emerald-700 dark:text-emerald-300 flex items-center gap-3">
                                <CircleCheck className="h-6 w-6 shrink-0" />
                                <div>
                                    <div className="font-semibold text-sm">All parents currently have portal access</div>
                                    <div className="text-xs opacity-80 mt-0.5">
                                        When new parents are registered without portal accounts, they will appear here.
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="flex flex-wrap gap-2 max-h-48 overflow-y-auto p-2 border border-slate-200 dark:border-slate-800 rounded-2xl bg-slate-50/40 dark:bg-slate-900/30">
                                {unactivatedParents.map((parent) => {
                                    const isSelected = selections.some((s) => s.parent_id === parent.id);
                                    const name = `${parent.profile_details?.first_name || ""} ${parent.profile_details?.last_name || ""}`.trim() || "Parent";
                                    return (
                                        <button
                                            key={parent.id}
                                            type="button"
                                            onClick={() => (isSelected ? removeSelection(parent.id) : addParent(parent))}
                                            className={cn(
                                                "px-3.5 py-2 rounded-xl text-xs font-semibold transition-all flex items-center gap-2 cursor-pointer border",
                                                isSelected
                                                    ? "bg-sky-600 text-white border-sky-600 shadow-xs"
                                                    : "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:border-sky-300"
                                            )}
                                        >
                                            <Users className="h-3.5 w-3.5 opacity-70" />
                                            <span>{name}</span>
                                            {parent.profile_details?.phone && (
                                                <span className="text-[10px] opacity-70 font-mono">
                                                    ({parent.profile_details.phone})
                                                </span>
                                            )}
                                        </button>
                                    );
                                })}
                            </div>
                        )}
                    </div>

                    {/* Staged Selections Table */}
                    {selections.length > 0 && (
                        <div className="space-y-4">
                            <div className="flex items-center justify-between">
                                <h4 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                    <ShieldCheck className="h-4 w-4 text-sky-500" />
                                    Staged For Account Creation ({selections.length})
                                </h4>
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setSelections([])}
                                    className="text-xs text-slate-400 hover:text-red-500"
                                >
                                    Clear all
                                </Button>
                            </div>

                            <div className="border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden">
                                <Table>
                                    <TableHeader className="bg-slate-50 dark:bg-slate-800/50">
                                        <TableRow>
                                            <TableHead className="py-3.5 pl-4">Parent Name</TableHead>
                                            <TableHead>Portal Username</TableHead>
                                            <TableHead>Temporary Password</TableHead>
                                            <TableHead>Notification Email</TableHead>
                                            <TableHead className="text-right pr-4">Action</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {selections.map((item) => {
                                            const parentObj = allParents.find((p) => p.id === item.parent_id);
                                            const name = `${parentObj?.profile_details?.first_name || ""} ${parentObj?.profile_details?.last_name || ""}`.trim();
                                            const err = errors.find((e) => e.id === item.parent_id)?.error;

                                            return (
                                                <TableRow key={item.parent_id} className={err ? "bg-red-50/40 dark:bg-red-950/20" : ""}>
                                                    <TableCell className="py-3 pl-4">
                                                        <div className="font-semibold text-sm text-slate-900 dark:text-white">
                                                            {name || "Parent"}
                                                        </div>
                                                        <div className="text-xs text-slate-400">
                                                            {parentObj?.profile_details?.phone || "No phone"}
                                                        </div>
                                                        {err && (
                                                            <div className="text-xs text-red-500 flex items-center gap-1 mt-1">
                                                                <TriangleAlert className="h-3 w-3" />
                                                                {err}
                                                            </div>
                                                        )}
                                                    </TableCell>

                                                    <TableCell>
                                                        <Input
                                                            value={item.username}
                                                            onChange={(e) => updateField(item.parent_id, "username", e.target.value)}
                                                            className="h-9 text-xs rounded-xl font-mono"
                                                        />
                                                    </TableCell>

                                                    <TableCell>
                                                        <div className="flex items-center gap-1.5">
                                                            <Input
                                                                value={item.password || ""}
                                                                onChange={(e) => updateField(item.parent_id, "password", e.target.value)}
                                                                className="h-9 text-xs rounded-xl font-mono max-w-[160px]"
                                                            />
                                                            <Button
                                                                type="button"
                                                                variant="outline"
                                                                size="icon"
                                                                onClick={() => regeneratePassword(item.parent_id)}
                                                                className="h-9 w-9 rounded-xl shrink-0 text-slate-400 hover:text-sky-500"
                                                                title="Generate new password"
                                                            >
                                                                <RefreshCw className="h-3.5 w-3.5" />
                                                            </Button>
                                                        </div>
                                                    </TableCell>

                                                    <TableCell>
                                                        <Input
                                                            value={item.email || ""}
                                                            onChange={(e) => updateField(item.parent_id, "email", e.target.value)}
                                                            placeholder="parent@example.com"
                                                            className="h-9 text-xs rounded-xl max-w-[200px]"
                                                        />
                                                    </TableCell>

                                                    <TableCell className="text-right pr-4">
                                                        <Button
                                                            type="button"
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => removeSelection(item.parent_id)}
                                                            className="h-8 w-8 text-slate-400 hover:text-red-500 rounded-lg"
                                                        >
                                                            <Trash2 className="h-4 w-4" />
                                                        </Button>
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        })}
                                    </TableBody>
                                </Table>
                            </div>

                            <div className="flex justify-end pt-2">
                                <Button
                                    onClick={handleBulkActivation}
                                    disabled={isPending || selections.length === 0}
                                    className="rounded-2xl h-12 px-8 min-w-[200px]"
                                >
                                    {isPending ? (
                                        <>
                                            <LoaderCircle className="h-4 w-4 mr-2 animate-spin" />
                                            Activating Accounts...
                                        </>
                                    ) : (
                                        `Activate ${selections.length} Parent Account(s)`
                                    )}
                                </Button>
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}

