"use client";

import React, { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
    usePublicAdmissionsInfo,
    usePublicApplicationStatus,
    useUploadPublicDocument,
    admissionsErrorMessage,
} from "@/hooks/useAdmissions";
import { DocumentType } from "@/types/Admissions";
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
import { Badge } from "@/components/ui/badge";
import {
    School,
    Search,
    Shield,
    FileText,
    Calendar,
    GraduationCap,
    CheckCircle2,
    Clock,
    AlertCircle,
    XCircle,
    Upload,
    ArrowLeft,
    Loader2,
    KeyRound,
    Lock,
    ExternalLink,
} from "lucide-react";

function StatusContent() {
    const searchParams = useSearchParams();
    const initialRef = searchParams.get("ref") || "";
    const initialToken = searchParams.get("token") || "";

    const { data: info } = usePublicAdmissionsInfo();
    const schoolName = info?.institution?.name || "EduSekai Partner School";

    const [appNumberInput, setAppNumberInput] = useState(initialRef);
    const [tokenInput, setTokenInput] = useState(initialToken);

    const [activeRef, setActiveRef] = useState(initialRef);
    const [activeToken, setActiveToken] = useState(initialToken);

    // Document upload state
    const [docType, setDocType] = useState<DocumentType>("birth_certificate");
    const [docTitle, setDocTitle] = useState("");
    const [selectedFile, setSelectedFile] = useState<File | null>(null);

    const uploadMutation = useUploadPublicDocument();

    const {
        data: statusData,
        isLoading,
        isError,
        error,
        refetch,
    } = usePublicApplicationStatus(activeRef, activeToken);

    useEffect(() => {
        let ref = "";
        let token = "";

        // 1. Check secure URL hash fragment (#ref=...&token=...) which is never transmitted over the wire
        if (typeof window !== "undefined" && window.location.hash) {
            const hash = window.location.hash.replace(/^#/, "");
            const params = new URLSearchParams(hash);
            ref = params.get("ref") || "";
            token = params.get("token") || "";
        }

        // 2. Fall back to searchParams for backward compatibility
        if (!ref && initialRef) ref = initialRef;
        if (!token && initialToken) token = initialToken;

        if (ref || token) {
            if (ref) {
                setActiveRef(ref);
                setAppNumberInput(ref);
            }
            if (token) {
                setActiveToken(token);
                setTokenInput(token);
            }

            // Immediately sanitize URL in address bar and browser history to prevent referrer leakage,
            // shoulder surfing, and browser history token persistence
            if (typeof window !== "undefined" && (window.location.hash || window.location.search)) {
                window.history.replaceState({}, document.title, window.location.pathname);
            }
        }
    }, [initialRef, initialToken]);

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        setActiveRef(appNumberInput.trim());
        setActiveToken(tokenInput.trim());
    };

    const handleUploadDoc = (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedFile || !activeRef || !activeToken) return;

        if (selectedFile.size > 10 * 1024 * 1024) {
            alert("File size exceeds 10MB limit.");
            return;
        }

        const formData = new FormData();
        formData.append("document_type", docType);
        if (docTitle.trim()) {
            formData.append("title", docTitle.trim());
        }
        formData.append("file", selectedFile);

        uploadMutation.mutate(
            {
                applicationNumber: activeRef,
                token: activeToken,
                formData,
            },
            {
                onSuccess: () => {
                    setSelectedFile(null);
                    setDocTitle("");
                },
            }
        );
    };

    const getStatusBadge = (status: string) => {
        switch (status) {
            case "submitted":
                return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300 border-none font-bold">Application Submitted</Badge>;
            case "under_review":
                return <Badge className="bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300 border-none font-bold">Under Review</Badge>;
            case "documents_pending":
                return <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 border-none font-bold">Documents Pending</Badge>;
            case "documents_verified":
                return <Badge className="bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300 border-none font-bold">Documents Verified</Badge>;
            case "assessment_pending":
                return <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300 border-none font-bold">Assessment Pending</Badge>;
            case "approved":
                return <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300 border-none font-bold">Admission Approved</Badge>;
            case "waitlisted":
                return <Badge className="bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300 border-none font-bold">Waitlisted</Badge>;
            case "rejected":
                return <Badge className="bg-slate-200 text-slate-800 dark:bg-slate-800 dark:text-slate-200 border-none font-bold">Decision Finalized</Badge>;
            case "offer_accepted":
                return <Badge className="bg-cyan-100 text-cyan-800 dark:bg-cyan-900/40 dark:text-cyan-300 border-none font-bold">Offer Accepted</Badge>;
            case "enrolled":
                return <Badge className="bg-green-600 text-white border-none font-bold">Officially Enrolled</Badge>;
            default:
                return <Badge variant="outline">{status}</Badge>;
        }
    };

    return (
        <div className="min-h-screen bg-slate-50/70 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
            {/* Navigation Header */}
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
                                Admissions Tracker
                            </span>
                        </div>
                    </div>

                    <Link
                        href="/apply"
                        className="text-xs font-bold text-slate-600 hover:text-blue-600 dark:text-slate-300 dark:hover:text-blue-400 px-3 py-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors flex items-center gap-1.5"
                    >
                        <ArrowLeft className="w-3.5 h-3.5" />
                        Apply Online
                    </Link>
                </div>
            </header>

            <main className="max-w-3xl mx-auto px-4 sm:px-6 py-10 space-y-8">
                {/* Search Form Card (if not active or to re-query) */}
                <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 sm:p-8 border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
                    <div>
                        <h2 className="text-xl font-black text-slate-900 dark:text-white flex items-center gap-2">
                            <Search className="w-5 h-5 text-blue-600" />
                            Track Admission Application
                        </h2>
                        <p className="text-xs text-slate-500 mt-1">
                            Enter your application reference number and private access token to check application status and upload missing documents.
                        </p>
                    </div>

                    <form onSubmit={handleSearch} className="space-y-4">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div className="space-y-1.5">
                                <Label className="text-xs font-bold">
                                    Application Reference <span className="text-red-500">*</span>
                                </Label>
                                <Input aria-label="e.g. APP-2026-0001"
                                    required
                                    placeholder="e.g. APP-2026-0001"
                                    value={appNumberInput}
                                    onChange={(e) => setAppNumberInput(e.target.value)}
                                    className="rounded-xl h-11 font-mono uppercase text-xs"
                                />
                            </div>

                            <div className="space-y-1.5">
                                <Label className="text-xs font-bold flex items-center gap-1">
                                    <KeyRound className="w-3.5 h-3.5 text-amber-500" />
                                    Access Token <span className="text-red-500">*</span>
                                </Label>
                                <Input aria-label="Paste private access token"
                                    required
                                    type="password"
                                    placeholder="Paste private access token"
                                    value={tokenInput}
                                    onChange={(e) => setTokenInput(e.target.value)}
                                    className="rounded-xl h-11 font-mono text-xs"
                                />
                            </div>
                        </div>

                        <Button
                            type="submit"
                            disabled={!appNumberInput.trim() || !tokenInput.trim() || isLoading}
                            className="w-full h-11 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs gap-2 shadow-sm"
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 className="w-4 h-4 animate-spin" /> Verifying Access...
                                </>
                            ) : (
                                "Check Application Status"
                            )}
                        </Button>
                    </form>
                </div>

                {/* Error Banner */}
                {isError && (
                    <div className="p-5 rounded-2xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-900/40 text-red-800 dark:text-red-300 text-xs font-medium space-y-1 flex items-start gap-3">
                        <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
                        <div>
                            <div className="font-bold">Access Denied or Not Found</div>
                            <p>{admissionsErrorMessage(error, "Invalid application reference or access token.")}</p>
                        </div>
                    </div>
                )}

                {/* Status Details */}
                {statusData && (
                    <div className="space-y-6">
                        {/* Status Summary Banner */}
                        <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 sm:p-8 border border-slate-200 dark:border-slate-800 shadow-sm space-y-5">
                            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pb-5 border-b border-slate-100 dark:border-slate-800">
                                <div>
                                    <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                                        Application Reference
                                    </span>
                                    <h3 className="font-mono text-xl sm:text-2xl font-black text-blue-600 dark:text-blue-400">
                                        {statusData.application_number}
                                    </h3>
                                    <div className="text-xs text-slate-500 mt-1 flex items-center gap-1.5">
                                        <Calendar className="w-3.5 h-3.5" />
                                        Submitted on: {statusData.submission_date?.split("T")[0] || "Recent"}
                                    </div>
                                </div>
                                <div>
                                    {getStatusBadge(statusData.status)}
                                </div>
                            </div>

                            {/* Student & Grade Placement */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                                <div>
                                    <span className="text-slate-400 font-medium">Applicant Name:</span>
                                    <div className="font-bold text-slate-800 dark:text-slate-100 text-sm mt-0.5">
                                        {statusData.student_masked_name}
                                    </div>
                                </div>
                                <div>
                                    <span className="text-slate-400 font-medium">Requested Grade & Session:</span>
                                    <div className="font-bold text-slate-800 dark:text-slate-100 text-sm mt-0.5">
                                        {statusData.level_name} (AY: {statusData.academic_year})
                                    </div>
                                </div>
                            </div>

                            {/* Status Explanation Card */}
                            <div className="p-4 rounded-2xl bg-blue-50/60 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-900/40 space-y-2">
                                <h4 className="text-xs font-black text-blue-900 dark:text-blue-200 flex items-center gap-1.5">
                                    <CheckCircle2 className="w-4 h-4 text-blue-600" />
                                    {statusData.status_display}
                                </h4>
                                <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                                    {statusData.status_description}
                                </p>
                                {statusData.next_steps && (
                                    <div className="pt-2 border-t border-blue-200/50 dark:border-blue-800/40 text-[11px] text-blue-800 dark:text-blue-300">
                                        <span className="font-bold">Next Steps: </span> {statusData.next_steps}
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Document Verification Checklist */}
                        <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 sm:p-8 border border-slate-200 dark:border-slate-800 shadow-sm space-y-5">
                            <div>
                                <h3 className="text-base font-black text-slate-900 dark:text-white flex items-center gap-2">
                                    <FileText className="w-4 h-4 text-blue-600" />
                                    Document Verification Status
                                </h3>
                                <p className="text-xs text-slate-500 mt-0.5">
                                    List of documents uploaded for this application and their review status.
                                </p>
                            </div>

                            {statusData.documents?.length === 0 ? (
                                <div className="p-6 rounded-2xl bg-slate-50 dark:bg-slate-800/50 text-center text-xs text-slate-500 space-y-1">
                                    <AlertCircle className="w-6 h-6 mx-auto text-amber-500 mb-1" />
                                    <div className="font-bold text-slate-700 dark:text-slate-300">No documents uploaded yet</div>
                                    <p>Please upload required documents below to expedite review.</p>
                                </div>
                            ) : (
                                <div className="space-y-2.5">
                                    {statusData.documents.map((doc) => (
                                        <div
                                            key={doc.id}
                                            className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs"
                                        >
                                            <div className="space-y-0.5">
                                                <div className="font-bold text-slate-800 dark:text-slate-100 flex items-center gap-1.5">
                                                    <FileText className="w-3.5 h-3.5 text-blue-500" />
                                                    {doc.title || doc.document_type_display}
                                                </div>
                                                <div className="text-[11px] text-slate-400 font-mono">
                                                    {doc.file_name} • Uploaded {doc.uploaded_at.split("T")[0]}
                                                </div>
                                                {doc.rejection_reason && (
                                                    <div className="text-[11px] text-red-600 dark:text-red-400 font-medium pt-1">
                                                        <span className="font-bold">Reason:</span> {doc.rejection_reason}
                                                    </div>
                                                )}
                                            </div>

                                            <div>
                                                {doc.verification_status === "verified" ? (
                                                    <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300 border-none font-bold gap-1">
                                                        <CheckCircle2 className="w-3 h-3" /> Verified
                                                    </Badge>
                                                ) : doc.verification_status === "rejected" ? (
                                                    <Badge className="bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300 border-none font-bold gap-1">
                                                        <XCircle className="w-3 h-3" /> Re-upload Needed
                                                    </Badge>
                                                ) : (
                                                    <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 border-none font-bold gap-1">
                                                        <Clock className="w-3 h-3" /> Pending Verification
                                                    </Badge>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* Document Upload Form (If allowed) */}
                            {statusData.can_upload_documents && (
                                <form
                                    onSubmit={handleUploadDoc}
                                    className="p-5 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-800 space-y-4 pt-4 mt-4"
                                >
                                    <h4 className="text-xs font-black text-slate-800 dark:text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                                        <Upload className="w-3.5 h-3.5 text-blue-600" />
                                        Upload / Replace Document
                                    </h4>

                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                        <div className="space-y-1">
                                            <Label className="text-[11px] font-bold">Document Type</Label>
                                            <Select value={docType} onValueChange={(v: any) => setDocType(v)}>
                                                <SelectTrigger className="h-10 text-xs rounded-xl bg-white dark:bg-slate-900">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="birth_certificate">Birth Certificate</SelectItem>
                                                    <SelectItem value="photo">Passport Photograph</SelectItem>
                                                    <SelectItem value="previous_marksheet">Report Card / Marksheet</SelectItem>
                                                    <SelectItem value="transfer_certificate">Transfer Certificate (TC)</SelectItem>
                                                    <SelectItem value="address_proof">Address Proof</SelectItem>
                                                    <SelectItem value="medical_record">Medical Record</SelectItem>
                                                    <SelectItem value="other">Other Document</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>

                                        <div className="space-y-1">
                                            <Label htmlFor="f-document-title-optional" className="text-[11px] font-bold">Document Title (Optional)</Label>
                                            <Input id="f-document-title-optional"
                                                value={docTitle}
                                                onChange={(e) => setDocTitle(e.target.value)}
                                                placeholder="e.g. Birth Certificate Copy"
                                                className="h-10 text-xs rounded-xl bg-white dark:bg-slate-900"
                                            />
                                        </div>
                                    </div>

                                    <div className="space-y-1">
                                        <Label className="text-[11px] font-bold">Choose File (PDF, JPG, PNG, DOC, max 10MB)</Label>
                                        <Input
                                            type="file"
                                            required
                                            accept=".pdf,.jpg,.jpeg,.png,.webp,.doc,.docx"
                                            onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                                            className="h-10 text-xs rounded-xl bg-white dark:bg-slate-900 file:mr-2 file:py-1 file:px-2 file:rounded-md file:border-0 file:text-[11px] file:font-semibold file:bg-blue-50 file:text-blue-700"
                                        />
                                    </div>

                                    <Button
                                        type="submit"
                                        disabled={!selectedFile || uploadMutation.isPending}
                                        className="h-10 px-5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs gap-1.5"
                                    >
                                        {uploadMutation.isPending ? (
                                            <>
                                                <Loader2 className="w-3.5 h-3.5 animate-spin" /> Uploading...
                                            </>
                                        ) : (
                                            <>
                                                <Upload className="w-3.5 h-3.5" /> Upload Document
                                            </>
                                        )}
                                    </Button>
                                </form>
                            )}
                        </div>
                    </div>
                )}
            </main>
        </div>
    );
}

export default function PublicApplicationStatusPage() {
    return (
        <Suspense
            fallback={
                <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex flex-col items-center justify-center p-6">
                    <Loader2 className="w-10 h-10 animate-spin text-blue-600 mb-3" />
                    <p className="text-sm font-semibold text-slate-600 dark:text-slate-400">Loading status tracker...</p>
                </div>
            }
        >
            <StatusContent />
        </Suspense>
    );
}

