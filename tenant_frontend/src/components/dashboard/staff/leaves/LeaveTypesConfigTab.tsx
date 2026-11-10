"use client";

import React, { useState } from "react";
import { LeaveType } from "@/types/Leave";
import {
    useCreateLeaveType,
    useDeactivateLeaveType,
    useLeaveTypes,
    useUpdateLeaveType,
} from "@/hooks/useStaffLeaves";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
    TableCellAction,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import { Plus, Edit2, Ban, CheckCircle2, Settings, Loader2 } from "lucide-react";

export function LeaveTypesConfigTab() {
    const { data: leaveTypes = [], isLoading } = useLeaveTypes(true);
    const createMutation = useCreateLeaveType();
    const updateMutation = useUpdateLeaveType();
    const deactivateMutation = useDeactivateLeaveType();

    const [modalOpen, setModalOpen] = useState(false);
    const [editingType, setEditingType] = useState<LeaveType | null>(null);

    const [name, setName] = useState("");
    const [code, setCode] = useState("");
    const [description, setDescription] = useState("");
    const [annualAllocation, setAnnualAllocation] = useState("12");
    const [isPaid, setIsPaid] = useState(true);
    const [requiresDocument, setRequiresDocument] = useState(false);
    const [maxConsecutive, setMaxConsecutive] = useState("");

    const openCreateModal = () => {
        setEditingType(null);
        setName("");
        setCode("");
        setDescription("");
        setAnnualAllocation("12");
        setIsPaid(true);
        setRequiresDocument(false);
        setMaxConsecutive("");
        setModalOpen(true);
    };

    const openEditModal = (lt: LeaveType) => {
        setEditingType(lt);
        setName(lt.name);
        setCode(lt.code);
        setDescription(lt.description || "");
        setAnnualAllocation(String(lt.annual_allocation_days));
        setIsPaid(lt.is_paid);
        setRequiresDocument(lt.requires_document);
        setMaxConsecutive(lt.max_consecutive_days ? String(lt.max_consecutive_days) : "");
        setModalOpen(true);
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        const payload: Partial<LeaveType> = {
            name: name.trim(),
            code: code.trim().toUpperCase(),
            description: description.trim(),
            annual_allocation_days: parseFloat(annualAllocation) || 0,
            is_paid: isPaid,
            requires_document: requiresDocument,
            max_consecutive_days: maxConsecutive ? parseInt(maxConsecutive, 10) : null,
        };

        if (editingType) {
            updateMutation.mutate(
                { id: editingType.id, payload },
                { onSuccess: () => setModalOpen(false) }
            );
        } else {
            createMutation.mutate(payload, { onSuccess: () => setModalOpen(false) });
        }
    };

    const isPending = createMutation.isPending || updateMutation.isPending;

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                    <h3 className="font-semibold text-base text-slate-900 dark:text-white">Leave types</h3>
                    <p className="text-xs text-slate-500">
                        Define school leave categories, annual allocations, and documentation policies.
                    </p>
                </div>
                <Button size="sm" onClick={openCreateModal} className="bg-indigo-600 hover:bg-indigo-700">
                    <Plus className="w-4 h-4 mr-1.5" />
                    Add Leave Type
                </Button>
            </div>

            <TableShell>
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="pl-4">Code</TableHead>
                            <TableHead>Leave Category</TableHead>
                            <TableHead>Days per year</TableHead>
                            <TableHead>Type</TableHead>
                            <TableHead>Document</TableHead>
                            <TableHead>Most days in a row</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead className="text-right pr-4">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {isLoading ? (
                            <TableRow>
                                <TableCell colSpan={8} className="text-center py-8 text-slate-400">
                                    <Loader2 className="w-6 h-6 animate-spin mx-auto" />
                                </TableCell>
                            </TableRow>
                        ) : leaveTypes.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={8} className="text-center py-8 text-slate-400">
                                    No leave types configured yet.
                                </TableCell>
                            </TableRow>
                        ) : (
                            leaveTypes.map((lt) => (
                                <TableRow key={lt.id} className={!lt.is_active ? "opacity-60 bg-slate-50/50 dark:bg-slate-900/30" : ""}>
                                    <TableCell className="font-mono font-bold text-xs">{lt.code}</TableCell>
                                    <TableCell>
                                        <div className="font-semibold text-slate-800 dark:text-slate-200">{lt.name}</div>
                                        {lt.description && <div className="text-xs text-slate-400">{lt.description}</div>}
                                    </TableCell>
                                    <TableCell className="font-medium text-xs">{lt.annual_allocation_days} days/year</TableCell>
                                    <TableCell>
                                        <Badge variant={lt.is_paid ? "default" : "secondary"} className="text-[10px]">
                                            {lt.is_paid ? "Paid" : "Unpaid"}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-xs text-slate-500">
                                        {lt.requires_document ? (
                                            <span className="text-amber-600 font-medium">Mandatory</span>
                                        ) : (
                                            "Optional"
                                        )}
                                    </TableCell>
                                    <TableCell className="text-xs text-slate-500">
                                        {lt.max_consecutive_days ? `${lt.max_consecutive_days} days` : "Unlimited"}
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant={lt.is_active ? "outline" : "secondary"} className="text-[10px]">
                                            {lt.is_active ? "Active" : "Deactivated"}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-right space-x-1">
                                        <Button size="sm" variant="ghost" className="h-8 w-8 p-0" onClick={() => openEditModal(lt)}>
                                            <Edit2 className="w-3.5 h-3.5 text-slate-600" />
                                        </Button>
                                        {lt.is_active && (
                                            <Button
                                                size="sm"
                                                variant="ghost"
                                                className="h-8 w-8 p-0 text-rose-500 hover:text-rose-600"
                                                onClick={() => deactivateMutation.mutate(lt.id)}
                                            >
                                                <Ban className="w-3.5 h-3.5" />
                                            </Button>
                                        )}
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </TableShell>

            {/* Create/Edit Modal */}
            <Dialog open={modalOpen} onOpenChange={setModalOpen}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>{editingType ? "Edit Leave Type" : "Add Leave Type"}</DialogTitle>
                        <DialogDescription>
                            Configure category details, annual days granted, and verification rules.
                        </DialogDescription>
                    </DialogHeader>

                    <form onSubmit={handleSubmit} className="space-y-3.5 pt-2">
                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1">
                                <Label htmlFor="typeName">Category Name *</Label>
                                <Input id="typeName" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Casual Leave" required />
                            </div>
                            <div className="space-y-1">
                                <Label htmlFor="typeCode">Code *</Label>
                                <Input id="typeCode" value={code} onChange={(e) => setCode(e.target.value)} placeholder="CL" required disabled={!!editingType} />
                            </div>
                        </div>

                        <div className="space-y-1">
                            <Label htmlFor="desc">Description</Label>
                            <Input id="desc" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional policy details" />
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1">
                                <Label htmlFor="annualDays">Days allowed per year *</Label>
                                <Input id="annualDays" type="number" step="0.5" min="0" value={annualAllocation} onChange={(e) => setAnnualAllocation(e.target.value)} required />
                            </div>
                            <div className="space-y-1">
                                <Label htmlFor="maxDays">Most days in a row</Label>
                                <Input id="maxDays" type="number" min="1" value={maxConsecutive} onChange={(e) => setMaxConsecutive(e.target.value)} placeholder="e.g. 3" />
                            </div>
                        </div>

                        <div className="flex flex-wrap items-center justify-between gap-2 p-3 rounded-lg border border-slate-200 dark:border-slate-800">
                            <div>
                                <Label htmlFor="paidToggle" className="text-xs font-semibold">Paid Leave</Label>
                                <p className="text-[11px] text-slate-400">Full salary credited during absence</p>
                            </div>
                            <Switch id="paidToggle" checked={isPaid} onCheckedChange={setIsPaid} />
                        </div>

                        <div className="flex flex-wrap items-center justify-between gap-2 p-3 rounded-lg border border-slate-200 dark:border-slate-800">
                            <div>
                                <Label htmlFor="docToggle" className="text-xs font-semibold">Proof Document Required</Label>
                                <p className="text-[11px] text-slate-400">Mandate doctor's slip or document upload</p>
                            </div>
                            <Switch id="docToggle" checked={requiresDocument} onCheckedChange={setRequiresDocument} />
                        </div>

                        <DialogFooter className="pt-2">
                            <Button type="button" variant="outline" onClick={() => setModalOpen(false)}>Cancel</Button>
                            <Button type="submit" disabled={isPending} className="bg-indigo-600 hover:bg-indigo-700">
                                {isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                                {editingType ? "Save Changes" : "Create Leave Type"}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>
        </div>
    );
}

