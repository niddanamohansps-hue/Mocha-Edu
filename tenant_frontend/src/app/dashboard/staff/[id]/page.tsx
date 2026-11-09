"use client";

import React, { use, useState } from "react";
import { useRouter } from "next/navigation";
import { useStaffMember } from "@/hooks/useStaff";
import { useAllLeaveBalances, useApproverInbox } from "@/hooks/useStaffLeaves";
import { useStaffAttendanceHistory } from "@/hooks/useAttendance";
import { useInstructorAssignments } from "@/hooks/useAcademics";
import { usePermissions } from "@/providers/PermissionProvider";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LeaveDetailModal } from "@/components/dashboard/staff/leaves/LeaveDetailModal";
import { ApplyLeaveDialog } from "@/components/dashboard/staff/leaves/ApplyLeaveDialog";
import { StaffIDCardModal } from "@/components/dashboard/staff/StaffIDCardModal";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import {
    Briefcase,
    ArrowLeft,
    Pencil,
    Calendar,
    Phone,
    Mail,
    MapPin,
    Shield,
    Users,
    Clock,
    CheckCircle2,
    XCircle,
    Building,
    GraduationCap,
    BookOpen,
    Copy,
    Check,
    Plus,
    UserCheck,
    FileText,
    Printer,
} from "lucide-react";
import { toast } from "sonner";

const AVATAR_PALETTES = [
    { bg: "bg-sky-100 dark:bg-sky-950/70", text: "text-sky-700 dark:text-sky-300", border: "border-sky-300/60 dark:border-sky-800" },
    { bg: "bg-emerald-100 dark:bg-emerald-950/70", text: "text-emerald-700 dark:text-emerald-300", border: "border-emerald-300/60 dark:border-emerald-800" },
    { bg: "bg-indigo-100 dark:bg-indigo-950/70", text: "text-indigo-700 dark:text-indigo-300", border: "border-indigo-300/60 dark:border-indigo-800" },
    { bg: "bg-purple-100 dark:bg-purple-950/70", text: "text-purple-700 dark:text-purple-300", border: "border-purple-300/60 dark:border-purple-800" },
    { bg: "bg-amber-100 dark:bg-amber-950/70", text: "text-amber-700 dark:text-amber-300", border: "border-amber-300/60 dark:border-amber-800" },
    { bg: "bg-rose-100 dark:bg-rose-950/70", text: "text-rose-700 dark:text-rose-300", border: "border-rose-300/60 dark:border-rose-800" },
    { bg: "bg-teal-100 dark:bg-teal-950/70", text: "text-teal-700 dark:text-teal-300", border: "border-teal-300/60 dark:border-teal-800" },
];

function getAvatarStyle(name?: string | null) {
    if (!name || typeof name !== "string") return AVATAR_PALETTES[0];
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    const index = Math.abs(hash) % AVATAR_PALETTES.length;
    return AVATAR_PALETTES[index];
}

function getInitials(first: string = "", last: string = "") {
    const f = first.trim()[0] || "";
    const l = last.trim()[0] || "";
    return `${f}${l}`.toUpperCase() || "ST";
}

function formatDate(dateStr?: string | null) {
    if (!dateStr) return "—";
    try {
        if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
            const [y, m, d] = dateStr.split("-").map(Number);
            const date = new Date(y, m - 1, d);
            return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
        }
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr.split("T")[0];
        return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    } catch {
        return dateStr.split("T")[0];
    }
}

const ATTENDANCE_STATUS_LABELS: Record<string, { label: string; badge: string }> = {
    present: { label: "Present", badge: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300" },
    absent: { label: "Absent", badge: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300" },
    late: { label: "Late Arrival", badge: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300" },
    half_day: { label: "Half Day", badge: "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-300" },
    leave: { label: "On Leave", badge: "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300" },
};

interface Staff360PageProps {
    params: Promise<{ id: string }>;
}

export default function Staff360Page({ params }: Staff360PageProps) {
    const { can, isOwner } = usePermissions();
    const router = useRouter();

    const resolvedParams = use(params);
    const { id } = resolvedParams;

    const canView = isOwner || can("view_staff");
    const canEdit = isOwner || can("change_staff");
    const canManagePortal = isOwner || can("manage_portal_access");
    const canManageLeaves = isOwner || can("manage_leaves");

    const [activeTab, setActiveTab] = useState("overview");
    const [copiedPhone, setCopiedPhone] = useState<string | null>(null);
    const [selectedLeaveId, setSelectedLeaveId] = useState<string | null>(null);
    const [isApplyLeaveOpen, setIsApplyLeaveOpen] = useState(false);
    const [isIdCardOpen, setIsIdCardOpen] = useState(false);

    const { data: staff, isLoading, isError, refetch } = useStaffMember(id);
    const { data: leaveBalancesData } = useAllLeaveBalances({ staff: id });
    const { data: leaveApplicationsData } = useApproverInbox({ staff: id });
    const { data: attendance } = useStaffAttendanceHistory(id);
    const { data: teachingAssignments = [] } = useInstructorAssignments(staff?.instructor_data?.id);

    const copyToClipboard = (text: string, label: string) => {
        if (!text) return;
        navigator.clipboard.writeText(text);
        setCopiedPhone(text);
        toast.success(`${label} copied to clipboard`);
        setTimeout(() => setCopiedPhone(null), 2000);
    };

    if (!canView) return <Unauthorized />;
    if (isLoading) return <LoadingState className="py-24" message="Loading Staff 360 Profile..." />;
    if (isError || !staff) return <ErrorState onRetry={refetch} message="Staff member record could not be loaded." />;

    const profile = staff.profile_details;
    const fullName = `${profile.first_name} ${profile.middle_name ? profile.middle_name + " " : ""}${profile.last_name}`.trim();
    const avatarStyle = getAvatarStyle(fullName);
    const initials = getInitials(profile.first_name, profile.last_name);
    const hasAccount = Boolean(profile.user_id);
    const leaveBalances = leaveBalancesData?.results || [];
    const leaveApplications = leaveApplicationsData?.results || [];

    const totalAvailableDays = leaveBalances.reduce((acc, b) => acc + (Number(b.available_days) || 0), 0);

    return (
        <div className="space-y-6 pb-16 max-w-7xl mx-auto animate-in fade-in duration-300">
            {/* Top Navigation & Breadcrumb */}
            <div className="flex items-center justify-between gap-4">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => router.push("/dashboard/staff")}
                    className="text-xs font-semibold text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 gap-1.5 h-8 px-2"
                >
                    <ArrowLeft className="h-4 w-4" />
                    <span>Back to Staff Directory</span>
                </Button>

                <div className="flex items-center gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setIsIdCardOpen(true)}
                        className="rounded-lg h-9 font-semibold text-xs gap-1.5 text-slate-700 dark:text-slate-200 border-slate-200 dark:border-slate-800"
                    >
                        <Printer className="h-3.5 w-3.5 text-indigo-600" />
                        <span>Print ID Card</span>
                    </Button>
                    {canManageLeaves && (
                        <Button
                            size="sm"
                            onClick={() => setIsApplyLeaveOpen(true)}
                            className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg h-9 font-semibold text-xs gap-1.5 shadow-xs"
                        >
                            <Plus className="h-3.5 w-3.5" />
                            <span>Apply Leave</span>
                        </Button>
                    )}
                    {canManagePortal && !hasAccount && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => router.push(`/dashboard/portal-access/staff`)}
                            className="rounded-lg h-9 font-semibold text-xs gap-1.5 text-emerald-600 border-emerald-300 dark:border-emerald-800 hover:bg-emerald-50 dark:hover:bg-emerald-950/40"
                        >
                            <UserCheck className="h-3.5 w-3.5" />
                            <span>Activate Portal</span>
                        </Button>
                    )}
                    {canEdit && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => router.push(`/dashboard/staff/edit/${staff.id}`)}
                            className="rounded-lg h-9 font-semibold text-xs gap-1.5 text-slate-700 dark:text-slate-200 border-slate-200 dark:border-slate-800"
                        >
                            <Pencil className="h-3.5 w-3.5 text-sky-600" />
                            <span>Edit Profile</span>
                        </Button>
                    )}
                </div>
            </div>

            {/* Executive Profile Header Card */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-6 shadow-xs relative overflow-hidden">
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-5">
                    <div className="flex items-center gap-4">
                        <div
                            className={`h-16 w-16 sm:h-20 sm:w-20 rounded-2xl flex items-center justify-center font-bold text-xl sm:text-2xl shrink-0 border ${avatarStyle.bg} ${avatarStyle.text} ${avatarStyle.border} shadow-inner`}
                        >
                            {initials}
                        </div>
                        <div className="space-y-1">
                            <div className="flex items-center gap-2.5 flex-wrap">
                                <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
                                    {fullName}
                                </h1>
                                <Badge className="bg-sky-50 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300 border border-sky-300/80 font-semibold text-xs">
                                    {staff.designation || "Staff Member"}
                                </Badge>
                                {hasAccount ? (
                                    <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300/80 font-semibold text-xs">
                                        Active Portal
                                    </Badge>
                                ) : (
                                    <Badge className="bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300/80 font-semibold text-xs">
                                        Pending Access
                                    </Badge>
                                )}
                            </div>

                            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400 font-medium pt-0.5">
                                <span className="flex items-center gap-1 font-mono text-sky-600 dark:text-sky-400 font-bold">
                                    <Shield className="h-3.5 w-3.5" />
                                    {staff.employee_id || "EMP-—"}
                                </span>
                                <span>•</span>
                                <span className="flex items-center gap-1">
                                    <Building className="h-3.5 w-3.5 text-slate-400" />
                                    {staff.department || "General Department"}
                                </span>
                                {staff.joining_date && (
                                    <>
                                        <span>•</span>
                                        <span className="flex items-center gap-1">
                                            <Calendar className="h-3.5 w-3.5 text-slate-400" />
                                            Joined {formatDate(staff.joining_date)}
                                        </span>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Quick Metric Badges */}
                    <div className="flex sm:flex-col items-end gap-2 shrink-0 self-stretch sm:self-auto justify-between border-t sm:border-t-0 border-slate-100 dark:border-slate-800 pt-3 sm:pt-0">
                        <div className="text-right">
                            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                                Leave Balance
                            </span>
                            <span className="text-base font-bold font-mono text-indigo-600 dark:text-indigo-400">
                                {totalAvailableDays} Days Remaining
                            </span>
                        </div>
                        {staff.experience_years !== undefined && staff.experience_years !== null && (
                            <div className="text-right">
                                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                                    Experience
                                </span>
                                <span className="text-sm font-bold text-slate-800 dark:text-slate-200">
                                    {staff.experience_years} Years
                                </span>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Main Tabs Navigation */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
                <TabsList className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 p-1 rounded-xl h-auto flex flex-wrap gap-1">
                    <TabsTrigger
                        value="overview"
                        className="rounded-lg text-xs font-semibold px-4 py-2 data-[state=active]:bg-sky-50 dark:data-[state=active]:bg-sky-950/60 data-[state=active]:text-sky-600 dark:data-[state=active]:text-sky-300 transition-all cursor-pointer"
                    >
                        <Briefcase className="h-3.5 w-3.5 mr-2" />
                        1. Professional Profile &amp; Bio
                    </TabsTrigger>
                    <TabsTrigger
                        value="leaves"
                        className="rounded-lg text-xs font-semibold px-4 py-2 data-[state=active]:bg-sky-50 dark:data-[state=active]:bg-sky-950/60 data-[state=active]:text-sky-600 dark:data-[state=active]:text-sky-300 transition-all cursor-pointer"
                    >
                        <Calendar className="h-3.5 w-3.5 mr-2" />
                        2. Leaves &amp; Absence Ledger
                    </TabsTrigger>
                    <TabsTrigger
                        value="attendance"
                        className="rounded-lg text-xs font-semibold px-4 py-2 data-[state=active]:bg-sky-50 dark:data-[state=active]:bg-sky-950/60 data-[state=active]:text-sky-600 dark:data-[state=active]:text-sky-300 transition-all cursor-pointer"
                    >
                        <Clock className="h-3.5 w-3.5 mr-2" />
                        3. Daily Attendance
                    </TabsTrigger>
                    <TabsTrigger
                        value="teaching"
                        className="rounded-lg text-xs font-semibold px-4 py-2 data-[state=active]:bg-sky-50 dark:data-[state=active]:bg-sky-950/60 data-[state=active]:text-sky-600 dark:data-[state=active]:text-sky-300 transition-all cursor-pointer"
                    >
                        <GraduationCap className="h-3.5 w-3.5 mr-2" />
                        4. Teaching &amp; Classes ({teachingAssignments.length})
                    </TabsTrigger>
                </TabsList>

                {/* Tab 1: Professional Profile & Bio */}
                <TabsContent value="overview" className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Employment Details */}
                        <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-xs space-y-4">
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
                                <Briefcase className="h-4 w-4 text-sky-600" />
                                <span>Institutional Appointment</span>
                            </h3>

                            <div className="grid grid-cols-2 gap-4 text-xs">
                                <div>
                                    <span className="text-slate-400 block font-medium">Designation</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5 block">
                                        {staff.designation || "Staff Member"}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block font-medium">Department</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5 block">
                                        {staff.department || "General"}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block font-medium">Employee Code</span>
                                    <span className="font-bold text-sky-600 font-mono mt-0.5 block">
                                        {staff.employee_id || "EMP-—"}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block font-medium">Date of Joining</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5 block">
                                        {formatDate(staff.joining_date)}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block font-medium">Total Experience</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5 block">
                                        {staff.experience_years ? `${staff.experience_years} Years` : "—"}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block font-medium">Educational Qualification</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5 block">
                                        {staff.qualification || "—"}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Contact Channels */}
                        <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-xs space-y-4">
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
                                <Phone className="h-4 w-4 text-emerald-600" />
                                <span>Contact Channels &amp; Address</span>
                            </h3>

                            <div className="space-y-3 text-xs">
                                <div>
                                    <span className="text-slate-400 block font-medium">Primary Phone Number</span>
                                    <div className="flex items-center gap-2 mt-0.5">
                                        {profile.phone ? (
                                            <>
                                                <a href={`tel:${profile.phone}`} className="font-semibold text-sky-600 hover:underline font-mono">
                                                    {profile.phone}
                                                </a>
                                                <button
                                                    type="button"
                                                    onClick={() => copyToClipboard(profile.phone, "Phone")}
                                                    className="p-1 rounded text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 cursor-pointer"
                                                    title="Copy phone"
                                                >
                                                    {copiedPhone === profile.phone ? <Check className="h-3 w-3 text-emerald-500" /> : <Copy className="h-3 w-3" />}
                                                </button>
                                            </>
                                        ) : "—"}
                                    </div>
                                </div>

                                <div>
                                    <span className="text-slate-400 block font-medium">Official Email Address</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5 block">
                                        {profile.email || "No email on file"}
                                    </span>
                                </div>

                                <div>
                                    <span className="text-slate-400 block font-medium">Residential Address</span>
                                    <p className="font-medium text-slate-700 dark:text-slate-300 mt-0.5 whitespace-pre-wrap leading-relaxed">
                                        {profile.address || "Address not provided"}
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Personal Bio */}
                        <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-xs space-y-4">
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
                                <Users className="h-4 w-4 text-purple-600" />
                                <span>Personal Demographics</span>
                            </h3>

                            <div className="grid grid-cols-2 gap-4 text-xs">
                                <div>
                                    <span className="text-slate-400 block font-medium">Gender</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 capitalize mt-0.5 block">
                                        {profile.gender || "—"}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block font-medium">Date of Birth</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5 block">
                                        {formatDate(profile.date_of_birth)}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Portal Security Details */}
                        <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-xs space-y-4">
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
                                <Shield className="h-4 w-4 text-indigo-600" />
                                <span>Portal &amp; Security Authentication</span>
                            </h3>

                            <div className="space-y-3 text-xs">
                                <div>
                                    <span className="text-slate-400 block font-medium">Account Access Status</span>
                                    <div className="mt-1">
                                        {hasAccount ? (
                                            <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300/80 font-semibold text-xs">
                                                Active Portal Account
                                            </Badge>
                                        ) : (
                                            <Badge className="bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300/80 font-semibold text-xs">
                                                No Portal Credentials Generated
                                            </Badge>
                                        )}
                                    </div>
                                </div>
                                {profile.local_username && (
                                    <div>
                                        <span className="text-slate-400 block font-medium">System Username</span>
                                        <code className="font-mono font-bold text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded text-xs mt-0.5 inline-block">
                                            {profile.local_username}
                                        </code>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </TabsContent>

                {/* Tab 2: Leaves & Absence Ledger */}
                <TabsContent value="leaves" className="space-y-6">
                    {/* Annual Quotas */}
                    <div className="space-y-3">
                        <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                            Annual Leave Category Quotas
                        </h3>
                        {leaveBalances.length > 0 ? (
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                                {leaveBalances.map((bal) => (
                                    <div
                                        key={bal.id}
                                        className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-4 shadow-xs space-y-1"
                                    >
                                        <div className="flex items-center justify-between">
                                            <span className="font-bold text-xs text-slate-900 dark:text-white">
                                                {bal.leave_type_name}
                                            </span>
                                            <Badge variant="outline" className="font-mono text-[10px]">
                                                {bal.leave_type_code}
                                            </Badge>
                                        </div>
                                        <div className="text-xl font-bold font-mono text-indigo-600 dark:text-indigo-400 pt-1">
                                            {bal.available_days}d available
                                        </div>
                                        <div className="text-[11px] text-slate-400 flex items-center justify-between pt-0.5">
                                            <span>Allocated: {bal.allocated_days}d</span>
                                            <span>Used: {bal.used_days}d</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="p-8 text-center text-xs text-slate-400 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800">
                                No leave balances allocated for the current academic session.
                            </div>
                        )}
                    </div>

                    {/* Leave Applications History */}
                    <div className="space-y-3 pt-2">
                        <div className="flex items-center justify-between">
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                                Leave Requests &amp; Approvals History ({leaveApplications.length})
                            </h3>
                            {canManageLeaves && (
                                <Button
                                    size="sm"
                                    onClick={() => setIsApplyLeaveOpen(true)}
                                    className="h-8 text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg"
                                >
                                    <Plus className="h-3.5 w-3.5 mr-1" />
                                    Submit Leave Request
                                </Button>
                            )}
                        </div>

                        <TableShell>
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="pl-5">Leave Category</TableHead>
                                        <TableHead>Dates Requested</TableHead>
                                        <TableHead className="text-right">Duration</TableHead>
                                        <TableHead className="text-center">Status</TableHead>
                                        <TableHead className="text-right pr-5">Action</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {leaveApplications.length > 0 ? (
                                        leaveApplications.map((app) => (
                                            <TableRow key={app.id}>
                                                <TableCell className="pl-5 font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                    {app.leave_type_name}
                                                </TableCell>
                                                <TableCell className="text-xs text-slate-600 dark:text-slate-400">
                                                    {formatDate(app.start_date)} → {formatDate(app.end_date)}
                                                </TableCell>
                                                <TableCell className="text-right text-xs font-mono tabular-nums font-bold">
                                                    {app.working_days} working days
                                                </TableCell>
                                                <TableCell className="text-center">
                                                    <Badge
                                                        className={`text-[10px] font-semibold ${
                                                            app.status === "approved"
                                                                ? "bg-emerald-50 text-emerald-700 border-emerald-300"
                                                                : app.status === "rejected"
                                                                ? "bg-rose-50 text-rose-700 border-rose-300"
                                                                : "bg-amber-50 text-amber-700 border-amber-300"
                                                        }`}
                                                    >
                                                        {app.status}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell className="text-right pr-5">
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        onClick={() => setSelectedLeaveId(app.id)}
                                                        className="h-7 text-xs font-semibold px-2 rounded-lg"
                                                    >
                                                        Inspect
                                                    </Button>
                                                </TableCell>
                                            </TableRow>
                                        ))
                                    ) : (
                                        <TableRow>
                                            <TableCell colSpan={5} className="py-10 text-center text-xs text-slate-400">
                                                No leave requests recorded for this staff member.
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </TableBody>
                            </Table>
                        </TableShell>
                    </div>
                </TabsContent>

                {/* Tab 3: Daily Attendance */}
                <TabsContent value="attendance" className="space-y-6">
                    {attendance ? (
                        <>
                            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                                <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl p-3.5 shadow-xs">
                                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                                        Attendance Rate
                                    </span>
                                    <div className="text-2xl font-black text-slate-900 dark:text-white mt-1">
                                        {attendance.percentage !== null ? `${attendance.percentage}%` : "—"}
                                    </div>
                                </div>

                                {Object.entries(ATTENDANCE_STATUS_LABELS).map(([key, cfg]) => {
                                    const count = (attendance.counts as any)?.[key] ?? 0;
                                    return (
                                        <div
                                            key={key}
                                            className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl p-3.5 shadow-xs"
                                        >
                                            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                                                {cfg.label}
                                            </span>
                                            <div className="text-2xl font-black text-slate-900 dark:text-white mt-1">
                                                {count}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>

                            <TableShell>
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead className="pl-5">Date</TableHead>
                                            <TableHead className="text-center">Status</TableHead>
                                            <TableHead className="pr-5">Check-in / Remarks</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {attendance.records && attendance.records.length > 0 ? (
                                            attendance.records.map((r: any, i: number) => {
                                                const cfg = ATTENDANCE_STATUS_LABELS[r.status] || { label: r.status, badge: "" };
                                                return (
                                                    <TableRow key={i}>
                                                        <TableCell className="pl-5 font-medium font-mono text-xs">
                                                            {formatDate(r.date)}
                                                        </TableCell>
                                                        <TableCell className="text-center">
                                                            <Badge className={`text-xs font-semibold ${cfg.badge}`}>
                                                                {cfg.label}
                                                            </Badge>
                                                        </TableCell>
                                                        <TableCell className="pr-5 text-xs text-slate-500">
                                                            {r.remarks || "—"}
                                                        </TableCell>
                                                    </TableRow>
                                                );
                                            })
                                        ) : (
                                            <TableRow>
                                                <TableCell colSpan={3} className="py-12 text-center text-xs text-slate-400">
                                                    No daily staff attendance records found for this period.
                                                </TableCell>
                                            </TableRow>
                                        )}
                                    </TableBody>
                                </Table>
                            </TableShell>
                        </>
                    ) : (
                        <div className="p-12 text-center text-xs text-slate-400 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800">
                            Loading attendance records...
                        </div>
                    )}
                </TabsContent>

                {/* Tab 4: Teaching & Classes */}
                <TabsContent value="teaching" className="space-y-6">
                    <div className="space-y-3">
                        <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                            Assigned Subjects &amp; Class Sections
                        </h3>
                        <TableShell>
                            <Table>
                                <TableHeader>
                                    <TableRow>
                                        <TableHead className="pl-5">Academic Level (Grade)</TableHead>
                                        <TableHead>Section</TableHead>
                                        <TableHead>Subject</TableHead>
                                        <TableHead className="text-right pr-5">Weekly Periods</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {teachingAssignments.length > 0 ? (
                                        teachingAssignments.map((a: any) => (
                                            <TableRow key={a.id}>
                                                <TableCell className="pl-5 font-bold text-xs text-slate-900 dark:text-white">
                                                    {a.level_name || a.level}
                                                </TableCell>
                                                <TableCell className="text-xs font-semibold text-sky-600">
                                                    Section {a.section_name || a.section || "A"}
                                                </TableCell>
                                                <TableCell className="text-xs text-slate-700 dark:text-slate-300">
                                                    {a.subject_name || a.subject}
                                                </TableCell>
                                                <TableCell className="text-right pr-5 text-xs font-mono font-bold">
                                                    {a.periods_per_week ? `${a.periods_per_week} hrs/wk` : "—"}
                                                </TableCell>
                                            </TableRow>
                                        ))
                                    ) : (
                                        <TableRow>
                                            <TableCell colSpan={4} className="py-12 text-center text-xs text-slate-400">
                                                No active teaching or classroom subject assignments found for this staff member.
                                            </TableCell>
                                        </TableRow>
                                    )}
                                </TableBody>
                            </Table>
                        </TableShell>
                    </div>
                </TabsContent>
            </Tabs>

            {/* Leave Details Modal */}
            <LeaveDetailModal
                applicationId={selectedLeaveId}
                onClose={() => setSelectedLeaveId(null)}
                canManage={canManageLeaves}
            />

            {/* Apply Leave Dialog */}
            <ApplyLeaveDialog
                open={isApplyLeaveOpen}
                onOpenChange={setIsApplyLeaveOpen}
            />

            {/* Staff Identity Card Generator & Printer */}
            <StaffIDCardModal
                isOpen={isIdCardOpen}
                onClose={() => setIsIdCardOpen(false)}
                staff={staff}
            />
        </div>
    );
}
