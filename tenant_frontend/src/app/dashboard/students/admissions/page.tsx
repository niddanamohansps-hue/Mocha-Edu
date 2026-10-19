"use client";

import React, { useState } from "react";
import { usePermissions } from "@/providers/PermissionProvider";
import Unauthorized from "@/components/Unauthorized";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import AdmissionsStatsCards from "@/components/dashboard/admissions/AdmissionsStatsCards";
import ApplicationsTab from "@/components/dashboard/admissions/ApplicationsTab";
import EnquiriesTab from "@/components/dashboard/admissions/EnquiriesTab";
import AdmissionWizard from "@/components/dashboard/students/AdmissionWizard";
import {
    GraduationCap,
    Users,
    UserPlus,
    Inbox,
    Layers,
    Sparkles,
} from "lucide-react";

export default function AdmissionsPage() {
    const { can, isOwner } = usePermissions();

    const canViewAdmissions =
        isOwner ||
        can("view_admissions") ||
        can("manage_admission_applications") ||
        can("manage_admission_enquiries") ||
        can("add_student");

    const [activeTab, setActiveTab] = useState<string>("applications");

    if (!canViewAdmissions) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-8 pb-12 max-w-7xl mx-auto">
            {/* Page Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                    <div className="flex items-center gap-2.5">
                        <div className="p-2 rounded-xl bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400">
                            <GraduationCap className="w-6 h-6" />
                        </div>
                        <h1 className="text-2xl sm:text-3xl font-black text-slate-900 dark:text-white tracking-tight">
                            Admissions Management Pipeline
                        </h1>
                    </div>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1.5 ml-1">
                        Track prospective enquiries, manage multi-stage application reviews, verify documentation, and enroll qualified students.
                    </p>
                </div>
            </div>

            {/* Top Metric Cards */}
            <AdmissionsStatsCards />

            {/* Main Tabs Container */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
                <div className="border-b border-slate-200 dark:border-slate-800">
                    <TabsList className="bg-transparent h-12 p-0 gap-6">
                        <TabsTrigger
                            value="applications"
                            className="h-12 rounded-none border-b-2 border-transparent px-2 font-bold text-sm text-slate-500 data-[state=active]:border-blue-600 data-[state=active]:text-blue-600 dark:data-[state=active]:text-blue-400 transition-all flex items-center gap-2"
                        >
                            <Layers className="w-4 h-4" />
                            Application Pipeline
                        </TabsTrigger>
                        <TabsTrigger
                            value="enquiries"
                            className="h-12 rounded-none border-b-2 border-transparent px-2 font-bold text-sm text-slate-500 data-[state=active]:border-blue-600 data-[state=active]:text-blue-600 dark:data-[state=active]:text-blue-400 transition-all flex items-center gap-2"
                        >
                            <Inbox className="w-4 h-4" />
                            Enquiries & Follow-ups
                        </TabsTrigger>
                        <TabsTrigger
                            value="direct_wizard"
                            className="h-12 rounded-none border-b-2 border-transparent px-2 font-bold text-sm text-slate-500 data-[state=active]:border-blue-600 data-[state=active]:text-blue-600 dark:data-[state=active]:text-blue-400 transition-all flex items-center gap-2"
                        >
                            <UserPlus className="w-4 h-4" />
                            Direct Walk-in Admission
                        </TabsTrigger>
                    </TabsList>
                </div>

                <TabsContent value="applications" className="space-y-6 mt-6 outline-none">
                    <ApplicationsTab />
                </TabsContent>

                <TabsContent value="enquiries" className="space-y-6 mt-6 outline-none">
                    <EnquiriesTab />
                </TabsContent>

                <TabsContent value="direct_wizard" className="mt-6 outline-none">
                    <div className="bg-white dark:bg-slate-900 rounded-3xl p-6 sm:p-8 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
                        <div className="flex items-center gap-3 pb-4 border-b border-slate-100 dark:border-slate-800">
                            <div className="p-2 rounded-xl bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600">
                                <Sparkles className="w-5 h-5" />
                            </div>
                            <div>
                                <h3 className="text-base font-bold text-slate-800 dark:text-white">
                                    Direct Walk-in Registration
                                </h3>
                                <p className="text-xs text-slate-500">
                                    Quick manual student registration wizard for on-the-spot walk-in admissions without prior online application.
                                </p>
                            </div>
                        </div>
                        <AdmissionWizard />
                    </div>
                </TabsContent>
            </Tabs>
        </div>
    );
}
