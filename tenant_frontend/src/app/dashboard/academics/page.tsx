"use client";

import { Suspense, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { usePermissions } from "@/providers/PermissionProvider";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { GraduationCap, Library, Layers, Kanban, Calendar } from "lucide-react";
import ProgramsTab from "@/components/dashboard/academics/ProgramsTab";
import LevelsTab from "@/components/dashboard/academics/LevelsTab";
import SectionsTab from "@/components/dashboard/academics/SectionsTab";
import SubjectsTab from "@/components/dashboard/academics/SubjectsTab";
import AcademicYearsTab from "@/components/dashboard/academics/AcademicYearsTab";
import Unauthorized from "@/components/Unauthorized";

function AcademicsContent() {
    const searchParams = useSearchParams();
    const tabParam = searchParams.get("tab");
    const [activeTab, setActiveTab] = useState("programs");

    useEffect(() => {
        if (tabParam && ["programs", "levels", "sections", "subjects", "years"].includes(tabParam)) {
            setActiveTab(tabParam);
        }
    }, [tabParam]);

    return (
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
            <TabsList>
                <TabsTrigger value="programs" className="gap-2">
                    <GraduationCap className="h-4 w-4" />
                    Programs
                </TabsTrigger>
                <TabsTrigger value="levels" className="gap-2">
                    <Layers className="h-4 w-4" />
                    Levels
                </TabsTrigger>
                <TabsTrigger value="sections" className="gap-2">
                    <Kanban className="h-4 w-4" />
                    Sections
                </TabsTrigger>
                <TabsTrigger value="subjects" className="gap-2">
                    <Library className="h-4 w-4" />
                    Subjects
                </TabsTrigger>
                <TabsTrigger value="years" className="gap-2">
                    <Calendar className="h-4 w-4" />
                    Academic Years
                </TabsTrigger>
            </TabsList>

            <TabsContent value="programs" className="space-y-4">
                <ProgramsTab />
            </TabsContent>
            <TabsContent value="levels" className="space-y-4">
                <LevelsTab />
            </TabsContent>
            <TabsContent value="sections" className="space-y-4">
                <SectionsTab />
            </TabsContent>
            <TabsContent value="subjects" className="space-y-4">
                <SubjectsTab />
            </TabsContent>
            <TabsContent value="years" className="space-y-4">
                <AcademicYearsTab />
            </TabsContent>
        </Tabs>
    );
}

export default function AcademicsPage() {
    const { can, isOwner } = usePermissions();
    const canViewAcademics = isOwner || can("view_program") || can("view_academic_level");

    if (!canViewAcademics) {
        return <Unauthorized />;
    }

    return (
        <div className="flex flex-col gap-6">
            <div>
                <h1 className="text-3xl font-bold tracking-tight">Academics</h1>
                <p className="text-muted-foreground">
                    Manage your institution's academic structure, curriculum, sessions, and classes.
                </p>
            </div>

            <Suspense fallback={<div className="h-40 animate-pulse bg-slate-100 dark:bg-slate-800 rounded-lg" />}>
                <AcademicsContent />
            </Suspense>
        </div>
    );
}
