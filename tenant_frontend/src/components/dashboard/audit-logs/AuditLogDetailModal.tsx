"use client";

import React from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AuditLogItem } from "@/types/AuditLog";
import { AuditLogChangesViewer } from "./AuditLogChangesViewer";
import { format } from "date-fns";
import { User, Calendar, Database, Hash, Globe, Laptop, Shield } from "lucide-react";

interface AuditLogDetailModalProps {
    log: AuditLogItem | null;
    isOpen: boolean;
    onClose: () => void;
}

function getActionBadgeVariant(action: string): "default" | "secondary" | "destructive" | "outline" {
    const act = action.toLowerCase();
    if (act.includes("delete") || act.includes("remove") || act.includes("cancel") || act.includes("revers")) {
        return "destructive";
    }
    if (act.includes("create") || act.includes("add") || act.includes("enroll") || act.includes("publish")) {
        return "default";
    }
    if (act.includes("update") || act.includes("change") || act.includes("edit")) {
        return "secondary";
    }
    return "outline";
}

export function AuditLogDetailModal({ log, isOpen, onClose }: AuditLogDetailModalProps) {
    if (!log) return null;

    let formattedDate = log.created_at;
    try {
        formattedDate = format(new Date(log.created_at), "PPP 'at' pp (zzzz)");
    } catch {
        formattedDate = log.created_at;
    }

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader className="space-y-2 border-b border-slate-200 dark:border-slate-800 pb-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                            <Shield className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                            <DialogTitle className="text-xl font-bold font-mono tracking-tight text-slate-900 dark:text-white">
                                {log.action}
                            </DialogTitle>
                        </div>
                        <Badge variant={getActionBadgeVariant(log.action)} className="font-mono text-xs">
                            {log.model_name}
                        </Badge>
                    </div>
                    <DialogDescription className="text-xs text-slate-500 font-mono">
                        Event ID: {log.id}
                    </DialogDescription>
                </DialogHeader>

                <div className="py-4 space-y-5">
                    {/* Event Metadata Grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                        <div className="flex items-start gap-2 p-2.5 rounded-lg bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800">
                            <User className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                            <div className="min-w-0">
                                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 block">
                                    Actor
                                </span>
                                <span className="font-medium text-slate-900 dark:text-white truncate block">
                                    {log.actor_username || "System / Automated"}
                                </span>
                                {log.actor_id && (
                                    <span className="text-[10px] text-slate-400 font-mono truncate block">
                                        ID: {log.actor_id}
                                    </span>
                                )}
                            </div>
                        </div>

                        <div className="flex items-start gap-2 p-2.5 rounded-lg bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800">
                            <Calendar className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                            <div className="min-w-0">
                                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 block">
                                    Timestamp
                                </span>
                                <span className="font-medium text-slate-900 dark:text-white block">
                                    {formattedDate}
                                </span>
                            </div>
                        </div>

                        <div className="flex items-start gap-2 p-2.5 rounded-lg bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800">
                            <Database className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                            <div className="min-w-0">
                                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 block">
                                    Resource
                                </span>
                                <span className="font-medium text-slate-900 dark:text-white block">
                                    {log.model_name}
                                </span>
                                {log.object_id && (
                                    <span className="text-[10px] text-slate-500 font-mono truncate block flex items-center gap-1">
                                        <Hash className="w-2.5 h-2.5" />
                                        {log.object_id}
                                    </span>
                                )}
                            </div>
                        </div>

                        <div className="flex items-start gap-2 p-2.5 rounded-lg bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800">
                            <Globe className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                            <div className="min-w-0">
                                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 block">
                                    Network & Device
                                </span>
                                <span className="font-medium font-mono text-slate-900 dark:text-white block">
                                    IP: {log.ip_address || "Unavailable"}
                                </span>
                                {log.user_agent && (
                                    <span className="text-[10px] text-slate-400 truncate block mt-0.5" title={log.user_agent}>
                                        <Laptop className="w-2.5 h-2.5 inline mr-1" />
                                        {log.user_agent}
                                    </span>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Changes Section */}
                    <div className="border-t border-slate-200 dark:border-slate-800 pt-4">
                        <AuditLogChangesViewer changes={log.changes} />
                    </div>
                </div>

                <DialogFooter className="border-t border-slate-200 dark:border-slate-800 pt-3">
                    <Button variant="outline" onClick={onClose}>
                        Close
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

