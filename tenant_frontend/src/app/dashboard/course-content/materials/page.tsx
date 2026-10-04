"use client";

import { useCourseContent } from "@/hooks/useCourseContent";
import { FileText } from "lucide-react";
import { useState } from "react";
import { MaterialsFilters } from "@/components/dashboard/course-content/MaterialsFilters";
import { MaterialCard } from "@/components/dashboard/course-content/MaterialCard";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

export default function StudyMaterialsPage() {
    const [searchQuery, setSearchQuery] = useState("");
    const [contentTypeFilter, setContentTypeFilter] = useState<string>("all");

    const { data: content, isLoading, isError, refetch } = useCourseContent(
        contentTypeFilter !== "all" ? contentTypeFilter : undefined,
        true // Exclude assignments - this is a study materials page
    );

    const filteredContent = content?.filter(item =>
        item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.description.toLowerCase().includes(searchQuery.toLowerCase())
    );

    if (isLoading) {
        return <LoadingState className="py-20" />;
    }

    if (isError) {
        return <ErrorState onRetry={refetch} />;
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Study Materials</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Access notes, documents, and resources from your instructors
                </p>
            </div>

            {/* Filters */}
            <MaterialsFilters
                searchQuery={searchQuery}
                onSearchChange={setSearchQuery}
                contentTypeFilter={contentTypeFilter}
                onContentTypeChange={setContentTypeFilter}
            />

            {/* Content Grid */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {filteredContent && filteredContent.length > 0 ? (
                    filteredContent.map((item) => (
                        <MaterialCard key={item.id} material={item} />
                    ))
                ) : (
                    <EmptyState
                        icon={<FileText className="h-16 w-16 text-slate-200 dark:text-slate-700 mb-4" />}
                        title="No materials found"
                        titleAs="h3"
                        description="Check back later for new content from your instructors"
                        className="col-span-full py-20 bg-slate-50/50 dark:bg-slate-900/50 rounded-2xl border-2 border-dashed border-slate-200 dark:border-slate-800"
                    />
                )}
            </div>
        </div>
    );
}
