"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface ApplicationStatus {
    reference: string;
    position: string;
    applied_on: string;
    status: string;
    interview: { round: string; scheduled_at: string; mode: string; location_or_url: string } | null;
}

export default function CareerStatusPage() {
    const [reference, setReference] = useState("");
    const [code, setCode] = useState("");
    const [error, setError] = useState("");

    const check = useMutation({
        mutationFn: async () =>
            (await axiosInstance.post<ApplicationStatus>("/recruitment/public/status/", { reference, access_code: code })).data,
        onMutate: () => setError(""),
        onError: (e: unknown) => {
            const status = (e as { response?: { status?: number } })?.response?.status;
            setError(
                status === 404
                    ? "No application matches those details. Check the reference and access code from your confirmation."
                    : "Your application could not be checked right now. Please try again shortly.",
            );
        },
    });
    const result = check.data;

    return (
        <main className="h-screen overflow-y-auto bg-slate-50 px-4 py-10 dark:bg-slate-950">
            <div className="mx-auto max-w-md space-y-6">
                <header className="space-y-1">
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Check your application</h1>
                    <Link href="/careers" className="text-sm text-slate-500 underline">
                        Back to careers
                    </Link>
                </header>
                <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
                    <div className="grid gap-1.5">
                        <Label>Reference</Label>
                        <Input placeholder="JOB-1A2B3C4D" value={reference} onChange={(e) => setReference(e.target.value)} />
                    </div>
                    <div className="grid gap-1.5">
                        <Label>Access code</Label>
                        <Input value={code} onChange={(e) => setCode(e.target.value)} />
                    </div>
                    {error && <p className="text-sm text-red-600">{error}</p>}
                    <Button disabled={!reference.trim() || !code.trim() || check.isPending} onClick={() => check.mutate()}>
                        {check.isPending ? "Checking..." : "Check status"}
                    </Button>
                </section>
                {result && (
                    <section className="space-y-2 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
                        <p className="text-sm text-slate-500">{result.position}</p>
                        <p className="text-xl font-semibold text-slate-900 dark:text-white">{result.status}</p>
                        <p className="text-xs text-slate-500">Applied on {result.applied_on}</p>
                        {result.interview && (
                            <p className="rounded-lg bg-slate-50 p-3 text-sm dark:bg-slate-800">
                                {result.interview.round}: {new Date(result.interview.scheduled_at).toLocaleString()}
                                {result.interview.location_or_url ? ` - ${result.interview.location_or_url}` : ""}
                            </p>
                        )}
                    </section>
                )}
            </div>
        </main>
    );
}
