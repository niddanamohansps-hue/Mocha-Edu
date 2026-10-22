"use client";

import { useState } from "react";
import { useStaffMembers, useDeleteStaff } from "@/hooks/useStaff";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import {
    Search,
    UserPlus,
    MoreHorizontal,
    Filter,
    Briefcase,
    Lock,
    Pencil,
    Trash2
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
import { Pagination } from "@/components/ui/pagination";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import Unauthorized from "@/components/Unauthorized";
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
import { StatusBadge } from "@/components/common/StatusBadge";
import { TableShell } from "@/components/common/table/TableShell";

const PAGE_SIZE = 20;

export default function StaffPage() {
    const { can, isOwner } = usePermissions();
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const pageParam = Number(searchParams.get("page"));
    const page = Number.isInteger(pageParam) && pageParam >= 1 ? pageParam : 1;
    const { data, isLoading, isError, refetch } = useStaffMembers({ page, pageSize: PAGE_SIZE });
    const staff = data?.results;
    const { mutate: deleteStaff } = useDeleteStaff();
    const [staffToDelete, setStaffToDelete] = useState<string | null>(null);

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

    const canView = isOwner || can("view_staff");
    const canEdit = isOwner || can("change_staff");
    const canDelete = isOwner || can("delete_staff");
    const canManagePortal = isOwner || can("activate_staff_portal");

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
                        Staff Directory
                    </h1>
                    <p className="text-slate-500 dark:text-slate-400 mt-2 text-lg">
                        View and manage all staff and instructors in your institution
                    </p>
                </div>

                <div className="flex items-center gap-3">
                    {(isOwner || canManagePortal) && (
                        <Button
                            onClick={() => router.push("/dashboard/portal-access/staff")}
                            variant="outline"
                            size="xl"
                        >
                            <Lock className="h-4 w-4 mr-2" />
                            Portal Activation
                        </Button>
                    )}
                    {(isOwner || can("add_staff")) && (
                        <Button
                            onClick={() => router.push("/dashboard/staff/onboarding")}
                            size="xl"
                        >
                            <UserPlus className="h-4 w-4 mr-2" />
                            Onboard Staff
                        </Button>
                    )}
                </div>
            </div>

            {/* Filter Bar */}
            <div className="flex flex-col md:flex-row gap-4 items-center justify-between p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm">
                <div className="relative flex-1 w-full max-w-md">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input aria-label="Search staff by name or ID..."
                        placeholder="Search staff by name or ID..."
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
                            <TableHead className="py-4 pl-6">Staff Name</TableHead>
                            <TableHead>Employee ID</TableHead>
                            <TableHead>Designation</TableHead>
                            <TableHead>Department</TableHead>
                            <TableHead>Joined</TableHead>
                            <TableHead>Account</TableHead>
                            <TableHead className="text-right pr-6">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {staff && staff.length > 0 ? (
                            staff.map((member: any) => (
                                <TableRow key={member.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/50 transition-colors">
                                    <TableCell className="py-4 pl-6">
                                        <div className="flex items-center gap-3">
                                            <div className="h-10 w-10 rounded-full bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 flex items-center justify-center font-bold text-sm">
                                                {member.profile_details.first_name[0]}
                                            </div>
                                            <div>
                                                <p className="font-semibold">{member.profile_details.first_name} {member.profile_details.last_name}</p>
                                                <p className="text-xs text-slate-500">{member.profile_details.phone}</p>
                                            </div>
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <code className="text-xs font-bold text-slate-600 dark:text-slate-400">
                                            {member.employee_id}
                                        </code>
                                    </TableCell>
                                    <TableCell className="font-medium text-slate-700 dark:text-slate-300">
                                        {member.designation}
                                    </TableCell>
                                    <TableCell>{member.department || 'General'}</TableCell>
                                    <TableCell>
                                        {member.joining_date || '-'}
                                    </TableCell>
                                    <TableCell>
                                        {member.profile_details.user_id ? (
                                            <StatusBadge
                                                label="Active"
                                                className="border border-emerald-200 text-emerald-600 bg-emerald-50"
                                            />
                                        ) : (
                                            <StatusBadge
                                                label="No Access"
                                                className="border text-slate-500 bg-slate-50"
                                            />
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
                                                        onClick={() => router.push(`/dashboard/staff/edit/${member.id}`)}
                                                        className="rounded-lg gap-2 cursor-pointer focus:bg-sky-50 focus:text-sky-600 dark:focus:bg-sky-900/20 dark:focus:text-sky-400"
                                                    >
                                                        <Pencil className="h-4 w-4" />
                                                        Edit
                                                    </DropdownMenuItem>
                                                )}
                                                {canDelete && (
                                                    <DropdownMenuItem
                                                        onClick={() => setStaffToDelete(member.id)}
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
                                        icon={<Briefcase className="h-12 w-12 mb-2 opacity-20" />}
                                        title="No staff members found."
                                    />
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableShell>

            <ConfirmationDialog
                open={!!staffToDelete}
                onOpenChange={(open) => !open && setStaffToDelete(null)}
                title="Are you sure?"
                description="This action cannot be undone. This will permanently delete the staff member profile and their employment records from the system."
                confirmLabel="Delete Staff"
                onConfirm={() => {
                    if (staffToDelete) {
                        deleteStaff(staffToDelete);
                        setStaffToDelete(null);
                    }
                }}
                contentClassName="rounded-3xl"
                cancelClassName="rounded-xl h-11"
                confirmClassName="rounded-xl h-11"
            />
        </div>
    );
}
