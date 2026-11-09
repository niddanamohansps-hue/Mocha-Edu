"use client";

import React, { use, useState } from "react";
import { useRouter } from "next/navigation";
import { useStudent } from "@/hooks/useStudents";
import { useStudentAttendanceHistory } from "@/hooks/useAttendance";
import { useStudentFees, useStudentPayments } from "@/hooks/useFees";
import { usePermissions } from "@/providers/PermissionProvider";
import { CURRENCY } from "@/lib/currency";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { StudentParentsCard } from "@/components/dashboard/families/StudentParentsCard";
import { ReceiptModal } from "@/components/dashboard/fees/ReceiptModal";
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
    GraduationCap,
    ArrowLeft,
    Pencil,
    CreditCard,
    Calendar,
    Phone,
    Mail,
    MapPin,
    Shield,
    Users,
    Clock,
    CheckCircle2,
    XCircle,
    Printer,
    Sparkles,
    BookOpen,
    FileText,
    UserPlus,
    User,
} from "lucide-react";

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

function formatIndianCurrency(val: number | string | undefined | null): string {
    const num = Number(val || 0);
    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 2,
    }).format(num);
}

const ATTENDANCE_STATUS_LABELS: Record<string, { label: string; badge: string }> = {
    present: { label: "Present", badge: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300" },
    absent: { label: "Absent", badge: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300" },
    late: { label: "Late Arrival", badge: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300" },
    half_day: { label: "Half Day", badge: "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-300" },
    leave: { label: "On Leave", badge: "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300" },
};

interface Student360PageProps {
    params: Promise<{ id: string }>;
}

export default function Student360Page({ params }: Student360PageProps) {
    const { can, isOwner } = usePermissions();
    const router = useRouter();

    const resolvedParams = use(params);
    const { id } = resolvedParams;

    const canView = isOwner || can("view_student");
    const canEdit = isOwner || can("change_student");
    const canCollectFee = isOwner || can("collect_payments");

    const [activeTab, setActiveTab] = useState("overview");
    const [receiptIdToPrint, setReceiptIdToPrint] = useState<string | null>(null);

    const { data: student, isLoading, isError, refetch } = useStudent(id);
    const { data: attendance } = useStudentAttendanceHistory(id);
    const { data: feesData } = useStudentFees(id);
    const { data: payments = [] } = useStudentPayments(id);

    const totalDue = feesData?.fees?.reduce((acc, f) => acc + parseFloat(f.amount_due || "0"), 0) || 0;
    const totalPaid = feesData?.fees?.reduce((acc, f) => acc + parseFloat(f.amount_paid || "0"), 0) || 0;

    if (!canView) return <Unauthorized />;
    if (isLoading) return <LoadingState className="py-24" message="Loading Student 360 Profile..." />;
    if (isError || !student) return <ErrorState onRetry={refetch} message="Student record could not be loaded." />;

    const fullName = `${student.first_name} ${student.middle_name ? student.middle_name + " " : ""}${student.last_name}`.trim();
    const avatarStyle = getAvatarStyle(fullName);
    const initials = getInitials(student.first_name, student.last_name);

    return (
        <div className="space-y-6 pb-16 max-w-7xl mx-auto animate-in fade-in duration-300">
            {/* Top Navigation & Breadcrumb */}
            <div className="flex items-center justify-between gap-4">
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => router.push("/dashboard/students")}
                    className="text-xs font-semibold text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 gap-1.5 h-8 px-2"
                >
                    <ArrowLeft className="h-4 w-4" />
                    <span>Back to Student Directory</span>
                </Button>

                <div className="flex items-center gap-2">
                    {canCollectFee && (
                        <Button
                            size="sm"
                            onClick={() => router.push(`/dashboard/fees/collect?search=${student.enrollment_id}`)}
                            className="bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg h-9 font-semibold text-xs gap-1.5 shadow-xs"
                        >
                            <CreditCard className="h-3.5 w-3.5" />
                            <span>Collect Fee</span>
                        </Button>
                    )}
                    {canEdit && (
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => router.push(`/dashboard/students/edit/${student.id}`)}
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
                                <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300/80 font-semibold text-xs">
                                    Enrolled Student
                                </Badge>
                                {student.is_rte && (
                                    <Badge variant="outline" className="text-amber-600 border-amber-300 dark:border-amber-800 text-xs">
                                        RTE Quota
                                    </Badge>
                                )}
                            </div>

                            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400 font-medium pt-0.5">
                                <span className="flex items-center gap-1 font-mono text-sky-600 dark:text-sky-400 font-bold">
                                    <Shield className="h-3.5 w-3.5" />
                                    {student.enrollment_id}
                                </span>
                                <span>•</span>
                                <span className="flex items-center gap-1">
                                    <GraduationCap className="h-3.5 w-3.5 text-slate-400" />
                                    {student.level || "Grade Not Set"} {student.section ? `• Sec ${student.section}` : ""}
                                </span>
                                {student.academic_year && (
                                    <>
                                        <span>•</span>
                                        <span className="flex items-center gap-1">
                                            <Calendar className="h-3.5 w-3.5 text-slate-400" />
                                            {student.academic_year}
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
                                Outstanding Dues
                            </span>
                            <span className={`text-base font-bold font-mono ${feesData && parseFloat(feesData.total_outstanding) > 0 ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"}`}>
                                {feesData ? formatIndianCurrency(feesData.total_outstanding) : "₹0.00"}
                            </span>
                        </div>
                        {attendance && attendance.percentage !== null && (
                            <div className="text-right">
                                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                                    Attendance
                                </span>
                                <span className="text-sm font-bold text-slate-800 dark:text-slate-200">
                                    {attendance.percentage}% Present
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
                        <UserPlus className="h-3.5 w-3.5 mr-2" />
                        1. Personal &amp; Bio
                    </TabsTrigger>
                    <TabsTrigger
                        value="parents"
                        className="rounded-lg text-xs font-semibold px-4 py-2 data-[state=active]:bg-sky-50 dark:data-[state=active]:bg-sky-950/60 data-[state=active]:text-sky-600 dark:data-[state=active]:text-sky-300 transition-all cursor-pointer"
                    >
                        <Users className="h-3.5 w-3.5 mr-2" />
                        2. Parents &amp; Family
                    </TabsTrigger>
                    <TabsTrigger
                        value="attendance"
                        className="rounded-lg text-xs font-semibold px-4 py-2 data-[state=active]:bg-sky-50 dark:data-[state=active]:bg-sky-950/60 data-[state=active]:text-sky-600 dark:data-[state=active]:text-sky-300 transition-all cursor-pointer"
                    >
                        <Clock className="h-3.5 w-3.5 mr-2" />
                        3. Attendance Pulse
                    </TabsTrigger>
                    <TabsTrigger
                        value="fees"
                        className="rounded-lg text-xs font-semibold px-4 py-2 data-[state=active]:bg-sky-50 dark:data-[state=active]:bg-sky-950/60 data-[state=active]:text-sky-600 dark:data-[state=active]:text-sky-300 transition-all cursor-pointer"
                    >
                        <CreditCard className="h-3.5 w-3.5 mr-2" />
                        4. Fee Ledger &amp; Dues
                    </TabsTrigger>
                </TabsList>

                {/* Tab 1: Overview & Bio */}
                <TabsContent value="overview" className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Personal Identification */}
                        <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-xs space-y-4">
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
                                <UserPlus className="h-4 w-4 text-sky-600" />
                                <span>Personal Demographics</span>
                            </h3>

                            <div className="grid grid-cols-2 gap-4 text-xs">
                                <div>
                                    <span className="text-slate-400 block font-medium">Gender</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 capitalize mt-0.5 block">
                                        {student.gender || "—"}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block font-medium">Date of Birth</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5 block">
                                        {formatDate(student.date_of_birth)}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block font-medium">Mother Tongue</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5 block">
                                        {student.mother_tongue || "—"}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block font-medium">Religion</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5 block">
                                        {student.religion || "—"}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block font-medium">Social Category</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5 block">
                                        {student.social_category || student.caste_category || "General"}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block font-medium">Aadhaar (Last 4)</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 font-mono mt-0.5 block">
                                        {student.aadhaar_last_4 ? `•••• •••• ${student.aadhaar_last_4}` : "—"}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Government & Education Identifiers */}
                        <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-xs space-y-4">
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
                                <Shield className="h-4 w-4 text-indigo-600" />
                                <span>Academic &amp; Official Identifiers</span>
                            </h3>

                            <div className="grid grid-cols-2 gap-4 text-xs">
                                <div>
                                    <span className="text-slate-400 block font-medium">Enrollment ID</span>
                                    <span className="font-bold text-sky-600 font-mono mt-0.5 block">
                                        {student.enrollment_id}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block font-medium">Admission Date</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5 block">
                                        {formatDate(student.admission_date)}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block font-medium">PEN (Permanent Edu No.)</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 font-mono mt-0.5 block">
                                        {student.pen || "Not Allocated"}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block font-medium">APAAR ID</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 font-mono mt-0.5 block">
                                        {student.apaar_id || "Not Linked"}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block font-medium">RTE Free Quota</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5 block">
                                        {student.is_rte ? "Yes (RTE Entitled)" : "No"}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block font-medium">Academic Year</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5 block">
                                        {student.academic_year || "Current Session"}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Contact & Residential Address */}
                        <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-xs space-y-4">
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
                                <MapPin className="h-4 w-4 text-emerald-600" />
                                <span>Contact &amp; Location Details</span>
                            </h3>

                            <div className="space-y-3 text-xs">
                                <div>
                                    <span className="text-slate-400 block font-medium">Primary Contact Phone</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 font-mono mt-0.5 block">
                                        {student.phone ? (
                                            <a href={`tel:${student.phone}`} className="text-sky-600 hover:underline">
                                                {student.phone}
                                            </a>
                                        ) : "—"}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block font-medium">Student / Guardian Email</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5 block">
                                        {student.email || "No email linked"}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block font-medium">Residential Address</span>
                                    <p className="font-medium text-slate-700 dark:text-slate-300 mt-0.5 whitespace-pre-wrap leading-relaxed">
                                        {student.address || "Address not specified"}
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Previous Academic History */}
                        <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-5 shadow-xs space-y-4">
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2 border-b border-slate-100 dark:border-slate-800 pb-3">
                                <BookOpen className="h-4 w-4 text-amber-600" />
                                <span>Previous Academic History</span>
                            </h3>

                            <div className="space-y-3 text-xs">
                                <div>
                                    <span className="text-slate-400 block font-medium">Previous School Attended</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5 block">
                                        {student.previous_school || "First-time admission (No prior school)"}
                                    </span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block font-medium">Last Grade / Level Passed</span>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200 mt-0.5 block">
                                        {student.last_grade_passed || "—"}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                </TabsContent>

                {/* Tab 2: Parents & Family */}
                <TabsContent value="parents" className="space-y-6">
                    <StudentParentsCard studentId={id} studentName={fullName} />
                </TabsContent>

                {/* Tab 3: Attendance Pulse */}
                <TabsContent value="attendance" className="space-y-6">
                    {attendance ? (
                        <>
                            {/* Attendance Pulse Stats */}
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

                            {/* Attendance Records Table */}
                            <TableShell>
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead className="pl-5">Date</TableHead>
                                            <TableHead className="text-center">Status</TableHead>
                                            <TableHead className="pr-5">Teacher Remarks</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {attendance.records && attendance.records.length > 0 ? (
                                            attendance.records.map((r, i) => {
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
                                                    No attendance logs recorded for this student yet.
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

                {/* Tab 4: Fee Ledger & Dues */}
                <TabsContent value="fees" className="space-y-6">
                    {feesData ? (
                        <>
                            {/* KPI Metrics */}
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-4 shadow-xs">
                                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
                                        Total Fee Assigned
                                    </span>
                                    <div className="text-2xl font-bold font-mono text-slate-900 dark:text-white mt-1">
                                        {formatIndianCurrency(totalDue)}
                                    </div>
                                </div>
                                <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-4 shadow-xs">
                                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
                                        Total Amount Paid
                                    </span>
                                    <div className="text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400 mt-1">
                                        {formatIndianCurrency(totalPaid)}
                                    </div>
                                </div>
                                <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-2xl p-4 shadow-xs">
                                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
                                        Outstanding Balance
                                    </span>
                                    <div className={`text-2xl font-bold font-mono mt-1 ${parseFloat(feesData.total_outstanding) > 0 ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"}`}>
                                        {formatIndianCurrency(feesData.total_outstanding)}
                                    </div>
                                </div>
                            </div>

                            {/* Assigned Fee Schedule Table */}
                            <div className="space-y-3">
                                <div className="flex items-center justify-between">
                                    <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                                        Assigned Fee Schedule &amp; Installments
                                    </h3>
                                    {canCollectFee && parseFloat(feesData.total_outstanding) > 0 && (
                                        <Button
                                            size="sm"
                                            onClick={() => router.push(`/dashboard/fees/collect?search=${student.enrollment_id}`)}
                                            className="h-8 text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg"
                                        >
                                            <CreditCard className="h-3.5 w-3.5 mr-1.5" />
                                            Pay Dues Now
                                        </Button>
                                    )}
                                </div>

                                <TableShell>
                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead className="pl-5">Fee Head &amp; Schedule</TableHead>
                                                <TableHead className="text-right">Amount Due</TableHead>
                                                <TableHead className="text-right">Paid</TableHead>
                                                <TableHead className="text-right">Outstanding</TableHead>
                                                <TableHead className="text-center pr-5">Status</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {feesData.fees.length > 0 ? (
                                                feesData.fees.map((fee) => {
                                                    const outstanding = parseFloat(fee.outstanding_balance);
                                                    return (
                                                        <TableRow key={fee.id}>
                                                            <TableCell className="pl-5">
                                                                <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                                    {fee.fee_head_name}
                                                                </div>
                                                                <div className="text-[10px] text-slate-400 flex items-center gap-1 mt-0.5">
                                                                    <Calendar className="w-3 h-3 text-slate-400" />
                                                                    <span>Due: {formatDate(fee.due_date)}</span>
                                                                </div>
                                                            </TableCell>
                                                            <TableCell className="text-right font-mono tabular-nums text-xs">
                                                                {formatIndianCurrency(fee.amount_due)}
                                                            </TableCell>
                                                            <TableCell className="text-right font-mono tabular-nums text-xs text-emerald-600 dark:text-emerald-400 font-semibold">
                                                                {formatIndianCurrency(fee.amount_paid)}
                                                            </TableCell>
                                                            <TableCell className="text-right font-mono tabular-nums text-xs font-bold">
                                                                {outstanding > 0 ? (
                                                                    <span className="text-rose-600 dark:text-rose-400">
                                                                        {formatIndianCurrency(fee.outstanding_balance)}
                                                                    </span>
                                                                ) : (
                                                                    <span className="text-emerald-600 dark:text-emerald-400">
                                                                        Paid
                                                                    </span>
                                                                )}
                                                            </TableCell>
                                                            <TableCell className="text-center pr-5">
                                                                <Badge
                                                                    className={`text-[10px] font-semibold ${
                                                                        fee.status === "active"
                                                                            ? outstanding === 0
                                                                                ? "bg-emerald-50 text-emerald-700 border-emerald-300/80"
                                                                                : "bg-amber-50 text-amber-700 border-amber-300/80"
                                                                            : "bg-rose-50 text-rose-700 border-rose-300/80"
                                                                    }`}
                                                                >
                                                                    {fee.status === "active" ? (outstanding === 0 ? "Cleared" : "Pending") : "Cancelled"}
                                                                </Badge>
                                                            </TableCell>
                                                        </TableRow>
                                                    );
                                                })
                                            ) : (
                                                <TableRow>
                                                    <TableCell colSpan={5} className="py-10 text-center text-xs text-slate-400">
                                                        No fees assigned to this student yet.
                                                    </TableCell>
                                                </TableRow>
                                            )}
                                        </TableBody>
                                    </Table>
                                </TableShell>
                            </div>

                            {/* Official Collection Receipts */}
                            {payments.length > 0 && (
                                <div className="space-y-3 pt-2">
                                    <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                                        Payment Receipts History ({payments.length})
                                    </h3>
                                    <TableShell>
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead className="pl-5">Receipt #</TableHead>
                                                    <TableHead>Date</TableHead>
                                                    <TableHead className="text-right">Amount Paid</TableHead>
                                                    <TableHead>Channel</TableHead>
                                                    <TableHead className="text-right pr-5">Receipt</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {payments.map((p) => (
                                                    <TableRow key={p.id}>
                                                        <TableCell className="pl-5">
                                                            <code className="text-xs font-mono font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-200 dark:border-emerald-800">
                                                                {p.receipt_number}
                                                            </code>
                                                        </TableCell>
                                                        <TableCell className="text-xs text-slate-600 dark:text-slate-400">
                                                            {formatDate(p.created_at)}
                                                        </TableCell>
                                                        <TableCell className="text-right text-xs font-mono tabular-nums font-bold text-slate-900 dark:text-white">
                                                            {formatIndianCurrency(p.amount)}
                                                        </TableCell>
                                                        <TableCell className="text-xs capitalize text-slate-600 dark:text-slate-300">
                                                            {p.method.replace("_", " ")}
                                                        </TableCell>
                                                        <TableCell className="text-right pr-5">
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                onClick={() => setReceiptIdToPrint(p.id)}
                                                                className="h-7 text-xs font-semibold px-2 rounded-lg gap-1"
                                                            >
                                                                <Printer className="h-3 w-3" />
                                                                <span>View Receipt</span>
                                                            </Button>
                                                        </TableCell>
                                                    </TableRow>
                                                ))}
                                            </TableBody>
                                        </Table>
                                    </TableShell>
                                </div>
                            )}
                        </>
                    ) : (
                        <div className="p-12 text-center text-xs text-slate-400 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800">
                            Loading fee records...
                        </div>
                    )}
                </TabsContent>
            </Tabs>

            {/* Official Receipt Dialog */}
            <ReceiptModal
                isOpen={Boolean(receiptIdToPrint)}
                onClose={() => setReceiptIdToPrint(null)}
                paymentId={receiptIdToPrint}
            />
        </div>
    );
}
