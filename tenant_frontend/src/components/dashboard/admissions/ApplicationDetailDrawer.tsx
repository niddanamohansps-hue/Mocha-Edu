"use client";

import React, { useState } from "react";
import { toast } from "sonner";
import {
    Dialog,
    DialogBody,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { ModalHeader } from "@/components/ui/modal-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
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
    useApplication,
    useTransitionApplicationStatus,
    useAssignReviewer,
    useUploadAdmissionDocument,
    useVerifyAdmissionDocument,
    useRejectAdmissionDocument,
    useScheduleInterview,
    useSendDecisionNotice,
    useIssueTrackingLink,
    useUpdateInterview,
} from "@/hooks/useAdmissions";
import { useStaffMembers } from "@/hooks/useStaff";
import { usePermissions } from "@/providers/PermissionProvider";
import {
    AdmissionApplication,
    ApplicationStatus,
    DocumentType,
    InterviewType,
    InterviewRecommendation,
} from "@/types/Admissions";
import DecisionDialog from "./DecisionDialog";
import EnrollDialog from "./EnrollDialog";
import {
    User,
    Users,
    FileText,
    FileCheck,
    CheckCircle2,
    XCircle,
    Clock,
    AlertCircle,
    Calendar,
    Upload,
    Download,
    Check,
    X,
    Loader2,
    GraduationCap,
    History,
    Shield,
} from "lucide-react";

interface ApplicationDetailDrawerProps {
    applicationId: string | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

const ALLOWED_TRANSITIONS: Record<string, ApplicationStatus[]> = {
    draft: ["submitted", "withdrawn"],
    submitted: ["under_review", "documents_pending", "withdrawn", "rejected"],
    under_review: [
        "documents_pending",
        "documents_verified",
        "assessment_pending",
        "approved",
        "waitlisted",
        "rejected",
        "withdrawn",
    ],
    documents_pending: ["under_review", "documents_verified", "withdrawn", "rejected"],
    documents_verified: [
        "under_review",
        "assessment_pending",
        "approved",
        "waitlisted",
        "rejected",
        "withdrawn",
    ],
    assessment_pending: ["under_review", "approved", "waitlisted", "rejected", "withdrawn"],
    approved: ["offer_accepted", "withdrawn", "rejected"],
    waitlisted: ["under_review", "approved", "rejected", "withdrawn"],
    offer_accepted: ["withdrawn", "rejected"],
    enrolled: [],
    rejected: ["under_review"],
    withdrawn: ["draft", "under_review"],
};

export default function ApplicationDetailDrawer({
    applicationId,
    open,
    onOpenChange,
}: ApplicationDetailDrawerProps) {
    const { can, isOwner } = usePermissions();
    const canManageApps = isOwner || can("manage_admission_applications");
    const canReviewDocs = isOwner || can("review_admission_documents");
    const canReviewApps = isOwner || can("review_admission_applications");
    const canDecide = isOwner || can("make_admission_decisions");
    const canEnroll = isOwner || can("enroll_admitted_students");

    const { data: application, isLoading } = useApplication(applicationId || undefined);
    const { data: staffData } = useStaffMembers({ pageSize: 50 });
    const staffList = staffData?.results || [];

    const transitionMutation = useTransitionApplicationStatus();
    const assignMutation = useAssignReviewer();
    const uploadDocMutation = useUploadAdmissionDocument();
    const verifyDocMutation = useVerifyAdmissionDocument();
    const rejectDocMutation = useRejectAdmissionDocument();
    const scheduleInterviewMutation = useScheduleInterview();
    const updateInterviewMutation = useUpdateInterview();

    // Modals
    const [decisionOpen, setDecisionOpen] = useState(false);
    const sendNotice = useSendDecisionNotice();
    const issueLink = useIssueTrackingLink();
    const [tracking, setTracking] = useState<{ reference: string; token: string; link: string; expires: string } | null>(null);
    const createTrackingLink = () => {
        if (!application) return;
        if (!window.confirm("Create a tracking link for this family? Any link they were given before will stop working.")) return;
        issueLink.mutate(application.id, {
            onSuccess: (data) =>
                setTracking({
                    reference: data.application_number,
                    token: data.access_token,
                    // The fragment (#) is never sent to the server or kept in its logs.
                    link: `${window.location.origin}/admissions/status#ref=${encodeURIComponent(data.application_number)}&token=${encodeURIComponent(data.access_token)}`,
                    expires: new Date(data.access_token_expires_at).toLocaleDateString(),
                }),
        });
    };
    const copy = (text: string, what: string) => {
        navigator.clipboard.writeText(text).then(() => toast.success(`${what} copied`), () => toast.error("Could not copy"));
    };
    const [enrollOpen, setEnrollOpen] = useState(false);

    // Document upload state
    const [docType, setDocType] = useState<DocumentType>("birth_certificate");
    const [docTitle, setDocTitle] = useState("");
    const [selectedFile, setSelectedFile] = useState<File | null>(null);

    // Document reject state
    const [rejectingDocId, setRejectingDocId] = useState<string | null>(null);
    const [rejectionReason, setRejectionReason] = useState("");

    // Interview schedule state
    const [interviewType, setInterviewType] = useState<InterviewType>("student_interview");
    const [scheduledAt, setScheduledAt] = useState("");
    const [interviewerId, setInterviewerId] = useState<string>("none");

    if (!applicationId) return null;

    const currentStatus = application?.status || "draft";
    const nextTransitions = ALLOWED_TRANSITIONS[currentStatus] || [];
    const isEnrolled = currentStatus === "enrolled";
    const canTakeEnrollmentAction = (currentStatus === "approved" || currentStatus === "offer_accepted") && !isEnrolled;

    const handleStatusTransition = (newStatus: string) => {
        if (!application) return;
        transitionMutation.mutate({
            id: application.id,
            status: newStatus as ApplicationStatus,
        });
    };

    const handleAssignReviewer = (staffId: string) => {
        if (!application) return;
        assignMutation.mutate({
            id: application.id,
            staff_id: staffId === "none" ? null : staffId,
        });
    };

    const handleUploadDoc = (e: React.FormEvent) => {
        e.preventDefault();
        if (!application || !selectedFile) return;

        const formData = new FormData();
        formData.append("document_type", docType);
        formData.append("title", docTitle.trim() || selectedFile.name);
        formData.append("file", selectedFile);

        uploadDocMutation.mutate(
            { id: application.id, formData },
            {
                onSuccess: () => {
                    setSelectedFile(null);
                    setDocTitle("");
                },
            }
        );
    };

    const handleRejectDoc = (docId: string) => {
        if (!rejectionReason.trim()) return;
        rejectDocMutation.mutate(
            { documentId: docId, reason: rejectionReason.trim() },
            {
                onSuccess: () => {
                    setRejectingDocId(null);
                    setRejectionReason("");
                },
            }
        );
    };

    const handleScheduleInterview = (e: React.FormEvent) => {
        e.preventDefault();
        if (!application) return;

        scheduleInterviewMutation.mutate(
            {
                id: application.id,
                data: {
                    interview_type: interviewType,
                    scheduled_at: scheduledAt || null,
                    interviewer: interviewerId === "none" ? null : interviewerId,
                },
            },
            {
                onSuccess: () => {
                    setScheduledAt("");
                    setInterviewerId("none");
                },
            }
        );
    };

    const getStatusBadge = (status: ApplicationStatus) => {
        switch (status) {
            case "draft":
                return <Badge variant="outline" className="font-semibold capitalize">Draft</Badge>;
            case "submitted":
                return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300 border-none font-semibold">Submitted</Badge>;
            case "under_review":
                return <Badge className="bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300 border-none font-semibold">Under Review</Badge>;
            case "documents_pending":
                return <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 border-none font-semibold">Documents Pending</Badge>;
            case "documents_verified":
                return <Badge className="bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300 border-none font-semibold">Documents Verified</Badge>;
            case "assessment_pending":
                return <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300 border-none font-semibold">Assessment Pending</Badge>;
            case "approved":
                return <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300 border-none font-semibold">Approved</Badge>;
            case "waitlisted":
                return <Badge className="bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300 border-none font-semibold">Waitlisted</Badge>;
            case "rejected":
                return <Badge className="bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300 border-none font-semibold">Rejected</Badge>;
            case "offer_accepted":
                return <Badge className="bg-cyan-100 text-cyan-800 dark:bg-cyan-900/40 dark:text-cyan-300 border-none font-semibold">Offer Accepted</Badge>;
            case "enrolled":
                return <Badge className="bg-green-600 text-white border-none font-bold">Enrolled</Badge>;
            case "withdrawn":
                return <Badge className="bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-none font-semibold">Withdrawn</Badge>;
            default:
                return <Badge variant="outline">{status}</Badge>;
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-4xl max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                {isLoading || !application ? (
                    <div className="h-64 flex flex-col items-center justify-center p-6">
                        <DialogTitle className="sr-only">Loading application</DialogTitle>
                        <Loader2 className="w-8 h-8 animate-spin text-sky-600" />
                        <span className="text-sm text-slate-500 mt-2">Loading application...</span>
                    </div>
                ) : (
                    <>
                        {/* Standardized Fixed Header */}
                        <ModalHeader
                            title={`${application.first_name} ${application.middle_name ? application.middle_name + " " : ""}${application.last_name}`}
                            badge={getStatusBadge(application.status)}
                            metadata={
                                <>
                                    <span className="font-mono text-sky-600 dark:text-sky-400 font-bold">
                                        {application.application_number}
                                    </span>
                                    <span>·</span>
                                    <span>Target Grade: <strong>{application.level_name || application.level}</strong></span>
                                    <span>·</span>
                                    <span>Academic Year: <strong>{application.academic_year}</strong></span>
                                    {application.student_enrollment_id && (
                                        <>
                                            <span>·</span>
                                            <span className="font-mono text-emerald-600 dark:text-emerald-400 font-bold">
                                                Enrolled ID: {application.student_enrollment_id}
                                            </span>
                                        </>
                                    )}
                                </>
                            }
                            actions={
                                <div className="flex items-center gap-2 mr-1">
                                    {canReviewApps && (
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={createTrackingLink}
                                            disabled={issueLink.isPending}
                                            title="Create a link the family can use to follow this application online"
                                        >
                                            {issueLink.isPending ? "Creating..." : "Tracking link"}
                                        </Button>
                                    )}
                                    {canDecide && !isEnrolled && currentStatus !== "rejected" && (
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => setDecisionOpen(true)}
                                            className="rounded-lg h-9 font-medium text-xs text-slate-700 dark:text-slate-200"
                                        >
                                            <Shield className="w-3.5 h-3.5 mr-1 text-sky-600" />
                                            Make Decision
                                        </Button>
                                    )}

                                    {canEnroll && canTakeEnrollmentAction && (
                                        <Button
                                            size="sm"
                                            onClick={() => setEnrollOpen(true)}
                                            className="bg-sky-600 hover:bg-sky-700 text-white rounded-lg h-9 font-medium text-xs shadow-xs"
                                        >
                                            <GraduationCap className="w-3.5 h-3.5 mr-1" />
                                            Enroll Student
                                        </Button>
                                    )}
                                </div>
                            }
                            onClose={() => onOpenChange(false)}
                        />

                        {/* Independently Scrollable Body */}
                        <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-6">
                            {tracking && tracking.reference === application.application_number && (
                                <div className="rounded-xl border border-sky-200 bg-sky-50 dark:border-sky-900 dark:bg-sky-950/30 p-4 space-y-3 text-sm">
                                    <p className="font-semibold text-sky-900 dark:text-sky-200">
                                        Give the family this link. It is shown only now, and works until {tracking.expires}.
                                    </p>
                                    <div className="flex flex-wrap items-center gap-2">
                                        <Input readOnly value={tracking.link} className="flex-1 min-w-0 font-mono text-xs" aria-label="Tracking link" />
                                        <Button size="sm" onClick={() => copy(tracking.link, "Link")}>Copy link</Button>
                                    </div>
                                    <p className="text-xs text-sky-800 dark:text-sky-300">
                                        Or, on the Track Application page: reference <span className="font-mono font-semibold">{tracking.reference}</span>, token{" "}
                                        <button type="button" className="underline" onClick={() => copy(tracking.token, "Token")}>copy token</button>.
                                    </p>
                                </div>
                            )}
                            {/* Lifecycle Status Bar & Reviewer Controls */}
                            <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-800 flex flex-wrap items-center justify-between gap-4">
                            <div className="flex items-center gap-3">
                                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                                    Assign Reviewer:
                                </span>
                                {canManageApps ? (
                                    <Select
                                        value={application.assigned_reviewer || "none"}
                                        onValueChange={handleAssignReviewer}
                                        disabled={assignMutation.isPending}
                                    >
                                        <SelectTrigger className="h-9 w-52 rounded-xl text-xs bg-white dark:bg-slate-900">
                                            <SelectValue placeholder="Unassigned" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="none">No Reviewer Assigned</SelectItem>
                                            {staffList.map((st) => (
                                                <SelectItem key={st.id} value={st.id}>
                                                    {st.profile_details?.first_name} {st.profile_details?.last_name} ({st.employee_id})
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                ) : (
                                    <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                                        {application.assigned_reviewer_name || "Unassigned"}
                                    </span>
                                )}
                            </div>

                            {/* Transition Status Dropdown */}
                            {canManageApps && nextTransitions.length > 0 && (
                                <div className="flex items-center gap-2">
                                    <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                                        Transition To:
                                    </span>
                                    <Select onValueChange={handleStatusTransition} disabled={transitionMutation.isPending}>
                                        <SelectTrigger className="h-9 w-44 rounded-xl text-xs bg-white dark:bg-slate-900 capitalize">
                                            <SelectValue placeholder="Next Step..." />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {nextTransitions.map((st) => (
                                                <SelectItem key={st} value={st} className="capitalize">
                                                    {st.replace(/_/g, " ")}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            )}
                        </div>

                        {/* Rejection / Decision Callout */}
                        {application.status === "rejected" && application.decision_reason && (
                            <div className="p-4 rounded-2xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900/60 flex items-start gap-3">
                                <XCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
                                <div>
                                    <h4 className="text-sm font-bold text-red-900 dark:text-red-200">
                                        Application Rejected
                                    </h4>
                                    <p className="text-xs text-red-700 dark:text-red-300 mt-1">
                                        {application.decision_reason}
                                    </p>
                                    <p className="text-xs text-red-800 dark:text-red-300 mt-2">
                                        {application.decision_notice_sent_at
                                            ? `The family was emailed on ${new Date(application.decision_notice_sent_at).toLocaleDateString()}.`
                                            : "The family has not been told yet. You may want to call them first."}
                                    </p>
                                    {canDecide && !application.decision_notice_sent_at && (
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            className="mt-2"
                                            disabled={sendNotice.isPending}
                                            onClick={() => sendNotice.mutate(application.id)}
                                        >
                                            {sendNotice.isPending ? "Sending..." : "Send rejection email"}
                                        </Button>
                                    )}
                                </div>
                            </div>
                        )}

                        {application.status === "documents_pending" && (
                            <p className="text-xs text-slate-500">
                                {application.documents_reminded_at
                                    ? `The family was last reminded about documents on ${new Date(application.documents_reminded_at).toLocaleDateString()}.`
                                    : "The family has not been sent a document reminder yet. One goes out a week after they were asked, if something is still theirs to send."}
                            </p>
                        )}

                        {/* Tabs */}
                        <Tabs defaultValue="overview" className="w-full">
                            <TabsList className="bg-slate-100 dark:bg-slate-800 p-1 rounded-2xl grid grid-cols-2 sm:grid-cols-4 w-full h-auto">
                                <TabsTrigger value="overview" className="rounded-xl font-semibold text-xs">
                                    <User className="w-3.5 h-3.5 mr-1.5" />
                                    Student & Guardians
                                </TabsTrigger>
                                <TabsTrigger value="documents" className="rounded-xl font-semibold text-xs">
                                    <FileCheck className="w-3.5 h-3.5 mr-1.5" />
                                    Documents ({application.documents?.length || 0})
                                </TabsTrigger>
                                <TabsTrigger value="interviews" className="rounded-xl font-semibold text-xs">
                                    <Calendar className="w-3.5 h-3.5 mr-1.5" />
                                    Assessment ({application.interviews?.length || 0})
                                </TabsTrigger>
                                <TabsTrigger value="history" className="rounded-xl font-semibold text-xs">
                                    <History className="w-3.5 h-3.5 mr-1.5" />
                                    History
                                </TabsTrigger>
                            </TabsList>

                            {/* Tab 1: Overview */}
                            <TabsContent value="overview" className="space-y-6 pt-4">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    {/* Student Card */}
                                    <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 space-y-3">
                                        <h4 className="text-sm font-bold text-slate-800 dark:text-white flex items-center gap-2">
                                            <User className="w-4 h-4 text-blue-600" />
                                            Applicant Information
                                        </h4>
                                        <div className="grid grid-cols-2 gap-2 text-xs">
                                            <div>
                                                <span className="text-slate-400 block">Date of Birth:</span>
                                                <span className="font-semibold text-slate-700 dark:text-slate-200">{application.date_of_birth}</span>
                                            </div>
                                            <div>
                                                <span className="text-slate-400 block">Gender:</span>
                                                <span className="font-semibold text-slate-700 dark:text-slate-200 capitalize">{application.gender}</span>
                                            </div>
                                            <div>
                                                <span className="text-slate-400 block">Contact Phone:</span>
                                                <span className="font-semibold text-slate-700 dark:text-slate-200">{application.phone || "—"}</span>
                                            </div>
                                            <div>
                                                <span className="text-slate-400 block">Email:</span>
                                                <span className="font-semibold text-slate-700 dark:text-slate-200">{application.email || "—"}</span>
                                            </div>
                                            <div className="col-span-2">
                                                <span className="text-slate-400 block">Residential Address:</span>
                                                <span className="font-semibold text-slate-700 dark:text-slate-200">{application.address || "—"}</span>
                                            </div>
                                            <div>
                                                <span className="text-slate-400 block">Previous School:</span>
                                                <span className="font-semibold text-slate-700 dark:text-slate-200">{application.previous_school || "—"}</span>
                                            </div>
                                            <div>
                                                <span className="text-slate-400 block">Last Grade Passed:</span>
                                                <span className="font-semibold text-slate-700 dark:text-slate-200">{application.last_grade_passed || "—"}</span>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Guardians Card */}
                                    <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 space-y-3">
                                        <h4 className="text-sm font-bold text-slate-800 dark:text-white flex items-center gap-2">
                                            <Users className="w-4 h-4 text-indigo-600" />
                                            Parent / Guardian Information
                                        </h4>
                                        <div className="grid grid-cols-2 gap-2 text-xs">
                                            <div>
                                                <span className="text-slate-400 block">Primary Guardian:</span>
                                                <span className="font-semibold text-slate-700 dark:text-slate-200">
                                                    {application.guardian_first_name} {application.guardian_last_name}
                                                </span>
                                            </div>
                                            <div>
                                                <span className="text-slate-400 block">Relationship:</span>
                                                <span className="font-semibold text-slate-700 dark:text-slate-200 capitalize">{application.guardian_relationship}</span>
                                            </div>
                                            <div>
                                                <span className="text-slate-400 block">Phone:</span>
                                                <span className="font-semibold text-slate-700 dark:text-slate-200">{application.guardian_phone}</span>
                                            </div>
                                            <div>
                                                <span className="text-slate-400 block">Occupation:</span>
                                                <span className="font-semibold text-slate-700 dark:text-slate-200">{application.guardian_occupation || "—"}</span>
                                            </div>
                                            <div className="col-span-2">
                                                <span className="text-slate-400 block">Email:</span>
                                                <span className="font-semibold text-slate-700 dark:text-slate-200">{application.guardian_email || "—"}</span>
                                            </div>
                                            {application.secondary_guardian_name && (
                                                <div className="col-span-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                                                    <span className="text-slate-400 block">Co-Guardian / Secondary:</span>
                                                    <span className="font-semibold text-slate-700 dark:text-slate-200">
                                                        {application.secondary_guardian_name} ({application.secondary_guardian_relationship || "Co-Guardian"}) · {application.secondary_guardian_phone}
                                                    </span>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </TabsContent>

                            {/* Tab 2: Documents */}
                            <TabsContent value="documents" className="space-y-4 pt-4">
                                {(application.document_checklist?.length ?? 0) > 0 && (
                                    <div className="rounded-2xl border border-slate-200 p-4 dark:border-slate-800">
                                        <span className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-300">
                                            Required for this class
                                        </span>
                                        <ul className="space-y-1 text-sm">
                                            {application.document_checklist?.map((item) => (
                                                <li key={item.document_type} className="flex items-center justify-between gap-2">
                                                    <span>{item.label}</span>
                                                    <Badge variant={item.status === "verified" ? "default" : item.status === "received" ? "secondary" : "destructive"}>
                                                        {item.status === "verified" ? "Verified" : item.status === "received" ? "Received, to check" : item.status === "rejected" ? "Send again" : "Missing"}
                                                    </Badge>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                                {canManageApps && (
                                    <form onSubmit={handleUploadDoc} className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-800 space-y-3">
                                        <span className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-300 block">
                                            Upload Required Document
                                        </span>
                                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                            <Select value={docType} onValueChange={(v) => setDocType(v as DocumentType)}>
                                                <SelectTrigger className="h-9 rounded-xl text-xs bg-white dark:bg-slate-900">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="birth_certificate">Birth Certificate</SelectItem>
                                                    <SelectItem value="transfer_certificate">Transfer Certificate (TC)</SelectItem>
                                                    <SelectItem value="previous_marksheet">Previous Marksheet / Report Card</SelectItem>
                                                    <SelectItem value="photo">Passport Photograph</SelectItem>
                                                    <SelectItem value="address_proof">Address Proof</SelectItem>
                                                    <SelectItem value="medical_record">Medical Record</SelectItem>
                                                    <SelectItem value="other">Other Document</SelectItem>
                                                </SelectContent>
                                            </Select>
                                            <Input aria-label="Title / Description (Optional)"
                                                placeholder="Title / Description (Optional)"
                                                value={docTitle}
                                                onChange={(e) => setDocTitle(e.target.value)}
                                                className="h-9 rounded-xl text-xs"
                                            />
                                            <div className="flex items-center gap-2">
                                                <Input
                                                    type="file"
                                                    required
                                                    onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                                                    className="h-9 rounded-xl text-xs file:mr-2 file:h-7 file:rounded-lg file:border-0 file:bg-slate-100 file:text-xs"
                                                />
                                                <Button
                                                    type="submit"
                                                    disabled={!selectedFile || uploadDocMutation.isPending}
                                                    className="h-9 px-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-semibold"
                                                >
                                                    {uploadDocMutation.isPending ? (
                                                        <Loader2 className="w-4 h-4 animate-spin" />
                                                    ) : (
                                                        <Upload className="w-4 h-4" />
                                                    )}
                                                </Button>
                                            </div>
                                        </div>
                                    </form>
                                )}

                                {/* Documents List */}
                                <div className="space-y-2">
                                    {application.documents?.length === 0 ? (
                                        <div className="p-8 text-center text-slate-400 text-xs rounded-2xl border border-dashed border-slate-200 dark:border-slate-800">
                                            No documents uploaded yet.
                                        </div>
                                    ) : (
                                        application.documents?.map((doc) => (
                                            <div
                                                key={doc.id}
                                                className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3"
                                            >
                                                <div>
                                                    <div className="flex items-center gap-2">
                                                        <span className="font-bold text-sm text-slate-800 dark:text-white">
                                                            {doc.title || doc.document_type_display}
                                                        </span>
                                                        <Badge variant="outline" className="text-xs">
                                                            {doc.document_type_display}
                                                        </Badge>
                                                        {doc.verification_status === "verified" ? (
                                                            <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border-none font-semibold text-xs">
                                                                <Check className="w-3 h-3 mr-1" /> Verified
                                                            </Badge>
                                                        ) : doc.verification_status === "rejected" ? (
                                                            <Badge className="bg-red-100 text-red-800 dark:bg-red-950/60 dark:text-red-300 border-none font-semibold text-xs">
                                                                <X className="w-3 h-3 mr-1" /> Rejected
                                                            </Badge>
                                                        ) : (
                                                            <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border-none font-semibold text-xs">
                                                                Pending Verification
                                                            </Badge>
                                                        )}
                                                    </div>
                                                    {doc.rejection_reason && (
                                                        <div className="text-xs text-red-600 dark:text-red-400 mt-1 font-medium">
                                                            Reason: {doc.rejection_reason}
                                                        </div>
                                                    )}
                                                    {doc.verified_by_name && (
                                                        <div className="text-xs text-slate-400 mt-0.5">
                                                            Verified by {doc.verified_by_name} on {doc.verified_at ? new Date(doc.verified_at).toLocaleDateString() : ""}
                                                        </div>
                                                    )}
                                                </div>

                                                <div className="flex items-center gap-2 self-end sm:self-center">
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        asChild
                                                        className="h-8 rounded-xl text-xs font-semibold"
                                                    >
                                                        <a
                                                            href={`/api/admissions/documents/${doc.id}/download/`}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                        >
                                                            <Download className="w-3.5 h-3.5 mr-1" />
                                                            View / Download
                                                        </a>
                                                    </Button>

                                                    {canReviewDocs && doc.verification_status !== "verified" && (
                                                        <Button
                                                            size="sm"
                                                            onClick={() => verifyDocMutation.mutate(doc.id)}
                                                            disabled={verifyDocMutation.isPending}
                                                            className="h-8 px-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold"
                                                        >
                                                            <Check className="w-3.5 h-3.5 mr-1" />
                                                            Verify
                                                        </Button>
                                                    )}

                                                    {canReviewDocs && doc.verification_status !== "rejected" && (
                                                        <Button
                                                            size="sm"
                                                            variant="destructive"
                                                            onClick={() => {
                                                                setRejectingDocId(doc.id);
                                                                setRejectionReason("");
                                                            }}
                                                            className="h-8 px-2.5 rounded-xl text-xs font-semibold"
                                                        >
                                                            <X className="w-3.5 h-3.5 mr-1" />
                                                            Reject
                                                        </Button>
                                                    )}
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>

                                {/* Inline Document Rejection Modal */}
                                {rejectingDocId && (
                                    <div className="p-4 rounded-2xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-900 space-y-3">
                                        <Label htmlFor="f-specify-reason-for-rejecting-d" className="text-xs font-bold text-red-900 dark:text-red-200">
                                            Specify Reason for Rejecting Document *
                                        </Label>
                                        <Input id="f-specify-reason-for-rejecting-d"
                                            value={rejectionReason}
                                            onChange={(e) => setRejectionReason(e.target.value)}
                                            placeholder="e.g. Incomplete scan, missing signature, seal not clear..."
                                            className="h-9 rounded-xl text-xs"
                                        />
                                        <div className="flex justify-end gap-2">
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                onClick={() => setRejectingDocId(null)}
                                                className="h-8 text-xs rounded-xl"
                                            >
                                                Cancel
                                            </Button>
                                            <Button
                                                size="sm"
                                                variant="destructive"
                                                onClick={() => handleRejectDoc(rejectingDocId)}
                                                disabled={!rejectionReason.trim() || rejectDocMutation.isPending}
                                                className="h-8 text-xs rounded-xl font-semibold"
                                            >
                                                Confirm Rejection
                                            </Button>
                                        </div>
                                    </div>
                                )}
                            </TabsContent>

                            {/* Tab 3: Interviews & Assessment */}
                            <TabsContent value="interviews" className="space-y-4 pt-4">
                                {canReviewApps && (
                                    <form onSubmit={handleScheduleInterview} className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-800 space-y-3">
                                        <span className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-300 block">
                                            Schedule Evaluation / Interaction
                                        </span>
                                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                            <Select value={interviewType} onValueChange={(v) => setInterviewType(v as InterviewType)}>
                                                <SelectTrigger className="h-9 rounded-xl text-xs bg-white dark:bg-slate-900">
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="student_interview">Student Interview</SelectItem>
                                                    <SelectItem value="written_test">Written Assessment</SelectItem>
                                                    <SelectItem value="parent_interaction">Parent Interaction</SelectItem>
                                                    <SelectItem value="portfolio_review">Portfolio Review</SelectItem>
                                                    <SelectItem value="other">Other Evaluation</SelectItem>
                                                </SelectContent>
                                            </Select>
                                            <Input
                                                type="datetime-local"
                                                value={scheduledAt}
                                                onChange={(e) => setScheduledAt(e.target.value)}
                                                className="h-9 rounded-xl text-xs"
                                            />
                                            <div className="flex items-center gap-2">
                                                <Select value={interviewerId} onValueChange={setInterviewerId}>
                                                    <SelectTrigger className="h-9 rounded-xl text-xs bg-white dark:bg-slate-900 flex-1">
                                                        <SelectValue placeholder="Evaluator" />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectItem value="none">Unassigned</SelectItem>
                                                        {staffList.map((st) => (
                                                            <SelectItem key={st.id} value={st.id}>
                                                                {st.profile_details?.first_name} {st.profile_details?.last_name}
                                                            </SelectItem>
                                                        ))}
                                                    </SelectContent>
                                                </Select>
                                                <Button
                                                    type="submit"
                                                    disabled={scheduleInterviewMutation.isPending}
                                                    className="h-9 px-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold"
                                                >
                                                    Schedule
                                                </Button>
                                            </div>
                                        </div>
                                    </form>
                                )}

                                {/* Interview List */}
                                <div className="space-y-3">
                                    {application.interviews?.length === 0 ? (
                                        <div className="p-8 text-center text-slate-400 text-xs rounded-2xl border border-dashed border-slate-200 dark:border-slate-800">
                                            No assessments or interviews recorded.
                                        </div>
                                    ) : (
                                        application.interviews?.map((iv) => (
                                            <div
                                                key={iv.id}
                                                className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 space-y-2"
                                            >
                                                <div className="flex flex-wrap items-center justify-between gap-2">
                                                    <div className="flex items-center gap-2">
                                                        <span className="font-bold text-sm text-slate-800 dark:text-white">
                                                            {iv.interview_type_display}
                                                        </span>
                                                        <Badge variant="outline" className="capitalize text-xs">
                                                            {iv.status}
                                                        </Badge>
                                                        {iv.recommendation && (
                                                            <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300 border-none capitalize text-xs">
                                                                {iv.recommendation.replace(/_/g, " ")}
                                                            </Badge>
                                                        )}
                                                    </div>
                                                    {iv.score && (
                                                        <span className="font-bold text-sm text-indigo-600 dark:text-indigo-400">
                                                            Score: {iv.score}%
                                                        </span>
                                                    )}
                                                </div>
                                                <div className="text-xs text-slate-500 flex items-center gap-4">
                                                    <span>Scheduled: {iv.scheduled_at ? new Date(iv.scheduled_at).toLocaleString() : "TBD"}</span>
                                                    {iv.interviewer_name && <span>Evaluator: {iv.interviewer_name}</span>}
                                                </div>
                                                {iv.feedback && (
                                                    <div className="text-xs bg-slate-50 dark:bg-slate-800/60 p-2.5 rounded-xl text-slate-700 dark:text-slate-300">
                                                        {iv.feedback}
                                                    </div>
                                                )}
                                            </div>
                                        ))
                                    )}
                                </div>
                            </TabsContent>

                            {/* Tab 4: History */}
                            <TabsContent value="history" className="space-y-3 pt-4">
                                <div className="space-y-3">
                                    {application.activities?.length === 0 ? (
                                        <div className="p-8 text-center text-slate-400 text-xs rounded-2xl border border-dashed border-slate-200 dark:border-slate-800">
                                            No activity logs available.
                                        </div>
                                    ) : (
                                        application.activities?.map((act) => (
                                            <div
                                                key={act.id}
                                                className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-800 flex flex-wrap items-start justify-between gap-2 text-xs"
                                            >
                                                <div>
                                                    <div className="font-bold text-slate-800 dark:text-white capitalize">
                                                        {act.action.replace(/_/g, " ")}
                                                    </div>
                                                    {act.notes && (
                                                        <div className="text-slate-600 dark:text-slate-300 mt-0.5">
                                                            {act.notes}
                                                        </div>
                                                    )}
                                                    {act.performed_by_name && (
                                                        <div className="text-slate-400 mt-1">
                                                            By: {act.performed_by_name}
                                                        </div>
                                                    )}
                                                </div>
                                                <div className="text-slate-400 font-mono">
                                                    {new Date(act.created_at).toLocaleString()}
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </TabsContent>
                        </Tabs>
                    </DialogBody>
                </>
                )}
            </DialogContent>

            <DecisionDialog
                open={decisionOpen}
                onOpenChange={setDecisionOpen}
                application={application || null}
            />

            <EnrollDialog
                open={enrollOpen}
                onOpenChange={setEnrollOpen}
                application={application || null}
            />
        </Dialog>
    );
}

