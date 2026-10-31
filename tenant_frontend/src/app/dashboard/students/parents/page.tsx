"use client";

import { useState, useMemo, useEffect } from "react";
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
    DropdownMenuLabel,
    DropdownMenuSeparator,
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
    CheckCircle2,
    Briefcase,
    X,
    Copy,
    GraduationCap,
    Shield,
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
import { toast } from "sonner";

const PAGE_SIZE = 20;

// Deterministic vibrant avatar color palette
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

function getInitials(name: string) {
    if (!name) return "P";
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
        return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
}

export default function ParentsPage() {
    const { can, isOwner } = usePermissions();
    if (!(isOwner || can("view_family"))) {
        return <Unauthorized />;
    }
    return <ParentsPageContent />;
}

function ParentsPageContent() {
    const { can, isOwner } = usePermissions();
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();

    const pageParam = Number(searchParams.get("page"));
    const page = Number.isInteger(pageParam) && pageParam >= 1 ? pageParam : 1;

    const [searchInput, setSearchInput] = useState(searchParams.get("search") || "");
    const [debouncedSearch, setDebouncedSearch] = useState(searchInput);
    const [statusTab, setStatusTab] = useState<"all" | "active" | "offline">("all");

    // Debounce search query
    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedSearch(searchInput.trim());
        }, 300);
        return () => clearTimeout(handler);
    }, [searchInput]);

    // Update URL on debounced search
    useEffect(() => {
        const params = new URLSearchParams(searchParams.toString());
        if (debouncedSearch) {
            params.set("search", debouncedSearch);
        } else {
            params.delete("search");
        }
        params.delete("page");
        router.replace(`${pathname}?${params.toString()}`);
    }, [debouncedSearch]);

    const { data, isLoading, isError, refetch } = useParents({
        page,
        pageSize: PAGE_SIZE,
        search: debouncedSearch,
    });
    const parents = data?.results || [];

    const { mutate: deleteParent, isPending: isDeleting } = useDeleteParent();

    // Dialog states
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [parentToEdit, setParentToEdit] = useState<Parent | null>(null);
    const [parentToView, setParentToView] = useState<Parent | null>(null);
    const [parentToLink, setParentToLink] = useState<Parent | null>(null);
    const [parentToDelete, setParentToDelete] = useState<Parent | null>(null);

    const canAdd = isOwner || can("add_family");
    const canEdit = isOwner || can("change_family");
    const canDelete = isOwner || can("delete_family");

    const handlePageChange = (nextPage: number) => {
        const params = new URLSearchParams(searchParams.toString());
        if (nextPage <= 1) {
            params.delete("page");
        } else {
            params.set("page", String(nextPage));
        }
        router.replace(`${pathname}?${params.toString()}`);
    };

    // Filter parents by portal tab client-side
    const filteredParents = useMemo(() => {
        if (!parents) return [];
        return parents.filter((p) => {
            const hasAccount = Boolean(p.profile_details?.user_id);
            if (statusTab === "active") return hasAccount;
            if (statusTab === "offline") return !hasAccount;
            return true;
        });
    }, [parents, statusTab]);

    const copyToClipboard = (text: string, label: string) => {
        navigator.clipboard.writeText(text);
        toast.success(`Copied ${label} to clipboard`);
    };

    if (isLoading && !data) {
        return <LoadingState className="h-[60vh]" />;
    }

    if (isError) {
        return <ErrorState onRetry={refetch} className="m-6" />;
    }

    const totalCount = data?.count ?? 0;

    return (
        <div className="space-y-5 max-w-7xl mx-auto pb-12 animate-in fade-in duration-500">
            {/* 1. Senior Executive Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Users className="h-7 w-7 text-sky-600 dark:text-sky-400" />
                        <span>Parents & Guardians</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Manage family profiles, contact channels, portal logins, and student linkages for <span className="font-semibold text-slate-700 dark:text-slate-300">{totalCount} parent records</span>
                    </p>
                </div>

                {/* Right Action Strip */}
                <div className="flex items-center gap-2.5 shrink-0">
                    <Button
                        onClick={() => router.push("/dashboard/portal-access/parents")}
                        variant="outline"
                        size="sm"
                        className="h-9 px-3 gap-1.5 border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 text-xs font-semibold cursor-pointer shadow-2xs"
                    >
                        <Lock className="h-3.5 w-3.5 text-slate-500" />
                        <span>Portal Activation</span>
                    </Button>
                    {canAdd && (
                        <Button
                            onClick={() => setIsCreateOpen(true)}
                            size="sm"
                            className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95"
                        >
                            <UserPlus className="h-3.5 w-3.5 stroke-[2.5]" />
                            <span>Add Parent</span>
                        </Button>
                    )}
                </div>
            </div>

            {/* 2. Quick Segmentation Tabs */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
                {[
                    { id: "all" as const, label: "All Parents", count: totalCount },
                    { id: "active" as const, label: "Portal Active" },
                    { id: "offline" as const, label: "Pending Activation" },
                ].map((tab) => {
                    const isActive = statusTab === tab.id;
                    return (
                        <button
                            key={tab.id}
                            onClick={() => setStatusTab(tab.id)}
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

            {/* 3. Search & Quick Filter Bar */}
            <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex flex-col sm:flex-row gap-2.5 items-center justify-between">
                <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                        placeholder="Search parents by name, phone number (+91...), or email..."
                        value={searchInput}
                        onChange={(e) => setSearchInput(e.target.value)}
                        className="pl-9 pr-8 h-9 text-xs rounded-lg border-slate-200 dark:border-slate-800 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20 bg-slate-50/50 dark:bg-slate-950/50"
                    />
                    {searchInput && (
                        <button
                            onClick={() => setSearchInput("")}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-400 hover:text-slate-600"
                        >
                            <X className="h-3.5 w-3.5" />
                        </button>
                    )}
                </div>

                <div className="flex items-center gap-2 w-full sm:w-auto shrink-0 justify-between sm:justify-start">
                    <span className="text-xs text-slate-500 dark:text-slate-400">
                        Showing <span className="font-semibold text-slate-700 dark:text-slate-200">{filteredParents.length}</span> results
                    </span>
                    {searchInput && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSearchInput("")}
                            className="h-8 px-2 text-xs text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40"
                        >
                            Clear
                        </Button>
                    )}
                </div>
            </div>

            {/* 4. Enterprise Parents Table */}
            <TableShell
                footer={
                    data && (
                        <div className="flex flex-col sm:flex-row items-center justify-between p-3 gap-3 border-t border-slate-200 dark:border-slate-800 bg-slate-50/40 dark:bg-slate-900/40">
                            <span className="text-xs text-slate-500 dark:text-slate-400">
                                Page {page} • Total {totalCount} parents registered
                            </span>
                            <Pagination
                                page={page}
                                pageSize={PAGE_SIZE}
                                count={data.count}
                                onPageChange={handlePageChange}
                            />
                        </div>
                    )
                }
            >
                <Table>
                    <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                        <TableRow className="hover:bg-transparent">
                            <TableHead className="py-3.5 pl-5 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                Parent Name & Role
                            </TableHead>
                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                Contact Channels
                            </TableHead>
                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                Occupation
                            </TableHead>
                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                Linked Children
                            </TableHead>
                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                Portal Access
                            </TableHead>
                            <TableHead className="text-right pr-5 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                Actions
                            </TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {filteredParents.length > 0 ? (
                            filteredParents.map((parent) => {
                                const profile = parent.profile_details;
                                const fullName = `${profile?.first_name || ""} ${profile?.last_name || ""}`.trim() || "Unnamed Parent";
                                const hasAccount = Boolean(profile?.user_id);
                                const children = parent.children || [];
                                const avatarStyle = getAvatarStyle(fullName);
                                const initials = getInitials(fullName);

                                // Determine relation role
                                const primaryChildRelation = children.find((c) => c.is_primary) || children[0];
                                const relationRole = primaryChildRelation?.relation_type
                                    ? primaryChildRelation.relation_type.charAt(0).toUpperCase() + primaryChildRelation.relation_type.slice(1)
                                    : profile?.gender === "female"
                                    ? "Mother"
                                    : profile?.gender === "male"
                                    ? "Father"
                                    : "Guardian";

                                return (
                                    <TableRow
                                        key={parent.id}
                                        className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors cursor-pointer border-b border-slate-100 dark:border-slate-800/70"
                                        onClick={() => setParentToView(parent)}
                                    >
                                        {/* Parent Name & Relationship */}
                                        <TableCell className="py-3 pl-5">
                                            <div className="flex items-center gap-3">
                                                <div
                                                    className={`h-9 w-9 rounded-full flex items-center justify-center font-bold text-xs shrink-0 border ${avatarStyle.bg} ${avatarStyle.text} ${avatarStyle.border}`}
                                                >
                                                    {initials}
                                                </div>
                                                <div className="min-w-0">
                                                    <span className="font-semibold text-xs text-slate-900 dark:text-slate-100 hover:text-sky-600 transition truncate block">
                                                        {fullName}
                                                    </span>
                                                    <div className="flex items-center gap-1.5 mt-0.5">
                                                        <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                                                            {relationRole}
                                                        </span>
                                                        {primaryChildRelation?.is_primary && (
                                                            <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-sky-50 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300 border border-sky-200 dark:border-sky-800">
                                                                Primary
                                                            </span>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        </TableCell>

                                        {/* Contact Channels with Quick Copy */}
                                        <TableCell onClick={(e) => e.stopPropagation()}>
                                            <div className="space-y-1 text-xs">
                                                {profile?.phone ? (
                                                    <div className="flex items-center gap-1.5 group">
                                                        <Phone className="h-3 w-3 text-slate-400 shrink-0" />
                                                        <a
                                                            href={`tel:${profile.phone}`}
                                                            className="font-mono text-[11px] font-medium text-slate-800 dark:text-slate-200 hover:text-sky-600 hover:underline"
                                                        >
                                                            {profile.phone}
                                                        </a>
                                                        <button
                                                            onClick={() => profile.phone && copyToClipboard(profile.phone, "phone")}
                                                            className="opacity-0 group-hover:opacity-100 transition p-0.5 hover:text-sky-600"
                                                            title="Copy phone"
                                                        >
                                                            <Copy className="h-2.5 w-2.5" />
                                                        </button>
                                                    </div>
                                                ) : null}
                                                {profile?.email ? (
                                                    <div className="flex items-center gap-1.5 group text-slate-500">
                                                        <Mail className="h-3 w-3 text-slate-400 shrink-0" />
                                                        <span className="truncate max-w-[160px] text-[11px]">{profile.email}</span>
                                                    </div>
                                                ) : null}
                                                {!profile?.phone && !profile?.email && (
                                                    <span className="text-slate-400 italic text-[11px]">No contact added</span>
                                                )}
                                            </div>
                                        </TableCell>

                                        {/* Occupation */}
                                        <TableCell>
                                            {parent.occupation ? (
                                                <div className="flex items-center gap-1.5 text-xs text-slate-700 dark:text-slate-300">
                                                    <Briefcase className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                                                    <span className="truncate max-w-[140px]">{parent.occupation}</span>
                                                </div>
                                            ) : (
                                                <span className="text-slate-400 text-xs italic">—</span>
                                            )}
                                        </TableCell>

                                        {/* Linked Children */}
                                        <TableCell onClick={(e) => e.stopPropagation()}>
                                            {children.length > 0 ? (
                                                <div className="flex flex-wrap items-center gap-1.5 max-w-[240px]">
                                                    {children.map((ch) => {
                                                        const childName = ch.student?.full_name?.split(" ")[0] || "Student";
                                                        const relLetter = (ch.relation_type || "G")[0].toUpperCase();
                                                        return (
                                                            <span
                                                                key={ch.relation_id}
                                                                onClick={() => {
                                                                    if (ch.student?.id) {
                                                                        router.push(`/dashboard/students/edit/${ch.student.id}`);
                                                                    }
                                                                }}
                                                                className="inline-flex items-center gap-1 text-[11px] font-semibold rounded-md px-2 py-0.5 bg-slate-100 hover:bg-sky-50 dark:bg-slate-800 dark:hover:bg-sky-950/50 text-slate-700 hover:text-sky-700 dark:text-slate-300 dark:hover:text-sky-300 border border-slate-200/80 dark:border-slate-700 transition cursor-pointer"
                                                                title={`Linked Student: ${ch.student?.full_name || ""} (${ch.relation_type})`}
                                                            >
                                                                <GraduationCap className="h-3 w-3 text-slate-400" />
                                                                <span>{childName}</span>
                                                                <span className="text-[10px] text-slate-400">({relLetter})</span>
                                                            </span>
                                                        );
                                                    })}
                                                </div>
                                            ) : (
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => setParentToLink(parent)}
                                                    className="h-7 px-2 text-[11px] text-sky-600 hover:bg-sky-50 dark:hover:bg-sky-950/40"
                                                >
                                                    <LinkIcon className="h-3 w-3 mr-1" />
                                                    Link Child
                                                </Button>
                                            )}
                                        </TableCell>

                                        {/* Portal Access Status */}
                                        <TableCell>
                                            {hasAccount ? (
                                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-500/20">
                                                    <CheckCircle2 className="h-3 w-3 text-emerald-500" />
                                                    <span>Active</span>
                                                </span>
                                            ) : (
                                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
                                                    <span className="h-1.5 w-1.5 rounded-full bg-slate-300 dark:bg-slate-600" />
                                                    <span>Not Activated</span>
                                                </span>
                                            )}
                                        </TableCell>

                                        {/* Actions Menu */}
                                        <TableCell className="text-right pr-5" onClick={(e) => e.stopPropagation()}>
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant="ghost" size="icon" className="h-8 w-8 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
                                                        <MoreHorizontal className="h-4 w-4 text-slate-500" />
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end" className="w-48 p-1.5 rounded-xl shadow-lg">
                                                    <DropdownMenuItem
                                                        onClick={() => setParentToView(parent)}
                                                        className="flex items-center gap-2 p-2 rounded-lg cursor-pointer text-xs focus:bg-sky-50 focus:text-sky-600"
                                                    >
                                                        <Eye className="h-4 w-4 text-sky-600" />
                                                        <span>View Details</span>
                                                    </DropdownMenuItem>

                                                    {canEdit && (
                                                        <>
                                                            <DropdownMenuItem
                                                                onClick={() => setParentToEdit(parent)}
                                                                className="flex items-center gap-2 p-2 rounded-lg cursor-pointer text-xs"
                                                            >
                                                                <Pencil className="h-4 w-4 text-slate-500" />
                                                                <span>Edit Profile</span>
                                                            </DropdownMenuItem>
                                                            <DropdownMenuItem
                                                                onClick={() => setParentToLink(parent)}
                                                                className="flex items-center gap-2 p-2 rounded-lg cursor-pointer text-xs"
                                                            >
                                                                <LinkIcon className="h-4 w-4 text-teal-600" />
                                                                <span>Link Student</span>
                                                            </DropdownMenuItem>
                                                        </>
                                                    )}

                                                    {canDelete && (
                                                        <>
                                                            <DropdownMenuSeparator />
                                                            <DropdownMenuItem
                                                                onClick={() => setParentToDelete(parent)}
                                                                className="flex items-center gap-2 p-2 rounded-lg cursor-pointer text-xs text-rose-600 focus:bg-rose-50 dark:focus:bg-rose-950/40"
                                                            >
                                                                <Trash2 className="h-4 w-4" />
                                                                <span>Delete Parent</span>
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
                                        icon={<Users className="h-10 w-10 mb-2 opacity-20 text-slate-500 mx-auto" />}
                                        title={debouncedSearch ? `No parents found matching "${debouncedSearch}".` : "No parents registered yet."}
                                        description="Try searching with a different name or phone number."
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
                contentClassName="rounded-2xl"
                cancelClassName="rounded-lg h-9 text-xs"
                confirmClassName="rounded-lg h-9 text-xs bg-rose-600 hover:bg-rose-500"
            />
        </div>
    );
}
