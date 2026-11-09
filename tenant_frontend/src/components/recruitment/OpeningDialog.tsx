"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogBody,
    DialogContent,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    FormSection,
    FormGrid,
    FormFieldWrapper,
} from "@/components/ui/form-layout";
import { useSaveOpening } from "@/hooks/useRecruitment";
import type { JobOpening, PositionType } from "@/types/Recruitment";
import { Loader2 } from "lucide-react";

export function OpeningDialog({ opening, onClose }: { opening: JobOpening | null; onClose: () => void }) {
    const save = useSaveOpening();
    const [title, setTitle] = useState(opening?.title ?? "");
    const [positionType, setPositionType] = useState<PositionType>(opening?.position_type ?? "instructor");
    const [department, setDepartment] = useState(opening?.department ?? "");
    const [specialization, setSpecialization] = useState(opening?.specialization ?? "");
    const [vacancies, setVacancies] = useState(String(opening?.vacancies ?? 1));
    const [minExperience, setMinExperience] = useState(String(opening?.min_experience_years ?? 0));
    const [lastDate, setLastDate] = useState(opening?.last_date ?? "");
    const [description, setDescription] = useState(opening?.description ?? "");
    const [requirements, setRequirements] = useState(opening?.requirements ?? "");

    const submit = () => {
        save.mutate(
            {
                id: opening?.id,
                data: {
                    title: title.trim(),
                    position_type: positionType,
                    department: department.trim(),
                    specialization: specialization.trim(),
                    vacancies: Number(vacancies) || 1,
                    min_experience_years: Number(minExperience) || 0,
                    last_date: lastDate || null,
                    description: description.trim(),
                    requirements: requirements.trim(),
                },
            },
            { onSuccess: onClose },
        );
    };

    return (
        <Dialog open onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-xl max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl">
                <DialogHeader className="px-6 py-4.5 border-b border-slate-100 dark:border-slate-800 shrink-0">
                    <DialogTitle className="text-lg font-bold text-slate-900 dark:text-white">
                        {opening ? "Edit Job Opening" : "New Job Opening"}
                    </DialogTitle>
                </DialogHeader>

                <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-5">
                    <FormFieldWrapper label="Position Title" htmlFor="opening_title" required colSpan="full">
                        <Input
                            id="opening_title"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            placeholder="e.g. Mathematics Teacher (Grades 6-8)"
                        />
                    </FormFieldWrapper>

                    <FormGrid>
                        <FormFieldWrapper label="Position Type" htmlFor="pos_type" required>
                            <Select value={positionType} onValueChange={(v) => setPositionType(v as PositionType)}>
                                <SelectTrigger id="pos_type">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="instructor">Instructor (Teaching)</SelectItem>
                                    <SelectItem value="staff">General Staff</SelectItem>
                                </SelectContent>
                            </Select>
                        </FormFieldWrapper>

                        <FormFieldWrapper label="Vacancies" htmlFor="vacancies" required>
                            <Input
                                id="vacancies"
                                type="number"
                                min={1}
                                value={vacancies}
                                onChange={(e) => setVacancies(e.target.value)}
                            />
                        </FormFieldWrapper>

                        <FormFieldWrapper label="Department" htmlFor="dept">
                            <Input
                                id="dept"
                                value={department}
                                onChange={(e) => setDepartment(e.target.value)}
                                placeholder="e.g. Science"
                            />
                        </FormFieldWrapper>

                        <FormFieldWrapper
                            label={positionType === "instructor" ? "Subject / Specialization" : "Area"}
                            htmlFor="spec"
                        >
                            <Input
                                id="spec"
                                value={specialization}
                                onChange={(e) => setSpecialization(e.target.value)}
                                placeholder="e.g. Physics / Calculus"
                            />
                        </FormFieldWrapper>

                        <FormFieldWrapper label="Minimum Experience (Years)" htmlFor="min_exp">
                            <Input
                                id="min_exp"
                                type="number"
                                min={0}
                                value={minExperience}
                                onChange={(e) => setMinExperience(e.target.value)}
                            />
                        </FormFieldWrapper>

                        <FormFieldWrapper label="Last Date to Apply" htmlFor="last_date">
                            <Input
                                id="last_date"
                                type="date"
                                value={lastDate}
                                onChange={(e) => setLastDate(e.target.value)}
                            />
                        </FormFieldWrapper>
                    </FormGrid>

                    <FormFieldWrapper label="Job Description" htmlFor="desc" colSpan="full">
                        <Textarea
                            id="desc"
                            rows={3}
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            placeholder="Key duties, classroom roles, and responsibilities..."
                        />
                    </FormFieldWrapper>

                    <FormFieldWrapper label="Candidate Requirements" htmlFor="reqs" colSpan="full">
                        <Textarea
                            id="reqs"
                            rows={3}
                            value={requirements}
                            onChange={(e) => setRequirements(e.target.value)}
                            placeholder="Degrees, certifications, languages, and technical skills..."
                        />
                    </FormFieldWrapper>
                </DialogBody>

                <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                    <Button variant="outline" onClick={onClose} disabled={save.isPending}>
                        Cancel
                    </Button>
                    <Button
                        onClick={submit}
                        disabled={!title.trim() || save.isPending}
                        className="bg-sky-600 hover:bg-sky-700 text-white min-w-[120px]"
                    >
                        {save.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                        {opening ? "Save Changes" : "Create Opening"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
