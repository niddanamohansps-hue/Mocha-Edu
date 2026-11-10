"use client";

import { useState, useMemo, useEffect } from "react";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import { useStudents, useDeleteStudent, Student } from "@/hooks/useStudents";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import {
    Search,
    UserPlus,
    Filter,
    GraduationCap,
    Lock,
    Pencil,
    Trash2,
    Users,
    Download,
    CreditCard,
    MoreHorizontal,
    FileSpreadsheet,
    FileText,
    ChevronDown,
    X,
    ExternalLink,
    CheckCircle2,
    Clock,
    Shield,
    Eye,
    Printer,
} from "lucide-react";
import { StudentIDCardModal } from "@/components/dashboard/students/StudentIDCardModal";
import { Input } from "@/components/ui/input";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Pagination } from "@/components/ui/pagination";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import Unauthorized from "@/components/Unauthorized";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { TableShell } from "@/components/common/table/TableShell";
import { Avatar } from "@/components/ui/avatar";

const PAGE_SIZE = 20;

export default function StudentsPage() {
    const { can, isOwner } = usePermissions();
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();

    const pageParam = Number(searchParams.get("page"));
    const page = Number.isInteger(pageParam) && pageParam >= 1 ? pageParam : 1;

    // Filters state from URL
    const [searchQuery, setSearchQuery] = useState(searchParams.get("search") || "");
    const [debouncedSearch, setDebouncedSearch] = useState(searchQuery);
    const [statusFilter, setStatusFilter] = useState(searchParams.get("status") || "all");
    const [gradeFilter, setGradeFilter] = useState<string>("all");
    const [sectionFilter, setSectionFilter] = useState<string>("all");

    // Debounce search query
    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedSearch(searchQuery);
        }, 300);
        return () => clearTimeout(handler);
    }, [searchQuery]);

    // Update URL when search or status filter changes
    useEffect(() => {
        const params = new URLSearchParams(searchParams.toString());
        if (debouncedSearch) {
            params.set("search", debouncedSearch);
        } else {
            params.delete("search");
        }

        if (statusFilter !== "all") {
            params.set("status", statusFilter);
        } else {
            params.delete("status");
        }

        params.delete("page"); // Reset to page 1 on filter
        router.replace(`${pathname}?${params.toString()}`);
    }, [debouncedSearch, statusFilter]);

    const { data, isLoading, isError, refetch } = useStudents({
        page,
        pageSize: PAGE_SIZE,
        search: debouncedSearch,
        status: statusFilter !== "all" ? statusFilter : undefined,
    });

    const students = data?.results;
    const { mutate: deleteStudent } = useDeleteStudent();
    const [studentToDelete, setStudentToDelete] = useState<string | null>(null);
    const [idCardStudent, setIdCardStudent] = useState<any>(null);
    const [exportingUdise, setExportingUdise] = useState(false);
    const [exportingCbseLoc, setExportingCbseLoc] = useState(false);

    // Extract unique grades & sections from current student results for fast client-side narrowing
    const availableGrades = useMemo(() => {
        if (!students) return [];
        const set = new Set<string>();
        students.forEach((s: Student) => {
            if (s.level) set.add(s.level);
        });
        return Array.from(set).sort();
    }, [students]);

    const availableSections = useMemo(() => {
        if (!students) return [];
        const set = new Set<string>();
        students.forEach((s: Student) => {
            if (s.section && s.section !== "Unassigned") set.add(s.section);
        });
        return Array.from(set).sort();
    }, [students]);

    // Filter students by grade & section client-side
    const filteredStudents = useMemo(() => {
        if (!students) return [];
        return students.filter((s: Student) => {
            if (gradeFilter !== "all" && s.level !== gradeFilter) return false;
            if (sectionFilter !== "all" && s.section !== sectionFilter) return false;
            return true;
        });
    }, [students, gradeFilter, sectionFilter]);

    const handleExportUdise = async () => {
        try {
            setExportingUdise(true);
            const response = await axiosInstance.get("/students/export/udise/", { responseType: "blob" });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement("a");
            link.href = url;
            link.setAttribute("download", `udise_plus_sdms_${new Date().toISOString().split("T")[0]}.csv`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            toast.success("UDISE+ SDMS export downloaded successfully");
        } catch {
            toast.error("Failed to export UDISE+ data");
        } finally {
            setExportingUdise(false);
        }
    };

    const handleExportCbseLoc = async () => {
        try {
            setExportingCbseLoc(true);
            const response = await axiosInstance.get("/students/export/cbse-loc/", { responseType: "blob" });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement("a");
            link.href = url;
            link.setAttribute("download", `cbse_loc_candidates_${new Date().toISOString().split("T")[0]}.csv`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            toast.success("CBSE LOC candidate export downloaded successfully");
        } catch {
            toast.error("Failed to export CBSE LOC data");
        } finally {
            setExportingCbseLoc(false);
        }
    };

    const handlePageChange = (nextPage: number) => {
        const params = new URLSearchParams(searchParams.toString());
        if (nextPage <= 1) {
            params.delete("page");
        } else {
            params.set("page", String(nextPage));
        }
        router.replace(`${pathname}?${params.toString()}`);
    };

    const canView = isOwner || can("view_student");
    const canEdit = isOwner || can("change_student");
    const canDelete = isOwner || can("delete_student");

    if (!canView) {
        return <Unauthorized />;
    }

    if (isLoading) {
        return <LoadingState className="h-[60vh]" />;
    }

    if (isError) {
        return <ErrorState onRetry={refetch} className="m-6" />;
    }

    const totalCount = data?.count ?? 0;

    return (
        <div className="space-y-5 max-w-7xl mx-auto pb-12 animate-in fade-in duration-500">
            {/* 1. Senior Executive Header (Clean 1-Row Action Hierarchy) */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white">
                        Student Directory
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Manage all <span className="font-semibold text-slate-700 dark:text-slate-300">{totalCount} enrolled students</span>, admission profiles, and government compliance rosters
                    </p>
                </div>

                {/* Single Aligned Action Strip */}
                <div className="flex flex-wrap items-center gap-2.5">
                    {/* Compliance Exports Dropdown */}
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Button
                                variant="outline"
                                size="sm"
                                className="gap-1.5"
                            >
                                <Download className="h-3.5 w-3.5 text-slate-500" />
                                <span>Export Data</span>
                                <ChevronDown className="h-3 w-3 text-slate-400" />
                            </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-56 p-1.5 rounded-xl shadow-lg">
                            <DropdownMenuLabel className="text-[11px] font-semibold text-slate-400 px-2 py-1">
                                National & Board Exports
                            </DropdownMenuLabel>
                            <DropdownMenuItem
                                onClick={handleExportUdise}
                                disabled={exportingUdise}
                                className="flex items-center gap-2 p-2 rounded-lg cursor-pointer text-xs"
                            >
                                <FileSpreadsheet className="h-4 w-4 text-emerald-600" />
                                <div className="flex-1">
                                    <p className="font-medium text-slate-800 dark:text-slate-200">UDISE+ SDMS Export</p>
                                    <p className="text-[10px] text-slate-400">Ministry of Education (.csv)</p>
                                </div>
                            </DropdownMenuItem>
                            <DropdownMenuItem
                                onClick={handleExportCbseLoc}
                                disabled={exportingCbseLoc}
                                className="flex items-center gap-2 p-2 rounded-lg cursor-pointer text-xs"
                            >
                                <FileText className="h-4 w-4 text-indigo-600" />
                                <div className="flex-1">
                                    <p className="font-medium text-slate-800 dark:text-slate-200">CBSE LOC Candidates</p>
                                    <p className="text-[10px] text-slate-400">Class 10 & 12 Roster (.csv)</p>
                                </div>
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>

                    {/* Parents Directory Link */}
                    {(isOwner || can("view_family")) && (
                        <Button
                            onClick={() => router.push("/dashboard/students/parents")}
                            variant="outline"
                            size="sm"
                            className="gap-1.5"
                        >
                            <Users className="h-3.5 w-3.5 text-slate-500" />
                            <span>Parents Directory</span>
                        </Button>
                    )}

                    {/* Secondary Operations Dropdown */}
                    {(isOwner || can("add_student")) && (
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="px-2.5"
                                    title="More Options"
                                >
                                    <MoreHorizontal className="h-4 w-4" />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-52 p-1.5 rounded-xl shadow-lg">
                                <DropdownMenuItem
                                    onClick={() => router.push("/dashboard/portal-access/students")}
                                    className="flex items-center gap-2 p-2 rounded-lg cursor-pointer text-xs"
                                >
                                    <Lock className="h-4 w-4 text-slate-500" />
                                    <span>Portal Access Activation</span>
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                    onClick={() => router.push("/dashboard/students/promotions")}
                                    className="flex items-center gap-2 p-2 rounded-lg cursor-pointer text-xs"
                                >
                                    <GraduationCap className="h-4 w-4 text-slate-500" />
                                    <span>Promotion & Transfer Hub</span>
                                </DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>
                    )}

                    {/* Primary Hero CTA Button */}
                    {(isOwner || can("add_student")) && (
                        <Button
                            onClick={() => router.push("/dashboard/students/admissions")}
                            size="sm"
                            className="gap-1.5"
                        >
                            <UserPlus className="h-3.5 w-3.5 stroke-[2.5]" />
                            <span>New Admission</span>
                        </Button>
                    )}
                </div>
            </div>

            {/* 2. Quick Segmentation Tabs */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
                {[
                    { id: "all", label: "All Students", count: totalCount },
                    { id: "active", label: "Active", count: totalCount },
                    { id: "inactive", label: "Inactive / Transferred" },
                ].map((tab) => {
                    const isActive = statusFilter === tab.id;
                    return (
                        <button
                            key={tab.id}
                            onClick={() => setStatusFilter(tab.id)}
                            className={`px-3 py-1.5 rounded-lg font-semibold transition cursor-pointer flex items-center gap-1.5 ${
                                isActive
                                    ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-2xs"
                                    : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200/80 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800"
                            }`}
                        >
                            <span>{tab.label}</span>
                            {tab.count !== undefined && (
                                <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                                    isActive ? "bg-white/20 text-white dark:bg-slate-900/20 dark:text-slate-900" : "bg-slate-100 dark:bg-slate-800 text-slate-500"
                                }`}>
                                    {tab.count}
                                </span>
                            )}
                        </button>
                    );
                })}
            </div>

            {/* 3. Search, Filter & Quick Narrowing Bar */}
            <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex flex-col md:flex-row gap-2.5 items-center justify-between">
                {/* Search Input */}
                <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                        aria-label="Search students by name or ID..."
                        placeholder="Search student by name, enrollment ID (e.g. SV/2025/0012) or PEN..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="pl-9 pr-8 h-9 text-xs rounded-lg border-slate-200 dark:border-slate-800 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20 bg-slate-50/50 dark:bg-slate-950/50"
                    />
                    {searchQuery && (
                        <button
                            onClick={() => setSearchQuery("")}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-400 hover:text-slate-600"
                        >
                            <X className="h-3.5 w-3.5" />
                        </button>
                    )}
                </div>

                {/* Instant Class & Section Dropdowns */}
                <div className="flex items-center gap-2 w-full md:w-auto shrink-0">
                    {/* Grade Selector */}
                    {availableGrades.length > 0 && (
                        <select
                            value={gradeFilter}
                            onChange={(e) => setGradeFilter(e.target.value)}
                            className="h-9 px-2.5 py-1 text-xs font-medium rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 focus:outline-hidden focus:ring-1 focus:ring-sky-500"
                        >
                            <option value="all">All Grades ({availableGrades.length})</option>
                            {availableGrades.map((g) => (
                                <option key={g} value={g}>{g}</option>
                            ))}
                        </select>
                    )}

                    {/* Section Selector */}
                    {availableSections.length > 0 && (
                        <select
                            value={sectionFilter}
                            onChange={(e) => setSectionFilter(e.target.value)}
                            className="h-9 px-2.5 py-1 text-xs font-medium rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 focus:outline-hidden focus:ring-1 focus:ring-sky-500"
                        >
                            <option value="all">All Sections</option>
                            {availableSections.map((s) => (
                                <option key={s} value={s}>Sec {s}</option>
                            ))}
                        </select>
                    )}

                    {/* Clear Filters Indicator */}
                    {(gradeFilter !== "all" || sectionFilter !== "all" || searchQuery) && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                                setGradeFilter("all");
                                setSectionFilter("all");
                                setSearchQuery("");
                            }}
                            className="h-9 px-2 text-xs text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40"
                        >
                            Reset
                        </Button>
                    )}
                </div>
            </div>

            {/* 4. Enterprise Student Table */}
            <TableShell
                footer={
                    data && totalCount > 0 && (
                        <Pagination
                            page={page}
                            pageSize={PAGE_SIZE}
                            count={data.count}
                            onPageChange={handlePageChange}
                        />
                    )
                }
            >
                <Table>
                    <TableHeader>
                        <TableRow className="hover:bg-transparent">
                            <TableHead className="pl-5">Student Name</TableHead>
                            <TableHead>Enrollment / PEN</TableHead>
                            <TableHead>Academic Class & Section</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead>Portal Access</TableHead>
                            <TableHead className="text-right pr-5">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {filteredStudents && filteredStudents.length > 0 ? (
                            filteredStudents.map((student: any) => {
                                return (
                                    <TableRow
                                        key={student.id}
                                        className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors border-b border-slate-100 dark:border-slate-800/70"
                                    >
                                        {/* Student Name & Badges */}
                                        <TableCell className="py-3 pl-5">
                                            <div className="flex items-center gap-3">
                                                {/* Colorful Deterministic Avatar */}
                                                <Avatar name={student.full_name} src={student.photo} size="md" />
                                                <div className="min-w-0">
                                                    <div className="flex items-center gap-1.5 flex-wrap">
                                                        <span
                                                            onClick={() => router.push(`/dashboard/students/${student.id}`)}
                                                            className="font-semibold text-xs text-slate-900 dark:text-slate-100 hover:text-sky-600 dark:hover:text-sky-400 cursor-pointer transition truncate"
                                                        >
                                                            {student.full_name}
                                                        </span>
                                                        {student.is_rte && (
                                                            <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300/80">
                                                                RTE 25%
                                                            </span>
                                                        )}
                                                        {student.caste_category && student.caste_category !== "GEN" && (
                                                            <span className="px-1.5 py-0.2 rounded text-[10px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                                                                {student.caste_category}
                                                            </span>
                                                        )}
                                                    </div>
                                                    {student.apaar_id && (
                                                        <p className="text-[10px] text-slate-400 font-mono mt-0.5">
                                                            APAAR: {student.apaar_id}
                                                        </p>
                                                    )}
                                                </div>
                                            </div>
                                        </TableCell>

                                        {/* Enrollment ID & PEN */}
                                        <TableCell>
                                            <code className="text-xs font-semibold font-mono text-slate-800 dark:text-slate-200 bg-slate-100/70 dark:bg-slate-800/70 px-1.5 py-0.5 rounded border border-slate-200/60 dark:border-slate-700">
                                                {student.enrollment_id}
                                            </code>
                                            {student.pen && (
                                                <p className="text-[10px] text-slate-400 font-mono mt-0.5">
                                                    PEN: {student.pen}
                                                </p>
                                            )}
                                        </TableCell>

                                        {/* Class & Section (Clean Combined Chip) */}
                                        <TableCell>
                                            <div className="inline-flex items-center gap-1.5">
                                                <span className="font-medium text-xs text-slate-800 dark:text-slate-200">
                                                    {student.level || "Unassigned"}
                                                </span>
                                                {student.section && student.section !== "Unassigned" ? (
                                                    <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-sky-50 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300 border border-sky-200 dark:border-sky-800">
                                                        Sec {student.section}
                                                    </span>
                                                ) : (
                                                    <span className="text-[10px] text-slate-400 italic">No Sec</span>
                                                )}
                                            </div>
                                        </TableCell>

                                        {/* Status Badge */}
                                        <TableCell>
                                            {student.status === "active" ? (
                                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-500/20">
                                                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                                                    Active
                                                </span>
                                            ) : (
                                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700 capitalize">
                                                    {student.status || "Inactive"}
                                                </span>
                                            )}
                                        </TableCell>

                                        {/* Portal Account Badge */}
                                        <TableCell>
                                            {student.has_account ? (
                                                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 dark:text-emerald-300">
                                                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                                                    <span>Activated</span>
                                                </span>
                                            ) : (
                                                <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-400">
                                                    <span className="h-1.5 w-1.5 rounded-full bg-slate-300 dark:bg-slate-600" />
                                                    <span>Offline</span>
                                                </span>
                                            )}
                                        </TableCell>

                                        {/* Row Actions */}
                                        <TableCell className="text-right pr-5">
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-8 w-8 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800"
                                                    >
                                                        <MoreHorizontal className="h-4 w-4 text-slate-500" />
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end" className="w-48 p-1.5 rounded-xl shadow-lg">
                                                    {/* View 360 Profile */}
                                                    <DropdownMenuItem
                                                        onClick={() => router.push(`/dashboard/students/${student.id}`)}
                                                        className="flex items-center gap-2 p-2 rounded-lg cursor-pointer text-xs focus:bg-sky-50 focus:text-sky-600 dark:focus:bg-sky-950/40"
                                                    >
                                                        <Eye className="h-4 w-4 text-sky-600" />
                                                        <span>View 360 Profile</span>
                                                    </DropdownMenuItem>

                                                    {/* Collect Fees Direct Shortcut */}
                                                    <DropdownMenuItem
                                                        onClick={() => router.push(`/dashboard/fees/collect?search=${student.enrollment_id}`)}
                                                        className="flex items-center gap-2 p-2 rounded-lg cursor-pointer text-xs focus:bg-emerald-50 focus:text-emerald-700 dark:focus:bg-emerald-950/40"
                                                    >
                                                        <CreditCard className="h-4 w-4 text-emerald-600" />
                                                        <span>Collect Fees</span>
                                                    </DropdownMenuItem>

                                                    {/* Print ID Card */}
                                                    <DropdownMenuItem
                                                        onClick={() => setIdCardStudent(student)}
                                                        className="flex items-center gap-2 p-2 rounded-lg cursor-pointer text-xs focus:bg-indigo-50 focus:text-indigo-600 dark:focus:bg-indigo-950/40"
                                                    >
                                                        <Printer className="h-4 w-4 text-indigo-600" />
                                                        <span>Print ID Card</span>
                                                    </DropdownMenuItem>

                                                    {canEdit && (
                                                        <DropdownMenuItem
                                                            onClick={() => router.push(`/dashboard/students/edit/${student.id}`)}
                                                            className="flex items-center gap-2 p-2 rounded-lg cursor-pointer text-xs focus:bg-sky-50 focus:text-sky-600 dark:focus:bg-sky-950/40"
                                                        >
                                                            <Pencil className="h-4 w-4 text-sky-600" />
                                                            <span>Edit Profile</span>
                                                        </DropdownMenuItem>
                                                    )}

                                                    {canDelete && (
                                                        <>
                                                            <DropdownMenuSeparator />
                                                            <DropdownMenuItem
                                                                onClick={() => setStudentToDelete(student.id)}
                                                                className="flex items-center gap-2 p-2 rounded-lg cursor-pointer text-xs text-rose-600 focus:bg-rose-50 dark:focus:bg-rose-950/40"
                                                            >
                                                                <Trash2 className="h-4 w-4" />
                                                                <span>Delete Student</span>
                                                            </DropdownMenuItem>
                                                        </>
                                                    )}
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        </TableCell>
                                    </TableRow>
                                );
                            })
                        ) : (
                            <TableRow>
                                <TableCell colSpan={6} className="h-48 text-center">
                                    <EmptyState
                                        icon={<GraduationCap className="h-10 w-10 mb-2 opacity-20 mx-auto" />}
                                        title="No matching students found."
                                        description="Try adjusting your search criteria or class filters."
                                    />
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableShell>

            {/* Delete Student Modal */}
            <ConfirmationDialog
                open={!!studentToDelete}
                onOpenChange={(open) => !open && setStudentToDelete(null)}
                title="Delete Student Record?"
                description="This will permanently delete the student profile and their academic enrollments. This action cannot be reversed."
                confirmLabel="Delete Student"
                onConfirm={() => {
                    if (studentToDelete) {
                        deleteStudent(studentToDelete);
                        setStudentToDelete(null);
                    }
                }}
                contentClassName="rounded-2xl"
                cancelClassName="rounded-lg h-9 text-xs"
                confirmClassName="rounded-lg h-9 text-xs bg-rose-600 hover:bg-rose-500"
            />

            {/* Student ID Card Modal */}
            <StudentIDCardModal
                isOpen={Boolean(idCardStudent)}
                onClose={() => setIdCardStudent(null)}
                student={idCardStudent}
            />
        </div>
    );
}
