"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
    usePublicAdmissionsInfo,
    useSubmitPublicApplication,
    useSubmitPublicEnquiry,
} from "@/hooks/useAdmissions";
import {
    PublicApplicationPayload,
    PublicEnquiryPayload,
    PublicApplicationSubmissionResult,
} from "@/types/Admissions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
    GraduationCap,
    School,
    CheckCircle2,
    Calendar,
    Phone,
    Mail,
    MapPin,
    ArrowRight,
    ArrowLeft,
    Copy,
    Check,
    FileText,
    Shield,
    Sparkles,
    AlertCircle,
    Loader2,
    HelpCircle,
    ExternalLink,
} from "lucide-react";

export default function PublicApplyPage() {
    const { data: info, isLoading: isInfoLoading } = usePublicAdmissionsInfo();

    const [formMode, setFormMode] = useState<"apply" | "enquiry">("apply");
    const [step, setStep] = useState<number>(1);
    const [submissionResult, setSubmissionResult] = useState<PublicApplicationSubmissionResult | null>(null);
    const [enquirySuccess, setEnquirySuccess] = useState<string | null>(null);
    const [copiedRef, setCopiedRef] = useState(false);
    const [copiedToken, setCopiedToken] = useState(false);

    // Form fields
    const [firstName, setFirstName] = useState("");
    const [middleName, setMiddleName] = useState("");
    const [lastName, setLastName] = useState("");
    const [dateOfBirth, setDateOfBirth] = useState("");
    const [gender, setGender] = useState<"male" | "female" | "other">("male");
    const [studentEmail, setStudentEmail] = useState("");
    const [studentPhone, setStudentPhone] = useState("");
    const [studentAddress, setStudentAddress] = useState("");
    const [previousSchool, setPreviousSchool] = useState("");
    const [lastGradePassed, setLastGradePassed] = useState("");

    const [guardianFirstName, setGuardianFirstName] = useState("");
    const [guardianLastName, setGuardianLastName] = useState("");
    const [guardianRelationship, setGuardianRelationship] = useState("father");
    const [guardianPhone, setGuardianPhone] = useState("");
    const [guardianEmail, setGuardianEmail] = useState("");
    const [guardianOccupation, setGuardianOccupation] = useState("");
    const [guardianAddress, setGuardianAddress] = useState("");

    const [secGuardianName, setSecGuardianName] = useState("");
    const [secGuardianRel, setSecGuardianRel] = useState("");
    const [secGuardianPhone, setSecGuardianPhone] = useState("");

    const [selectedLevelId, setSelectedLevelId] = useState("");
    const [selectedYearId, setSelectedYearId] = useState("");
    const [enquiryNumberRef, setEnquiryNumberRef] = useState("");
    const [consent, setConsent] = useState(false);

    // Enquiry quick form
    const [enqStudentName, setEnqStudentName] = useState("");
    const [enqGuardianName, setEnqGuardianName] = useState("");
    const [enqRelationship, setEnqRelationship] = useState("parent");
    const [enqPhone, setEnqPhone] = useState("");
    const [enqEmail, setEnqEmail] = useState("");
    const [enqLevelId, setEnqLevelId] = useState("");
    const [enqYearId, setEnqYearId] = useState("");
    const [enqNotes, setEnqNotes] = useState("");
    const [enqConsent, setEnqConsent] = useState(false);

    const applyMutation = useSubmitPublicApplication();
    const enquiryMutation = useSubmitPublicEnquiry();

    // Set defaults when info loads
    React.useEffect(() => {
        if (info) {
            if (info.academic_years?.length > 0 && !selectedYearId) {
                const cur = info.academic_years.find((y) => y.is_current) || info.academic_years[0];
                setSelectedYearId(cur.id);
                setEnqYearId(cur.id);
            }
            if (info.levels?.length > 0 && !selectedLevelId) {
                setSelectedLevelId(info.levels[0].id);
                setEnqLevelId(info.levels[0].id);
            }
        }
    }, [info, selectedYearId, selectedLevelId]);

    const handleCopy = (text: string, isToken: boolean) => {
        navigator.clipboard.writeText(text);
        if (isToken) {
            setCopiedToken(true);
            setTimeout(() => setCopiedToken(false), 2000);
        } else {
            setCopiedRef(true);
            setTimeout(() => setCopiedRef(false), 2000);
        }
    };

    const handleApplySubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!consent) {
            alert("You must agree to the admissions consent terms before submitting.");
            return;
        }

        const payload: PublicApplicationPayload = {
            first_name: firstName.trim(),
            middle_name: middleName.trim() || undefined,
            last_name: lastName.trim(),
            date_of_birth: dateOfBirth,
            gender,
            email: studentEmail.trim() || undefined,
            phone: studentPhone.trim() || undefined,
            address: studentAddress.trim() || undefined,
            previous_school: previousSchool.trim() || undefined,
            last_grade_passed: lastGradePassed.trim() || undefined,
            guardian_first_name: guardianFirstName.trim(),
            guardian_last_name: guardianLastName.trim(),
            guardian_relationship: guardianRelationship,
            guardian_phone: guardianPhone.trim(),
            guardian_email: guardianEmail.trim() || undefined,
            guardian_occupation: guardianOccupation.trim() || undefined,
            guardian_address: guardianAddress.trim() || undefined,
            secondary_guardian_name: secGuardianName.trim() || undefined,
            secondary_guardian_relationship: secGuardianRel.trim() || undefined,
            secondary_guardian_phone: secGuardianPhone.trim() || undefined,
            academic_year_ref: selectedYearId,
            level: selectedLevelId,
            enquiry_number: enquiryNumberRef.trim() || undefined,
            consent: true,
        };

        applyMutation.mutate(payload, {
            onSuccess: (res) => {
                setSubmissionResult(res);
                window.scrollTo({ top: 0, behavior: "smooth" });
            },
        });
    };

    const handleEnquirySubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!enqConsent) {
            alert("You must agree to the privacy policy to submit an enquiry.");
            return;
        }

        const payload: PublicEnquiryPayload = {
            student_name: enqStudentName.trim(),
            guardian_name: enqGuardianName.trim(),
            guardian_relationship: enqRelationship,
            guardian_phone: enqPhone.trim(),
            guardian_email: enqEmail.trim() || undefined,
            preferred_level: enqLevelId,
            academic_year_ref: enqYearId,
            notes: enqNotes.trim() || undefined,
            consent: true,
        };

        enquiryMutation.mutate(payload, {
            onSuccess: (res) => {
                setEnquirySuccess(res.enquiry_number);
                window.scrollTo({ top: 0, behavior: "smooth" });
            },
        });
    };

    if (isInfoLoading) {
        return (
            <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex flex-col items-center justify-center p-6">
                <Loader2 className="w-10 h-10 animate-spin text-blue-600 mb-3" />
                <p className="text-sm font-semibold text-slate-600 dark:text-slate-400">Loading admissions portal...</p>
            </div>
        );
    }

    const schoolName = info?.institution?.name || "EduSekai Partner School";

    return (
        <div className="h-screen overflow-y-auto bg-slate-50/70 dark:bg-slate-950 text-slate-900 dark:text-slate-100 selection:bg-blue-500 selection:text-white">
            {/* Top Navigation Bar */}
            <header className="sticky top-0 z-40 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200/80 dark:border-slate-800">
                <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-xl bg-blue-600 text-white shadow-sm">
                            <School className="w-5 h-5" />
                        </div>
                        <div>
                            <h1 className="text-base font-extrabold tracking-tight text-slate-900 dark:text-white leading-tight">
                                {schoolName}
                            </h1>
                            <span className="text-[11px] font-semibold text-blue-600 dark:text-blue-400">
                                Admissions Portal
                            </span>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        <Link
                            href="/admissions/status"
                            className="text-xs font-bold text-slate-600 hover:text-blue-600 dark:text-slate-300 dark:hover:text-blue-400 px-3 py-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors flex items-center gap-1.5"
                        >
                            <FileText className="w-3.5 h-3.5" />
                            Track Application
                        </Link>
                    </div>
                </div>
            </header>

            <main className="max-w-4xl mx-auto px-4 sm:px-6 py-10 space-y-8">
                {/* Submission Success Screen */}
                {submissionResult && (
                    <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 sm:p-10 border border-emerald-200 dark:border-emerald-900/50 shadow-xl shadow-emerald-500/5 space-y-8">
                        <div className="text-center space-y-3">
                            <div className="w-16 h-16 mx-auto rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
                                <CheckCircle2 className="w-9 h-9" />
                            </div>
                            <h2 className="text-2xl sm:text-3xl font-black text-slate-900 dark:text-white">
                                Application Submitted Successfully!
                            </h2>
                            <p className="text-sm text-slate-600 dark:text-slate-300 max-w-lg mx-auto">
                                Thank you for applying to <span className="font-bold text-slate-800 dark:text-slate-100">{schoolName}</span>.
                                Your application has been registered into our admissions review pipeline.
                            </p>
                        </div>

                        {/* Reference & Access Token Card */}
                        <div className="bg-slate-50 dark:bg-slate-800/60 rounded-2xl p-6 border border-slate-200 dark:border-slate-700/80 space-y-5">
                            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pb-4 border-b border-slate-200 dark:border-slate-700">
                                <div>
                                    <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                                        Application Reference Number
                                    </span>
                                    <div className="font-mono text-xl sm:text-2xl font-black text-blue-600 dark:text-blue-400 mt-0.5">
                                        {submissionResult.application_number}
                                    </div>
                                </div>
                                <Button
                                    type="button"
                                    variant="outline"
                                    onClick={() => handleCopy(submissionResult.application_number, false)}
                                    className="rounded-xl text-xs font-bold gap-1.5 self-start sm:self-center"
                                >
                                    {copiedRef ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                                    {copiedRef ? "Copied" : "Copy Reference"}
                                </Button>
                            </div>

                            <div className="space-y-2">
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div className="flex items-center gap-1.5">
                                        <Shield className="w-4 h-4 text-amber-600" />
                                        <span className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                            Private Access Token (Keep Safe)
                                        </span>
                                    </div>
                                    <Button
                                        type="button"
                                        variant="outline"
                                        onClick={() => handleCopy(submissionResult.access_token, true)}
                                        className="h-8 px-3 rounded-xl text-xs font-bold gap-1"
                                    >
                                        {copiedToken ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                                        {copiedToken ? "Copied" : "Copy Token"}
                                    </Button>
                                </div>
                                <div className="p-3 bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700 font-mono text-xs break-all text-slate-700 dark:text-slate-300 font-semibold select-all">
                                    {submissionResult.access_token}
                                </div>
                                <p className="text-[11px] text-amber-700 dark:text-amber-400 font-medium">
                                    Notice: For your privacy and child protection, your access token cannot be retrieved if lost.
                                    Copy and save it securely now to check your application status and upload documents.
                                </p>
                            </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
                            <Link
                                href={`/admissions/status#ref=${encodeURIComponent(submissionResult.application_number)}&token=${encodeURIComponent(submissionResult.access_token)}`}
                                className="w-full sm:w-auto px-6 py-3 rounded-2xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm text-center flex items-center justify-center gap-2 shadow-lg shadow-blue-600/20 transition-all"
                            >
                                <FileText className="w-4 h-4" />
                                Track Status & Upload Documents
                            </Link>
                            <Button
                                type="button"
                                variant="ghost"
                                onClick={() => {
                                    setSubmissionResult(null);
                                    setStep(1);
                                    setFirstName("");
                                    setLastName("");
                                }}
                                className="w-full sm:w-auto text-xs text-slate-500 font-semibold"
                            >
                                Submit Another Application
                            </Button>
                        </div>
                    </div>
                )}

                {/* Enquiry Success Screen */}
                {enquirySuccess && !submissionResult && (
                    <div className="bg-white dark:bg-slate-900 rounded-3xl p-8 border border-blue-200 dark:border-blue-900/50 shadow-lg text-center space-y-4">
                        <div className="w-14 h-14 mx-auto rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-600 flex items-center justify-center">
                            <CheckCircle2 className="w-8 h-8" />
                        </div>
                        <h2 className="text-2xl font-black text-slate-900 dark:text-white">
                            Enquiry Received
                        </h2>
                        <p className="text-sm text-slate-600 dark:text-slate-300 max-w-md mx-auto">
                            Your enquiry has been logged with reference number:
                        </p>
                        <div className="font-mono text-2xl font-black text-blue-600 dark:text-blue-400">
                            {enquirySuccess}
                        </div>
                        <p className="text-xs text-slate-500 max-w-sm mx-auto">
                            Our admissions counseling staff will contact you shortly regarding curriculum details, campus visits, and fee structures.
                        </p>
                        <div className="pt-3">
                            <Button
                                onClick={() => setEnquirySuccess(null)}
                                variant="outline"
                                className="rounded-xl text-xs font-bold"
                            >
                                Back to Admissions Portal
                            </Button>
                        </div>
                    </div>
                )}

                {/* Form Mode Toggle & Hero Banner */}
                {!submissionResult && !enquirySuccess && (
                    <>
                        <div className="bg-gradient-to-br from-blue-600 via-indigo-600 to-blue-700 rounded-3xl p-8 sm:p-10 text-white shadow-xl shadow-blue-500/10 space-y-4">
                            <Badge className="bg-white/20 text-white hover:bg-white/30 border-none font-semibold text-xs px-3 py-1">
                                Open Admissions
                            </Badge>
                            <h2 className="text-3xl sm:text-4xl font-black tracking-tight leading-tight">
                                Prospective Student Admissions
                            </h2>
                            <p className="text-blue-100 text-sm sm:text-base max-w-2xl leading-relaxed">
                                Welcome to the online admissions portal for <span className="font-bold text-white">{schoolName}</span>.
                                Submit a formal application or log an initial enquiry to begin the admission process.
                            </p>

                            <div className="flex flex-wrap items-center gap-2 pt-2">
                                <button
                                    type="button"
                                    onClick={() => setFormMode("apply")}
                                    className={`px-5 py-2.5 rounded-xl font-bold text-xs transition-all ${
                                        formMode === "apply"
                                            ? "bg-white text-blue-700 shadow-md"
                                            : "bg-white/10 hover:bg-white/20 text-white"
                                    }`}
                                >
                                    Full Online Application
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setFormMode("enquiry")}
                                    className={`px-5 py-2.5 rounded-xl font-bold text-xs transition-all ${
                                        formMode === "enquiry"
                                            ? "bg-white text-blue-700 shadow-md"
                                            : "bg-white/10 hover:bg-white/20 text-white"
                                    }`}
                                >
                                    Quick Enquiry / Callback Request
                                </button>
                            </div>
                        </div>

                        {/* Quick Enquiry Form */}
                        {formMode === "enquiry" && (
                            <form
                                onSubmit={handleEnquirySubmit}
                                className="bg-white dark:bg-slate-900 rounded-3xl p-6 sm:p-8 border border-slate-200 dark:border-slate-800 shadow-sm space-y-6"
                            >
                                <div>
                                    <h3 className="text-lg font-black text-slate-900 dark:text-white">
                                        Admissions Enquiry & Callback Request
                                    </h3>
                                    <p className="text-xs text-slate-500 mt-1">
                                        Fill out this quick form if you have questions or want to request a callback from our admissions office.
                                    </p>
                                </div>

                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                    <div className="space-y-1.5">
                                        <Label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                                            Student Full Name <span className="text-red-500">*</span>
                                        </Label>
                                        <Input aria-label="e.g. Aarav Sharma"
                                            required
                                            value={enqStudentName}
                                            onChange={(e) => setEnqStudentName(e.target.value)}
                                            placeholder="e.g. Aarav Sharma"
                                            className="rounded-xl h-11"
                                        />
                                    </div>

                                    <div className="space-y-1.5">
                                        <Label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                                            Parent / Guardian Name <span className="text-red-500">*</span>
                                        </Label>
                                        <Input aria-label="e.g. Rajesh Sharma"
                                            required
                                            value={enqGuardianName}
                                            onChange={(e) => setEnqGuardianName(e.target.value)}
                                            placeholder="e.g. Rajesh Sharma"
                                            className="rounded-xl h-11"
                                        />
                                    </div>

                                    <div className="space-y-1.5">
                                        <Label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                                            Primary Contact Phone <span className="text-red-500">*</span>
                                        </Label>
                                        <Input aria-label="e.g. 9876543210"
                                            required
                                            type="tel" autoComplete="tel"
                                            value={enqPhone}
                                            onChange={(e) => setEnqPhone(e.target.value)}
                                            placeholder="e.g. 9876543210"
                                            className="rounded-xl h-11"
                                        />
                                    </div>

                                    <div className="space-y-1.5">
                                        <Label htmlFor="f-contact-email-optional" className="text-xs font-bold text-slate-700 dark:text-slate-300">
                                            Contact Email (Optional)
                                        </Label>
                                        <Input id="f-contact-email-optional"
                                            type="email" autoComplete="email"
                                            value={enqEmail}
                                            onChange={(e) => setEnqEmail(e.target.value)}
                                            placeholder="e.g. parent@example.com"
                                            className="rounded-xl h-11"
                                        />
                                    </div>

                                    <div className="space-y-1.5">
                                        <Label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                                            Applying Grade / Level <span className="text-red-500">*</span>
                                        </Label>
                                        <Select value={enqLevelId} onValueChange={setEnqLevelId}>
                                            <SelectTrigger className="rounded-xl h-11">
                                                <SelectValue placeholder="Select Grade" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {info?.levels?.map((lvl) => (
                                                    <SelectItem key={lvl.id} value={lvl.id}>
                                                        {lvl.name} ({lvl.program_code})
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div className="space-y-1.5">
                                        <Label className="text-xs font-bold text-slate-700 dark:text-slate-300">
                                            Academic Session <span className="text-red-500">*</span>
                                        </Label>
                                        <Select value={enqYearId} onValueChange={setEnqYearId}>
                                            <SelectTrigger className="rounded-xl h-11">
                                                <SelectValue placeholder="Select Session" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {info?.academic_years?.map((y) => (
                                                    <SelectItem key={y.id} value={y.id}>
                                                        {y.name} {y.is_current ? "(Current)" : ""}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>

                                <div className="space-y-1.5">
                                    <Label htmlFor="f-enquiry-message-specific-quest" className="text-xs font-bold text-slate-700 dark:text-slate-300">
                                        Enquiry Message / Specific Questions
                                    </Label>
                                    <Textarea id="f-enquiry-message-specific-quest"
                                        rows={3}
                                        value={enqNotes}
                                        onChange={(e) => setEnqNotes(e.target.value)}
                                        placeholder="Any specific questions about curriculum, bus transport, or timings..."
                                        className="rounded-xl resize-none"
                                    />
                                </div>

                                <div className="flex items-start gap-2.5 pt-2">
                                    <Checkbox
                                        id="enq_consent"
                                        checked={enqConsent}
                                        onCheckedChange={(c) => setEnqConsent(Boolean(c))}
                                        className="mt-0.5"
                                    />
                                    <label htmlFor="enq_consent" className="text-xs text-slate-600 dark:text-slate-400 font-medium cursor-pointer">
                                        I agree to allow {schoolName} to contact me regarding admissions and academic information.
                                    </label>
                                </div>

                                <Button
                                    type="submit"
                                    disabled={enquiryMutation.isPending || !enqConsent}
                                    className="w-full h-12 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm shadow-sm"
                                >
                                    {enquiryMutation.isPending ? (
                                        <>
                                            <Loader2 className="w-4 h-4 animate-spin mr-2" /> Submitting Enquiry...
                                        </>
                                    ) : (
                                        "Submit Enquiry"
                                    )}
                                </Button>
                            </form>
                        )}

                        {/* Full Application Multi-Step Form */}
                        {formMode === "apply" && (
                            <form
                                onSubmit={handleApplySubmit}
                                className="bg-white dark:bg-slate-900 rounded-3xl p-6 sm:p-10 border border-slate-200 dark:border-slate-800 shadow-sm space-y-8"
                            >
                                {/* Step Navigation Tracker */}
                                <div className="flex flex-wrap items-center justify-between gap-2 pb-6 border-b border-slate-100 dark:border-slate-800">
                                    {[
                                        { num: 1, label: "Student Details" },
                                        { num: 2, label: "Guardian Details" },
                                        { num: 3, label: "Academic Placement" },
                                        { num: 4, label: "Review & Submit" },
                                    ].map((s) => (
                                        <button
                                            key={s.num}
                                            type="button"
                                            onClick={() => setStep(s.num)}
                                            className="flex items-center gap-2 text-left group"
                                        >
                                            <div
                                                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-black transition-all ${
                                                    step === s.num
                                                        ? "bg-blue-600 text-white shadow-md shadow-blue-500/20"
                                                        : step > s.num
                                                        ? "bg-emerald-500 text-white"
                                                        : "bg-slate-100 dark:bg-slate-800 text-slate-500"
                                                }`}
                                            >
                                                {step > s.num ? <Check className="w-4 h-4" /> : s.num}
                                            </div>
                                            <span
                                                className={`text-xs font-bold hidden sm:inline ${
                                                    step === s.num
                                                        ? "text-blue-600 dark:text-blue-400"
                                                        : "text-slate-500 dark:text-slate-400"
                                                }`}
                                            >
                                                {s.label}
                                            </span>
                                        </button>
                                    ))}
                                </div>

                                {/* Step 1: Student Details */}
                                {step === 1 && (
                                    <div className="space-y-6">
                                        <div>
                                            <h3 className="text-lg font-black text-slate-900 dark:text-white">
                                                Student Information
                                            </h3>
                                            <p className="text-xs text-slate-500 mt-0.5">
                                                Enter the legal details of the student seeking admission.
                                            </p>
                                        </div>

                                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                            <div className="space-y-1.5">
                                                <Label className="text-xs font-bold">
                                                    First Name <span className="text-red-500">*</span>
                                                </Label>
                                                <Input aria-label="First Name"
                                                    required
                                                    value={firstName}
                                                    onChange={(e) => setFirstName(e.target.value)}
                                                    placeholder="First Name"
                                                    className="rounded-xl h-11"
                                                />
                                            </div>
                                            <div className="space-y-1.5">
                                                <Label htmlFor="f-middle-name" className="text-xs font-bold">Middle Name</Label>
                                                <Input id="f-middle-name"
                                                    value={middleName}
                                                    onChange={(e) => setMiddleName(e.target.value)}
                                                    placeholder="Middle Name (Optional)"
                                                    className="rounded-xl h-11"
                                                />
                                            </div>
                                            <div className="space-y-1.5">
                                                <Label className="text-xs font-bold">
                                                    Last Name <span className="text-red-500">*</span>
                                                </Label>
                                                <Input aria-label="Last Name"
                                                    required
                                                    value={lastName}
                                                    onChange={(e) => setLastName(e.target.value)}
                                                    placeholder="Last Name"
                                                    className="rounded-xl h-11"
                                                />
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                            <div className="space-y-1.5">
                                                <Label className="text-xs font-bold">
                                                    Date of Birth <span className="text-red-500">*</span>
                                                </Label>
                                                <Input
                                                    required
                                                    type="date"
                                                    value={dateOfBirth}
                                                    onChange={(e) => setDateOfBirth(e.target.value)}
                                                    className="rounded-xl h-11"
                                                />
                                            </div>

                                            <div className="space-y-1.5">
                                                <Label className="text-xs font-bold">
                                                    Gender <span className="text-red-500">*</span>
                                                </Label>
                                                <Select value={gender} onValueChange={(val: any) => setGender(val)}>
                                                    <SelectTrigger className="rounded-xl h-11">
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectItem value="male">Male</SelectItem>
                                                        <SelectItem value="female">Female</SelectItem>
                                                        <SelectItem value="other">Other</SelectItem>
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                            <div className="space-y-1.5">
                                                <Label htmlFor="f-previous-school-if-any" className="text-xs font-bold">Previous School (If any)</Label>
                                                <Input id="f-previous-school-if-any"
                                                    value={previousSchool}
                                                    onChange={(e) => setPreviousSchool(e.target.value)}
                                                    placeholder="Name of last school attended"
                                                    className="rounded-xl h-11"
                                                />
                                            </div>
                                            <div className="space-y-1.5">
                                                <Label htmlFor="f-last-grade-passed" className="text-xs font-bold">Last Grade Passed</Label>
                                                <Input id="f-last-grade-passed"
                                                    value={lastGradePassed}
                                                    onChange={(e) => setLastGradePassed(e.target.value)}
                                                    placeholder="e.g. Grade 4"
                                                    className="rounded-xl h-11"
                                                />
                                            </div>
                                        </div>

                                        <div className="space-y-1.5">
                                            <Label htmlFor="f-residential-address" className="text-xs font-bold">Residential Address</Label>
                                            <Textarea id="f-residential-address"
                                                rows={2}
                                                value={studentAddress}
                                                onChange={(e) => setStudentAddress(e.target.value)}
                                                placeholder="Street, City, Postal Code"
                                                className="rounded-xl resize-none"
                                            />
                                        </div>

                                        <div className="flex justify-end pt-4">
                                            <Button
                                                type="button"
                                                disabled={!firstName || !lastName || !dateOfBirth}
                                                onClick={() => setStep(2)}
                                                className="rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs px-6 h-11 gap-1.5"
                                            >
                                                Continue to Guardian Info <ArrowRight className="w-4 h-4" />
                                            </Button>
                                        </div>
                                    </div>
                                )}

                                {/* Step 2: Guardian Details */}
                                {step === 2 && (
                                    <div className="space-y-6">
                                        <div>
                                            <h3 className="text-lg font-black text-slate-900 dark:text-white">
                                                Parent / Primary Guardian Details
                                            </h3>
                                            <p className="text-xs text-slate-500 mt-0.5">
                                                Contact details for admissions correspondence and emergency communications.
                                            </p>
                                        </div>

                                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                            <div className="space-y-1.5">
                                                <Label className="text-xs font-bold">
                                                    Guardian First Name <span className="text-red-500">*</span>
                                                </Label>
                                                <Input aria-label="First Name"
                                                    required
                                                    value={guardianFirstName}
                                                    onChange={(e) => setGuardianFirstName(e.target.value)}
                                                    placeholder="First Name"
                                                    className="rounded-xl h-11"
                                                />
                                            </div>
                                            <div className="space-y-1.5">
                                                <Label className="text-xs font-bold">
                                                    Guardian Last Name <span className="text-red-500">*</span>
                                                </Label>
                                                <Input aria-label="Last Name"
                                                    required
                                                    value={guardianLastName}
                                                    onChange={(e) => setGuardianLastName(e.target.value)}
                                                    placeholder="Last Name"
                                                    className="rounded-xl h-11"
                                                />
                                            </div>
                                            <div className="space-y-1.5">
                                                <Label className="text-xs font-bold">Relationship</Label>
                                                <Select value={guardianRelationship} onValueChange={setGuardianRelationship}>
                                                    <SelectTrigger className="rounded-xl h-11">
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

                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                            <div className="space-y-1.5">
                                                <Label className="text-xs font-bold">
                                                    Primary Phone Number <span className="text-red-500">*</span>
                                                </Label>
                                                <Input aria-label="e.g. 9876543210"
                                                    required
                                                    type="tel" autoComplete="tel"
                                                    value={guardianPhone}
                                                    onChange={(e) => setGuardianPhone(e.target.value)}
                                                    placeholder="e.g. 9876543210"
                                                    className="rounded-xl h-11"
                                                />
                                            </div>

                                            <div className="space-y-1.5">
                                                <Label htmlFor="f-email-address-for-acknowledgem" className="text-xs font-bold">
                                                    Email Address (For Acknowledgements)
                                                </Label>
                                                <Input id="f-email-address-for-acknowledgem"
                                                    type="email" autoComplete="email"
                                                    value={guardianEmail}
                                                    onChange={(e) => setGuardianEmail(e.target.value)}
                                                    placeholder="e.g. parent@example.com"
                                                    className="rounded-xl h-11"
                                                />
                                            </div>
                                        </div>

                                        <div className="space-y-1.5">
                                            <Label htmlFor="f-occupation-employer" className="text-xs font-bold">Occupation / Employer</Label>
                                            <Input id="f-occupation-employer"
                                                value={guardianOccupation}
                                                onChange={(e) => setGuardianOccupation(e.target.value)}
                                                placeholder="e.g. Engineer, Business, Government Service"
                                                className="rounded-xl h-11"
                                            />
                                        </div>

                                        {/* Optional Secondary Guardian */}
                                        <div className="pt-4 border-t border-slate-100 dark:border-slate-800 space-y-3">
                                            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                                                Secondary Guardian / Emergency Contact (Optional)
                                            </span>
                                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                                <Input aria-label="Name"
                                                    value={secGuardianName}
                                                    onChange={(e) => setSecGuardianName(e.target.value)}
                                                    placeholder="Name"
                                                    className="rounded-xl h-10 text-xs"
                                                />
                                                <Input aria-label="Relationship (e.g. Mother)"
                                                    value={secGuardianRel}
                                                    onChange={(e) => setSecGuardianRel(e.target.value)}
                                                    placeholder="Relationship (e.g. Mother)"
                                                    className="rounded-xl h-10 text-xs"
                                                />
                                                <Input aria-label="Phone"
                                                    value={secGuardianPhone}
                                                    onChange={(e) => setSecGuardianPhone(e.target.value)}
                                                    placeholder="Phone"
                                                    className="rounded-xl h-10 text-xs"
                                                />
                                            </div>
                                        </div>

                                        <div className="flex flex-wrap items-center justify-between gap-2 pt-4">
                                            <Button
                                                type="button"
                                                variant="outline"
                                                onClick={() => setStep(1)}
                                                className="rounded-xl text-xs font-bold h-11"
                                            >
                                                <ArrowLeft className="w-4 h-4 mr-1.5" /> Back
                                            </Button>
                                            <Button
                                                type="button"
                                                disabled={!guardianFirstName || !guardianLastName || !guardianPhone}
                                                onClick={() => setStep(3)}
                                                className="rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs px-6 h-11 gap-1.5"
                                            >
                                                Continue to Placement <ArrowRight className="w-4 h-4" />
                                            </Button>
                                        </div>
                                    </div>
                                )}

                                {/* Step 3: Academic Placement */}
                                {step === 3 && (
                                    <div className="space-y-6">
                                        <div>
                                            <h3 className="text-lg font-black text-slate-900 dark:text-white">
                                                Academic Placement & Program Selection
                                            </h3>
                                            <p className="text-xs text-slate-500 mt-0.5">
                                                Select the grade level and academic session for admission.
                                            </p>
                                        </div>

                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                            <div className="space-y-1.5">
                                                <Label className="text-xs font-bold">
                                                    Academic Session / Year <span className="text-red-500">*</span>
                                                </Label>
                                                <Select value={selectedYearId} onValueChange={setSelectedYearId}>
                                                    <SelectTrigger className="rounded-xl h-11">
                                                        <SelectValue placeholder="Select Session" />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {info?.academic_years?.map((y) => (
                                                            <SelectItem key={y.id} value={y.id}>
                                                                {y.name} {y.is_current ? "(Current)" : ""}
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>

                                            <div className="space-y-1.5">
                                                <Label className="text-xs font-bold">
                                                    Grade / Academic Level <span className="text-red-500">*</span>
                                                </Label>
                                                <Select value={selectedLevelId} onValueChange={setSelectedLevelId}>
                                                    <SelectTrigger className="rounded-xl h-11">
                                                        <SelectValue placeholder="Select Grade" />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        {info?.levels?.map((lvl) => (
                                                            <SelectItem key={lvl.id} value={lvl.id}>
                                                                {lvl.name} ({lvl.program_code})
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                        </div>

                                        <div className="space-y-1.5">
                                            <Label htmlFor="f-prior-enquiry-number-if-you-al" className="text-xs font-bold">
                                                Prior Enquiry Number (If you already logged an enquiry)
                                            </Label>
                                            <Input id="f-prior-enquiry-number-if-you-al"
                                                value={enquiryNumberRef}
                                                onChange={(e) => setEnquiryNumberRef(e.target.value)}
                                                placeholder="e.g. ENQ-2026-0001"
                                                className="rounded-xl h-11 font-mono text-xs uppercase"
                                            />
                                        </div>

                                        {/* Document Checklist Advisory */}
                                        <div className="bg-slate-50 dark:bg-slate-800/50 rounded-2xl p-5 border border-slate-200 dark:border-slate-800 space-y-3">
                                            <div className="flex items-center gap-2 text-xs font-bold text-slate-800 dark:text-slate-200">
                                                <FileText className="w-4 h-4 text-blue-600" />
                                                Required Documents Advisory
                                            </div>
                                            <p className="text-xs text-slate-500">
                                                You can upload required documents (Birth Certificate, Photo, Prior Marksheet) directly on the tracking portal after submitting your application.
                                            </p>
                                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                                                {info?.document_requirements?.map((doc) => (
                                                    <div
                                                        key={doc.document_type}
                                                        className="text-xs text-slate-600 dark:text-slate-300 flex items-center gap-1.5"
                                                    >
                                                        <div className={`w-1.5 h-1.5 rounded-full ${doc.required ? "bg-blue-600" : "bg-slate-400"}`} />
                                                        <span className="font-semibold">{doc.label}</span>
                                                        {doc.required && <span className="text-[10px] text-red-500">(Required)</span>}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>

                                        <div className="flex flex-wrap items-center justify-between gap-2 pt-4">
                                            <Button
                                                type="button"
                                                variant="outline"
                                                onClick={() => setStep(2)}
                                                className="rounded-xl text-xs font-bold h-11"
                                            >
                                                <ArrowLeft className="w-4 h-4 mr-1.5" /> Back
                                            </Button>
                                            <Button
                                                type="button"
                                                disabled={!selectedYearId || !selectedLevelId}
                                                onClick={() => setStep(4)}
                                                className="rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs px-6 h-11 gap-1.5"
                                            >
                                                Review Application <ArrowRight className="w-4 h-4" />
                                            </Button>
                                        </div>
                                    </div>
                                )}

                                {/* Step 4: Review & Confirm */}
                                {step === 4 && (
                                    <div className="space-y-6">
                                        <div>
                                            <h3 className="text-lg font-black text-slate-900 dark:text-white">
                                                Review & Confirm Submission
                                            </h3>
                                            <p className="text-xs text-slate-500 mt-0.5">
                                                Please review all entered details before finalizing submission.
                                            </p>
                                        </div>

                                        <div className="bg-slate-50 dark:bg-slate-800/40 rounded-2xl p-6 border border-slate-200 dark:border-slate-800 space-y-4">
                                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                                                <div>
                                                    <span className="text-slate-400 font-medium">Student Name:</span>
                                                    <div className="font-bold text-slate-800 dark:text-slate-100 text-sm mt-0.5">
                                                        {firstName} {middleName} {lastName}
                                                    </div>
                                                </div>
                                                <div>
                                                    <span className="text-slate-400 font-medium">Date of Birth & Gender:</span>
                                                    <div className="font-bold text-slate-800 dark:text-slate-100 text-sm mt-0.5 capitalize">
                                                        {dateOfBirth} ({gender})
                                                    </div>
                                                </div>
                                                <div>
                                                    <span className="text-slate-400 font-medium">Parent / Guardian:</span>
                                                    <div className="font-bold text-slate-800 dark:text-slate-100 text-sm mt-0.5">
                                                        {guardianFirstName} {guardianLastName} ({guardianRelationship})
                                                    </div>
                                                </div>
                                                <div>
                                                    <span className="text-slate-400 font-medium">Primary Contact:</span>
                                                    <div className="font-bold text-slate-800 dark:text-slate-100 text-sm mt-0.5">
                                                        {guardianPhone} {guardianEmail ? `• ${guardianEmail}` : ""}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Privacy Consent Checkbox */}
                                        <div className="p-4 rounded-2xl bg-blue-50/50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-900/40 space-y-2">
                                            <div className="flex items-start gap-3">
                                                <Checkbox
                                                    id="apply_consent"
                                                    checked={consent}
                                                    onCheckedChange={(c) => setConsent(Boolean(c))}
                                                    className="mt-0.5"
                                                />
                                                <label htmlFor="apply_consent" className="text-xs text-slate-700 dark:text-slate-300 font-medium cursor-pointer leading-relaxed">
                                                    I certify that the information supplied in this application is true and complete to the best of my knowledge.
                                                    I agree to the admissions policy and consent to the processing of personal data for the purpose of prospective student evaluation.
                                                </label>
                                            </div>
                                        </div>

                                        <div className="flex flex-wrap items-center justify-between gap-2 pt-4">
                                            <Button
                                                type="button"
                                                variant="outline"
                                                onClick={() => setStep(3)}
                                                className="rounded-xl text-xs font-bold h-11"
                                            >
                                                <ArrowLeft className="w-4 h-4 mr-1.5" /> Back
                                            </Button>
                                            <Button
                                                type="submit"
                                                disabled={applyMutation.isPending || !consent}
                                                className="rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-sm px-8 h-12 shadow-lg shadow-blue-500/20 gap-2"
                                            >
                                                {applyMutation.isPending ? (
                                                    <>
                                                        <Loader2 className="w-4 h-4 animate-spin" /> Submitting Application...
                                                    </>
                                                ) : (
                                                    <>
                                                        Confirm & Submit Application <ArrowRight className="w-4 h-4" />
                                                    </>
                                                )}
                                            </Button>
                                        </div>
                                    </div>
                                )}
                            </form>
                        )}
                    </>
                )}
            </main>
        </div>
    );
}

