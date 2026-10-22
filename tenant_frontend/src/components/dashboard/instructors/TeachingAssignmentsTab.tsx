"use client";

import { useState } from "react";
import {
    useInstructorAssignments,
    useCreateAssignment,
    useUpdateAssignment,
    useDeleteAssignment,
    useAcademicLevels,
    useSections,
    useSubjects
} from "@/hooks/useAcademics";
import { Button } from "@/components/ui/button";
import { Plus, Trash2, BookOpen, Edit2 } from "lucide-react";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
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
import { usePermissions } from "@/providers/PermissionProvider";

interface TeachingAssignmentsTabProps {
    instructorId: string; // The ID of the Instructor record (Not User ID)
}

export default function TeachingAssignmentsTab({ instructorId }: TeachingAssignmentsTabProps) {
    const { can } = usePermissions();
    const { data: assignments, isLoading } = useInstructorAssignments(instructorId);
    const { mutate: assignSubject, isPending: isAssigning } = useCreateAssignment();
    const { mutate: updateAssignment, isPending: isUpdating } = useUpdateAssignment();
    const { mutate: removeAssignment, isPending: isRemoving } = useDeleteAssignment();

    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [editingAssignment, setEditingAssignment] = useState<any>(null);
    const [deletingAssignment, setDeletingAssignment] = useState<string | null>(null);

    // Form States
    const { data: levels } = useAcademicLevels();
    const { data: allSections } = useSections();
    const { data: allSubjects } = useSubjects();

    const [selectedLevel, setSelectedLevel] = useState("");
    const [selectedSection, setSelectedSection] = useState("");
    const [selectedSubject, setSelectedSubject] = useState("");

    // Filter available options
    const filteredSections = allSections?.filter(s => s.level === selectedLevel) || [];
    const filteredSubjects = allSubjects?.filter(s => s.level === selectedLevel) || [];

    const handleOpenAssign = () => {
        setEditingAssignment(null);
        setSelectedLevel("");
        setSelectedSection("");
        setSelectedSubject("");
        setIsDialogOpen(true);
    };

    const handleOpenEdit = (assignment: any) => {
        setEditingAssignment(assignment);
        setSelectedLevel(assignment.subject_details?.level_id || "");
        setSelectedSection(assignment.section || "");
        setSelectedSubject(assignment.subject || "");
        setIsDialogOpen(true);
    };

    const handleSubmit = () => {
        if (!instructorId || !selectedSection || !selectedSubject) return;

        const payload = {
            instructor: instructorId,
            section: selectedSection,
            subject: selectedSubject,
        };

        if (editingAssignment) {
            updateAssignment({ id: editingAssignment.id, data: payload }, {
                onSuccess: () => {
                    setIsDialogOpen(false);
                    setEditingAssignment(null);
                }
            });
        } else {
            assignSubject(payload, {
                onSuccess: () => {
                    setIsDialogOpen(false);
                    setSelectedSection("");
                    setSelectedSubject("");
                }
            });
        }
    };

    const confirmDelete = () => {
        if (deletingAssignment) {
            removeAssignment(deletingAssignment, {
                onSuccess: () => setDeletingAssignment(null)
            });
        }
    };

    if (isLoading) return <div className="p-4 text-center">Loading assignments...</div>;

    const canManage = can("add_subject_assignment");

    return (
        <div className="space-y-6">
            <div className="flex flex-wrap justify-between gap-2 items-center">
                <div>
                    <h3 className="text-lg font-medium">Teaching Load</h3>
                    <p className="text-sm text-slate-500">Classes and subjects assigned to this instructor.</p>
                </div>
                {canManage && (
                    <Button onClick={handleOpenAssign} className="gap-2">
                        <Plus className="h-4 w-4" />
                        Assign Class
                    </Button>
                )}
            </div>

            {/* Assignment Dialog (Create/Edit) */}
            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{editingAssignment ? "Edit Assignment" : "Assign Subject & Class"}</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label>1. Select Level</Label>
                            <Select value={selectedLevel} onValueChange={setSelectedLevel}>
                                <SelectTrigger>
                                    <SelectValue placeholder="Select Grade/Level" />
                                </SelectTrigger>
                                <SelectContent>
                                    {levels?.map((lvl) => (
                                        <SelectItem key={lvl.id} value={lvl.id}>
                                            {lvl.program_name} - {lvl.name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>2. Select Section</Label>
                                <Select
                                    value={selectedSection}
                                    onValueChange={setSelectedSection}
                                    disabled={!selectedLevel}
                                >
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select Section" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {filteredSections.map((sec) => (
                                            <SelectItem key={sec.id} value={sec.id}>
                                                {sec.name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <Label>3. Select Subject</Label>
                                <Select
                                    value={selectedSubject}
                                    onValueChange={setSelectedSubject}
                                    disabled={!selectedLevel}
                                >
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select Subject" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {filteredSubjects.map((sub) => (
                                            <SelectItem key={sub.id} value={sub.id}>
                                                {sub.name} ({sub.code})
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        <div className="pt-4 flex justify-end">
                            <Button
                                onClick={handleSubmit}
                                disabled={isAssigning || isUpdating || !selectedSection || !selectedSubject}
                            >
                                {isAssigning || isUpdating ? "Saving..." : editingAssignment ? "Update Assignment" : "Confirm Assignment"}
                            </Button>
                        </div>
                    </div>
                </DialogContent>
            </Dialog>

            {/* Delete Confirmation Dialog */}
            <ConfirmationDialog
                open={!!deletingAssignment}
                onOpenChange={(open) => !open && setDeletingAssignment(null)}
                description="This will remove the teaching assignment for this instructor. This action cannot be undone."
                confirmLabel={isRemoving ? "Removing..." : "Remove Assignment"}
                onConfirm={confirmDelete}
            />

            <div className="border rounded-lg bg-white dark:bg-slate-950">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Subject</TableHead>
                            <TableHead>Class / Section</TableHead>
                            <TableHead>Level</TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {assignments?.map((assignment) => (
                            <TableRow key={assignment.id}>
                                <TableCell className="font-medium flex items-center gap-2">
                                    <BookOpen className="h-4 w-4 text-sky-500" />
                                    {assignment.subject_details?.name}
                                    <span className="text-xs text-muted-foreground ml-1">
                                        ({assignment.subject_details?.code})
                                    </span>
                                </TableCell>
                                <TableCell>{assignment.section_details?.name}</TableCell>
                                <TableCell>{assignment.subject_details?.level_name}</TableCell>
                                <TableCell className="text-right">
                                    {canManage && (
                                        <div className="flex justify-end gap-2">
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50"
                                                onClick={() => handleOpenEdit(assignment)}
                                            >
                                                <Edit2 className="h-4 w-4" />
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="text-red-500 hover:text-red-700 hover:bg-red-50"
                                                onClick={() => setDeletingAssignment(assignment.id)}
                                                disabled={isRemoving}
                                            >
                                                <Trash2 className="h-4 w-4" />
                                            </Button>
                                        </div>
                                    )}
                                </TableCell>
                            </TableRow>
                        ))}
                        {(!assignments || assignments.length === 0) && (
                            <TableRow>
                                <TableCell colSpan={4} className="text-center py-8 text-muted-foreground">
                                    No teaching assignments found.
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </div>
        </div>
    );
}
