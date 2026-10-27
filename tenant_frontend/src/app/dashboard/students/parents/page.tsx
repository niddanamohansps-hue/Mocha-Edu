"use client";

import { useState } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import {
    useParents,
    useDeleteParent,
} from "@/hooks/useFamilies";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Pagination } from "@/components/ui/pagination";
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
import {
    Users,
    UserPlus,
    Search,
    Lock,
    Eye,
    Pencil,
    Trash2,
    Link as LinkIcon,
    MoreHorizontal,
    Phone,
    Mail,
    UserCheck,
    Briefcase,
} from "lucide-react";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { TableShell } from "@/components/common/table/TableShell";
import { ParentFormDialog } from "@/components/dashboard/families/ParentFormDialog";
import { ParentDetailDialog } from "@/components/dashboard/families/ParentDetailDialog";
import { LinkChildDialog } from "@/components/dashboard/families/LinkChildDialog";
import type { Parent } from "@/types/Families";

const PAGE_SIZE = 20;

export default function ParentsPage() {
    const { can, isOwner } = usePermissions();
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();

    const pageParam = Number(searchParams.get("page"));
    const page = Number.isInteger(pageParam) && pageParam >= 1 ? pageParam : 1;

    const [searchInput, setSearchInput] = useState(searchParams.get("search") || "");
    const [appliedSearch, setAppliedSearch] = useState(searchParams.get("search") || "");

    const { data, isLoading, isError, refetch } = useParents({
        page,
        pageSize: PAGE_SIZE,
        search: appliedSearch,
    });
    const parents = data?.results || [];

    const { mutate: deleteParent, isPending: isDeleting } = useDeleteParent();

    // Dialog states
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [parentToEdit, setParentToEdit] = useState<Parent | null>(null);
    const [parentToView, setParentToView] = useState<Parent | null>(null);
    const [parentToLink, setParentToLink] = useState<Parent | null>(null);
    const [parentToDelete, setParentToDelete] = useState<Parent | null>(null);

    const canView = isOwner || can("view_family");
    const canAdd = isOwner || can("add_family");
    const canEdit = isOwner || can("change_family");
    const canDelete = isOwner || can("delete_family");

    if (!canView) {
        return <Unauthorized />;
    }

    const handleSearchSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        setAppliedSearch(searchInput.trim());
        const params = new URLSearchParams(searchParams.toString());
        if (searchInput.trim()) {
            params.set("search", searchInput.trim());
        } else {
            params.delete("search");
        }
        params.delete("page");
        const query = params.toString();
        router.replace(query ? `${pathname}?${query}` : pathname);
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

    if (isLoading && !data) {
        return <LoadingState className="h-[60vh]" />;
    }

    if (isError) {
        return <ErrorState onRetry={refetch} className="m-6" />;
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                        <Users className="h-8 w-8 text-sky-500" />
                        Parents & Guardians
                    </h1>
                    <p className="text-slate-500 dark:text-slate-400 mt-2 text-lg">
                        Manage family profiles, contact channels, portal logins, and student links.
                    </p>
                </div>

                <div className="flex items-center gap-3">
                    <Button
                        onClick={() => router.push("/dashboard/portal-access/parents")}
                        variant="outline"
                        size="xl"
                        className="rounded-2xl"
                    >
                        <Lock className="h-4 w-4 mr-2" />
                        Portal Activation
                    </Button>
                    {canAdd && (
                        <Button
                            onClick={() => setIsCreateOpen(true)}
                            size="xl"
                            className="rounded-2xl"
                        >
                            <UserPlus className="h-4 w-4 mr-2" />
                            Add Parent
                        </Button>
                    )}
                </div>
            </div>

            {/* Search Bar */}
            <form
                onSubmit={handleSearchSubmit}
                className="flex flex-col sm:flex-row gap-4 items-center justify-between p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-xs"
            >
                <div className="relative flex-1 w-full max-w-md">
                    <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                        placeholder="Search parents by name or phone..."
                        value={searchInput}
                        onChange={(e) => setSearchInput(e.target.value)}
                        className="pl-10 h-11 rounded-xl border-slate-200 dark:border-slate-800 focus:border-sky-500"
                    />
                </div>
                <div className="flex items-center gap-2 w-full sm:w-auto">
                    <Button type="submit" variant="outline" className="rounded-xl h-11 px-5">
                        Search
                    </Button>
                    {appliedSearch && (
                        <Button
                            type="button"
                            variant="ghost"
                            onClick={() => {
                                setSearchInput("");
                                setAppliedSearch("");
                                const params = new URLSearchParams(searchParams.toString());
                                params.delete("search");
                                params.delete("page");
                                const query = params.toString();
                                router.replace(query ? `${pathname}?${query}` : pathname);
                            }}
                            className="rounded-xl h-11 text-slate-400"
                        >
                            Clear
                        </Button>
                    )}
                </div>
            </form>

            {/* Table */}
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
                            <TableHead className="py-4 pl-6">Parent Name</TableHead>
                            <TableHead>Contact</TableHead>
                            <TableHead>Occupation</TableHead>
                            <TableHead>Children</TableHead>
                            <TableHead>Portal Access</TableHead>
                            <TableHead className="text-right pr-6">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {parents.length > 0 ? (
                            parents.map((parent) => {
                                const profile = parent.profile_details;
                                const fullName = `${profile?.first_name || ""} ${profile?.last_name || ""}`.trim() || "Unnamed Parent";
                                const hasAccount = Boolean(profile?.user_id);
                                const children = parent.children || [];

                                return (
                                    <TableRow
                                        key={parent.id}
                                        className="hover:bg-slate-50/50 dark:hover:bg-slate-800/50 transition-colors cursor-pointer"
                                        onClick={() => setParentToView(parent)}
                                    >
                                        <TableCell className="py-4 pl-6">
                                            <div className="flex items-center gap-3">
                                                <div className="h-10 w-10 rounded-full bg-sky-100 dark:bg-sky-900/40 text-sky-600 flex items-center justify-center font-bold text-sm shrink-0">
                                                    {fullName[0]?.toUpperCase() || "P"}
                                                </div>
                                                <div>
                                                    <span className="font-semibold text-slate-900 dark:text-white">
                                                        {fullName}
                                                    </span>
                                                    {profile?.gender && (
                                                        <div className="text-xs text-slate-400 capitalize">
                                                            {profile.gender}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        </TableCell>

                                        <TableCell>
                                            <div className="space-y-0.5 text-xs">
                                                {profile?.phone ? (
                                                    <div className="flex items-center gap-1.5 text-slate-700 dark:text-slate-300">
                                                        <Phone className="h-3 w-3 text-slate-400" />
                                                        <span>{profile.phone}</span>
                                                    </div>
                                                ) : null}
                                                {profile?.email ? (
                                                    <div className="flex items-center gap-1.5 text-slate-500">
                                                        <Mail className="h-3 w-3 text-slate-400" />
                                                        <span className="truncate max-w-[180px]">{profile.email}</span>
                                                    </div>
                                                ) : null}
                                                {!profile?.phone && !profile?.email && (
                                                    <span className="text-slate-400 italic">No contact added</span>
                                                )}
                                            </div>
                                        </TableCell>

                                        <TableCell>
                                            {parent.occupation ? (
                                                <div className="flex items-center gap-1.5 text-sm text-slate-700 dark:text-slate-300">
                                                    <Briefcase className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                                                    <span className="truncate max-w-[140px]">{parent.occupation}</span>
                                                </div>
                                            ) : (
                                                <span className="text-slate-400 text-xs italic">—</span>
                                            )}
                                        </TableCell>

                                        <TableCell>
                                            {children.length > 0 ? (
                                                <div className="flex flex-wrap items-center gap-1.5 max-w-[220px]">
                                                    {children.map((ch) => (
                                                        <Badge
                                                            key={ch.relation_id}
                                                            variant="secondary"
                                                            className="text-xs font-normal rounded-lg px-2 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300"
                                                        >
                                                            {ch.student?.full_name?.split(" ")[0]} ({ch.relation_type[0].toUpperCase()})
                                                        </Badge>
                                                    ))}
                                                </div>
                                            ) : (
                                                <span className="text-xs text-slate-400 italic">No children linked</span>
                                            )}
                                        </TableCell>

                                        <TableCell>
                                            {hasAccount ? (
                                                <Badge className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20 text-xs font-medium rounded-lg">
                                                    <UserCheck className="h-3 w-3 mr-1" />
                                                    Active
                                                </Badge>
                                            ) : (
                                                <Badge variant="outline" className="text-slate-400 text-xs font-normal rounded-lg border-slate-200 dark:border-slate-800">
                                                    Not Activated
                                                </Badge>
                                            )}
                                        </TableCell>

                                        <TableCell className="text-right pr-6" onClick={(e) => e.stopPropagation()}>
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant="ghost" size="icon" className="h-8 w-8 rounded-lg">
                                                        <MoreHorizontal className="h-4 w-4" />
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end" className="w-48 p-2 rounded-xl">
                                                    <DropdownMenuItem
                                                        onClick={() => setParentToView(parent)}
                                                        className="rounded-lg gap-2 cursor-pointer"
                                                    >
                                                        <Eye className="h-4 w-4" />
                                                        View Details
                                                    </DropdownMenuItem>

                                                    {canEdit && (
                                                        <>
                                                            <DropdownMenuItem
                                                                onClick={() => setParentToEdit(parent)}
                                                                className="rounded-lg gap-2 cursor-pointer"
                                                            >
                                                                <Pencil className="h-4 w-4" />
                                                                Edit
                                                            </DropdownMenuItem>
                                                            <DropdownMenuItem
                                                                onClick={() => setParentToLink(parent)}
                                                                className="rounded-lg gap-2 cursor-pointer"
                                                            >
                                                                <LinkIcon className="h-4 w-4" />
                                                                Link Child
                                                            </DropdownMenuItem>
                                                        </>
                                                    )}

                                                    {canDelete && (
                                                        <DropdownMenuItem
                                                            onClick={() => setParentToDelete(parent)}
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
                                );
                            })
                        ) : (
                            <TableRow>
                                <TableCell colSpan={6} className="h-48 text-center">
                                    <EmptyState
                                        icon={<Users className="h-12 w-12 mb-2 opacity-20 text-slate-500" />}
                                        title={appliedSearch ? `No parents found matching "${appliedSearch}".` : "No parents registered yet."}
                                    />
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableShell>

            {/* Dialogs */}
            <ParentFormDialog
                open={isCreateOpen}
                onOpenChange={setIsCreateOpen}
                onSuccess={() => refetch()}
            />

            <ParentFormDialog
                open={Boolean(parentToEdit)}
                onOpenChange={(open) => !open && setParentToEdit(null)}
                parent={parentToEdit}
                onSuccess={() => {
                    setParentToEdit(null);
                    refetch();
                }}
            />

            <ParentDetailDialog
                open={Boolean(parentToView)}
                onOpenChange={(open) => !open && setParentToView(null)}
                parentId={parentToView?.id}
                canEdit={canEdit}
                onActivatePortal={() => router.push("/dashboard/portal-access/parents")}
            />

            <LinkChildDialog
                open={Boolean(parentToLink)}
                onOpenChange={(open) => !open && setParentToLink(null)}
                parentId={parentToLink?.id}
                parentName={`${parentToLink?.profile_details?.first_name || ""} ${parentToLink?.profile_details?.last_name || ""}`.trim()}
                onSuccess={() => {
                    setParentToLink(null);
                    refetch();
                }}
            />

            <ConfirmationDialog
                open={Boolean(parentToDelete)}
                onOpenChange={(open) => !open && setParentToDelete(null)}
                title="Delete Parent Profile?"
                description={`Are you sure you want to delete ${parentToDelete?.profile_details?.first_name} ${parentToDelete?.profile_details?.last_name}? Any linked child relations will also be removed.`}
                confirmLabel="Delete Parent"
                isLoading={isDeleting}
                onConfirm={() => {
                    if (parentToDelete) {
                        deleteParent(parentToDelete.id, {
                            onSuccess: () => setParentToDelete(null),
                        });
                    }
                }}
                contentClassName="rounded-3xl"
            />
        </div>
    );
}

