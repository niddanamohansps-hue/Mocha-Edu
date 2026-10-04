"use client";

import { useState } from "react";
import { useSubjects, useAcademicLevels, useCreateSubject, useUpdateSubject, useDeleteSubject } from "@/hooks/useAcademics";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Plus, MoreHorizontal, Pencil, Trash2, BookOpen } from "lucide-react";
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
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { TableShell } from "@/components/common/table/TableShell";
import { Subject } from "@/types/Academics";
import { Badge } from "@/components/ui/badge";

export default function SubjectsTab() {
    const { data: subjects, isLoading: isLoadingSubjects, isError, refetch } = useSubjects();
    const { data: levels, isLoading: isLoadingLevels } = useAcademicLevels();
    const { mutate: createSubject, isPending: isCreating } = useCreateSubject();
    const { mutate: updateSubject, isPending: isUpdating } = useUpdateSubject();
    const { mutate: deleteSubject } = useDeleteSubject();

    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [editingSubject, setEditingSubject] = useState<Subject | null>(null);
    const [subjectToDelete, setSubjectToDelete] = useState<string | null>(null);
    const [isElective, setIsElective] = useState(false);

    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const formData = new FormData(e.currentTarget);
        const data = {
            level: formData.get("level"),
            name: formData.get("name"),
            code: formData.get("code"),
            credits: parseFloat(formData.get("credits") as string),
            is_elective: isElective,
            description: formData.get("description"),
        };

        if (editingSubject) {
            updateSubject({ id: editingSubject.id, data }, {
                onSuccess: () => {
                    setIsDialogOpen(false);
                    setEditingSubject(null);
                    setIsElective(false);
                }
            });
        } else {
            createSubject(data, {
                onSuccess: () => {
                    setIsDialogOpen(false);
                    setIsElective(false);
                }
            });
        }
    };

    const handleEdit = (subject: Subject) => {
        setEditingSubject(subject);
        setIsElective(subject.is_elective);
        setIsDialogOpen(true);
    };

    const handleDelete = () => {
        if (subjectToDelete) {
            deleteSubject(subjectToDelete);
            setSubjectToDelete(null);
        }
    };

    const handleDialogClose = () => {
        setIsDialogOpen(false);
        setEditingSubject(null);
        setIsElective(false);
    };

    if (isLoadingSubjects || isLoadingLevels) {
        return <LoadingState className="py-20" />;
    }

    if (isError) {
        return <ErrorState onRetry={refetch} />;
    }

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Subjects</h3>
                    <p className="text-sm text-slate-500 dark:text-slate-400">Manage subjects and courses</p>
                </div>
                <Button onClick={() => setIsDialogOpen(true)} className="gap-2">
                    <Plus className="h-4 w-4" />
                    New Subject
                </Button>
            </div>

            <Dialog open={isDialogOpen} onOpenChange={handleDialogClose}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>{editingSubject ? "Edit Subject" : "Create New Subject"}</DialogTitle>
                        <DialogDescription>
                            {editingSubject ? "Update subject information" : "Add a new subject to an academic level"}
                        </DialogDescription>
                    </DialogHeader>
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="level">Academic Level</Label>
                            <Select name="level" defaultValue={editingSubject?.level} required>
                                <SelectTrigger>
                                    <SelectValue placeholder="Select level" />
                                </SelectTrigger>
                                <SelectContent>
                                    {levels?.map((level) => (
                                        <SelectItem key={level.id} value={level.id}>
                                            {level.program_name} - {level.name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="name">Subject Name</Label>
                            <Input
                                id="name"
                                name="name"
                                placeholder="e.g., Mathematics"
                                defaultValue={editingSubject?.name}
                                required
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="code">Subject Code</Label>
                            <Input
                                id="code"
                                name="code"
                                placeholder="e.g., MTH101"
                                defaultValue={editingSubject?.code}
                                required
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="credits">Credits</Label>
                            <Input
                                id="credits"
                                name="credits"
                                type="number"
                                step="0.1"
                                placeholder="e.g., 3.0"
                                defaultValue={editingSubject?.credits}
                                required
                            />
                        </div>
                        <div className="flex items-center space-x-2">
                            <Checkbox
                                id="is_elective"
                                checked={isElective}
                                onCheckedChange={(checked) => setIsElective(checked as boolean)}
                            />
                            <Label htmlFor="is_elective" className="text-sm font-normal cursor-pointer">
                                This is an elective subject
                            </Label>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="description">Description</Label>
                            <Textarea
                                id="description"
                                name="description"
                                placeholder="Optional description..."
                                defaultValue={editingSubject?.description}
                            />
                        </div>
                        <div className="pt-4 flex justify-end gap-2">
                            <Button type="button" variant="outline" onClick={handleDialogClose}>
                                Cancel
                            </Button>
                            <Button type="submit" disabled={isCreating || isUpdating}>
                                {isCreating || isUpdating ? "Saving..." : editingSubject ? "Update" : "Create"}
                            </Button>
                        </div>
                    </form>
                </DialogContent>
            </Dialog>

            <TableShell className="dark:bg-slate-950">
                <Table>
                    <TableHeader className="bg-slate-50/50 dark:bg-slate-900/50">
                        <TableRow>
                            <TableHead>Subject Name</TableHead>
                            <TableHead>Code</TableHead>
                            <TableHead>Level</TableHead>
                            <TableHead>Credits</TableHead>
                            <TableHead>Type</TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {subjects && subjects.length > 0 ? (
                            subjects.map((subject) => (
                                <TableRow key={subject.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/50 transition-colors">
                                    <TableCell className="font-medium">{subject.name}</TableCell>
                                    <TableCell>
                                        <span className="font-mono text-xs bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded">
                                            {subject.code}
                                        </span>
                                    </TableCell>
                                    <TableCell className="text-slate-600 dark:text-slate-400">{subject.level_name}</TableCell>
                                    <TableCell>
                                        <span className="text-sm">{subject.credits}</span>
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant={subject.is_elective ? "secondary" : "outline"} className="text-xs">
                                            {subject.is_elective ? "Elective" : "Core"}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <DropdownMenu>
                                            <DropdownMenuTrigger asChild>
                                                <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                                    <MoreHorizontal className="h-4 w-4" />
                                                </Button>
                                            </DropdownMenuTrigger>
                                            <DropdownMenuContent align="end">
                                                <DropdownMenuItem onClick={() => handleEdit(subject)}>
                                                    <Pencil className="h-4 w-4 mr-2" />
                                                    Edit
                                                </DropdownMenuItem>
                                                <DropdownMenuItem
                                                    onClick={() => setSubjectToDelete(subject.id)}
                                                    className="text-red-600"
                                                >
                                                    <Trash2 className="h-4 w-4 mr-2" />
                                                    Delete
                                                </DropdownMenuItem>
                                            </DropdownMenuContent>
                                        </DropdownMenu>
                                    </TableCell>
                                </TableRow>
                            ))
                        ) : (
                            <TableRow>
                                <TableCell colSpan={6} className="h-32 text-center">
                                    <EmptyState
                                        icon={<BookOpen className="h-12 w-12 mb-2 opacity-20" />}
                                        title="No subjects found. Create one to get started."
                                        className="py-0"
                                    />
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableShell>

            <ConfirmationDialog
                open={!!subjectToDelete}
                onOpenChange={() => setSubjectToDelete(null)}
                description="This action cannot be undone. This will permanently delete the subject."
                confirmLabel="Delete"
                onConfirm={handleDelete}
            />
        </div>
    );
}
