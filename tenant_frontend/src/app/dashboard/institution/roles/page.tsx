"use client";

import { useRoles, useDeleteRole } from "@/hooks/useRoles";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { Can } from "@/providers/PermissionProvider";
import Unauthorized from "@/components/Unauthorized";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { EmptyState } from "@/components/feedback/EmptyState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { TableShell } from "@/components/common/table/TableShell";
import {
    Plus,
    MoreHorizontal,
    Pencil,
    Trash2,
    Search,
    ShieldCheck,
    Users
} from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { Card, CardContent } from "@/components/ui/card";

export default function RolesPage() {
    const { can, isOwner: isUserOwner } = usePermissions();
    const { data: roles, isLoading: isRolesLoading } = useRoles();
    const { mutate: deleteRole } = useDeleteRole();
    const router = useRouter();

    const [searchQuery, setSearchQuery] = useState("");
    const [roleToDelete, setRoleToDelete] = useState<string | null>(null);

    const canView = isUserOwner || can("view_role");

    if (isRolesLoading) {
        return <LoadingState className="h-[60vh]" />;
    }

    if (!canView) {
        return <Unauthorized />;
    }

    const handleDelete = () => {
        if (roleToDelete) {
            deleteRole(roleToDelete);
            setRoleToDelete(null);
        }
    };

    const filteredRoles = roles?.filter((role) =>
        role.name.toLowerCase().includes(searchQuery.trim().toLowerCase())
    );

    return (
        <div className="space-y-6">
            {/* Header Section */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                        Roles & Permissions
                    </h1>
                    <p className="text-slate-500 dark:text-slate-400 mt-1">Manage access control and user roles for your institution</p>
                </div>

                <Can I="add_role">
                    <Button
                        onClick={() => router.push("/dashboard/institution/roles/new")}
                        size="xl"
                    >
                        <Plus className="h-5 w-5 mr-2" />
                        Create New Role
                    </Button>
                </Can>
            </div>

            {/* Controls Section */}
            <Card className="border-none shadow-sm dark:bg-slate-900/50">
                <CardContent className="px-4">
                    <div className="relative max-w-md">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                        <Input
                            placeholder="Search roles by name..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="pl-10 bg-slate-50 dark:bg-slate-800 border-transparent focus:border-sky-500 rounded-xl h-10"
                        />
                    </div>
                </CardContent>
            </Card>

            {/* Table Section */}
            <TableShell>
                <Table className="px-4">
                    <TableHeader className="bg-slate-100 dark:bg-slate-800">
                        <TableRow>
                            <TableHead className="w-[250px] font-bold text-slate-900 dark:text-white py-4 pl-6">Role Name</TableHead>
                            <TableHead className="min-w-[300px] font-bold text-slate-900 dark:text-white">Description</TableHead>
                            <TableHead className="w-[150px] font-bold text-slate-900 dark:text-white">Members</TableHead>
                            <TableHead className="w-[200px] font-bold text-slate-900 dark:text-white text-center">Permissions</TableHead>
                            <TableHead className="w-[150px] font-bold text-slate-900 dark:text-white">Created At</TableHead>
                            <TableHead className="w-[80px] text-right pr-6 font-bold text-slate-900 dark:text-white">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {filteredRoles && filteredRoles.length > 0 ? (
                            filteredRoles.map((role) => (
                                <TableRow key={role.id} className="group hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors">
                                    <TableCell className="py-4 pl-6">
                                        <div className="flex items-center gap-3">
                                            <div className="flex flex-col">
                                                <span className="font-semibold text-slate-900 dark:text-white">{role.name}</span>
                                            </div>
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <p className="text-slate-500 dark:text-slate-400 text-sm line-clamp-1">{role.description || "No description provided."}</p>
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex items-center gap-2 text-slate-600 dark:text-slate-300 font-medium">
                                            <Users className="h-4 w-4 text-slate-400" />
                                            {role.user_count}
                                        </div>
                                    </TableCell>
                                    <TableCell className="text-center">
                                        <Badge variant="outline" className="bg-slate-100 dark:bg-slate-800 border-none font-bold text-slate-700 dark:text-slate-300">
                                            {role.permissions?.length || 0} Permissions
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-slate-500 dark:text-slate-400 text-sm">
                                        {format(new Date(role.created_at), 'MMM dd, yyyy')}
                                    </TableCell>
                                    <TableCell className="text-right pr-6">
                                        <DropdownMenu>
                                            <DropdownMenuTrigger asChild>
                                                <Button variant="ghost" size="icon" className="h-8 w-8 rounded-md">
                                                    <MoreHorizontal className="h-4 w-4" />
                                                </Button>
                                            </DropdownMenuTrigger>
                                            <DropdownMenuContent align="end" className="w-48 p-2 rounded-xl">
                                                <Can I="change_role">
                                                    <DropdownMenuItem
                                                        onClick={() => router.push(`/dashboard/institution/roles/${role.id}/edit`)}
                                                        className="rounded-lg gap-2 cursor-pointer focus:bg-sky-50 focus:text-sky-600 dark:focus:bg-sky-900/20 dark:focus:text-sky-400"
                                                    >
                                                        <Pencil className="h-4 w-4" />
                                                        Edit
                                                    </DropdownMenuItem>
                                                </Can>
                                                <Can I="delete_role">
                                                    {!role.is_system_role && (
                                                        <DropdownMenuItem
                                                            onClick={() => setRoleToDelete(role.id)}
                                                            className="rounded-lg gap-2 cursor-pointer text-red-600 focus:bg-red-50 focus:text-red-600 dark:focus:bg-red-900/20"
                                                        >
                                                            <Trash2 className="h-4 w-4" />
                                                            Delete
                                                        </DropdownMenuItem>
                                                    )}
                                                </Can>
                                            </DropdownMenuContent>
                                        </DropdownMenu>
                                    </TableCell>
                                </TableRow>
                            ))
                        ) : (
                            <TableRow>
                                <TableCell colSpan={6} className="h-32 text-center">
                                    <EmptyState
                                        icon={<ShieldCheck className="h-10 w-10 mb-2 opacity-20" />}
                                        title={searchQuery.trim() ? "No roles match your search." : "No roles found."}
                                        className="text-slate-500 dark:text-slate-400"
                                    />
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableShell>

            {/* Delete Confirmation Dialog */}
            <ConfirmationDialog
                open={!!roleToDelete}
                onOpenChange={(open) => !open && setRoleToDelete(null)}
                icon={
                    <div className="h-12 w-12 bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 rounded-full flex items-center justify-center mb-4">
                        <Trash2 className="h-6 w-6" />
                    </div>
                }
                title={<span className="text-2xl font-bold">Delete Role?</span>}
                description={
                    <span className="text-slate-500 dark:text-slate-400 text-lg">
                        This action cannot be undone. This will permanently delete the role and remove it from all assigned users.
                    </span>
                }
                confirmLabel="Delete Now"
                onConfirm={handleDelete}
                contentClassName="rounded-2xl p-8 max-w-md"
                footerClassName="mt-8 gap-3"
                cancelClassName="rounded-xl h-11 border-slate-200"
                confirmClassName="font-bold h-11 px-8 rounded-xl"
            />
        </div>
    );
}
