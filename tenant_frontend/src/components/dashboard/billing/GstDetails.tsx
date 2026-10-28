"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import axiosInstance from "@/lib/axios";

/** GST state / union territory codes (the first two digits of a GSTIN). */
export const GST_STATES: Record<string, string> = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh", "05": "Uttarakhand",
    "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
    "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur", "15": "Mizoram", "16": "Tripura",
    "17": "Meghalaya", "18": "Assam", "19": "West Bengal", "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh",
    "23": "Madhya Pradesh", "24": "Gujarat", "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra",
    "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
};

const SELECT = "w-full h-10 rounded-md border border-slate-200 dark:border-slate-800 bg-transparent px-3 text-sm";

export function GstDetails({ state, gstin }: { state: string; gstin: string }) {
    const queryClient = useQueryClient();
    const [stateCode, setStateCode] = useState(state);
    const [gstNumber, setGstNumber] = useState(gstin);
    const [error, setError] = useState("");
    const save = useMutation({
        mutationFn: async () =>
            (await axiosInstance.put("/billing/my/gst/", { state: stateCode, gstin: gstNumber.trim() })).data as
                { billing_state: string; billing_gstin: string },
        onSuccess: (data) => {
            setStateCode(data.billing_state);
            setGstNumber(data.billing_gstin);
            setError("");
            queryClient.invalidateQueries({ queryKey: ["billing"] });
            toast.success("GST details saved. They are used on your next invoice.");
        },
        onError: (err: unknown) => {
            const data = (err as { response?: { data?: Record<string, string[]> } })?.response?.data;
            setError(data?.gstin?.[0] ?? data?.state?.[0] ?? "Could not save the GST details.");
        },
    });

    return (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 space-y-4">
            <div>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">GST details for invoices</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Add your GSTIN to claim input tax credit. Your state decides whether invoices show CGST + SGST or IGST.
                </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                    <Label htmlFor="gstin">GSTIN (optional)</Label>
                    <Input id="gstin" value={gstNumber} maxLength={15} placeholder="e.g. 29ABCDE1234F1Z5"
                        onChange={(e) => setGstNumber(e.target.value.toUpperCase())} />
                </div>
                <div className="space-y-1.5">
                    <Label htmlFor="gst-state">State</Label>
                    <select id="gst-state" className={SELECT} value={gstNumber.length >= 2 && GST_STATES[gstNumber.slice(0, 2)] ? gstNumber.slice(0, 2) : stateCode}
                        disabled={gstNumber.length >= 2 && !!GST_STATES[gstNumber.slice(0, 2)]}
                        onChange={(e) => setStateCode(e.target.value)}>
                        <option value="">Choose your state</option>
                        {Object.entries(GST_STATES).sort((a, b) => a[1].localeCompare(b[1])).map(([code, name]) => (
                            <option key={code} value={code}>{name}</option>
                        ))}
                    </select>
                </div>
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <Button onClick={() => save.mutate()} disabled={save.isPending}>Save GST details</Button>
        </div>
    );
}
