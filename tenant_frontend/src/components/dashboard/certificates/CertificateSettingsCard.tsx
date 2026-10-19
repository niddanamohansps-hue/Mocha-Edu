"use client";

import { useState } from "react";
import { useCertificateSettings, useUpdateCertificateSettings } from "@/hooks/useCertificates";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";

function SettingsForm({ initial }: { initial: { signatory_name: string; signatory_title: string; has_signature: boolean } }) {
    const update = useUpdateCertificateSettings();
    const [name, setName] = useState(initial.signatory_name);
    const [title, setTitle] = useState(initial.signatory_title);
    const [file, setFile] = useState<File | null>(null);

    return (
        <form
            className="space-y-4 max-w-md"
            onSubmit={(e) => {
                e.preventDefault();
                update.mutate({ signatory_name: name.trim(), signatory_title: title.trim(), signature: file });
            }}
        >
            <div className="space-y-2">
                <Label htmlFor="signatory_name">Signatory name</Label>
                <Input id="signatory_name" value={name} maxLength={150} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-2">
                <Label htmlFor="signatory_title">Signatory title</Label>
                <Input id="signatory_title" value={title} maxLength={150} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="space-y-2">
                <Label htmlFor="signature">Signature image {initial.has_signature ? "(one is on file; choose a file to replace it)" : ""}</Label>
                <Input id="signature" type="file" accept="image/png,image/jpeg" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </div>
            <Button type="submit" disabled={update.isPending}>
                {update.isPending ? "Saving..." : "Save settings"}
            </Button>
        </form>
    );
}

export function CertificateSettingsCard() {
    const { data, isLoading, isError, refetch } = useCertificateSettings();
    return (
        <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-4">
            <div>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Certificate settings</h2>
                <p className="text-sm text-slate-500">Printed above the signature line on every certificate.</p>
            </div>
            {isLoading ? (
                <LoadingState className="py-8" />
            ) : isError || !data ? (
                <ErrorState message="Failed to load settings." onRetry={refetch} />
            ) : (
                <SettingsForm initial={data} />
            )}
        </section>
    );
}
