"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useIssueCertificate } from "@/hooks/useCertificates";
import { usePermissions } from "@/providers/PermissionProvider";
import { CERTIFICATE_TYPE_LABELS, CertificateType, IssueCertificateInput } from "@/types/Certificates";
import { PersonPicker } from "@/components/dashboard/certificates/PersonPicker";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorState } from "@/components/feedback/ErrorState";

const SELECT_CLASS = "w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-transparent px-3 py-2 text-sm";

export default function IssueCertificatePage() {
    const router = useRouter();
    const { can } = usePermissions();
    const issue = useIssueCertificate();

    // Transfer and experience certificates need the approver permission.
    const allowed = (Object.keys(CERTIFICATE_TYPE_LABELS) as CertificateType[]).filter((t) =>
        t === "transfer" || t === "experience" ? can("approve_certificates") : can("issue_certificates")
    );
    const [type, setType] = useState<CertificateType | "">("");
    const [personId, setPersonId] = useState("");
    const [reason, setReason] = useState("");
    const [conduct, setConduct] = useState("");
    const [leavingDate, setLeavingDate] = useState("");
    const [periodEnd, setPeriodEnd] = useState("");
    const [errors, setErrors] = useState<Record<string, string>>({});

    if (allowed.length === 0) {
        return <ErrorState message="You do not have permission to issue certificates." />;
    }

    const selected = type || allowed[0];
    const isStaff = selected === "experience";

    const submit = (event: React.FormEvent) => {
        event.preventDefault();
        const next: Record<string, string> = {};
        if (!personId) next.person = isStaff ? "Select a staff member." : "Select a student.";
        if (selected === "transfer") {
            if (!leavingDate) next.leaving_date = "Enter the leaving date.";
            if (!reason.trim()) next.reason = "Enter the reason for leaving.";
        }
        if (selected === "character" && !conduct.trim()) next.conduct = "Enter the conduct.";
        if (isStaff && !periodEnd) next.period_end = "Enter the employment end date.";
        setErrors(next);
        if (Object.keys(next).length) return;

        const input: IssueCertificateInput = {
            certificate_type: selected,
            ...(isStaff ? { staff_id: personId } : { student_id: personId }),
            reason: reason.trim(),
            conduct: conduct.trim(),
            leaving_date: selected === "transfer" ? leavingDate : null,
            period_end: isStaff ? periodEnd : null,
        };
        issue.mutate(input, { onSuccess: (cert) => router.push(`/dashboard/certificates/${cert.id}`) });
    };

    return (
        <div className="space-y-6 max-w-2xl">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Issue certificate</h1>
            <form onSubmit={submit} className="space-y-5" noValidate>
                <div className="space-y-2">
                    <Label htmlFor="type">Certificate type</Label>
                    <select
                        id="type"
                        className={SELECT_CLASS}
                        value={selected}
                        onChange={(e) => {
                            setType(e.target.value as CertificateType);
                            setPersonId("");
                            setErrors({});
                        }}
                    >
                        {allowed.map((t) => (
                            <option key={t} value={t}>
                                {CERTIFICATE_TYPE_LABELS[t]}
                            </option>
                        ))}
                    </select>
                </div>

                <PersonPicker
                    key={selected}
                    kind={isStaff ? "staff" : "student"}
                    value={personId}
                    onChange={setPersonId}
                    error={errors.person}
                    studentStatus={selected === "transfer" ? "transferred,withdrawn" : selected === "bonafide" ? "active" : ""}
                    staffActive={isStaff ? false : undefined}
                />

                {selected === "transfer" && (
                    <>
                        <p className="text-xs text-slate-500">
                            A transfer certificate needs the student&apos;s exit to be recorded in Promotion &amp; Transfer (status Transferred or Withdrawn). Issuing it does not change the student record. If a student is missing from this list, their exit was not recorded there - ask the school owner.
                        </p>
                        <div className="space-y-2">
                            <Label htmlFor="leaving_date">Leaving date</Label>
                            <Input id="leaving_date" type="date" value={leavingDate} onChange={(e) => setLeavingDate(e.target.value)} />
                            {errors.leaving_date && <p className="text-xs text-red-600">{errors.leaving_date}</p>}
                        </div>
                    </>
                )}

                {isStaff && (
                    <>
                        <p className="text-xs text-slate-500">
                            Only staff who are no longer active are listed. The start date is taken from the staff record&apos;s joining date. The staff record holds no exit date, so the end date below is entered by you and recorded as such.
                        </p>
                        <div className="space-y-2">
                            <Label htmlFor="period_end">Employed until</Label>
                            <Input id="period_end" type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
                            {errors.period_end && <p className="text-xs text-red-600">{errors.period_end}</p>}
                        </div>
                    </>
                )}

                {(selected === "transfer" || selected === "bonafide") && (
                    <div className="space-y-2">
                        <Label htmlFor="reason">{selected === "transfer" ? "Reason for leaving" : "Purpose (optional)"}</Label>
                        <Input id="reason" value={reason} maxLength={255} onChange={(e) => setReason(e.target.value)} />
                        {errors.reason && <p className="text-xs text-red-600">{errors.reason}</p>}
                    </div>
                )}

                {(selected === "transfer" || selected === "character" || selected === "experience") && (
                    <div className="space-y-2">
                        <Label htmlFor="conduct">{selected === "experience" ? "Conduct and performance (optional)" : selected === "transfer" ? "Conduct (optional)" : "Conduct"}</Label>
                        <Input id="conduct" value={conduct} maxLength={100} onChange={(e) => setConduct(e.target.value)} />
                        {errors.conduct && <p className="text-xs text-red-600">{errors.conduct}</p>}
                    </div>
                )}

                <div className="flex gap-3">
                    <Button type="submit" disabled={issue.isPending}>
                        {issue.isPending ? "Issuing..." : "Issue certificate"}
                    </Button>
                    <Button type="button" variant="outline" disabled={issue.isPending} onClick={() => router.back()}>
                        Cancel
                    </Button>
                </div>
            </form>
        </div>
    );
}
