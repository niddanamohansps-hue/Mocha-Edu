"use client";

import { useState } from "react";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import { useStudents, useDeleteStudent } from "@/hooks/useStudents";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import {
    Plus,
    Search,
    UserPlus,
    Upload,
    MoreHorizontal,
    Filter,
    GraduationCap,
    Lock,
    Pencil,
    Trash2,
    Users,
    Download
} from "lucide-react";
import { Input } from "@/components/ui/input";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Pagination } from "@/components/ui/pagination";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import Unauthorized from "@/components/Unauthorized";
import { cn } from "@/lib/utils";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { TableShell } from "@/components/common/table/TableShell";

const PAGE_SIZE = 20;

export default function StudentsPage() {
    const { can, isOwner } = usePermissions();
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const pageParam = Number(searchParams.get("page"));
    const page = Number.isInteger(pageParam) && pageParam >= 1 ? pageParam : 1;
    const { data, isLoading, isError, refetch } = useStudents({ page, pageSize: PAGE_SIZE });
    const students = data?.results;
    const { mutate: deleteStudent } = useDeleteStudent();
    const [studentToDelete, setStudentToDelete] = useState<string | null>(null);
    const [exportingUdise, setExportingUdise] = useState(false);
    const [exportingCbseLoc, setExportingCbseLoc] = useState(false);

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
        } catch (e) {
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
        } catch (e) {
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
        const query = params.toString();
        router.replace(query ? `${pathname}?${query}` : pathname);
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

    return (
        <div className="space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                        Student Directory
                    </h1>
                    <p className="text-slate-500 dark:text-slate-400 mt-2 text-lg">
                        View and manage all students enrolled in your institution
                    </p>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                    {canView && (
                        <>
                            <Button
                                onClick={handleExportUdise}
                                variant="outline"
                                size="xl"
                                disabled={exportingUdise}
                            >
                                <Download className="h-4 w-4 mr-2 text-emerald-600" />
                                {exportingUdise ? "Exporting..." : "UDISE+ Export"}
                            </Button>
                            <Button
                                onClick={handleExportCbseLoc}
                                variant="outline"
                                size="xl"
                                disabled={exportingCbseLoc}
                            >
                                <Download className="h-4 w-4 mr-2 text-indigo-600" />
                                {exportingCbseLoc ? "Exporting..." : "CBSE LOC"}
                            </Button>
                        </>
                    )}
                    {(isOwner || can("view_family")) && (
                        <Button
                            onClick={() => router.push("/dashboard/students/parents")}
                            variant="outline"
                            size="xl"
                        >
                            <Users className="h-4 w-4 mr-2" />
                            Parents Directory
                        </Button>
                    )}
                    {(isOwner || can("add_student")) && (
                        <>
                            <Button
                                onClick={() => router.push("/dashboard/portal-access/students")}
                                variant="outline"
                                size="xl"
                            >
                                <Lock className="h-4 w-4 mr-2" />
                                Portal Activation
                            </Button>
                            <Button
                                onClick={() => router.push("/dashboard/students/admissions")}
                                size="xl"
                            >
                                <UserPlus className="h-4 w-4 mr-2" />
                                New Admission
                            </Button>
                        </>
                    )}
                </div>
            </div>

            {/* Stats Summary could go here */}

            {/* Filter Bar */}
            <div className="flex flex-col md:flex-row gap-4 items-center justify-between p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm">
                <div className="relative flex-1 w-full max-w-md">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input aria-label="Search students by name or ID..."
                        placeholder="Search students by name or ID..."
                        className="pl-10 h-10 rounded-xl border-slate-100 dark:border-slate-800 focus:border-sky-500"
                    />
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="lg">
                        <Filter className="h-4 w-4 mr-2" />
                        Filters
                    </Button>
                </div>
            </div>

            <TableShell
                footer={
                    data && (
                        <Pagination
                            page={page}
                            pageSize={PAGE_SIZE}
                            count={data.count}
                            onPageChange={handlePageChange}
                            className="border-t border-slate-200 dark:border-slate-800"
                        />
                    )
                }
            >
                <Table>
                    <TableHeader className="bg-slate-50 dark:bg-slate-800/50">
                        <TableRow>
                            <TableHead className="py-4 pl-6">Student Name</TableHead>
                            <TableHead>Enrollment ID / PEN</TableHead>
                            <TableHead>Level / Grade</TableHead>
                            <TableHead>Section</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead>Account</TableHead>
                            <TableHead className="text-right pr-6">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {students && students.length > 0 ? (
                            students.map((student: any) => (
                                <TableRow key={student.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/50 transition-colors">
                                    <TableCell className="py-4 pl-6">
                                        <div className="flex items-center gap-3">
                                            <div className="h-10 w-10 rounded-full bg-sky-100 dark:bg-sky-900/40 text-sky-600 flex items-center justify-center font-bold text-sm shrink-0">
                                                {student.full_name[0]}
                                            </div>
                                            <div>
                                                <div className="flex items-center gap-2">
                                                    <span className="font-semibold">{student.full_name}</span>
                                                    {student.is_rte && (
                                                        <Badge variant="outline" className="border-amber-500 text-amber-600 dark:text-amber-400 text-[10px] px-1 py-0">
                                                            RTE 25%
                                                        </Badge>
                                                    )}
                                                    {student.caste_category && student.caste_category !== "GEN" && (
                                                        <Badge variant="secondary" className="text-[10px] px-1 py-0">
                                                            {student.caste_category}
                                                        </Badge>
                                                    )}
                                                </div>
                                                {student.apaar_id && (
                                                    <p className="text-[11px] text-slate-400 font-mono">APAAR: {student.apaar_id}</p>
                                                )}
                                            </div>
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <code className="text-xs font-semibold">
                                            {student.enrollment_id}
                                        </code>
                                        {student.pen && (
                                            <p className="text-[11px] text-slate-500 font-mono">PEN: {student.pen}</p>
                                        )}
                                    </TableCell>
                                    <TableCell className="font-medium text-sky-600">{student.level}</TableCell>
                                    <TableCell>{student.section || 'Unassigned'}</TableCell>
                                    <TableCell className="capitalize">
                                        {student.status}
                                    </TableCell>
                                    <TableCell>
                                        {student.has_account ? (
                                            <>
                                                Activated
                                            </>
                                        ) : (
                                            <>
                                                Offline
                                            </>
                                        )}
                                    </TableCell>
                                    <TableCell className="text-right pr-6">
                                        <DropdownMenu>
                                            <DropdownMenuTrigger asChild>
                                                <Button variant="ghost" size="icon" className="h-8 w-8 rounded-lg">
                                                    <MoreHorizontal className="h-4 w-4" />
                                                </Button>
                                            </DropdownMenuTrigger>
                                            <DropdownMenuContent align="end" className="w-48 p-2 rounded-xl">
                                                {canEdit && (
                                                    <DropdownMenuItem
                                                        onClick={() => router.push(`/dashboard/students/edit/${student.id}`)}
                                                        className="rounded-lg gap-2 cursor-pointer focus:bg-sky-50 focus:text-sky-600 dark:focus:bg-sky-900/20 dark:focus:text-sky-400"
                                                    >
                                                        <Pencil className="h-4 w-4" />
                                                        Edit
                                                    </DropdownMenuItem>
                                                )}
                                                {canDelete && (
                                                    <DropdownMenuItem
                                                        onClick={() => setStudentToDelete(student.id)}
                                                        className="rounded-lg gap-2 cursor-pointer text-red-600 focus:bg-red-50 focus:text-red-600 dark:focus:bg-red-900/20"
                                                    >
                                                        <Trash2 className="h-4 w-4" />
                                                        Delete
                                                    </DropdownMenuItem>
                                                )}
                                            </DropdownMenuContent>
                                        </DropdownMenu>
                                    </TableCell>
                                </TableRow>
                            ))
                        ) : (
                            <TableRow>
                                <TableCell colSpan={7} className="h-48 text-center">
                                    <EmptyState
                                        icon={<GraduationCap className="h-12 w-12 mb-2 opacity-20" />}
                                        title="No students found."
                                    />
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableShell>

            <ConfirmationDialog
                open={!!studentToDelete}
                onOpenChange={(open) => !open && setStudentToDelete(null)}
                title="Are you sure?"
                description="This action cannot be undone. This will permanently delete the student profile and their academic records from the system."
                confirmLabel="Delete Student"
                onConfirm={() => {
                    if (studentToDelete) {
                        deleteStudent(studentToDelete);
                        setStudentToDelete(null);
                    }
                }}
                contentClassName="rounded-3xl"
                cancelClassName="rounded-xl h-11"
                confirmClassName="rounded-xl h-11"
            />
        </div>
    );
}
