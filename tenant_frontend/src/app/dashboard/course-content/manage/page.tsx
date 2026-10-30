"use client";

import { useState, useMemo } from "react";
import {
    useMyCourseContent,
    useCreateContent,
    useDeleteContent
} from "@/hooks/useCourseContent";
import { useSections } from "@/hooks/useAcademics";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
    FolderOpen,
    Plus,
    Search,
    X,
    Pin,
    FileText,
    Calendar,
    Users,
    Trash2,
    CheckCircle2,
    Eye,
    Layers,
    File,
} from "lucide-react";
import { UploadContentDialog } from "@/components/dashboard/course-content/UploadContentDialog";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { format } from "date-fns";

export default function ManageContentPage() {
    const { data: content = [], isLoading, isError, refetch } = useMyCourseContent();
    const { mutate: createContent, isPending: isCreating } = useCreateContent();
    const { mutate: deleteContent, isPending: isDeleting } = useDeleteContent();

    const { data: sections } = useSections();

    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [contentToDelete, setContentToDelete] = useState<string | null>(null);
    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState<"all" | "published" | "draft">("all");

    const handleSubmit = (data: any) => {
        createContent(data, {
            onSuccess: () => {
                setIsDialogOpen(false);
                refetch();
            }
        });
    };

    const handleDelete = () => {
        if (contentToDelete) {
            deleteContent(contentToDelete, {
                onSuccess: () => {
                    setContentToDelete(null);
                    refetch();
                }
            });
        }
    };

    // Filter content
    const filteredContent = useMemo(() => {
        return content.filter((item) => {
            const matchesSearch =
                !search.trim() ||
                item.title.toLowerCase().includes(search.toLowerCase()) ||
                item.description.toLowerCase().includes(search.toLowerCase());

            if (!matchesSearch) return false;

            if (statusFilter === "published") return item.is_published;
            if (statusFilter === "draft") return !item.is_published;

            return true;
        });
    }, [content, search, statusFilter]);

    // Metrics
    const metrics = useMemo(() => {
        const total = content.length;
        const published = content.filter((c) => c.is_published).length;
        const drafts = content.filter((c) => !c.is_published).length;
        const pinned = content.filter((c) => c.is_pinned).length;
        return { total, published, drafts, pinned };
    }, [content]);

    if (isLoading) {
        return <LoadingState className="py-20" />;
    }

    if (isError) {
        return <ErrorState onRetry={refetch} />;
    }

    return (
        <div className="space-y-6 pb-12 animate-in fade-in duration-300">
            {/* 1. Executive Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <FolderOpen className="w-7 h-7 text-sky-600 dark:text-sky-400" />
                        <span>Course Content & Digital Uploads Desk</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Author lecture handouts, upload reference files, allocate target class cohorts, and manage publishing states
                    </p>
                </div>

                <Button
                    onClick={() => setIsDialogOpen(true)}
                    size="sm"
                    className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95 shrink-0"
                >
                    <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                    <span>Upload New Content</span>
                </Button>
            </div>

            {/* 2. Executive 4-Card Operational Pulse Strip */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
                {/* Total Content Items */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Total Uploads</span>
                        <div className="p-1.5 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400">
                            <FolderOpen className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.total}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">catalog items</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Authored by your faculty account
                    </p>
                </div>

                {/* Published & Live */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Published Live</span>
                        <div className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
                            <CheckCircle2 className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.published}
                        </span>
                        <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold">
                            active
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Visible to student cohorts
                    </p>
                </div>

                {/* Pinned Items */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Pinned Resources</span>
                        <div className="p-1.5 rounded-lg bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400">
                            <Pin className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.pinned}
                        </span>
                        <span className="text-[11px] text-amber-600 dark:text-amber-400 font-semibold">
                            featured
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Highlighted at top of class portal
                    </p>
                </div>

                {/* Drafts */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Draft Content</span>
                        <div className="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
                            <FileText className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.drafts}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">unpublished</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Under preparation
                    </p>
                </div>
            </div>

            {/* 3. Search & Funnel Filters */}
            <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex flex-col sm:flex-row items-center justify-between gap-3">
                <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                        placeholder="Search your uploads by title or description..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="pl-9 pr-8 h-9 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                    />
                    {search && (
                        <button
                            onClick={() => setSearch("")}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-400 hover:text-slate-600 cursor-pointer"
                        >
                            <X className="h-3.5 w-3.5" />
                        </button>
                    )}
                </div>

                <div className="flex items-center gap-1 self-start sm:self-auto shrink-0">
                    {[
                        { value: "all", label: "All Uploads" },
                        { value: "published", label: "Live Only" },
                        { value: "draft", label: "Drafts Only" },
                    ].map((opt) => (
                        <button
                            key={opt.value}
                            type="button"
                            onClick={() => setStatusFilter(opt.value as any)}
                            className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                                statusFilter === opt.value
                                    ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-2xs"
                                    : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200/80 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800"
                            }`}
                        >
                            {opt.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* 4. Table */}
            {filteredContent.length === 0 ? (
                <EmptyState
                    icon={<FolderOpen className="h-14 w-14 text-slate-200 dark:text-slate-700 mb-3" />}
                    title={search ? "No uploads matched your query" : "No course materials uploaded yet"}
                    titleAs="h3"
                    description={
                        search
                            ? "Try adjusting your search terms or clearing your status filter."
                            : "Upload your first syllabus document, lecture presentation, or reference file to share with enrolled students."
                    }
                    action={
                        !search ? (
                            <Button
                                onClick={() => setIsDialogOpen(true)}
                                size="sm"
                                className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg"
                            >
                                <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                                <span>Upload First Content Item</span>
                            </Button>
                        ) : undefined
                    }
                />
            ) : (
                <TableShell>
                    <Table>
                        <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                            <TableRow className="hover:bg-transparent">
                                <TableHead className="py-3.5 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Content Title & Scope
                                </TableHead>
                                <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Format Type
                                </TableHead>
                                <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Target Cohorts
                                </TableHead>
                                <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Publishing Status
                                </TableHead>
                                <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Created On
                                </TableHead>
                                <TableHead className="text-right pr-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Actions
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {filteredContent.map((item) => (
                                <TableRow
                                    key={item.id}
                                    className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                >
                                    {/* Title & Scope */}
                                    <TableCell className="py-3.5 pl-4">
                                        <div className="flex items-center gap-2">
                                            {item.is_pinned && (
                                                <Pin className="h-3.5 w-3.5 text-amber-500 fill-amber-500 shrink-0" />
                                            )}
                                            <span className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                {item.title}
                                            </span>
                                        </div>
                                        {item.description && (
                                            <div className="text-[11px] text-slate-400 line-clamp-1 mt-0.5 pl-5.5">
                                                {item.description}
                                            </div>
                                        )}
                                    </TableCell>

                                    {/* Format Type */}
                                    <TableCell className="py-3.5">
                                        <Badge variant="outline" className="text-[11px] font-semibold capitalize">
                                            {item.content_type_display || item.content_type}
                                        </Badge>
                                    </TableCell>

                                    {/* Target Cohorts */}
                                    <TableCell className="py-3.5 text-xs text-slate-600 dark:text-slate-400">
                                        <span className="font-semibold text-slate-800 dark:text-slate-200">
                                            {item.target_sections_details?.length || 0}
                                        </span>{" "}
                                        {item.target_sections_details?.length === 1 ? "Section" : "Sections"}
                                    </TableCell>

                                    {/* Status */}
                                    <TableCell className="py-3.5">
                                        {item.is_published ? (
                                            <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300/80 font-semibold text-[11px]">
                                                Published
                                            </Badge>
                                        ) : (
                                            <Badge variant="outline" className="text-[11px] text-slate-400 border-slate-300">
                                                Draft
                                            </Badge>
                                        )}
                                    </TableCell>

                                    {/* Created On */}
                                    <TableCell className="py-3.5 text-xs text-slate-500 font-medium">
                                        {format(new Date(item.created_at), "MMM d, yyyy")}
                                    </TableCell>

                                    {/* Actions */}
                                    <TableCell className="py-3.5 pr-4 text-right">
                                        <Button
                                            size="sm"
                                            variant="ghost"
                                            onClick={() => setContentToDelete(item.id)}
                                            className="h-8 w-8 p-0 text-rose-500 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-lg cursor-pointer"
                                            title="Delete content item"
                                        >
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableShell>
            )}

            {/* Modals & Dialogs */}
            <UploadContentDialog
                open={isDialogOpen}
                onOpenChange={setIsDialogOpen}
                onSubmit={handleSubmit}
                sections={sections}
                isCreating={isCreating}
            />

            <ConfirmationDialog
                open={Boolean(contentToDelete)}
                onOpenChange={() => setContentToDelete(null)}
                title="Permanently Delete Material?"
                description="This course content item and its attached file will be permanently removed. Enrolled students will no longer be able to access this resource."
                confirmLabel="Yes, Delete Material"
                variant="destructive"
                isLoading={isDeleting}
                onConfirm={handleDelete}
            />
        </div>
    );
}
