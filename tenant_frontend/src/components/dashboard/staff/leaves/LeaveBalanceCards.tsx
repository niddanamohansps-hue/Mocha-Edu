"use client";

import React from "react";
import { StaffLeaveBalance } from "@/types/Leave";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Calendar, Clock, CheckCircle2, AlertCircle } from "lucide-react";

interface LeaveBalanceCardsProps {
    balances: StaffLeaveBalance[];
    isLoading?: boolean;
}

export function LeaveBalanceCards({ balances, isLoading }: LeaveBalanceCardsProps) {
    if (isLoading) {
        return (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse">
                {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="h-32 bg-slate-100 dark:bg-slate-800 rounded-xl" />
                ))}
            </div>
        );
    }

    if (!balances || balances.length === 0) {
        return (
            <div className="p-6 text-center rounded-xl border border-dashed border-slate-200 dark:border-slate-800 text-slate-500">
                <Calendar className="w-8 h-8 mx-auto mb-2 opacity-40" />
                <p className="text-sm font-medium">No leave quotas allocated for this academic year.</p>
            </div>
        );
    }

    return (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {balances.map((bal) => {
                const available = parseFloat(String(bal.available_days || 0));
                const used = parseFloat(String(bal.used_days || 0));
                const pending = parseFloat(String(bal.pending_days || 0));
                const total = parseFloat(String(bal.allocated_days || 0));
                const pct = total > 0 ? Math.min(100, Math.round((available / total) * 100)) : 0;

                return (
                    <Card key={bal.id} className="border border-slate-200 dark:border-slate-800 shadow-sm relative overflow-hidden">
                        <div
                            className={`h-1.5 w-full ${
                                available > 3 ? "bg-emerald-500" : available > 0 ? "bg-amber-500" : "bg-rose-500"
                            }`}
                        />
                        <CardContent className="p-4 space-y-3">
                            <div className="flex flex-wrap items-start justify-between gap-2">
                                <div>
                                    <div className="flex items-center gap-2">
                                        <h3 className="font-bold text-slate-900 dark:text-white text-base">{bal.leave_type_name}</h3>
                                        <Badge variant="outline" className="text-[10px] font-mono px-1.5 py-0">
                                            {bal.leave_type_code}
                                        </Badge>
                                    </div>
                                    <p className="text-xs text-slate-500 mt-0.5">
                                        {bal.is_paid ? "Paid Leave" : "Unpaid (LWP)"}
                                    </p>
                                </div>
                                <span className="text-2xl font-extrabold text-slate-900 dark:text-white">
                                    {available}
                                    <span className="text-xs font-normal text-slate-500 ml-1">days left</span>
                                </span>
                            </div>

                            {/* Progress bar */}
                            <div className="space-y-1">
                                <div className="flex flex-wrap justify-between gap-2 text-[11px] text-slate-500 font-medium">
                                    <span>Remaining</span>
                                    <span>{pct}%</span>
                                </div>
                                <div className="h-1.5 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                                    <div
                                        className={`h-full rounded-full transition-all ${
                                            available > 3 ? "bg-emerald-500" : available > 0 ? "bg-amber-500" : "bg-rose-500"
                                        }`}
                                        style={{ width: `${pct}%` }}
                                    />
                                </div>
                            </div>

                            {/* Balance Breakdown */}
                            <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-100 dark:border-slate-800/80 text-[11px]">
                                <div>
                                    <span className="text-slate-400 block">Total</span>
                                    <span className="font-semibold text-slate-700 dark:text-slate-300">{total}d</span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block">Used</span>
                                    <span className="font-semibold text-slate-700 dark:text-slate-300">{used}d</span>
                                </div>
                                <div>
                                    <span className="text-slate-400 block">Pending</span>
                                    <span className={`font-semibold ${pending > 0 ? "text-amber-600 dark:text-amber-400" : "text-slate-700 dark:text-slate-300"}`}>
                                        {pending}d
                                    </span>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                );
            })}
        </div>
    );
}

