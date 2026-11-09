"use client";

import React, { useState } from "react";
import {
    Dialog,
    DialogBody,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { FormFieldWrapper } from "@/components/ui/form-layout";
import { Search, Loader2, Check, User, GraduationCap, Link2 } from "lucide-react";
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
            <DialogContent className="max-w-xl max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl">
                <DialogHeader className="px-6 py-4.5 border-b border-slate-100 dark:border-slate-800 shrink-0">
                    <DialogTitle className="flex items-center gap-2 text-lg font-bold text-slate-900 dark:text-white">
                        <Link2 className="w-5 h-5 text-sky-600" />
                        {isSelectingStudent
                            ? `Link Student to ${parentName || "Parent"}`
                            : `Link Parent to ${studentName || "Student"}`}
                    </DialogTitle>
                    <DialogDescription className="text-xs text-slate-500">
                        {isSelectingStudent
                            ? "Search and select a student to establish a family relationship."
                            : "Search and select an existing parent to link to this student."}
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={handleSubmit} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                    <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-5">
                        {/* Search and Selection List */}
                        <div className="space-y-2">
                            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                                {isSelectingStudent ? "Select Student" : "Select Parent"}
                            </span>

                            <div className="relative">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
                                <Input
                                    placeholder={
                                        isSelectingStudent
                                            ? "Search student by name or enrollment ID..."
                                            : "Search parent by name or phone..."
                                    }
                                    value={searchTerm}
                                    onChange={(e) => setSearchTerm(e.target.value)}
                                    className="pl-9"
                                />
                            </div>

                            <div className="max-h-48 overflow-y-auto border border-slate-200 dark:border-slate-800 rounded-xl divide-y divide-slate-100 dark:divide-slate-800 bg-slate-50/50 dark:bg-slate-900/50 p-1">
                                {isSelectingStudent ? (
                                    isLoadingStudents ? (
                                        <div className="py-8 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
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
                                                    className={`w-full flex items-center justify-between p-2.5 rounded-lg text-left text-xs transition-colors cursor-pointer ${
                                                        isSelected
                                                            ? "bg-sky-100/70 text-sky-900 dark:bg-sky-950/60 dark:text-sky-200 font-semibold"
                                                            : "hover:bg-slate-100 dark:hover:bg-slate-800/60 text-slate-700 dark:text-slate-300"
                                                    }`}
                                                >
                                                    <div className="flex items-center gap-2.5 min-w-0">
                                                        <GraduationCap className="h-4 w-4 text-sky-500 shrink-0" />
                                                        <div className="truncate">
                                                            <div className="font-medium truncate">{st.full_name}</div>
                                                            <div className="text-[11px] text-slate-400">
                                                                {st.enrollment_id} • {st.level || "Grade"}
                                                            </div>
                                                        </div>
                                                    </div>
                                                    {isSelected && <Check className="h-4 w-4 text-sky-600 shrink-0" />}
                                                </button>
                                            );
                                        })
                                    ) : (
                                        <div className="py-8 text-center text-xs text-slate-400">
                                            No students found matching &quot;{searchTerm}&quot;.
                                        </div>
                                    )
                                ) : isLoadingParents ? (
                                    <div className="py-8 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
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
                                                className={`w-full flex items-center justify-between p-2.5 rounded-lg text-left text-xs transition-colors cursor-pointer ${
                                                    isSelected
                                                        ? "bg-sky-100/70 text-sky-900 dark:bg-sky-950/60 dark:text-sky-200 font-semibold"
                                                        : "hover:bg-slate-100 dark:hover:bg-slate-800/60 text-slate-700 dark:text-slate-300"
                                                }`}
                                            >
                                                <div className="flex items-center gap-2.5 min-w-0">
                                                    <User className="h-4 w-4 text-emerald-500 shrink-0" />
                                                    <div className="truncate">
                                                        <div className="font-medium truncate">{fullName || "Unnamed Parent"}</div>
                                                        <div className="text-[11px] text-slate-400">
                                                            {pr.profile_details?.phone || "No phone"} • {pr.occupation || "Parent"}
                                                        </div>
                                                    </div>
                                                </div>
                                                {isSelected && <Check className="h-4 w-4 text-sky-600 shrink-0" />}
                                            </button>
                                        );
                                    })
                                ) : (
                                    <div className="py-8 text-center text-xs text-slate-400">
                                        No parents found matching &quot;{searchTerm}&quot;.
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Relationship Details */}
                        <div className="space-y-4 pt-1">
                            <FormFieldWrapper label="Relationship Type" htmlFor="relation_type" required colSpan="full">
                                <Select value={relationType} onValueChange={setRelationType}>
                                    <SelectTrigger id="relation_type">
                                        <SelectValue placeholder="Select relation" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="father">Father</SelectItem>
                                        <SelectItem value="mother">Mother</SelectItem>
                                        <SelectItem value="guardian">Legal Guardian</SelectItem>
                                        <SelectItem value="other">Other Relative</SelectItem>
                                    </SelectContent>
                                </Select>
                            </FormFieldWrapper>

                            <div className="flex items-center justify-between p-3.5 bg-slate-50 dark:bg-slate-900/60 border border-slate-100 dark:border-slate-800 rounded-xl">
                                <div className="space-y-0.5">
                                    <div className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                                        Primary Emergency Contact
                                    </div>
                                    <div className="text-[11px] text-slate-400">
                                        Unsets any previous primary contact for this student.
                                    </div>
                                </div>
                                <Switch
                                    checked={isPrimaryContact}
                                    onCheckedChange={setIsPrimaryContact}
                                />
                            </div>

                            <div className="flex items-center justify-between p-3.5 bg-slate-50 dark:bg-slate-900/60 border border-slate-100 dark:border-slate-800 rounded-xl">
                                <div className="space-y-0.5">
                                    <div className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                                        Authorized for Student Pickup
                                    </div>
                                    <div className="text-[11px] text-slate-400">
                                        Allowed to sign student out of campus premises.
                                    </div>
                                </div>
                                <Switch
                                    checked={canPickup}
                                    onCheckedChange={setCanPickup}
                                />
                            </div>
                        </div>
                    </DialogBody>

                    <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => handleOpenChange(false)}
                            disabled={isLinking}
                        >
                            Cancel
                        </Button>
                        <Button
                            type="submit"
                            disabled={!finalStudentId || !finalParentId || isLinking}
                            className="bg-sky-600 hover:bg-sky-700 text-white min-w-[120px]"
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
