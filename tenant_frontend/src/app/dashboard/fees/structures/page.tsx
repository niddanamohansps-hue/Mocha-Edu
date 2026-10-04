"use client";

import { useState } from "react";
import { LoaderCircle, Plus } from "lucide-react";
import {
    useCreateFeeHead,
    useCreateFeeStructure,
    useFeeHeads,
    useFeeStructures,
} from "@/hooks/useFees";
import { FEE_FREQUENCY_CHOICES } from "@/types/Fees";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import Unauthorized from "@/components/Unauthorized";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { StatusBadge } from "@/components/common/StatusBadge";

function currentYear() {
    return String(new Date().getFullYear());
}

export default function FeeStructuresPage() {
    const { can, isOwner } = usePermissions();
    const canManage = isOwner || can("manage_fee_structures");
    const canView = canManage || can("view_fees");

    const [academicYear, setAcademicYear] = useState(currentYear());
    const { data: heads, isLoading: loadingHeads, isError: headsError, refetch: refetchHeads } = useFeeHeads();
    const { data: structures, isLoading: loadingStructures, isError: structuresError, refetch: refetchStructures } = useFeeStructures(academicYear);

    const { mutate: createHead, isPending: creatingHead } = useCreateFeeHead();
    const { mutate: createStructure, isPending: creatingStructure } = useCreateFeeStructure();

    const [newHeadName, setNewHeadName] = useState("");
    const [form, setForm] = useState({ fee_head: "", amount: "", frequency: "one_time", due_date: "" });

    const handleCreateHead = () => {
        createHead({ name: newHeadName }, { onSuccess: () => setNewHeadName("") });
    };

    const handleCreateStructure = () => {
        createStructure(
            {
                fee_head: form.fee_head,
                academic_year: academicYear,
                amount: form.amount,
                frequency: form.frequency as any,
                due_date: form.due_date || null,
            } as any,
            { onSuccess: () => setForm({ fee_head: "", amount: "", frequency: "one_time", due_date: "" }) }
        );
    };

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-8 max-w-4xl">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Fee Structures</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Configure fee heads and per-year charge definitions.
                </p>
            </div>

            <div className="w-40">
                <label className="text-xs font-medium text-slate-500 mb-1 block">Academic Year</label>
                <Input value={academicYear} onChange={(e) => setAcademicYear(e.target.value)} />
            </div>

            {canManage && (
                <div className="space-y-3 border-b border-slate-200 dark:border-slate-800 pb-6">
                    <h2 className="text-lg font-bold">Fee Heads</h2>
                    <div className="flex gap-3 items-end">
                        <div className="w-64">
                            <label className="text-xs font-medium text-slate-500 mb-1 block">New Fee Head</label>
                            <Input value={newHeadName} onChange={(e) => setNewHeadName(e.target.value)} placeholder="e.g. Sports Fee" />
                        </div>
                        <Button onClick={handleCreateHead} disabled={creatingHead || !newHeadName} className="gap-2">
                            {creatingHead && <LoaderCircle className="h-4 w-4 animate-spin" />}
                            <Plus className="h-4 w-4" /> Add
                        </Button>
                    </div>
                </div>
            )}

            {loadingHeads ? (
                <LoaderCircle className="h-6 w-6 animate-spin text-indigo-600" />
            ) : headsError ? (
                <ErrorState onRetry={refetchHeads} />
            ) : (
                <div className="flex flex-wrap gap-2">
                    {heads?.map((h) => (
                        <StatusBadge
                            key={h.id}
                            label={h.name}
                            className={`px-3 ${h.is_active ? "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300" : "bg-red-50 text-red-500"}`}
                        />
                    ))}
                </div>
            )}

            {canManage && (
                <div className="space-y-3 pt-2">
                    <h2 className="text-lg font-bold">New Fee Structure ({academicYear})</h2>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 items-end">
                        <div>
                            <label className="text-xs font-medium text-slate-500 mb-1 block">Fee Head</label>
                            <Select value={form.fee_head} onValueChange={(v) => setForm((f) => ({ ...f, fee_head: v }))}>
                                <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                                <SelectContent>
                                    {heads?.filter((h) => h.is_active).map((h) => (
                                        <SelectItem key={h.id} value={h.id}>{h.name}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div>
                            <label className="text-xs font-medium text-slate-500 mb-1 block">Amount</label>
                            <Input type="number" value={form.amount} onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))} />
                        </div>
                        <div>
                            <label className="text-xs font-medium text-slate-500 mb-1 block">Frequency</label>
                            <Select value={form.frequency} onValueChange={(v) => setForm((f) => ({ ...f, frequency: v }))}>
                                <SelectTrigger><SelectValue /></SelectTrigger>
                                <SelectContent>
                                    {FEE_FREQUENCY_CHOICES.map((f) => (
                                        <SelectItem key={f} value={f}>{f.replace("_", " ")}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div>
                            <label className="text-xs font-medium text-slate-500 mb-1 block">Due Date (optional)</label>
                            <Input type="date" value={form.due_date} onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))} />
                        </div>
                    </div>
                    <Button
                        onClick={handleCreateStructure}
                        disabled={creatingStructure || !form.fee_head || !form.amount}
                        className="gap-2"
                    >
                        {creatingStructure && <LoaderCircle className="h-4 w-4 animate-spin" />}
                        <Plus className="h-4 w-4" /> Create Structure
                    </Button>
                </div>
            )}

            <div className="space-y-3 pt-2">
                <h2 className="text-lg font-bold">Existing Structures ({academicYear})</h2>
                {loadingStructures ? (
                    <LoaderCircle className="h-6 w-6 animate-spin text-indigo-600" />
                ) : structuresError ? (
                    <ErrorState onRetry={refetchStructures} />
                ) : !structures || structures.length === 0 ? (
                    <EmptyState title={`No fee structures defined for ${academicYear} yet.`} className="py-4 text-slate-500 text-sm" />
                ) : (
                    <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                        <table className="w-full text-sm">
                            <thead className="bg-slate-50 dark:bg-slate-900">
                                <tr className="text-left text-xs font-semibold text-slate-500 uppercase">
                                    <th className="px-4 py-3">Fee Head</th>
                                    <th className="px-4 py-3">Amount</th>
                                    <th className="px-4 py-3">Frequency</th>
                                    <th className="px-4 py-3">Due Date</th>
                                    <th className="px-4 py-3">Level</th>
                                </tr>
                            </thead>
                            <tbody>
                                {structures.map((s) => (
                                    <tr key={s.id} className="border-t border-slate-100 dark:border-slate-800">
                                        <td className="px-4 py-2 font-medium">{s.fee_head_name}</td>
                                        <td className="px-4 py-2">{s.amount}</td>
                                        <td className="px-4 py-2 capitalize">{s.frequency.replace("_", " ")}</td>
                                        <td className="px-4 py-2 text-slate-500">{s.due_date || "—"}</td>
                                        <td className="px-4 py-2 text-slate-500">{s.level_name || "All levels"}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}
