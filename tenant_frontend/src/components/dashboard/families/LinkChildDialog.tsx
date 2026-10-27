"use client";

import React, { useState } from "react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Search, Loader2, Check, User, GraduationCap } from "lucide-react";
import { useStudents } from "@/hooks/useStudents";
import { useParents, useLinkChild } from "@/hooks/useFamilies";

interface LinkChildDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    /** If provided, we search students to link to this parent */
    parentId?: string;
    parentName?: string;
    /** If provided, we search parents to link to this student */
    studentId?: string;
    studentName?: string;
    onSuccess?: () => void;
}

export function LinkChildDialog({
    open,
    onOpenChange,
    parentId,
    parentName,
    studentId,
    studentName,
    onSuccess,
}: LinkChildDialogProps) {
    const [searchTerm, setSearchTerm] = useState("");
    const [selectedStudentId, setSelectedStudentId] = useState<string>(studentId || "");
    const [selectedParentId, setSelectedParentId] = useState<string>(parentId || "");
    const [relationType, setRelationType] = useState<string>("father");
    const [isPrimaryContact, setIsPrimaryContact] = useState<boolean>(false);
    const [canPickup, setCanPickup] = useState<boolean>(true);

    const isSelectingStudent = Boolean(parentId);

    // Queries based on selection mode
    const { data: studentsData, isLoading: isLoadingStudents } = useStudents({
        search: searchTerm,
        pageSize: 20,
    });
    const { data: parentsData, isLoading: isLoadingParents } = useParents({
        search: searchTerm,
        pageSize: 20,
    });

    const { mutate: linkChild, isPending: isLinking } = useLinkChild();

    const handleOpenChange = (nextOpen: boolean) => {
        if (!nextOpen) {
            setSearchTerm("");
            if (!studentId) setSelectedStudentId("");
            if (!parentId) setSelectedParentId("");
            setRelationType("father");
            setIsPrimaryContact(false);
            setCanPickup(true);
        }
        onOpenChange(nextOpen);
    };

    const finalStudentId = studentId || selectedStudentId;
    const finalParentId = parentId || selectedParentId;

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!finalStudentId || !finalParentId) return;

        linkChild(
            {
                student: finalStudentId,
                parent: finalParentId,
                relation_type: relationType,
                is_primary_contact: isPrimaryContact,
                can_pickup: canPickup,
            },
            {
                onSuccess: () => {
                    handleOpenChange(false);
                    onSuccess?.();
                },
            }
        );
    };

    const students = studentsData?.results || [];
    const parents = parentsData?.results || [];

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto rounded-3xl">
                <DialogHeader>
                    <DialogTitle className="text-xl font-bold">
                        {isSelectingStudent
                            ? `Link Child to ${parentName || "Parent"}`
                            : `Link Guardian to ${studentName || "Student"}`}
                    </DialogTitle>
                    <DialogDescription>
                        {isSelectingStudent
                            ? "Search and select a student to establish a family relationship."
                            : "Search and select an existing parent to link to this student."}
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={handleSubmit} className="space-y-6 pt-2">
                    {/* Search and Selection List */}
                    <div className="space-y-3">
                        <Label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                            {isSelectingStudent ? "Select Student" : "Select Parent"}
                        </Label>

                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                            <Input
                                placeholder={
                                    isSelectingStudent
                                        ? "Search student by name or enrollment ID..."
                                        : "Search parent by name or phone..."
                                }
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                className="pl-9 rounded-xl"
                            />
                        </div>

                        <div className="max-h-48 overflow-y-auto border border-slate-200 dark:border-slate-800 rounded-2xl divide-y divide-slate-100 dark:divide-slate-800 bg-slate-50/50 dark:bg-slate-900/50 p-1">
                            {isSelectingStudent ? (
                                isLoadingStudents ? (
                                    <div className="py-8 text-center text-sm text-slate-400 flex items-center justify-center gap-2">
                                        <Loader2 className="h-4 w-4 animate-spin" /> Searching students...
                                    </div>
                                ) : students.length > 0 ? (
                                    students.map((st: { id: string; full_name: string; enrollment_id: string; level?: string }) => {
                                        const isSelected = selectedStudentId === st.id;
                                        return (
                                            <button
                                                key={st.id}
                                                type="button"
                                                onClick={() => setSelectedStudentId(st.id)}
                                                className={`w-full flex items-center justify-between p-2.5 rounded-xl text-left text-sm transition-colors ${
                                                    isSelected
                                                        ? "bg-sky-100/70 text-sky-900 dark:bg-sky-950/60 dark:text-sky-200 font-semibold"
                                                        : "hover:bg-slate-100 dark:hover:bg-slate-800/60 text-slate-700 dark:text-slate-300"
                                                }`}
                                            >
                                                <div className="flex items-center gap-2.5">
                                                    <GraduationCap className="h-4 w-4 text-sky-500 shrink-0" />
                                                    <div>
                                                        <div>{st.full_name}</div>
                                                        <div className="text-xs text-slate-400 font-normal">
                                                            {st.enrollment_id} • {st.level || "Grade"}
                                                        </div>
                                                    </div>
                                                </div>
                                                {isSelected && <Check className="h-4 w-4 text-sky-600" />}
                                            </button>
                                        );
                                    })
                                ) : (
                                    <div className="py-8 text-center text-sm text-slate-400">
                                        No students found matching &quot;{searchTerm}&quot;.
                                    </div>
                                )
                            ) : isLoadingParents ? (
                                <div className="py-8 text-center text-sm text-slate-400 flex items-center justify-center gap-2">
                                    <Loader2 className="h-4 w-4 animate-spin" /> Searching parents...
                                </div>
                            ) : parents.length > 0 ? (
                                parents.map((pr) => {
                                    const isSelected = selectedParentId === pr.id;
                                    const fullName = `${pr.profile_details?.first_name || ""} ${pr.profile_details?.last_name || ""}`.trim();
                                    return (
                                        <button
                                            key={pr.id}
                                            type="button"
                                            onClick={() => setSelectedParentId(pr.id)}
                                            className={`w-full flex items-center justify-between p-2.5 rounded-xl text-left text-sm transition-colors ${
                                                isSelected
                                                    ? "bg-sky-100/70 text-sky-900 dark:bg-sky-950/60 dark:text-sky-200 font-semibold"
                                                    : "hover:bg-slate-100 dark:hover:bg-slate-800/60 text-slate-700 dark:text-slate-300"
                                            }`}
                                        >
                                            <div className="flex items-center gap-2.5">
                                                <User className="h-4 w-4 text-emerald-500 shrink-0" />
                                                <div>
                                                    <div>{fullName || "Unnamed Parent"}</div>
                                                    <div className="text-xs text-slate-400 font-normal">
                                                        {pr.profile_details?.phone || "No phone"} • {pr.occupation || "Parent"}
                                                    </div>
                                                </div>
                                            </div>
                                            {isSelected && <Check className="h-4 w-4 text-sky-600" />}
                                        </button>
                                    );
                                })
                            ) : (
                                <div className="py-8 text-center text-sm text-slate-400">
                                    No parents found matching &quot;{searchTerm}&quot;.
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Relationship Details */}
                    <div className="space-y-4 pt-1">
                        <div className="space-y-1.5">
                            <Label htmlFor="relation_type" className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                                Relationship Type
                            </Label>
                            <Select value={relationType} onValueChange={setRelationType}>
                                <SelectTrigger id="relation_type" className="rounded-xl">
                                    <SelectValue placeholder="Select relation" />
                                </SelectTrigger>
                                <SelectContent className="rounded-xl">
                                    <SelectItem value="father">Father</SelectItem>
                                    <SelectItem value="mother">Mother</SelectItem>
                                    <SelectItem value="guardian">Legal Guardian</SelectItem>
                                    <SelectItem value="other">Other Relative</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="flex items-center justify-between p-3.5 bg-slate-50 dark:bg-slate-900/60 border border-slate-100 dark:border-slate-800 rounded-2xl">
                            <div>
                                <div className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                                    Primary Emergency Contact
                                </div>
                                <div className="text-xs text-slate-400">
                                    Unsets any previous primary contact for this student.
                                </div>
                            </div>
                            <Switch
                                checked={isPrimaryContact}
                                onCheckedChange={setIsPrimaryContact}
                            />
                        </div>

                        <div className="flex items-center justify-between p-3.5 bg-slate-50 dark:bg-slate-900/60 border border-slate-100 dark:border-slate-800 rounded-2xl">
                            <div>
                                <div className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                                    Authorized for Student Pickup
                                </div>
                                <div className="text-xs text-slate-400">
                                    Allowed to sign student out of campus premises.
                                </div>
                            </div>
                            <Switch
                                checked={canPickup}
                                onCheckedChange={setCanPickup}
                            />
                        </div>
                    </div>

                    <DialogFooter className="gap-2 pt-2">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => handleOpenChange(false)}
                            disabled={isLinking}
                            className="rounded-xl"
                        >
                            Cancel
                        </Button>
                        <Button
                            type="submit"
                            disabled={!finalStudentId || !finalParentId || isLinking}
                            className="rounded-xl min-w-[120px]"
                        >
                            {isLinking ? (
                                <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    Linking...
                                </>
                            ) : (
                                "Confirm Link"
                            )}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

