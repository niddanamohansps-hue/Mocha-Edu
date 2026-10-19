"use client";

import React, { useState } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
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
                // reset form
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
            <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto rounded-3xl">
                <DialogHeader>
                    <DialogTitle className="text-xl font-bold">
                        New Admission Application
                    </DialogTitle>
                </DialogHeader>

                <form onSubmit={handleSubmit} className="space-y-6 pt-2">
                    {/* Section 1: Prospective Student */}
                    <div>
                        <h4 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">
                            1. Student Personal Information
                        </h4>
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                            <div className="space-y-1.5">
                                <Label htmlFor="appFirstName">First Name *</Label>
                                <Input
                                    id="appFirstName"
                                    required
                                    value={firstName}
                                    onChange={(e) => setFirstName(e.target.value)}
                                    placeholder="e.g. Diya"
                                />
                            </div>
                            <div className="space-y-1.5">
                                <Label htmlFor="appMiddleName">Middle Name</Label>
                                <Input
                                    id="appMiddleName"
                                    value={middleName}
                                    onChange={(e) => setMiddleName(e.target.value)}
                                />
                            </div>
                            <div className="space-y-1.5">
                                <Label htmlFor="appLastName">Last Name *</Label>
                                <Input
                                    id="appLastName"
                                    required
                                    value={lastName}
                                    onChange={(e) => setLastName(e.target.value)}
                                    placeholder="e.g. Patel"
                                />
                            </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
                            <div className="space-y-1.5">
                                <Label htmlFor="appDob">Date of Birth *</Label>
                                <Input
                                    id="appDob"
                                    required
                                    type="date"
                                    value={dateOfBirth}
                                    onChange={(e) => setDateOfBirth(e.target.value)}
                                />
                            </div>
                            <div className="space-y-1.5">
                                <Label htmlFor="appGender">Gender *</Label>
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
                            </div>
                            <div className="space-y-1.5">
                                <Label htmlFor="appPhone">Student Phone</Label>
                                <Input
                                    id="appPhone"
                                    value={phone}
                                    onChange={(e) => setPhone(e.target.value)}
                                    placeholder="Optional"
                                />
                            </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
                            <div className="space-y-1.5">
                                <Label htmlFor="appPrevSchool">Previous School</Label>
                                <Input
                                    id="appPrevSchool"
                                    value={previousSchool}
                                    onChange={(e) => setPreviousSchool(e.target.value)}
                                    placeholder="e.g. Modern Public School"
                                />
                            </div>
                            <div className="space-y-1.5">
                                <Label htmlFor="appLastGrade">Last Class / Grade Passed</Label>
                                <Input
                                    id="appLastGrade"
                                    value={lastGradePassed}
                                    onChange={(e) => setLastGradePassed(e.target.value)}
                                    placeholder="e.g. Grade 4"
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5 mt-4">
                            <Label htmlFor="appAddress">Residential Address *</Label>
                            <Input
                                id="appAddress"
                                required
                                value={address}
                                onChange={(e) => setAddress(e.target.value)}
                                placeholder="Complete street, area, city, pincode"
                            />
                        </div>
                    </div>

                    {/* Section 2: Guardian Details */}
                    <div>
                        <h4 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">
                            2. Primary Guardian Details
                        </h4>
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                            <div className="space-y-1.5">
                                <Label htmlFor="gFirstName">Guardian First Name *</Label>
                                <Input
                                    id="gFirstName"
                                    required
                                    value={guardianFirstName}
                                    onChange={(e) => setGuardianFirstName(e.target.value)}
                                    placeholder="e.g. Suresh"
                                />
                            </div>
                            <div className="space-y-1.5">
                                <Label htmlFor="gLastName">Guardian Last Name *</Label>
                                <Input
                                    id="gLastName"
                                    required
                                    value={guardianLastName}
                                    onChange={(e) => setGuardianLastName(e.target.value)}
                                    placeholder="e.g. Patel"
                                />
                            </div>
                            <div className="space-y-1.5">
                                <Label htmlFor="gRel">Relationship *</Label>
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
                            </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
                            <div className="space-y-1.5">
                                <Label htmlFor="gPhone">Guardian Phone *</Label>
                                <Input
                                    id="gPhone"
                                    required
                                    value={guardianPhone}
                                    onChange={(e) => setGuardianPhone(e.target.value)}
                                    placeholder="e.g. +91 98112 23344"
                                />
                            </div>
                            <div className="space-y-1.5">
                                <Label htmlFor="gEmail">Guardian Email</Label>
                                <Input
                                    id="gEmail"
                                    type="email"
                                    value={guardianEmail}
                                    onChange={(e) => setGuardianEmail(e.target.value)}
                                    placeholder="e.g. guardian@example.com"
                                />
                            </div>
                            <div className="space-y-1.5">
                                <Label htmlFor="gOcc">Occupation</Label>
                                <Input
                                    id="gOcc"
                                    value={guardianOccupation}
                                    onChange={(e) => setGuardianOccupation(e.target.value)}
                                    placeholder="e.g. Architect"
                                />
                            </div>
                        </div>

                        {/* Optional Secondary Guardian */}
                        <div className="mt-4 p-4 rounded-2xl bg-slate-50/70 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-800 space-y-3">
                            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                                Secondary Contact / Co-Guardian (Optional)
                            </span>
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                <Input
                                    placeholder="Co-Guardian Name"
                                    value={secondaryName}
                                    onChange={(e) => setSecondaryName(e.target.value)}
                                />
                                <Input
                                    placeholder="Relationship (e.g. Mother)"
                                    value={secondaryRel}
                                    onChange={(e) => setSecondaryRel(e.target.value)}
                                />
                                <Input
                                    placeholder="Contact Phone"
                                    value={secondaryPhone}
                                    onChange={(e) => setSecondaryPhone(e.target.value)}
                                />
                            </div>
                        </div>
                    </div>

                    {/* Section 3: Academic Placement */}
                    <div>
                        <h4 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">
                            3. Grade Level & Academic Year
                        </h4>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                                <Label htmlFor="appLevel">Grade Level *</Label>
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
                            </div>
                            <div className="space-y-1.5">
                                <Label htmlFor="appYear">Academic Year *</Label>
                                <Input
                                    id="appYear"
                                    required
                                    value={academicYear}
                                    onChange={(e) => setAcademicYear(e.target.value)}
                                    placeholder="e.g. 2026-27"
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5 mt-4">
                            <Label htmlFor="appNotes">Notes / Special Requirements</Label>
                            <Textarea
                                id="appNotes"
                                rows={2}
                                value={notes}
                                onChange={(e) => setNotes(e.target.value)}
                                placeholder="Additional requirements or special remarks..."
                            />
                        </div>
                    </div>

                    <DialogFooter className="gap-2 sm:gap-0 pt-4 border-t">
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
                            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold"
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

