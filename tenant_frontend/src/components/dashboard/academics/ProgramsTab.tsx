"use client";

import { useState } from "react";
import { usePrograms, useCreateProgram, useUpdateProgram, useDeleteProgram } from "@/hooks/useAcademics";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Plus, MoreHorizontal, Pencil, Trash2, GraduationCap } from "lucide-react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow
} from "@/components/ui/table";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { TableShell } from "@/components/common/table/TableShell";
import { Program } from "@/types/Academics";

export default function ProgramsTab() {
    const { can, isOwner } = usePermissions();
    const { data: programs, isLoading, isError, refetch } = usePrograms();
    const { mutate: createProgram, isPending: isCreating } = useCreateProgram();
    const { mutate: updateProgram, isPending: isUpdating } = useUpdateProgram();
    const { mutate: deleteProgram } = useDeleteProgram();

    const canCreate = isOwner || can("add_program");
    const canEdit = isOwner || can("change_program");
    const canDelete = isOwner || can("delete_program");

    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [editingProgram, setEditingProgram] = useState<Program | null>(null);
    const [programToDelete, setProgramToDelete] = useState<string | null>(null);

    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const formData = new FormData(e.currentTarget);
        const data = {
            name: formData.get("name"),
            code: formData.get("code"),
            description: formData.get("description"),
        };

        if (editingProgram) {
            updateProgram({ id: editingProgram.id, data }, {
                onSuccess: () => {
                    setIsDialogOpen(false);
                    setEditingProgram(null);
                }
            });
        } else {
            createProgram(data, {
                onSuccess: () => {
                    setIsDialogOpen(false);
                }
            });
        }
    };

    const handleEdit = (program: Program) => {
        setEditingProgram(program);
        setIsDialogOpen(true);
    };

    const handleDelete = () => {
        if (programToDelete) {
            deleteProgram(programToDelete);
            setProgramToDelete(null);
        }
    };

    const handleDialogClose = () => {
        setIsDialogOpen(false);
        setEditingProgram(null);
    };

    if (isLoading) {
        return <LoadingState className="py-20" />;
    }

    if (isError) {
        return <ErrorState onRetry={refetch} />;
    }

    return (
        <div className="space-y-6">
            <div className="flex flex-wrap justify-between gap-2 items-center">
                <div>
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Academic Programs</h3>
                    <p className="text-sm text-slate-500 dark:text-slate-400">Manage your institution's academic programs</p>
                </div>
                {canCreate && (
                    <Button onClick={() => setIsDialogOpen(true)} className="gap-2">
                        <Plus className="h-4 w-4" />
                        New Program
                    </Button>
                )}
            </div>

            <Dialog open={isDialogOpen} onOpenChange={handleDialogClose}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>{editingProgram ? "Edit Program" : "Create New Program"}</DialogTitle>
                        <DialogDescription>
                            {editingProgram ? "Update program information" : "Add a new academic program to your institution"}
                        </DialogDescription>
                    </DialogHeader>
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="name">Program Name</Label>
                            <Input
                                id="name"
                                name="name"
                                placeholder="e.g., Bachelor of Science Computer"
                                defaultValue={editingProgram?.name}
                                required
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="code">Program Code</Label>
                            <Input
                                id="code"
                                name="code"
                                placeholder="e.g., BSC"
                                defaultValue={editingProgram?.code}
                                required
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="description">Description</Label>
                            <Textarea
                                id="description"
                                name="description"
                                placeholder="Optional description..."
                                defaultValue={editingProgram?.description}
                            />
                        </div>
                        <div className="pt-4 flex justify-end gap-2">
                            <Button type="button" variant="outline" onClick={handleDialogClose}>
                                Cancel
                            </Button>
                            <Button type="submit" disabled={isCreating || isUpdating}>
                                {isCreating || isUpdating ? "Saving..." : editingProgram ? "Update" : "Create"}
                            </Button>
                        </div>
                    </form>
                </DialogContent>
            </Dialog>

            <TableShell className="dark:bg-slate-950">
                <Table>
                    <TableHeader className="bg-slate-50/50 dark:bg-slate-900/50">
                        <TableRow>
                            <TableHead>Program Name</TableHead>
                            <TableHead>Code</TableHead>
                            <TableHead>Description</TableHead>
                            <TableHead>Levels</TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {programs && programs.length > 0 ? (
                            programs.map((program) => (
                                <TableRow key={program.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/50 transition-colors">
                                    <TableCell className="font-medium">{program.name}</TableCell>
                                    <TableCell>
                                        <span className="font-mono text-xs bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded">
                                            {program.code}
                                        </span>
                                    </TableCell>
                                    <TableCell className="max-w-xs truncate text-slate-500">
                                        {program.description || "—"}
                                    </TableCell>
                                    <TableCell>
                                        <span className="text-sm text-slate-600 dark:text-slate-400">
                                            {program.levels?.length || 0} level{program.levels?.length !== 1 ? 's' : ''}
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
                                                        <DropdownMenuItem onClick={() => handleEdit(program)}>
                                                            <Pencil className="h-4 w-4 mr-2" />
                                                            Edit
                                                        </DropdownMenuItem>
                                                    )}
                                                    {canDelete && (
                                                        <DropdownMenuItem
                                                            onClick={() => setProgramToDelete(program.id)}
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
                                    <EmptyState
                                        icon={<GraduationCap className="h-12 w-12 mb-2 opacity-20" />}
                                        title="No programs found. Create one to get started."
                                        className="py-0"
                                    />
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableShell>

            <ConfirmationDialog
                open={!!programToDelete}
                onOpenChange={() => setProgramToDelete(null)}
                description="This action cannot be undone. This will permanently delete the program and all its associated levels, sections, and subjects."
                confirmLabel="Delete"
                onConfirm={handleDelete}
            />
        </div>
    );
}
