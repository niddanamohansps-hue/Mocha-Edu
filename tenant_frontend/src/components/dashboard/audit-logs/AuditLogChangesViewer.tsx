"use client";

import React, { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Code, Eye, ArrowRight } from "lucide-react";

interface AuditLogChangesViewerProps {
    changes: Record<string, any> | null | undefined;
}

function formatValue(value: any): string {
    if (value === null || value === undefined) return "(empty)";
    if (typeof value === "boolean") return value ? "true" : "false";
    if (typeof value === "object") {
        try {
            return JSON.stringify(value, null, 2);
        } catch {
            return String(value);
        }
    }
    return String(value);
}

function isDiffEntry(val: any): val is { old?: any; new?: any } {
    return (
        typeof val === "object" &&
        val !== null &&
        ("old" in val || "new" in val)
    );
}

export function AuditLogChangesViewer({ changes }: AuditLogChangesViewerProps) {
    const [showRawJson, setShowRawJson] = useState(false);

    if (!changes || Object.keys(changes).length === 0) {
        return (
            <div className="p-4 rounded-lg bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800 text-sm text-slate-500 italic">
                No change payload recorded for this event.
            </div>
        );
    }

    const entries = Object.entries(changes);

    return (
        <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Changes ({entries.length} {entries.length === 1 ? "field" : "fields"})
                </span>
                <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    onClick={() => setShowRawJson(!showRawJson)}
                >
                    {showRawJson ? (
                        <>
                            <Eye className="w-3.5 h-3.5 mr-1" />
                            Formatted View
                        </>
                    ) : (
                        <>
                            <Code className="w-3.5 h-3.5 mr-1" />
                            Raw JSON
                        </>
                    )}
                </Button>
            </div>

            {showRawJson ? (
                <pre className="p-3 bg-slate-950 text-slate-100 rounded-md text-xs font-mono overflow-x-auto max-h-80 border border-slate-800">
                    {JSON.stringify(changes, null, 2)}
                </pre>
            ) : (
                <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
                    {entries.map(([field, value]) => {
                        const isDiff = isDiffEntry(value);

                        return (
                            <div
                                key={field}
                                className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 shadow-xs space-y-2"
                            >
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                    <span className="font-medium text-xs text-slate-900 dark:text-slate-100 font-mono">
                                        {field}
                                    </span>
                                    {isDiff && (
                                        <Badge variant="outline" className="text-[10px] uppercase font-semibold">
                                            Modified
                                        </Badge>
                                    )}
                                </div>

                                {isDiff ? (
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                                        <div className="p-2 rounded bg-rose-50/70 dark:bg-rose-950/30 border border-rose-200/60 dark:border-rose-900/40">
                                            <span className="text-[10px] font-semibold uppercase tracking-wider text-rose-700 dark:text-rose-400 block mb-1">
                                                Old Value
                                            </span>
                                            <div className="font-mono text-rose-900 dark:text-rose-200 break-all whitespace-pre-wrap">
                                                {formatValue(value.old)}
                                            </div>
                                        </div>
                                        <div className="p-2 rounded bg-emerald-50/70 dark:bg-emerald-950/30 border border-emerald-200/60 dark:border-emerald-900/40">
                                            <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-400 block mb-1 flex items-center gap-1">
                                                <ArrowRight className="w-2.5 h-2.5" />
                                                New Value
                                            </span>
                                            <div className="font-mono text-emerald-900 dark:text-emerald-200 break-all whitespace-pre-wrap">
                                                {formatValue(value.new)}
                                            </div>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="p-2 rounded bg-slate-50 dark:bg-slate-800/40 font-mono text-xs text-slate-800 dark:text-slate-200 break-all whitespace-pre-wrap">
                                        {formatValue(value)}
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

