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
import { useCreateApplicant } from "@/hooks/useRecruitment";
import type { JobOpening } from "@/types/Recruitment";
import { Loader2 } from "lucide-react";

export function AddApplicantDialog({
    openings,
    defaultOpening,
    onClose,
}: {
    openings: JobOpening[];
    defaultOpening?: string;
    onClose: () => void;
}) {
    const create = useCreateApplicant();
    const accepting = openings.filter((o) => o.accepting_applications);
    const [opening, setOpening] = useState(
        accepting.find((o) => o.id === defaultOpening)?.id ?? accepting[0]?.id ?? "",
    );
    const [values, setValues] = useState<Record<string, string>>({ experience_years: "0" });
    const [resume, setResume] = useState<File | null>(null);
    const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
        setValues((v) => ({ ...v, [key]: e.target.value }));

    const submit = () => {
        const form = new FormData();
        form.append("opening", opening);
        Object.entries(values).forEach(([key, value]) => value !== "" && form.append(key, value));
        if (resume) form.append("resume", resume);
        create.mutate(form, { onSuccess: onClose });
    };

    return (
        <Dialog open onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-xl max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl">
                <DialogHeader className="px-6 py-4.5 border-b border-slate-100 dark:border-slate-800 shrink-0">
                    <DialogTitle className="text-lg font-bold text-slate-900 dark:text-white">
                        Add New Applicant
                    </DialogTitle>
                </DialogHeader>

                <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-5">
                    {accepting.length === 0 ? (
                        <p className="text-sm text-slate-500 py-6 text-center">
                            No opening is accepting applications. Publish an opening first (and check its last date).
                        </p>
                    ) : (
                        <>
                            <FormFieldWrapper label="Job Opening" htmlFor="target_opening" required colSpan="full">
                                <Select value={opening} onValueChange={setOpening}>
                                    <SelectTrigger id="target_opening">
                                        <SelectValue placeholder="Select target opening" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {accepting.map((o) => (
                                            <SelectItem key={o.id} value={o.id}>
                                                {o.title}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </FormFieldWrapper>

                            <FormGrid>
                                <FormFieldWrapper label="First Name" htmlFor="app_fn" required>
                                    <Input
                                        id="app_fn"
                                        placeholder="e.g. Ananya"
                                        onChange={set("first_name")}
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper label="Last Name" htmlFor="app_ln" required>
                                    <Input
                                        id="app_ln"
                                        placeholder="e.g. Verma"
                                        onChange={set("last_name")}
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper label="Email Address" htmlFor="app_email">
                                    <Input
                                        id="app_email"
                                        type="email"
                                        placeholder="e.g. ananya@example.com"
                                        onChange={set("email")}
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper label="Phone Number" htmlFor="app_phone">
                                    <Input
                                        id="app_phone"
                                        placeholder="e.g. +91 98765 43210"
                                        onChange={set("phone")}
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper label="Gender" htmlFor="app_gender">
                                    <Select
                                        value={values.gender || "not_stated"}
                                        onValueChange={(val) => setValues((v) => ({ ...v, gender: val === "not_stated" ? "" : val }))}
                                    >
                                        <SelectTrigger id="app_gender">
                                            <SelectValue placeholder="Not stated" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="not_stated">Not stated</SelectItem>
                                            <SelectItem value="male">Male</SelectItem>
                                            <SelectItem value="female">Female</SelectItem>
                                            <SelectItem value="other">Other</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </FormFieldWrapper>

                                <FormFieldWrapper label="Date of Birth" htmlFor="app_dob">
                                    <Input
                                        id="app_dob"
                                        type="date"
                                        onChange={set("date_of_birth")}
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper label="Highest Qualification" htmlFor="app_qual">
                                    <Input
                                        id="app_qual"
                                        placeholder="e.g. M.Sc. Mathematics, B.Ed."
                                        onChange={set("qualification")}
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper label="Experience (Years)" htmlFor="app_exp">
                                    <Input
                                        id="app_exp"
                                        type="number"
                                        min={0}
                                        defaultValue={0}
                                        onChange={set("experience_years")}
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper label="Current Employer" htmlFor="app_emp">
                                    <Input
                                        id="app_emp"
                                        placeholder="e.g. Delhi Public School"
                                        onChange={set("current_employer")}
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper label="Expected Monthly Salary" htmlFor="app_salary">
                                    <Input
                                        id="app_salary"
                                        type="number"
                                        min={0}
                                        placeholder="e.g. 45000"
                                        onChange={set("expected_salary")}
                                    />
                                </FormFieldWrapper>
                            </FormGrid>

                            <FormFieldWrapper label="Lead / Application Source" htmlFor="app_source" colSpan="full">
                                <Input
                                    id="app_source"
                                    placeholder="e.g. Newspaper ad, referral, walk-in, website..."
                                    onChange={set("source")}
                                />
                            </FormFieldWrapper>

                            <FormFieldWrapper label="Cover Note / Discussion Summary" htmlFor="app_note" colSpan="full">
                                <Textarea
                                    id="app_note"
                                    rows={2}
                                    placeholder="Remarks on candidate background, subject knowledge, availability..."
                                    onChange={set("cover_note")}
                                />
                            </FormFieldWrapper>

                            <FormFieldWrapper label="Resume Document" htmlFor="app_resume" colSpan="full">
                                <Input
                                    id="app_resume"
                                    type="file"
                                    accept=".pdf,.doc,.docx"
                                    onChange={(e) => setResume(e.target.files?.[0] ?? null)}
                                    className="file:mr-3 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-sky-50 file:text-sky-700 hover:file:bg-sky-100"
                                />
                                <p className="text-[11px] text-slate-400 mt-1">
                                    Accepted formats: PDF, DOC, DOCX (Max 5 MB).
                                </p>
                            </FormFieldWrapper>
                        </>
                    )}
                </DialogBody>

                <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                    <Button variant="outline" onClick={onClose} disabled={create.isPending}>
                        Cancel
                    </Button>
                    <Button
                        onClick={submit}
                        disabled={!opening || !values.first_name?.trim() || !values.last_name?.trim() || create.isPending}
                        className="bg-sky-600 hover:bg-sky-700 text-white min-w-[120px]"
                    >
                        {create.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                        Add Applicant
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
