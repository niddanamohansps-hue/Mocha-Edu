"use client";

import React, { useState, useEffect } from "react";
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
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto rounded-3xl">
                <DialogHeader>
                    <DialogTitle className="text-xl font-bold">
                        {isEdit ? `Edit Enquiry: ${enquiry?.enquiry_number}` : "New Admission Enquiry"}
                    </DialogTitle>
                </DialogHeader>

                <form onSubmit={handleSubmit} className="space-y-6 pt-2">
                    {/* Prospective Student Details */}
                    <div>
                        <h4 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">
                            Prospective Student
                        </h4>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                                <Label htmlFor="studentName">Student Full Name *</Label>
                                <Input
                                    id="studentName"
                                    required
                                    value={studentName}
                                    onChange={(e) => setStudentName(e.target.value)}
                                    placeholder="e.g. Aarav Sharma"
                                />
                            </div>

                            <div className="space-y-1.5">
                                <Label htmlFor="gender">Gender</Label>
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
                            </div>

                            <div className="space-y-1.5">
                                <Label htmlFor="dob">Date of Birth</Label>
                                <Input
                                    id="dob"
                                    type="date"
                                    value={dateOfBirth}
                                    onChange={(e) => setDateOfBirth(e.target.value)}
                                />
                            </div>

                            <div className="space-y-1.5">
                                <Label htmlFor="preferredLevel">Preferred Grade Level</Label>
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
                            </div>
                        </div>
                    </div>

                    {/* Guardian Information */}
                    <div>
                        <h4 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">
                            Guardian Details
                        </h4>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                                <Label htmlFor="guardianName">Guardian Full Name *</Label>
                                <Input
                                    id="guardianName"
                                    required
                                    value={guardianName}
                                    onChange={(e) => setGuardianName(e.target.value)}
                                    placeholder="e.g. Rajesh Sharma"
                                />
                            </div>

                            <div className="space-y-1.5">
                                <Label htmlFor="guardianRelationship">Relationship</Label>
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
                            </div>

                            <div className="space-y-1.5">
                                <Label htmlFor="guardianPhone">Contact Phone *</Label>
                                <Input
                                    id="guardianPhone"
                                    required
                                    value={guardianPhone}
                                    onChange={(e) => setGuardianPhone(e.target.value)}
                                    placeholder="e.g. +91 98765 43210"
                                />
                            </div>

                            <div className="space-y-1.5">
                                <Label htmlFor="guardianEmail">Email Address</Label>
                                <Input
                                    id="guardianEmail"
                                    type="email"
                                    value={guardianEmail}
                                    onChange={(e) => setGuardianEmail(e.target.value)}
                                    placeholder="e.g. parent@example.com"
                                />
                            </div>
                        </div>
                    </div>

                    {/* Academic & Source Tracking */}
                    <div>
                        <h4 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-3">
                            Academic & Source Details
                        </h4>
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                            <div className="space-y-1.5">
                                <Label htmlFor="academicYear">Academic Year</Label>
                                <Input
                                    id="academicYear"
                                    value={academicYear}
                                    onChange={(e) => setAcademicYear(e.target.value)}
                                    placeholder="e.g. 2026-27"
                                />
                            </div>

                            <div className="space-y-1.5">
                                <Label htmlFor="source">Lead Source</Label>
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
                            </div>

                            <div className="space-y-1.5">
                                <Label htmlFor="status">Enquiry Status</Label>
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
                            </div>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
                            <div className="space-y-1.5">
                                <Label htmlFor="previousSchool">Previous School (Optional)</Label>
                                <Input
                                    id="previousSchool"
                                    value={previousSchool}
                                    onChange={(e) => setPreviousSchool(e.target.value)}
                                    placeholder="e.g. Little Star Play School"
                                />
                            </div>

                            <div className="space-y-1.5">
                                <Label htmlFor="followUpDate">Next Follow-up Date</Label>
                                <Input
                                    id="followUpDate"
                                    type="date"
                                    value={followUpDate}
                                    onChange={(e) => setFollowUpDate(e.target.value)}
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5 mt-4">
                            <Label htmlFor="address">Current Residential Address</Label>
                            <Input
                                id="address"
                                value={address}
                                onChange={(e) => setAddress(e.target.value)}
                                placeholder="City, locality or address"
                            />
                        </div>

                        <div className="space-y-1.5 mt-4">
                            <Label htmlFor="notes">Internal Discussion / Notes</Label>
                            <Textarea
                                id="notes"
                                rows={3}
                                value={notes}
                                onChange={(e) => setNotes(e.target.value)}
                                placeholder="Notes on guardian queries, visit schedules, transport needs..."
                            />
                        </div>
                    </div>

                    <DialogFooter className="gap-2 sm:gap-0 pt-4 border-t">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => onOpenChange(false)}
                            disabled={isPending}
                        >
                            Cancel
                        </Button>
                        <Button type="submit" disabled={isPending} className="bg-blue-600 hover:bg-blue-700 text-white">
                            {isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                            {isEdit ? "Save Changes" : "Create Enquiry"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

