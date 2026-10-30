"use client";

import { useState, useMemo } from "react";
import { useCourseContent } from "@/hooks/useCourseContent";
import {
    BookOpen,
    FileText,
    Video,
    Link as LinkIcon,
    Search,
    X,
    File,
    Layers,
    Download,
    ExternalLink,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { MaterialCard } from "@/components/dashboard/course-content/MaterialCard";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

export default function StudyMaterialsPage() {
    const [searchQuery, setSearchQuery] = useState("");
    const [contentTypeFilter, setContentTypeFilter] = useState<string>("all");

    const { data: content = [], isLoading, isError, refetch } = useCourseContent(
        contentTypeFilter !== "all" ? contentTypeFilter : undefined,
        true // Exclude assignments - this is a study materials page
    );

    const filteredContent = useMemo(() => {
        return content.filter((item) =>
            item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            item.description.toLowerCase().includes(searchQuery.toLowerCase())
        );
    }, [content, searchQuery]);

    // Metrics
    const metrics = useMemo(() => {
        const total = content.length;
        const notes = content.filter((c) => c.content_type === "note").length;
        const documents = content.filter((c) => c.content_type === "document").length;
        const media = content.filter((c) => c.content_type === "video" || c.content_type === "link").length;
        return { total, notes, documents, media };
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
                        <BookOpen className="w-7 h-7 text-sky-600 dark:text-sky-400" />
                        <span>Study Materials & Digital Library</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Access course lecture notes, syllabus handouts, curated reading documents, and multimedia learning resources
                    </p>
                </div>
            </div>

            {/* 2. Executive 4-Card Operational Pulse Strip */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
                {/* Total Materials */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Total Resources</span>
                        <div className="p-1.5 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400">
                            <BookOpen className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.total}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">learning files</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Published by faculty
                    </p>
                </div>

                {/* Documents */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Documents & PDFs</span>
                        <div className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
                            <File className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.documents}
                        </span>
                        <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold">
                            handouts
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Downloadable files
                    </p>
                </div>

                {/* Lecture Notes */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Lecture Notes</span>
                        <div className="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
                            <FileText className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.notes}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">summaries</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Class syllabus notes
                    </p>
                </div>

                {/* Videos & External Links */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Media & Links</span>
                        <div className="p-1.5 rounded-lg bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400">
                            <Video className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.media}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">videos / URLs</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        External learning references
                    </p>
                </div>
            </div>

            {/* 3. Search and Content Type Funnel Controls */}
            <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex flex-col sm:flex-row items-center justify-between gap-3">
                <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                        placeholder="Search materials by title or topic..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="pl-9 pr-8 h-9 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                    />
                    {searchQuery && (
                        <button
                            onClick={() => setSearchQuery("")}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-400 hover:text-slate-600 cursor-pointer"
                        >
                            <X className="h-3.5 w-3.5" />
                        </button>
                    )}
                </div>

                <div className="flex items-center gap-1 overflow-x-auto scrollbar-none self-start sm:self-auto shrink-0">
                    {[
                        { value: "all", label: "All Formats" },
                        { value: "note", label: "Notes" },
                        { value: "document", label: "Documents" },
                        { value: "video", label: "Videos" },
                        { value: "link", label: "Links" },
                    ].map((opt) => (
                        <button
                            key={opt.value}
                            type="button"
                            onClick={() => setContentTypeFilter(opt.value)}
                            className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                                contentTypeFilter === opt.value
                                    ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-2xs"
                                    : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200/80 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800"
                            }`}
                        >
                            {opt.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* 4. Materials Grid */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {filteredContent.length > 0 ? (
                    filteredContent.map((item) => (
                        <MaterialCard key={item.id} material={item} />
                    ))
                ) : (
                    <EmptyState
                        icon={<BookOpen className="h-14 w-14 text-slate-200 dark:text-slate-700 mb-3" />}
                        title="No study materials found"
                        titleAs="h3"
                        description={
                            searchQuery
                                ? "No materials match your search query. Try searching with different terms."
                                : "Your instructors have not published materials for this filter yet. Check back soon."
                        }
                        className="col-span-full py-16 bg-slate-50/50 dark:bg-slate-900/50 rounded-xl border border-dashed border-slate-200 dark:border-slate-800"
                    />
                )}
            </div>
        </div>
    );
}
