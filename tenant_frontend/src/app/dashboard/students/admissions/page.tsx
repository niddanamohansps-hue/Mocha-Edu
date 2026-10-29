"use client";

import React, { useState } from "react";
import { usePermissions } from "@/providers/PermissionProvider";
import Unauthorized from "@/components/Unauthorized";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import AdmissionsStatsCards from "@/components/dashboard/admissions/AdmissionsStatsCards";
import ApplicationsTab from "@/components/dashboard/admissions/ApplicationsTab";
import EnquiriesTab from "@/components/dashboard/admissions/EnquiriesTab";
import AdmissionWizard from "@/components/dashboard/students/AdmissionWizard";
import NewApplicationDialog from "@/components/dashboard/admissions/NewApplicationDialog";
import EnquiryDialog from "@/components/dashboard/admissions/EnquiryDialog";
import { useAdmissionsDashboard } from "@/hooks/useAdmissions";
import { Button } from "@/components/ui/button";
import {
    GraduationCap,
    UserPlus,
    Inbox,
    Layers,
    Sparkles,
    Plus,
    PhoneCall,
    FileText,
} from "lucide-react";

export default function AdmissionsPage() {
    const { can, isOwner } = usePermissions();

    const canViewAdmissions =
        isOwner ||
        can("view_admissions") ||
        can("manage_admission_applications") ||
        can("manage_admission_enquiries") ||
        can("add_student");

    const canManageApplications = isOwner || can("manage_admission_applications");
    const canManageEnquiries = isOwner || can("manage_admission_enquiries");

    const [activeTab, setActiveTab] = useState<string>("applications");
    const [isNewApplicationOpen, setIsNewApplicationOpen] = useState(false);
    const [isNewEnquiryOpen, setIsNewEnquiryOpen] = useState(false);

    // Live Admissions Dashboard stats from backend API
    const { data: stats, isLoading: statsLoading } = useAdmissionsDashboard();

    if (!canViewAdmissions) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-6 pb-12 max-w-7xl mx-auto animate-in fade-in duration-500">
            {/* 1. Page Header with Clean Action Strip */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <GraduationCap className="w-7 h-7 text-sky-600 dark:text-sky-400" />
                        <span>Admissions & Enrollment Hub</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Track prospective enquiries, manage multi-stage application reviews, verify documents, and enroll qualified students
                    </p>
                </div>

                {/* Primary Action Buttons */}
                <div className="flex items-center gap-2.5 shrink-0">
                    {canManageEnquiries && (
                        <Button
                            onClick={() => setIsNewEnquiryOpen(true)}
                            variant="outline"
                            size="sm"
                            className="h-9 px-3 gap-1.5 border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 text-xs font-semibold cursor-pointer shadow-2xs"
                        >
                            <PhoneCall className="h-3.5 w-3.5 text-slate-500" />
                            <span>New Enquiry</span>
                        </Button>
                    )}
                    {canManageApplications && (
                        <Button
                            onClick={() => setIsNewApplicationOpen(true)}
                            size="sm"
                            className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95"
                        >
                            <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                            <span>New Application</span>
                        </Button>
                    )}
                </div>
            </div>

            {/* 2. Top Metric Cards (High-Density Enterprise KPI Cards) */}
            <AdmissionsStatsCards stats={stats} isLoading={statsLoading} />

            {/* 3. Main Operational Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-5">
                <div className="border-b border-slate-200 dark:border-slate-800">
                    <TabsList className="bg-transparent h-11 p-0 gap-6">
                        <TabsTrigger
                            value="applications"
                            className="h-11 rounded-none border-b-2 border-transparent px-1 font-semibold text-xs text-slate-500 data-[state=active]:border-sky-600 data-[state=active]:text-sky-600 dark:data-[state=active]:text-sky-400 transition-all flex items-center gap-2 cursor-pointer"
                        >
                            <Layers className="w-4 h-4" />
                            <span>Application Pipeline</span>
                        </TabsTrigger>
                        <TabsTrigger
                            value="enquiries"
                            className="h-11 rounded-none border-b-2 border-transparent px-1 font-semibold text-xs text-slate-500 data-[state=active]:border-sky-600 data-[state=active]:text-sky-600 dark:data-[state=active]:text-sky-400 transition-all flex items-center gap-2 cursor-pointer"
                        >
                            <Inbox className="w-4 h-4" />
                            <span>Enquiries & Follow-ups</span>
                        </TabsTrigger>
                        <TabsTrigger
                            value="direct_wizard"
                            className="h-11 rounded-none border-b-2 border-transparent px-1 font-semibold text-xs text-slate-500 data-[state=active]:border-sky-600 data-[state=active]:text-sky-600 dark:data-[state=active]:text-sky-400 transition-all flex items-center gap-2 cursor-pointer"
                        >
                            <UserPlus className="w-4 h-4" />
                            <span>Direct Walk-in Admission</span>
                        </TabsTrigger>
                    </TabsList>
                </div>

                <TabsContent value="applications" className="space-y-5 outline-none">
                    <ApplicationsTab />
                </TabsContent>

                <TabsContent value="enquiries" className="space-y-5 outline-none">
                    <EnquiriesTab />
                </TabsContent>

                <TabsContent value="direct_wizard" className="outline-none">
                    <div className="bg-white dark:bg-slate-900 rounded-2xl p-6 sm:p-8 border border-slate-200/80 dark:border-slate-800 shadow-2xs space-y-4">
                        <div className="flex items-center gap-3 pb-4 border-b border-slate-100 dark:border-slate-800">
                            <div className="p-2 rounded-xl bg-emerald-50 dark:bg-emerald-900/30 text-emerald-600">
                                <Sparkles className="w-5 h-5" />
                            </div>
                            <div>
                                <h3 className="text-base font-bold text-slate-800 dark:text-white">
                                    Register a walk-in student
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

            {/* Quick Header Modals */}
            <NewApplicationDialog
                open={isNewApplicationOpen}
                onOpenChange={setIsNewApplicationOpen}
            />

            <EnquiryDialog
                open={isNewEnquiryOpen}
                onOpenChange={setIsNewEnquiryOpen}
            />
        </div>
    );
}
