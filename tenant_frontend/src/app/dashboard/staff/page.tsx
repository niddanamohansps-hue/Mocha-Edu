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
    LoaderCircle,
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
import { Badge } from "@/components/ui/badge";
import { Pagination } from "@/components/ui/pagination";
import { useRouter } from "next/navigation";
import Unauthorized from "@/components/Unauthorized";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";

const PAGE_SIZE = 20;

export default function StaffPage() {
    const { can, isOwner } = usePermissions();
    const [page, setPage] = useState(1);
    const { data, isLoading } = useStaffMembers({ page, pageSize: PAGE_SIZE });
    const staff = data?.results;
    const { mutate: deleteStaff } = useDeleteStaff();
    const [staffToDelete, setStaffToDelete] = useState<string | null>(null);
    const router = useRouter();

    const canView = isOwner || can("view_staff");
    const canEdit = isOwner || can("change_staff");
    const canDelete = isOwner || can("delete_staff");
    const canManagePortal = isOwner || can("activate_staff_portal");

    if (!canView) {
        return <Unauthorized />;
    }

    if (isLoading) {
        return (
            <div className="flex h-[60vh] items-center justify-center">
                <LoaderCircle className="h-12 w-12 animate-spin text-sky-600" />
            </div>
        );
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
                    <Input
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

            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-sm">
                <div className="overflow-x-auto">
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
                                                <Badge variant="outline" className="text-emerald-600 bg-emerald-50 border-emerald-200">
                                                    Active
                                                </Badge>
                                            ) : (
                                                <Badge variant="outline" className="text-slate-500 bg-slate-50">
                                                    No Access
                                                </Badge>
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
                                        <div className="flex flex-col items-center justify-center text-slate-400 py-10">
                                            <Briefcase className="h-12 w-12 mb-2 opacity-20" />
                                            <p className="font-medium">No staff members found.</p>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </div>
                {data && (
                    <Pagination
                        page={page}
                        pageSize={PAGE_SIZE}
                        count={data.count}
                        onPageChange={setPage}
                        className="border-t border-slate-200 dark:border-slate-800"
                    />
                )}
            </div>

            <AlertDialog open={!!staffToDelete} onOpenChange={(open) => !open && setStaffToDelete(null)}>
                <AlertDialogContent className="rounded-3xl">
                    <AlertDialogHeader>
                        <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This action cannot be undone. This will permanently delete the staff member profile and their employment records from the system.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel className="rounded-xl h-11">Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={() => {
                                if (staffToDelete) {
                                    deleteStaff(staffToDelete);
                                    setStaffToDelete(null);
                                }
                            }}
                            className="bg-red-600 hover:bg-red-700 text-white rounded-xl h-11"
                        >
                            Delete Staff
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}
