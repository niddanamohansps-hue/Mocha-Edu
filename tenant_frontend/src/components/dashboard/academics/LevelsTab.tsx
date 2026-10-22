"use client";

import { useState } from "react";
import { useAcademicLevels, usePrograms, useCreateLevel, useUpdateLevel, useDeleteLevel } from "@/hooks/useAcademics";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Plus, MoreHorizontal, Pencil, Trash2, GraduationCap, LoaderCircle } from "lucide-react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
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
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { TableShell } from "@/components/common/table/TableShell";
import { AcademicLevel } from "@/types/Academics";

export default function LevelsTab() {
    const { can, isOwner } = usePermissions();
    const { data: levels, isLoading: isLoadingLevels } = useAcademicLevels();
    const { data: programs, isLoading: isLoadingPrograms } = usePrograms();
    const { mutate: createLevel, isPending: isCreating } = useCreateLevel();
    const { mutate: updateLevel, isPending: isUpdating } = useUpdateLevel();
    const { mutate: deleteLevel } = useDeleteLevel();

    const canCreate = isOwner || can("add_academic_level");
    const canEdit = isOwner || can("change_academic_level");
    const canDelete = isOwner || can("delete_academic_level");

    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [editingLevel, setEditingLevel] = useState<AcademicLevel | null>(null);
    const [levelToDelete, setLevelToDelete] = useState<string | null>(null);

    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const formData = new FormData(e.currentTarget);
        const data = {
            program: formData.get("program"),
            name: formData.get("name"),
            order: parseInt(formData.get("order") as string),
        };

        if (editingLevel) {
            updateLevel({ id: editingLevel.id, data }, {
                onSuccess: () => {
                    setIsDialogOpen(false);
                    setEditingLevel(null);
                }
            });
        } else {
            createLevel(data, {
                onSuccess: () => {
                    setIsDialogOpen(false);
                }
            });
        }
    };

    const handleEdit = (level: AcademicLevel) => {
        setEditingLevel(level);
        setIsDialogOpen(true);
    };

    const handleDelete = () => {
        if (levelToDelete) {
            deleteLevel(levelToDelete);
            setLevelToDelete(null);
        }
    };

    const handleDialogClose = () => {
        setIsDialogOpen(false);
        setEditingLevel(null);
    };

    if (isLoadingLevels || isLoadingPrograms) {
        return (
            <div className="flex items-center justify-center py-20">
                <LoaderCircle className="h-8 w-8 animate-spin text-indigo-600" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex flex-wrap justify-between gap-2 items-center">
                <div>
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Academic Levels</h3>
                    <p className="text-sm text-slate-500 dark:text-slate-400">Manage grades, years, or semesters within programs</p>
                </div>
                {canCreate && (
                    <Button onClick={() => setIsDialogOpen(true)} className="gap-2">
                        <Plus className="h-4 w-4" />
                        New Level
                    </Button>
                )}
            </div>

            <Dialog open={isDialogOpen} onOpenChange={handleDialogClose}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>{editingLevel ? "Edit Academic Level" : "Create New Level"}</DialogTitle>
                        <DialogDescription>
                            {editingLevel ? "Update level information" : "Add a new academic level (grade/year/semester)"}
                        </DialogDescription>
                    </DialogHeader>
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="program">Program</Label>
                            <Select name="program" defaultValue={editingLevel?.program} required>
                                <SelectTrigger>
                                    <SelectValue placeholder="Select program" />
                                </SelectTrigger>
                                <SelectContent>
                                    {programs?.map((program) => (
                                        <SelectItem key={program.id} value={program.id}>
                                            {program.name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="name">Level Name</Label>
                            <Input
                                id="name"
                                name="name"
                                placeholder="e.g., Grade 10, Semester 1"
                                defaultValue={editingLevel?.name}
                                required
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="order">Order</Label>
                            <Input
                                id="order"
                                name="order"
                                type="number"
                                placeholder="e.g., 1"
                                defaultValue={editingLevel?.order}
                                required
                            />
                            <p className="text-xs text-slate-500">Used for sorting (1, 2, 3...)</p>
                        </div>
                        <div className="pt-4 flex justify-end gap-2">
                            <Button type="button" variant="outline" onClick={handleDialogClose}>
                                Cancel
                            </Button>
                            <Button type="submit" disabled={isCreating || isUpdating}>
                                {isCreating || isUpdating ? "Saving..." : editingLevel ? "Update" : "Create"}
                            </Button>
                        </div>
                    </form>
                </DialogContent>
            </Dialog>

            <TableShell className="dark:bg-slate-950">
                <Table>
                    <TableHeader className="bg-slate-50/50 dark:bg-slate-900/50">
                        <TableRow>
                            <TableHead>Level Name</TableHead>
                            <TableHead>Program</TableHead>
                            <TableHead>Order</TableHead>
                            <TableHead>Sections</TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {levels && levels.length > 0 ? (
                            levels.map((level) => (
                                <TableRow key={level.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/50 transition-colors">
                                    <TableCell className="font-medium">{level.name}</TableCell>
                                    <TableCell className="text-slate-600 dark:text-slate-400">{level.program_name}</TableCell>
                                    <TableCell>
                                        <span className="inline-flex items-center justify-center h-6 w-6 rounded-full bg-slate-100 dark:bg-slate-800 text-xs font-medium">
                                            {level.order}
                                        </span>
                                    </TableCell>
                                    <TableCell>
                                        <span className="text-sm text-slate-600 dark:text-slate-400">
                                            {level.sections?.length || 0}
                                        </span>
                                    </TableCell>
                                    <TableCell className="text-right">
                                        {(canEdit || canDelete) && (
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                                        <MoreHorizontal className="h-4 w-4" />
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end">
                                                    {canEdit && (
                                                        <DropdownMenuItem onClick={() => handleEdit(level)}>
                                                            <Pencil className="h-4 w-4 mr-2" />
                                                            Edit
                                                        </DropdownMenuItem>
                                                    )}
                                                    {canDelete && (
                                                        <DropdownMenuItem
                                                            onClick={() => setLevelToDelete(level.id)}
                                                            className="text-red-600"
                                                        >
                                                            <Trash2 className="h-4 w-4 mr-2" />
                                                            Delete
                                                        </DropdownMenuItem>
                                                    )}
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        )}
                                    </TableCell>
                                </TableRow>
                            ))
                        ) : (
                            <TableRow>
                                <TableCell colSpan={5} className="h-32 text-center">
                                    <div className="flex flex-col items-center justify-center text-slate-400">
                                        <GraduationCap className="h-12 w-12 mb-2 opacity-20" />
                                        <p>No academic levels found. Create one to get started.</p>
                                    </div>
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableShell>

            <ConfirmationDialog
                open={!!levelToDelete}
                onOpenChange={() => setLevelToDelete(null)}
                description="This action cannot be undone. This will permanently delete the level and all its associated sections and subjects."
                confirmLabel="Delete"
                onConfirm={handleDelete}
            />
        </div>
    );
}
