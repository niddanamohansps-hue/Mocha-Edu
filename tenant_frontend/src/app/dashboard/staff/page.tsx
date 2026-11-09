"use client";

import { useState, useEffect } from "react";
import { useStaffMembers, useDeleteStaff } from "@/hooks/useStaff";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import {
    Search,
    UserPlus,
    MoreHorizontal,
    Briefcase,
    Lock,
    Pencil,
    Trash2,
    X,
    Phone,
    Mail,
    Check,
    Copy,
    Users,
    Building,
    Calendar,
    Shield,
    Eye,
    Printer,
} from "lucide-react";
import { StaffIDCardModal } from "@/components/dashboard/staff/StaffIDCardModal";
import { Input } from "@/components/ui/input";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Pagination } from "@/components/ui/pagination";
import { Badge } from "@/components/ui/badge";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import Unauthorized from "@/components/Unauthorized";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { TableShell } from "@/components/common/table/TableShell";
import { toast } from "sonner";

const PAGE_SIZE = 20;

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

export default function StaffPage() {
    const { can, isOwner } = usePermissions();
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();

    const pageParam = Number(searchParams.get("page"));
    const page = Number.isInteger(pageParam) && pageParam >= 1 ? pageParam : 1;

    // Search and status filter
    const [searchQuery, setSearchQuery] = useState("");
    const [debouncedSearch, setDebouncedSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
    const [copiedPhone, setCopiedPhone] = useState<string | null>(null);

    // 300ms debounce
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedSearch(searchQuery);
        }, 300);
        return () => clearTimeout(timer);
    }, [searchQuery]);

    const activeFilterParam =
        statusFilter === "all" ? undefined : statusFilter === "active";

    const { data, isLoading, isError, refetch } = useStaffMembers({
        page,
        pageSize: PAGE_SIZE,
        search: debouncedSearch || undefined,
        isActive: activeFilterParam,
    });

    const staff = data?.results || [];
    const totalCount = data?.count || 0;
    const { mutate: deleteStaff } = useDeleteStaff();
    const [staffToDelete, setStaffToDelete] = useState<string | null>(null);
    const [idCardStaff, setIdCardStaff] = useState<any>(null);

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

    const copyToClipboard = (text: string, label: string) => {
        if (!text) return;
        navigator.clipboard.writeText(text);
        setCopiedPhone(text);
        toast.success(`Copied ${label} to clipboard`);
        setTimeout(() => setCopiedPhone(null), 2000);
    };

    const canView = isOwner || can("view_staff");
    const canEdit = isOwner || can("change_staff");
    const canDelete = isOwner || can("delete_staff");
    const canManagePortal = isOwner || can("activate_staff_portal");

    if (!canView) {
        return <Unauthorized />;
    }

    if (isLoading && !data) {
        return <LoadingState className="h-[60vh]" />;
    }

    if (isError) {
        return <ErrorState onRetry={refetch} className="m-6" />;
    }

    return (
        <div className="space-y-4">
            {/* 1. Executive Top Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1">
                <div>
                    <div className="flex items-center gap-2.5">
                        <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                            Staff Directory
                        </h1>
                        <Badge
                            variant="secondary"
                            className="bg-sky-50 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300 border border-sky-300/80 font-semibold text-xs px-2 py-0.5"
                        >
                            {totalCount} Active Members
                        </Badge>
                    </div>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-0.5">
                        Manage employee profiles, designations, department allocations, and portal credentials.
                    </p>
                </div>

                <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
                    {(isOwner || canManagePortal) && (
                        <Button
                            onClick={() => router.push("/dashboard/portal-access/staff")}
                            variant="outline"
                            size="sm"
                            className="h-9 px-3 gap-1.5 border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 text-xs font-semibold cursor-pointer shadow-2xs hover:bg-slate-50 dark:hover:bg-slate-800"
                        >
                            <Lock className="h-3.5 w-3.5 text-slate-500" />
                            <span>Portal Access</span>
                        </Button>
                    )}
                    {(isOwner || can("add_staff")) && (
                        <Button
                            onClick={() => router.push("/dashboard/staff/onboarding")}
                            size="sm"
                            className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95"
                        >
                            <UserPlus className="h-3.5 w-3.5 stroke-[2.5]" />
                            <span>Onboard Staff</span>
                        </Button>
                    )}
                </div>
            </div>

            {/* 2. Unified High-Density Filter & Segment Bar */}
            <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex flex-col sm:flex-row gap-2.5 items-center justify-between">
                {/* Search Input */}
                <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                        aria-label="Search staff by name, phone, or employee ID..."
                        placeholder="Search staff by name, employee ID, phone, designation..."
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

                {/* Quick Segment Filter Tabs */}
                <div className="flex items-center gap-1.5 w-full sm:w-auto shrink-0 justify-between sm:justify-start">
                    <div className="inline-flex p-1 bg-slate-100 dark:bg-slate-800/80 rounded-lg text-xs font-medium">
                        <button
                            type="button"
                            onClick={() => setStatusFilter("all")}
                            className={`px-3 py-1 rounded-md text-xs font-semibold transition cursor-pointer ${
                                statusFilter === "all"
                                    ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-2xs"
                                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
                            }`}
                        >
                            All
                        </button>
                        <button
                            type="button"
                            onClick={() => setStatusFilter("active")}
                            className={`px-3 py-1 rounded-md text-xs font-semibold transition cursor-pointer ${
                                statusFilter === "active"
                                    ? "bg-white dark:bg-slate-900 text-emerald-700 dark:text-emerald-400 shadow-2xs"
                                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
                            }`}
                        >
                            Active Portal
                        </button>
                        <button
                            type="button"
                            onClick={() => setStatusFilter("inactive")}
                            className={`px-3 py-1 rounded-md text-xs font-semibold transition cursor-pointer ${
                                statusFilter === "inactive"
                                    ? "bg-white dark:bg-slate-900 text-amber-700 dark:text-amber-400 shadow-2xs"
                                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
                            }`}
                        >
                            Pending Access
                        </button>
                    </div>

                    {(searchQuery || statusFilter !== "all") && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                                setSearchQuery("");
                                setStatusFilter("all");
                            }}
                            className="h-9 px-2 text-xs text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40"
                        >
                            Reset
                        </Button>
                    )}
                </div>
            </div>

            {/* 3. TableShell with Staff Directory Table */}
            <TableShell
                footer={
                    totalCount > 0 && (
                        <Pagination
                            page={page}
                            pageSize={PAGE_SIZE}
                            count={totalCount}
                            onPageChange={handlePageChange}
                            className="border-t border-slate-200/80 dark:border-slate-800 px-4 py-3 bg-slate-50/40 dark:bg-slate-900/40"
                        />
                    )
                }
            >
                <Table>
                    <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                        <TableRow className="hover:bg-transparent">
                            <TableHead className="py-3.5 pl-5 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                Staff Name &amp; Contact
                            </TableHead>
                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                Employee ID
                            </TableHead>
                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                Role / Designation
                            </TableHead>
                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                Department
                            </TableHead>
                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                Joining Date
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
                        {staff && staff.length > 0 ? (
                            staff.map((member: any) => {
                                const profile = member.profile_details || {};
                                const fullName = `${profile.first_name || ""} ${profile.last_name || ""}`.trim() || "Unnamed Member";
                                const avatarStyle = getAvatarStyle(fullName);
                                const initials = getInitials(profile.first_name, profile.last_name);
                                const hasAccount = Boolean(profile.user_id);

                                return (
                                    <TableRow
                                        key={member.id}
                                        className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors border-b border-slate-100 dark:border-slate-800/70"
                                    >
                                        {/* Staff Name & Contact */}
                                        <TableCell className="py-3 pl-5">
                                            <div className="flex items-center gap-3">
                                                <div
                                                    className={`h-9 w-9 rounded-full flex items-center justify-center font-bold text-xs shrink-0 border ${avatarStyle.bg} ${avatarStyle.text} ${avatarStyle.border}`}
                                                >
                                                    {initials}
                                                </div>
                                                <div className="min-w-0">
                                                    <span
                                                        onClick={() => router.push(`/dashboard/staff/${member.id}`)}
                                                        className="font-semibold text-xs text-slate-900 dark:text-slate-100 hover:text-sky-600 dark:hover:text-sky-400 cursor-pointer transition block truncate"
                                                    >
                                                        {fullName}
                                                    </span>
                                                    <div className="flex items-center gap-2 mt-0.5">
                                                        {profile.phone ? (
                                                            <button
                                                                type="button"
                                                                onClick={(e) => {
                                                                    e.stopPropagation();
                                                                    copyToClipboard(profile.phone, "Phone");
                                                                }}
                                                                className="inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition font-mono cursor-pointer"
                                                                title="Click to copy phone"
                                                            >
                                                                <Phone className="w-3 h-3 text-slate-400" />
                                                                <span>{profile.phone}</span>
                                                                {copiedPhone === profile.phone ? (
                                                                    <Check className="w-3 h-3 text-emerald-500" />
                                                                ) : (
                                                                    <Copy className="w-2.5 h-2.5 text-slate-400 opacity-0 group-hover:opacity-100" />
                                                                )}
                                                            </button>
                                                        ) : (
                                                            <span className="text-[11px] text-slate-400">No phone</span>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        </TableCell>

                                        {/* Employee ID */}
                                        <TableCell className="py-3">
                                            <code className="text-xs font-mono font-bold text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800/80 px-1.5 py-0.5 rounded border border-slate-200 dark:border-slate-700">
                                                {member.employee_id || "EMP-—"}
                                            </code>
                                        </TableCell>

                                        {/* Role / Designation */}
                                        <TableCell className="py-3">
                                            <div className="flex items-center gap-1.5">
                                                <Briefcase className="w-3.5 h-3.5 text-slate-400" />
                                                <span className="font-medium text-xs text-slate-800 dark:text-slate-200">
                                                    {member.designation || "Staff"}
                                                </span>
                                            </div>
                                        </TableCell>

                                        {/* Department */}
                                        <TableCell className="py-3">
                                            <Badge
                                                variant="outline"
                                                className="text-[11px] font-medium border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400"
                                            >
                                                <Building className="w-3 h-3 mr-1 text-slate-400" />
                                                {member.department || "General"}
                                            </Badge>
                                        </TableCell>

                                        {/* Joining Date */}
                                        <TableCell className="py-3">
                                            <div className="text-xs text-slate-600 dark:text-slate-400 flex items-center gap-1">
                                                <Calendar className="w-3 h-3 text-slate-400" />
                                                <span>{formatDate(member.joining_date)}</span>
                                            </div>
                                        </TableCell>

                                        {/* Portal Access Status */}
                                        <TableCell className="py-3">
                                            {hasAccount ? (
                                                <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300/80 font-semibold text-xs">
                                                    Active Portal
                                                </Badge>
                                            ) : (
                                                <Badge className="bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300/80 font-semibold text-xs">
                                                    Pending Access
                                                </Badge>
                                            )}
                                        </TableCell>

                                        {/* Row Actions */}
                                        <TableCell className="text-right pr-5 py-3">
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant="ghost" size="icon" className="h-8 w-8 rounded-lg cursor-pointer">
                                                        <MoreHorizontal className="h-4 w-4" />
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="end" className="w-48 p-1.5 rounded-xl border-slate-200 dark:border-slate-800 shadow-md">
                                                    {/* View 360 Profile */}
                                                    <DropdownMenuItem
                                                        onClick={() => router.push(`/dashboard/staff/${member.id}`)}
                                                        className="flex items-center gap-2 p-2 rounded-lg cursor-pointer text-xs focus:bg-sky-50 focus:text-sky-600 dark:focus:bg-sky-950/40"
                                                    >
                                                        <Eye className="h-4 w-4 text-sky-600" />
                                                        <span>View 360 Profile</span>
                                                    </DropdownMenuItem>

                                                    {/* Print ID Card */}
                                                    <DropdownMenuItem
                                                        onClick={() => setIdCardStaff(member)}
                                                        className="flex items-center gap-2 p-2 rounded-lg cursor-pointer text-xs focus:bg-indigo-50 focus:text-indigo-600 dark:focus:bg-indigo-950/40"
                                                    >
                                                        <Printer className="h-4 w-4 text-indigo-600" />
                                                        <span>Print ID Card</span>
                                                    </DropdownMenuItem>

                                                    {canEdit && (
                                                        <DropdownMenuItem
                                                            onClick={() => router.push(`/dashboard/staff/edit/${member.id}`)}
                                                            className="flex items-center gap-2 p-2 rounded-lg cursor-pointer text-xs focus:bg-sky-50 focus:text-sky-600 dark:focus:bg-sky-950/40"
                                                        >
                                                            <Pencil className="h-4 w-4 text-sky-600" />
                                                            <span>Edit Profile</span>
                                                        </DropdownMenuItem>
                                                    )}

                                                    {canManagePortal && !hasAccount && (
                                                        <DropdownMenuItem
                                                            onClick={() => router.push(`/dashboard/portal-access/staff`)}
                                                            className="flex items-center gap-2 p-2 rounded-lg cursor-pointer text-xs focus:bg-emerald-50 focus:text-emerald-600 dark:focus:bg-emerald-950/40"
                                                        >
                                                            <Lock className="h-4 w-4 text-emerald-600" />
                                                            <span>Activate Portal</span>
                                                        </DropdownMenuItem>
                                                    )}

                                                    {canDelete && (
                                                        <>
                                                            <DropdownMenuSeparator />
                                                            <DropdownMenuItem
                                                                onClick={() => setStaffToDelete(member.id)}
                                                                className="flex items-center gap-2 p-2 rounded-lg cursor-pointer text-xs text-rose-600 focus:bg-rose-50 dark:focus:bg-rose-950/40"
                                                            >
                                                                <Trash2 className="h-4 w-4" />
                                                                <span>Delete Record</span>
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
                                <TableCell colSpan={7} className="h-48 text-center">
                                    <EmptyState
                                        icon={<Briefcase className="h-10 w-10 mb-2 opacity-20 mx-auto" />}
                                        title={debouncedSearch ? `No staff members found matching "${debouncedSearch}".` : "No staff members registered yet."}
                                        description="Try searching with a different name, designation, or phone number."
                                    />
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </TableShell>

            {/* Delete Confirmation Modal */}
            <ConfirmationDialog
                open={!!staffToDelete}
                onOpenChange={(open) => !open && setStaffToDelete(null)}
                title="Delete Staff Member?"
                description="This will permanently delete this employee record and their portal credentials from the system. This action cannot be reversed."
                confirmLabel="Delete Staff"
                onConfirm={() => {
                    if (staffToDelete) {
                        deleteStaff(staffToDelete);
                        setStaffToDelete(null);
                    }
                }}
                contentClassName="rounded-2xl"
                cancelClassName="rounded-lg h-9 text-xs"
                confirmClassName="rounded-lg h-9 text-xs bg-rose-600 hover:bg-rose-500"
            />

            {/* Staff ID Card Modal */}
            <StaffIDCardModal
                isOpen={Boolean(idCardStaff)}
                onClose={() => setIdCardStaff(null)}
                staff={idCardStaff}
            />
        </div>
    );
}
