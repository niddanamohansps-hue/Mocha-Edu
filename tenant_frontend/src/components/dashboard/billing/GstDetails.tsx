"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Building2, CheckCircle2, FileText, Loader2, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import axiosInstance from "@/lib/axios";

/** GST state / union territory codes (the first two digits of a GSTIN). */
export const GST_STATES: Record<string, string> = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
};

export function GstDetails({ state, gstin }: { state: string; gstin: string }) {
    const queryClient = useQueryClient();
    const [stateCode, setStateCode] = useState(state);
    const [gstNumber, setGstNumber] = useState(gstin);
    const [error, setError] = useState("");

    const detectedState = gstNumber.length >= 2 && GST_STATES[gstNumber.slice(0, 2)];
    const activeStateCode = detectedState ? gstNumber.slice(0, 2) : stateCode;

    const save = useMutation({
        mutationFn: async () =>
            (await axiosInstance.put("/billing/my/gst/", { state: activeStateCode, gstin: gstNumber.trim() })).data as {
                billing_state: string;
                billing_gstin: string;
            },
        onSuccess: (data) => {
            setStateCode(data.billing_state);
            setGstNumber(data.billing_gstin);
            setError("");
            queryClient.invalidateQueries({ queryKey: ["billing"] });
            toast.success("GST and institutional tax details saved. They will be reflected on your next tax invoice.");
        },
        onError: (err: unknown) => {
            const data = (err as { response?: { data?: Record<string, string[]> } })?.response?.data;
            setError(data?.gstin?.[0] ?? data?.state?.[0] ?? "Could not save the GST tax details.");
        },
    });

    return (
        <div className="rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-5 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400 border border-sky-100 dark:border-sky-900 shrink-0">
                        <Building2 className="h-5 w-5" />
                    </div>
                    <div>
                        <div className="flex items-center gap-2">
                            <h2 className="text-base font-semibold text-slate-900 dark:text-white">
                                Institutional GSTIN & Tax Details
                            </h2>
                            {gstin && (
                                <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300 text-[10px]">
                                    Configured
                                </Badge>
                            )}
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                            Add your school or trust GSTIN to claim Input Tax Credit (ITC). Your state jurisdiction determines CGST + SGST vs IGST.
                        </p>
                    </div>
                </div>

                <Button
                    size="sm"
                    onClick={() => save.mutate()}
                    disabled={save.isPending}
                    className="shrink-0 h-9 font-medium text-xs bg-sky-600 hover:bg-sky-700 text-white"
                >
                    {save.isPending ? (
                        <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
                    ) : (
                        <ShieldCheck className="h-3.5 w-3.5 mr-2" />
                    )}
                    Save Tax Details
                </Button>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                        <Label htmlFor="gstin" className="text-xs font-medium text-slate-700 dark:text-slate-300">
                            GSTIN (15 Digits)
                        </Label>
                        <span className="text-[11px] text-slate-400">Optional</span>
                    </div>
                    <Input
                        id="gstin"
                        value={gstNumber}
                        maxLength={15}
                        placeholder="e.g. 07AAAAA0000A1Z5"
                        className="font-mono text-xs uppercase h-9 border-slate-200 dark:border-slate-700 focus:ring-sky-500"
                        onChange={(e) => setGstNumber(e.target.value.toUpperCase())}
                    />
                    {detectedState && (
                        <p className="text-[11px] text-emerald-600 dark:text-emerald-400 flex items-center gap-1 mt-1">
                            <CheckCircle2 className="h-3 w-3" /> State detected from GSTIN: <span className="font-medium">{GST_STATES[gstNumber.slice(0, 2)]}</span>
                        </p>
                    )}
                </div>

                <div className="space-y-1.5">
                    <Label htmlFor="gst-state" className="text-xs font-medium text-slate-700 dark:text-slate-300">
                        State / Union Territory
                    </Label>
                    <select
                        id="gst-state"
                        className="w-full h-9 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500 disabled:opacity-75 disabled:cursor-not-allowed"
                        value={activeStateCode}
                        disabled={Boolean(detectedState)}
                        onChange={(e) => setStateCode(e.target.value)}
                    >
                        <option value="">Choose State Jurisdiction</option>
                        {Object.entries(GST_STATES)
                            .sort((a, b) => a[1].localeCompare(b[1]))
                            .map(([code, name]) => (
                                <option key={code} value={code}>
                                    {code} - {name}
                                </option>
                            ))}
                    </select>
                    <p className="text-[11px] text-slate-400 mt-1">
                        Determines intra-state vs inter-state GST breakdown on issued invoices.
                    </p>
                </div>
            </div>

            {error && (
                <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900 text-xs text-rose-700 dark:text-rose-300">
                    {error}
                </div>
            )}
        </div>
    );
}
