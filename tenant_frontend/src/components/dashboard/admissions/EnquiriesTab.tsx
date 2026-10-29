"use client";

import React, { useState } from "react";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
    useEnquiries,
    useConvertEnquiry,
    useDeleteEnquiry,
} from "@/hooks/useAdmissions";
import { AdmissionEnquiry, EnquiryStatus } from "@/types/Admissions";
import { usePermissions } from "@/providers/PermissionProvider";
import EnquiryDialog from "./EnquiryDialog";
import {
    Search,
    Plus,
    Calendar,
    Phone,
    ArrowRightCircle,
    Edit2,
    Trash2,
    Loader2,
} from "lucide-react";

export default function EnquiriesTab() {
    const { can, isOwner } = usePermissions();
    const canManageEnquiries = isOwner || can("manage_admission_enquiries");
    const canManageApplications = isOwner || can("manage_admission_applications");

    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState<string>("all");
    const [dialogOpen, setDialogOpen] = useState(false);
    const [editingEnquiry, setEditingEnquiry] = useState<AdmissionEnquiry | null>(null);

    const {
        data: enquiries = [],
        isLoading,
    } = useEnquiries({
        search: search || undefined,
        status: statusFilter === "all" ? undefined : (statusFilter as EnquiryStatus),
    });

    const convertMutation = useConvertEnquiry();
    const deleteMutation = useDeleteEnquiry();

    const handleCreateNew = () => {
        setEditingEnquiry(null);
        setDialogOpen(true);
    };

    const handleEdit = (enq: AdmissionEnquiry) => {
        setEditingEnquiry(enq);
        setDialogOpen(true);
    };

    const handleConvert = (id: string, num: string) => {
        if (confirm(`Convert enquiry ${num} into an admission application?`)) {
            convertMutation.mutate(id);
        }
    };

    const handleDelete = (id: string, num: string) => {
        if (confirm(`Are you sure you want to delete enquiry ${num}?`)) {
            deleteMutation.mutate(id);
        }
    };

    const getStatusBadge = (status: EnquiryStatus) => {
        switch (status) {
            case "new":
                return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300 border-none font-semibold">New</Badge>;
            case "contacted":
                return <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 border-none font-semibold">Contacted</Badge>;
            case "qualified":
                return <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300 border-none font-semibold">Qualified</Badge>;
            case "converted":
                return <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300 border-none font-semibold">Converted</Badge>;
            case "closed":
                return <Badge className="bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300 border-none font-semibold">Closed</Badge>;
            default:
                return <Badge variant="outline">{status}</Badge>;
        }
    };

    return (
        <div className="space-y-4">
            {/* Control Bar */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white dark:bg-slate-900 p-4 rounded-2xl border border-slate-200/80 dark:border-slate-800 shadow-xs">
                <div className="flex flex-1 items-center gap-3 w-full sm:w-auto">
                    <div className="relative flex-1 sm:w-80">
                        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                        <Input aria-label="Search by student, guardian, phone, ref..."
                            placeholder="Search by student, guardian, phone, ref..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            className="pl-9 h-10 rounded-xl"
                        />
                    </div>
                    <Select value={statusFilter} onValueChange={setStatusFilter}>
                        <SelectTrigger className="w-40 h-10 rounded-xl">
                            <SelectValue placeholder="All Statuses" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="all">All Statuses</SelectItem>
                            <SelectItem value="new">New</SelectItem>
                            <SelectItem value="contacted">Contacted</SelectItem>
                            <SelectItem value="qualified">Qualified</SelectItem>
                            <SelectItem value="converted">Converted</SelectItem>
                            <SelectItem value="closed">Closed / Lost</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                {canManageEnquiries && (
                    <Button
                        onClick={handleCreateNew}
                        className="bg-blue-600 hover:bg-blue-700 text-white rounded-xl h-10 px-4 font-semibold shadow-xs"
                    >
                        <Plus className="w-4 h-4 mr-2" />
                        New Enquiry
                    </Button>
                )}
            </div>

            {/* Table */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 shadow-xs overflow-hidden">
                <Table>
                    <TableHeader className="bg-slate-50/70 dark:bg-slate-800/50">
                        <TableRow>
                            <TableHead className="font-bold">Reference #</TableHead>
                            <TableHead className="font-bold">Prospective Student</TableHead>
                            <TableHead className="font-bold">Guardian & Contact</TableHead>
                            <TableHead className="font-bold">Target Grade & Year</TableHead>
                            <TableHead className="font-bold">Source</TableHead>
                            <TableHead className="font-bold">Status</TableHead>
                            <TableHead className="font-bold">Follow-up</TableHead>
                            <TableHead className="text-right font-bold">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {isLoading ? (
                            <TableRow>
                                <TableCell colSpan={8} className="h-40 text-center">
                                    <Loader2 className="w-6 h-6 animate-spin mx-auto text-blue-600" />
                                    <span className="text-xs text-slate-500 mt-2 block">Loading enquiries...</span>
                                </TableCell>
                            </TableRow>
                        ) : enquiries.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={8} className="h-40 text-center text-slate-500">
                                    No admission enquiries found. Click &quot;New Enquiry&quot; to log a lead.
                                </TableCell>
                            </TableRow>
                        ) : (
                            enquiries.map((enq) => (
                                <TableRow key={enq.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
                                    <TableCell className="font-mono text-xs font-semibold text-blue-600 dark:text-blue-400">
                                        {enq.enquiry_number}
                                    </TableCell>
                                    <TableCell>
                                        <div className="font-semibold text-slate-800 dark:text-white">
                                            {enq.student_name}
                                        </div>
                                        {enq.date_of_birth && (
                                            <div className="text-xs text-slate-400">
                                                DOB: {enq.date_of_birth}
                                            </div>
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        <div className="font-medium text-slate-700 dark:text-slate-200">
                                            {enq.guardian_name}{enq.guardian_relationship ? ` (${enq.guardian_relationship})` : ""}
                                        </div>
                                        <div className="flex items-center gap-1 text-xs text-slate-500">
                                            <Phone className="w-3 h-3 text-slate-400" />
                                            {enq.guardian_phone}
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <div className="font-medium text-slate-700 dark:text-slate-200">
                                            {enq.preferred_level_name || "Any Grade"}
                                        </div>
                                        <div className="text-xs text-slate-400">{enq.academic_year}</div>
                                    </TableCell>
                                    <TableCell className="capitalize text-xs text-slate-600 dark:text-slate-300">
                                        {enq.source.replace(/_/g, " ")}
                                    </TableCell>
                                    <TableCell>{getStatusBadge(enq.status)}</TableCell>
                                    <TableCell>
                                        {enq.follow_up_date ? (
                                            <div className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400 font-medium">
                                                <Calendar className="w-3 h-3" />
                                                {enq.follow_up_date}
                                            </div>
                                        ) : (
                                            <span className="text-xs text-slate-400">—</span>
                                        )}
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <div className="flex items-center justify-end gap-1">
                                            {enq.status !== "converted" && canManageApplications && (
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    onClick={() => handleConvert(enq.id, enq.enquiry_number)}
                                                    className="text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 text-xs font-semibold px-2 h-8"
                                                    title="Convert to Application"
                                                >
                                                    <ArrowRightCircle className="w-4 h-4 mr-1" />
                                                    Convert
                                                </Button>
                                            )}

                                            {canManageEnquiries && (
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    onClick={() => handleEdit(enq)}
                                                    className="text-slate-500 hover:text-slate-800 dark:hover:text-white h-8 w-8 p-0"
                                                    title="Edit Enquiry"
                                                >
                                                    <Edit2 className="w-3.5 h-3.5" />
                                                </Button>
                                            )}

                                            {canManageEnquiries && (
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    onClick={() => handleDelete(enq.id, enq.enquiry_number)}
                                                    className="text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/40 h-8 w-8 p-0"
                                                    title="Delete Enquiry"
                                                >
                                                    <Trash2 className="w-3.5 h-3.5" />
                                                </Button>
                                            )}
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </div>

            <EnquiryDialog
                open={dialogOpen}
                onOpenChange={setDialogOpen}
                enquiry={editingEnquiry}
            />
        </div>
    );
}

