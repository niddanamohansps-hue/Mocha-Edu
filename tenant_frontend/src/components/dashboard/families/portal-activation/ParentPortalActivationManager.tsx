"use client";

import { useState } from "react";
import { usePermissions } from "@/providers/PermissionProvider";
import Unauthorized from "@/components/Unauthorized";
import { cn } from "@/lib/utils";
import { useParentCredentials } from "@/hooks/useFamilies";

import ParentActivationTab from "./ParentActivationTab";
import ParentDistributionTab from "./ParentDistributionTab";

export default function ParentPortalActivationManager() {
    const { can, isOwner } = usePermissions();

    const [activeTab, setActiveTab] = useState<"activation" | "distribution">("activation");

    // Queries (for badge count)
    const { data: pendingCreds } = useParentCredentials();

    const canManage = isOwner || can("change_family");

    if (!canManage) {
        return <Unauthorized />;
    }

    return (
        <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 pb-20">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div className="space-y-1">
                    <h1 className="text-3xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                        Parent Portal Access
                    </h1>
                    <p className="text-lg text-slate-500 dark:text-slate-400">
                        Provision parent identities and distribute onboarding credentials.
                    </p>
                </div>
            </div>

            {/* Custom Tabs */}
            <div className="flex p-1 bg-slate-100 dark:bg-slate-800/50 rounded-2xl w-fit">
                <button
                    type="button"
                    onClick={() => setActiveTab("activation")}
                    className={cn(
                        "px-6 py-2.5 rounded-xl font-bold transition-all flex items-center gap-2 text-sm cursor-pointer",
                        activeTab === "activation"
                            ? "bg-white dark:bg-slate-900 text-primary shadow-xs"
                            : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                    )}
                >
                    Account Setup
                </button>
                <button
                    type="button"
                    onClick={() => setActiveTab("distribution")}
                    className={cn(
                        "px-6 py-2.5 rounded-xl font-bold transition-all flex items-center gap-2 text-sm cursor-pointer",
                        activeTab === "distribution"
                            ? "bg-white dark:bg-slate-900 text-primary shadow-xs"
                            : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                    )}
                >
                    Distribution List
                    {pendingCreds && pendingCreds.length > 0 && (
                        <span className="ml-1 px-2 py-0.5 bg-primary text-white text-[10px] rounded-full">
                            {pendingCreds.length}
                        </span>
                    )}
                </button>
            </div>

            {activeTab === "activation" ? (
                <ParentActivationTab onSuccess={() => setActiveTab("distribution")} />
            ) : (
                <ParentDistributionTab />
            )}
        </div>
    );
}

