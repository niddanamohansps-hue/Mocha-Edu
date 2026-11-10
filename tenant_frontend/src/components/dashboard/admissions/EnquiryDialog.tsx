"use client";

import React, { useState, useEffect } from "react";
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
import { useCreateEnquiry, useUpdateEnquiry } from "@/hooks/useAdmissions";
import { AdmissionEnquiry, EnquirySource, EnquiryStatus } from "@/types/Admissions";
import { Loader2 } from "lucide-react";

interface EnquiryDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    enquiry?: AdmissionEnquiry | null;
}

export default function EnquiryDialog({
    open,
    onOpenChange,
    enquiry,
}: EnquiryDialogProps) {
    const isEdit = !!enquiry;
    const { selectedYear, currentYear } = useAcademicYear();
    const activeYear = selectedYear || currentYear;
    const { data: levels = [] } = useAcademicLevels();
    const { data: years = [] } = useAcademicYears();

    const createMutation = useCreateEnquiry();
    const updateMutation = useUpdateEnquiry();

    const isPending = createMutation.isPending || updateMutation.isPending;

    const [studentName, setStudentName] = useState("");
    const [dateOfBirth, setDateOfBirth] = useState("");
    const [gender, setGender] = useState<string>("other");
    const [guardianName, setGuardianName] = useState("");
    const [guardianRelationship, setGuardianRelationship] = useState("father");
    const [guardianPhone, setGuardianPhone] = useState("");
    const [guardianEmail, setGuardianEmail] = useState("");
    const [address, setAddress] = useState("");
    const [previousSchool, setPreviousSchool] = useState("");
    const [preferredLevel, setPreferredLevel] = useState<string>("");
    const [academicYear, setAcademicYear] = useState<string>("");
    const [source, setSource] = useState<EnquirySource>("walk_in");
    const [status, setStatus] = useState<EnquiryStatus>("new");
    const [followUpDate, setFollowUpDate] = useState("");
    const [notes, setNotes] = useState("");

    useEffect(() => {
        if (enquiry) {
            setStudentName(enquiry.student_name || "");
            setDateOfBirth(enquiry.date_of_birth || "");
            setGender(enquiry.gender || "other");
            setGuardianName(enquiry.guardian_name || "");
            setGuardianRelationship(enquiry.guardian_relationship || "father");
            setGuardianPhone(enquiry.guardian_phone || "");
            setGuardianEmail(enquiry.guardian_email || "");
            setAddress(enquiry.address || "");
            setPreviousSchool(enquiry.previous_school || "");
            setPreferredLevel(enquiry.preferred_level || "");
            setAcademicYear(enquiry.academic_year || activeYear?.name || "");
            setSource(enquiry.source || "walk_in");
            setStatus(enquiry.status || "new");
            setFollowUpDate(enquiry.follow_up_date || "");
            setNotes(enquiry.notes || "");
        } else {
            setStudentName("");
            setDateOfBirth("");
            setGender("other");
            setGuardianName("");
            setGuardianRelationship("father");
            setGuardianPhone("");
            setGuardianEmail("");
            setAddress("");
            setPreviousSchool("");
            setPreferredLevel("");
            setAcademicYear(activeYear?.name || (years[0]?.name ?? "2026-27"));
            setSource("walk_in");
            setStatus("new");
            setFollowUpDate("");
            setNotes("");
        }
    }, [enquiry, open, activeYear, years]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        const payload: Partial<AdmissionEnquiry> = {
            student_name: studentName.trim(),
            date_of_birth: dateOfBirth || null,
            gender,
            guardian_name: guardianName.trim(),
            guardian_relationship: guardianRelationship,
            guardian_phone: guardianPhone.trim(),
            guardian_email: guardianEmail.trim() || undefined,
            address: address.trim(),
            previous_school: previousSchool.trim(),
            preferred_level: preferredLevel || null,
            academic_year: academicYear || (activeYear?.name ?? "2026-27"),
            source,
            status,
            follow_up_date: followUpDate || null,
            notes: notes.trim(),
        };

        if (isEdit && enquiry) {
            updateMutation.mutate(
                { id: enquiry.id, data: payload },
                {
                    onSuccess: () => onOpenChange(false),
                }
            );
        } else {
            createMutation.mutate(payload, {
                onSuccess: () => onOpenChange(false),
            });
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                <ModalHeader
                    title={isEdit ? `Edit Enquiry: ${enquiry?.enquiry_number}` : "New Admission Enquiry"}
                    subtitle="Capture prospective student details, guardian contact, and admission follow-up status."
                    onClose={() => onOpenChange(false)}
                />

                <form onSubmit={handleSubmit} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                    <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-6">
                        {/* Prospective Student Details */}
                        <FormSection title="Prospective Student">
                            <FormGrid>
                                <FormFieldWrapper label="Student Full Name" htmlFor="studentName" required>
                                    <Input
                                        id="studentName"
                                        required
                                        value={studentName}
                                        onChange={(e) => setStudentName(e.target.value)}
                                        placeholder="e.g. Aarav Sharma"
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper label="Gender" htmlFor="gender">
                                    <Select value={gender} onValueChange={setGender}>
                                        <SelectTrigger id="gender">
                                            <SelectValue placeholder="Select gender" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="male">Male</SelectItem>
                                            <SelectItem value="female">Female</SelectItem>
                                            <SelectItem value="other">Other</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </FormFieldWrapper>

                                <FormFieldWrapper label="Date of Birth" htmlFor="dob">
                                    <Input
                                        id="dob"
                                        type="date"
                                        value={dateOfBirth}
                                        onChange={(e) => setDateOfBirth(e.target.value)}
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper label="Preferred Grade Level" htmlFor="preferredLevel">
                                    <Select
                                        value={preferredLevel}
                                        onValueChange={setPreferredLevel}
                                    >
                                        <SelectTrigger id="preferredLevel">
                                            <SelectValue placeholder="Select grade" />
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
                            </FormGrid>
                        </FormSection>

                        {/* Guardian Information */}
                        <FormSection title="Guardian Details">
                            <FormGrid>
                                <FormFieldWrapper label="Guardian Full Name" htmlFor="guardianName" required>
                                    <Input
                                        id="guardianName"
                                        required
                                        value={guardianName}
                                        onChange={(e) => setGuardianName(e.target.value)}
                                        placeholder="e.g. Rajesh Sharma"
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper label="Relationship" htmlFor="guardianRelationship">
                                    <Select
                                        value={guardianRelationship}
                                        onValueChange={setGuardianRelationship}
                                    >
                                        <SelectTrigger id="guardianRelationship">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="father">Father</SelectItem>
                                            <SelectItem value="mother">Mother</SelectItem>
                                            <SelectItem value="guardian">Guardian</SelectItem>
                                            <SelectItem value="other">Other</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </FormFieldWrapper>

                                <FormFieldWrapper label="Contact Phone" htmlFor="guardianPhone" required>
                                    <Input
                                        id="guardianPhone"
                                        required
                                        value={guardianPhone}
                                        onChange={(e) => setGuardianPhone(e.target.value)}
                                        placeholder="e.g. +91 98765 43210"
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper label="Email Address" htmlFor="guardianEmail">
                                    <Input
                                        id="guardianEmail"
                                        type="email"
                                        value={guardianEmail}
                                        onChange={(e) => setGuardianEmail(e.target.value)}
                                        placeholder="e.g. parent@example.com"
                                    />
                                </FormFieldWrapper>
                            </FormGrid>
                        </FormSection>

                        {/* Academic & Source Tracking */}
                        <FormSection title="Academic & Source Details">
                            <FormGrid3>
                                <FormFieldWrapper label="Academic Year" htmlFor="academicYear">
                                    <Input
                                        id="academicYear"
                                        value={academicYear}
                                        onChange={(e) => setAcademicYear(e.target.value)}
                                        placeholder="e.g. 2026-27"
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper label="Lead Source" htmlFor="source">
                                    <Select value={source} onValueChange={(v) => setSource(v as EnquirySource)}>
                                        <SelectTrigger id="source">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="walk_in">Walk-in</SelectItem>
                                            <SelectItem value="website">Website</SelectItem>
                                            <SelectItem value="phone">Phone Call</SelectItem>
                                            <SelectItem value="referral">Referral</SelectItem>
                                            <SelectItem value="campaign">Social / Campaign</SelectItem>
                                            <SelectItem value="other">Other</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </FormFieldWrapper>

                                <FormFieldWrapper label="Enquiry Status" htmlFor="status">
                                    <Select value={status} onValueChange={(v) => setStatus(v as EnquiryStatus)}>
                                        <SelectTrigger id="status">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="new">New</SelectItem>
                                            <SelectItem value="contacted">Contacted</SelectItem>
                                            <SelectItem value="qualified">Qualified</SelectItem>
                                            <SelectItem value="converted">Converted</SelectItem>
                                            <SelectItem value="closed">Closed / Lost</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </FormFieldWrapper>
                            </FormGrid3>

                            <FormGrid className="mt-4">
                                <FormFieldWrapper label="Previous School (Optional)" htmlFor="previousSchool">
                                    <Input
                                        id="previousSchool"
                                        value={previousSchool}
                                        onChange={(e) => setPreviousSchool(e.target.value)}
                                        placeholder="e.g. Little Star Play School"
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper label="Next Follow-up Date" htmlFor="followUpDate">
                                    <Input
                                        id="followUpDate"
                                        type="date"
                                        value={followUpDate}
                                        onChange={(e) => setFollowUpDate(e.target.value)}
                                    />
                                </FormFieldWrapper>
                            </FormGrid>

                            <div className="space-y-4 mt-4">
                                <FormFieldWrapper label="Current Residential Address" htmlFor="address" colSpan="full">
                                    <Input
                                        id="address"
                                        value={address}
                                        onChange={(e) => setAddress(e.target.value)}
                                        placeholder="City, locality or address"
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper label="Internal Discussion / Notes" htmlFor="notes" colSpan="full">
                                    <Textarea
                                        id="notes"
                                        rows={3}
                                        value={notes}
                                        onChange={(e) => setNotes(e.target.value)}
                                        placeholder="Notes on guardian queries, visit schedules, transport needs..."
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
                            disabled={isPending}
                        >
                            Cancel
                        </Button>
                        <Button type="submit" disabled={isPending}>
                            {isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                            {isEdit ? "Save Changes" : "Create Enquiry"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
