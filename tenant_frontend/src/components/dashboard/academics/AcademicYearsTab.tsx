"use client";

import React, { useState } from "react";
import {
    useAcademicYears,
    useCreateAcademicYear,
    useUpdateAcademicYear,
    useDeleteAcademicYear,
    useSetCurrentAcademicYear,
} from "@/hooks/useAcademics";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
    Plus,
    MoreHorizontal,
    Pencil,
    Trash2,
    Calendar,
    CheckCircle2,
    Star,
} from "lucide-react";
import {
    Dialog,
    DialogBody,
    DialogContent,
    DialogFooter,
} from "@/components/ui/dialog";
import { ModalHeader } from "@/components/ui/modal-header";
import { FormGrid, FormFieldWrapper } from "@/components/ui/form-layout";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { TableShell } from "@/components/common/table/TableShell";
import { AcademicYear } from "@/types/Academics";

export default function AcademicYearsTab() {
    const { can, isOwner } = usePermissions();
    const { data: years = [], isLoading, isError, refetch } = useAcademicYears();
    // The school's local date as YYYY-MM-DD, compared with each year's start/end (also YYYY-MM-DD).
    const today = new Date().toLocaleDateString("en-CA");
    const { mutate: createYear, isPending: isCreating } = useCreateAcademicYear();
    const { mutate: updateYear, isPending: isUpdating } = useUpdateAcademicYear();
    const { mutate: deleteYear, isPending: isDeleting } = useDeleteAcademicYear();
    const { mutate: setCurrentYear, isPending: isSettingCurrent } = useSetCurrentAcademicYear();

    const canCreate = isOwner || can("add_academic_level");
    const canEdit = isOwner || can("change_academic_level");
    const canDelete = isOwner || can("delete_academic_level");

    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [editingYear, setEditingYear] = useState<AcademicYear | null>(null);
    const [yearToDelete, setYearToDelete] = useState<AcademicYear | null>(null);

    const [formData, setFormData] = useState({
        name: "",
        start_date: "",
        end_date: "",
    });

    const handleOpenCreate = () => {
        setEditingYear(null);
        setFormData({ name: "", start_date: "", end_date: "" });
        setIsDialogOpen(true);
    };

    const handleOpenEdit = (year: AcademicYear) => {
        setEditingYear(year);
        setFormData({
            name: year.name,
            start_date: year.start_date,
            end_date: year.end_date,
        });
        setIsDialogOpen(true);
    };

    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();

        if (editingYear) {
            updateYear(
                { id: editingYear.id, data: formData },
                {
                    onSuccess: () => {
                        setIsDialogOpen(false);
                        setEditingYear(null);
                    },
                }
            );
        } else {
            createYear(formData, {
                onSuccess: () => {
                    setIsDialogOpen(false);
                },
            });
        }
    };

    const handleDelete = () => {
        if (yearToDelete) {
            deleteYear(yearToDelete.id, {
                onSuccess: () => {
                    setYearToDelete(null);
                },
            });
        }
    };

    const formatDate = (dateStr: string) => {
        try {
            return new Date(dateStr).toLocaleDateString(undefined, {
                year: "numeric",
                month: "short",
                day: "numeric",
            });
        } catch {
            return dateStr;
        }
    };

    if (isLoading) {
        return <LoadingState className="py-20" />;
    }

    if (isError) {
        return (
            <ErrorState
                message="Failed to load academic years"
                description="An error occurred while fetching academic years. Please check permissions or try again."
                onRetry={refetch}
            />
        );
    }

    return (
        <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h2 className="text-lg font-semibold tracking-tight text-slate-900 dark:text-white">
                        Academic Years
                    </h2>
                    <p className="text-sm text-slate-500">
                        Configure academic sessions, calendar boundaries, and the active year.
                    </p>
                </div>
                {canCreate && (
                    <Button onClick={handleOpenCreate} className="gap-2">
                        <Plus className="h-4 w-4" />
                        <span>Add Academic Year</span>
                    </Button>
                )}
            </div>

            {years.length === 0 ? (
                <EmptyState
                    icon={<Calendar className="h-12 w-12 mb-2 opacity-20" />}
                    title="No academic years defined"
                    description="Create your first academic year session (e.g. 2025-2026) to manage class enrollments, fees, timetables, and exams."
                    action={
                        canCreate ? (
                            <Button onClick={handleOpenCreate} className="gap-2">
                                <Plus className="h-4 w-4" />
                                <span>Create Academic Year</span>
                            </Button>
                        ) : undefined
                    }
                />
            ) : (
                <TableShell>
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Academic Year</TableHead>
                                <TableHead>Start Date</TableHead>
                                <TableHead>End Date</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {years.map((year) => (
                                <TableRow key={year.id}>
                                    <TableCell className="font-semibold text-slate-900 dark:text-white">
                                        <div className="flex items-center gap-2">
                                            <Calendar className="h-4 w-4 text-sky-600 dark:text-sky-400" />
                                            <span>{year.name}</span>
                                        </div>
                                    </TableCell>
                                    <TableCell>{formatDate(year.start_date)}</TableCell>
                                    <TableCell>{formatDate(year.end_date)}</TableCell>
                                    <TableCell>
                                        {year.is_current ? (
                                            <Badge
                                                variant="outline"
                                                className="border-emerald-500/40 bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 gap-1 font-medium"
                                            >
                                                <Star className="h-3 w-3 fill-emerald-600 text-emerald-600" />
                                                <span>Current Year</span>
                                            </Badge>
                                        ) : year.start_date > today ? (
                                            <Badge
                                                variant="outline"
                                                className="border-sky-300 bg-sky-50 text-sky-700 dark:border-sky-800 dark:bg-sky-950/40 dark:text-sky-300 font-medium"
                                            >
                                                Upcoming
                                            </Badge>
                                        ) : (
                                            <Badge
                                                variant="outline"
                                                className="border-slate-200 text-slate-500 dark:border-slate-800 dark:text-slate-400 font-normal"
                                            >
                                                {year.end_date < today ? "Past" : "Not current"}
                                            </Badge>
                                        )}
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <div className="flex items-center justify-end gap-1">
                                            {!year.is_current && canEdit && (
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => setCurrentYear(year.id)}
                                                    disabled={isSettingCurrent}
                                                    className="h-8 gap-1 text-xs text-emerald-700 hover:text-emerald-800 hover:bg-emerald-50 dark:text-emerald-400 dark:hover:bg-emerald-950/40"
                                                    title="Set as the tenant's active academic year"
                                                >
                                                    <CheckCircle2 className="h-3.5 w-3.5" />
                                                    <span className="hidden sm:inline">Set as Current</span>
                                                </Button>
                                            )}

                                            {(canEdit || canDelete) && (
                                                <DropdownMenu>
                                                    <DropdownMenuTrigger asChild>
                                                        <Button variant="ghost" size="icon" className="h-8 w-8">
                                                            <MoreHorizontal className="h-4 w-4" />
                                                        </Button>
                                                    </DropdownMenuTrigger>
                                                    <DropdownMenuContent align="end">
                                                        {canEdit && (
                                                            <DropdownMenuItem
                                                                onClick={() => handleOpenEdit(year)}
                                                                className="gap-2 cursor-pointer"
                                                            >
                                                                <Pencil className="h-4 w-4" />
                                                                <span>Edit</span>
                                                            </DropdownMenuItem>
                                                        )}
                                                        {canDelete && (
                                                            <>
                                                                <DropdownMenuSeparator />
                                                                <DropdownMenuItem
                                                                    onClick={() => setYearToDelete(year)}
                                                                    disabled={year.is_current}
                                                                    className="gap-2 text-red-600 focus:text-red-600 focus:bg-red-50 dark:focus:bg-red-950/50 cursor-pointer disabled:opacity-50"
                                                                >
                                                                    <Trash2 className="h-4 w-4" />
                                                                    <span>
                                                                        {year.is_current ? "Cannot delete current year" : "Delete"}
                                                                    </span>
                                                                </DropdownMenuItem>
                                                            </>
                                                        )}
                                                    </DropdownMenuContent>
                                                </DropdownMenu>
                                            )}
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableShell>
            )}

            {/* Create / Edit Dialog */}
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                <DialogContent className="max-w-md max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                    <ModalHeader
                        icon={<Calendar className="w-5 h-5 text-sky-600" />}
                        title={editingYear ? "Edit Academic Year" : "New Academic Year"}
                        subtitle={
                            editingYear
                                ? "Update the academic session name or dates."
                                : "Define a new academic session with start and end dates."
                        }
                        onClose={() => setIsDialogOpen(false)}
                    />
                    <form onSubmit={handleSubmit} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                        <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-4">
                            <FormFieldWrapper
                                label="Academic Year Name"
                                htmlFor="year-name"
                                required
                                helpText="e.g. 2026-2027"
                            >
                                <Input
                                    id="year-name"
                                    required
                                    placeholder="e.g. 2025-2026"
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                />
                            </FormFieldWrapper>
                            <FormGrid>
                                <FormFieldWrapper label="Start Date" htmlFor="start-date" required>
                                    <Input
                                        id="start-date"
                                        type="date"
                                        required
                                        value={formData.start_date}
                                        onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="End Date" htmlFor="end-date" required>
                                    <Input
                                        id="end-date"
                                        type="date"
                                        required
                                        value={formData.end_date}
                                        onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
                                    />
                                </FormFieldWrapper>
                            </FormGrid>
                        </DialogBody>
                        <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => setIsDialogOpen(false)}
                            >
                                Cancel
                            </Button>
                            <Button
                                type="submit"
                                disabled={isCreating || isUpdating}
                            >
                                {isCreating || isUpdating
                                    ? "Saving..."
                                    : editingYear
                                    ? "Update Academic Year"
                                    : "Create Academic Year"}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            {/* Confirmation Dialog for Delete */}
            <ConfirmationDialog
                open={!!yearToDelete}
                onOpenChange={(open) => {
                    if (!open) setYearToDelete(null);
                }}
                title="Delete Academic Year"
                description={`Are you sure you want to delete "${yearToDelete?.name}"? If there are any associated fees, examinations, or student records, the deletion will be safely rejected by the server.`}
                confirmLabel="Delete"
                isLoading={isDeleting}
                variant="destructive"
                onConfirm={handleDelete}
            />
        </div>
    );
}

