"use client";

import React, { useState } from "react";
import {
    Dialog,
    DialogBody,
    DialogContent,
    DialogFooter,
} from "@/components/ui/dialog";
import { ModalHeader } from "@/components/ui/modal-header";
import { Button } from "@/components/ui/button";
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
    FormGrid3,
    FormFieldWrapper,
} from "@/components/ui/form-layout";
import { useAcademicLevels, useAcademicYears } from "@/hooks/useAcademics";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { useCreateApplication } from "@/hooks/useAdmissions";
import { AdmissionApplication } from "@/types/Admissions";
import { Loader2 } from "lucide-react";

interface NewApplicationDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export default function NewApplicationDialog({
    open,
    onOpenChange,
}: NewApplicationDialogProps) {
    const { selectedYear, currentYear } = useAcademicYear();
    const activeYear = selectedYear || currentYear;
    const { data: levels = [] } = useAcademicLevels();
    const { data: years = [] } = useAcademicYears();

    const createMutation = useCreateApplication();

    const [firstName, setFirstName] = useState("");
    const [middleName, setMiddleName] = useState("");
    const [lastName, setLastName] = useState("");
    const [dateOfBirth, setDateOfBirth] = useState("");
    const [gender, setGender] = useState<"male" | "female" | "other">("male");
    const [phone, setPhone] = useState("");
    const [email, setEmail] = useState("");
    const [address, setAddress] = useState("");
    const [previousSchool, setPreviousSchool] = useState("");
    const [lastGradePassed, setLastGradePassed] = useState("");

    const [guardianFirstName, setGuardianFirstName] = useState("");
    const [guardianLastName, setGuardianLastName] = useState("");
    const [guardianRelationship, setGuardianRelationship] = useState("father");
    const [guardianPhone, setGuardianPhone] = useState("");
    const [guardianEmail, setGuardianEmail] = useState("");
    const [guardianOccupation, setGuardianOccupation] = useState("");

    const [secondaryName, setSecondaryName] = useState("");
    const [secondaryRel, setSecondaryRel] = useState("");
    const [secondaryPhone, setSecondaryPhone] = useState("");

    const [level, setLevel] = useState<string>("");
    const [academicYear, setAcademicYear] = useState<string>(activeYear?.name || "2026-27");
    const [notes, setNotes] = useState("");

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!level) return;

        const payload: Partial<AdmissionApplication> = {
            first_name: firstName.trim(),
            middle_name: middleName.trim(),
            last_name: lastName.trim(),
            date_of_birth: dateOfBirth,
            gender,
            phone: phone.trim() || undefined,
            email: email.trim() || undefined,
            address: address.trim(),
            previous_school: previousSchool.trim(),
            last_grade_passed: lastGradePassed.trim(),
            guardian_first_name: guardianFirstName.trim(),
            guardian_last_name: guardianLastName.trim(),
            guardian_relationship: guardianRelationship,
            guardian_phone: guardianPhone.trim(),
            guardian_email: guardianEmail.trim() || undefined,
            guardian_occupation: guardianOccupation.trim(),
            guardian_address: address.trim(),
            secondary_guardian_name: secondaryName.trim() || undefined,
            secondary_guardian_relationship: secondaryRel.trim() || undefined,
            secondary_guardian_phone: secondaryPhone.trim() || undefined,
            level,
            academic_year: academicYear || (activeYear?.name ?? "2026-27"),
            notes: notes.trim(),
        };

        createMutation.mutate(payload, {
            onSuccess: () => {
                onOpenChange(false);
                // Reset form fields
                setFirstName("");
                setMiddleName("");
                setLastName("");
                setDateOfBirth("");
                setPhone("");
                setEmail("");
                setAddress("");
                setPreviousSchool("");
                setLastGradePassed("");
                setGuardianFirstName("");
                setGuardianLastName("");
                setGuardianPhone("");
                setGuardianEmail("");
                setGuardianOccupation("");
                setSecondaryName("");
                setSecondaryRel("");
                setSecondaryPhone("");
                setNotes("");
            },
        });
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-4xl max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                <ModalHeader
                    title="New Admission Application"
                    subtitle="Register a new student application with personal, guardian, and placement details."
                    onClose={() => onOpenChange(false)}
                />

                <form onSubmit={handleSubmit} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                    <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-6">
                        {/* Section 1: Prospective Student */}
                        <FormSection title="1. Student Personal Information">
                            <FormGrid3>
                                <FormFieldWrapper label="First Name" htmlFor="appFirstName" required>
                                    <Input
                                        id="appFirstName"
                                        required
                                        value={firstName}
                                        onChange={(e) => setFirstName(e.target.value)}
                                        placeholder="e.g. Diya"
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Middle Name" htmlFor="appMiddleName">
                                    <Input
                                        id="appMiddleName"
                                        value={middleName}
                                        onChange={(e) => setMiddleName(e.target.value)}
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Last Name" htmlFor="appLastName" required>
                                    <Input
                                        id="appLastName"
                                        required
                                        value={lastName}
                                        onChange={(e) => setLastName(e.target.value)}
                                        placeholder="e.g. Patel"
                                    />
                                </FormFieldWrapper>
                            </FormGrid3>

                            <FormGrid3 className="mt-4">
                                <FormFieldWrapper label="Date of Birth" htmlFor="appDob" required>
                                    <Input
                                        id="appDob"
                                        required
                                        type="date"
                                        value={dateOfBirth}
                                        onChange={(e) => setDateOfBirth(e.target.value)}
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Gender" htmlFor="appGender" required>
                                    <Select
                                        value={gender}
                                        onValueChange={(v) => setGender(v as "male" | "female" | "other")}
                                    >
                                        <SelectTrigger id="appGender">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="male">Male</SelectItem>
                                            <SelectItem value="female">Female</SelectItem>
                                            <SelectItem value="other">Other</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Student Phone" htmlFor="appPhone">
                                    <Input
                                        id="appPhone"
                                        value={phone}
                                        onChange={(e) => setPhone(e.target.value)}
                                        placeholder="Optional"
                                    />
                                </FormFieldWrapper>
                            </FormGrid3>

                            <FormGrid className="mt-4">
                                <FormFieldWrapper label="Previous School" htmlFor="appPrevSchool">
                                    <Input
                                        id="appPrevSchool"
                                        value={previousSchool}
                                        onChange={(e) => setPreviousSchool(e.target.value)}
                                        placeholder="e.g. Modern Public School"
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Last Class / Grade Passed" htmlFor="appLastGrade">
                                    <Input
                                        id="appLastGrade"
                                        value={lastGradePassed}
                                        onChange={(e) => setLastGradePassed(e.target.value)}
                                        placeholder="e.g. Grade 4"
                                    />
                                </FormFieldWrapper>
                            </FormGrid>

                            <div className="mt-4">
                                <FormFieldWrapper label="Residential Address" htmlFor="appAddress" required colSpan="full">
                                    <Input
                                        id="appAddress"
                                        required
                                        value={address}
                                        onChange={(e) => setAddress(e.target.value)}
                                        placeholder="Complete street, area, city, pincode"
                                    />
                                </FormFieldWrapper>
                            </div>
                        </FormSection>

                        {/* Section 2: Guardian Details */}
                        <FormSection title="2. Primary Guardian Details">
                            <FormGrid3>
                                <FormFieldWrapper label="Guardian First Name" htmlFor="gFirstName" required>
                                    <Input
                                        id="gFirstName"
                                        required
                                        value={guardianFirstName}
                                        onChange={(e) => setGuardianFirstName(e.target.value)}
                                        placeholder="e.g. Suresh"
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Guardian Last Name" htmlFor="gLastName" required>
                                    <Input
                                        id="gLastName"
                                        required
                                        value={guardianLastName}
                                        onChange={(e) => setGuardianLastName(e.target.value)}
                                        placeholder="e.g. Patel"
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Relationship" htmlFor="gRel" required>
                                    <Select
                                        value={guardianRelationship}
                                        onValueChange={setGuardianRelationship}
                                    >
                                        <SelectTrigger id="gRel">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="father">Father</SelectItem>
                                            <SelectItem value="mother">Mother</SelectItem>
                                            <SelectItem value="guardian">Legal Guardian</SelectItem>
                                            <SelectItem value="other">Other</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </FormFieldWrapper>
                            </FormGrid3>

                            <FormGrid3 className="mt-4">
                                <FormFieldWrapper label="Guardian Phone" htmlFor="gPhone" required>
                                    <Input
                                        id="gPhone"
                                        required
                                        value={guardianPhone}
                                        onChange={(e) => setGuardianPhone(e.target.value)}
                                        placeholder="e.g. +91 98112 23344"
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Guardian Email" htmlFor="gEmail">
                                    <Input
                                        id="gEmail"
                                        type="email"
                                        value={guardianEmail}
                                        onChange={(e) => setGuardianEmail(e.target.value)}
                                        placeholder="e.g. guardian@example.com"
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Occupation" htmlFor="gOcc">
                                    <Input
                                        id="gOcc"
                                        value={guardianOccupation}
                                        onChange={(e) => setGuardianOccupation(e.target.value)}
                                        placeholder="e.g. Architect"
                                    />
                                </FormFieldWrapper>
                            </FormGrid3>

                            {/* Optional Secondary Guardian */}
                            <div className="mt-4 p-4 rounded-xl bg-slate-50/70 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-800 space-y-3">
                                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                                    Secondary Contact / Co-Guardian (Optional)
                                </span>
                                <FormGrid3>
                                    <Input
                                        aria-label="Co-Guardian Name"
                                        placeholder="Co-Guardian Name"
                                        value={secondaryName}
                                        onChange={(e) => setSecondaryName(e.target.value)}
                                    />
                                    <Input
                                        aria-label="Relationship (e.g. Mother)"
                                        placeholder="Relationship (e.g. Mother)"
                                        value={secondaryRel}
                                        onChange={(e) => setSecondaryRel(e.target.value)}
                                    />
                                    <Input
                                        aria-label="Contact Phone"
                                        placeholder="Contact Phone"
                                        value={secondaryPhone}
                                        onChange={(e) => setSecondaryPhone(e.target.value)}
                                    />
                                </FormGrid3>
                            </div>
                        </FormSection>

                        {/* Section 3: Academic Placement */}
                        <FormSection title="3. Grade Level & Academic Year">
                            <FormGrid>
                                <FormFieldWrapper label="Grade Level" htmlFor="appLevel" required>
                                    <Select value={level} onValueChange={setLevel} required>
                                        <SelectTrigger id="appLevel">
                                            <SelectValue placeholder="Select target grade level" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {levels.map((lvl) => (
                                                <SelectItem key={lvl.id} value={lvl.id}>
                                                    {lvl.name}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Academic Year" htmlFor="appYear" required>
                                    <Input
                                        id="appYear"
                                        required
                                        value={academicYear}
                                        onChange={(e) => setAcademicYear(e.target.value)}
                                        placeholder="e.g. 2026-27"
                                    />
                                </FormFieldWrapper>
                            </FormGrid>

                            <div className="mt-4">
                                <FormFieldWrapper label="Notes / Special Requirements" htmlFor="appNotes" colSpan="full">
                                    <Textarea
                                        id="appNotes"
                                        rows={3}
                                        value={notes}
                                        onChange={(e) => setNotes(e.target.value)}
                                        placeholder="Additional requirements or special remarks..."
                                    />
                                </FormFieldWrapper>
                            </div>
                        </FormSection>
                    </DialogBody>

                    <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => onOpenChange(false)}
                            disabled={createMutation.isPending}
                        >
                            Cancel
                        </Button>
                        <Button
                            type="submit"
                            disabled={createMutation.isPending || !level}
                        >
                            {createMutation.isPending && (
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            )}
                            Submit Application
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
