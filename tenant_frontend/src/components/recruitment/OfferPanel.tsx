"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useSaveOffer, useSendOffer } from "@/hooks/useRecruitment";
import type { Applicant } from "@/types/Recruitment";

/** The terms of the offer, the printable letter, and emailing it. Shown while the applicant is at the offered stage. */
export function OfferPanel({ applicant }: { applicant: Applicant }) {
    const save = useSaveOffer();
    const send = useSendOffer();
    const [designation, setDesignation] = useState(applicant.offered_designation || applicant.opening_title);
    const [salary, setSalary] = useState(applicant.offered_salary ? String(Number(applicant.offered_salary)) : "");
    const [joining, setJoining] = useState(applicant.offered_joining_date || "");
    const [validUntil, setValidUntil] = useState(applicant.offer_valid_until || "");
    const [notes, setNotes] = useState(applicant.offer_notes);
    const hasTerms = applicant.offered_salary !== null;

    return (
        <section className="space-y-3 rounded-lg border border-indigo-200 p-4 dark:border-indigo-900">
            <h3 className="text-sm font-semibold">Offer letter</h3>
            <p className="text-xs text-slate-500">
                Set the terms, then print the letter or email it to the candidate. Hiring starts from these terms.
            </p>
            <div className="grid grid-cols-2 gap-3">
                <div className="grid gap-1.5">
                    <Label>Position</Label>
                    <Input value={designation} onChange={(e) => setDesignation(e.target.value)} />
                </div>
                <div className="grid gap-1.5">
                    <Label>Monthly salary</Label>
                    <Input type="number" min={0} value={salary} onChange={(e) => setSalary(e.target.value)} />
                </div>
                <div className="grid gap-1.5">
                    <Label>Joining date</Label>
                    <Input type="date" value={joining} onChange={(e) => setJoining(e.target.value)} />
                </div>
                <div className="grid gap-1.5">
                    <Label>Offer open until (optional)</Label>
                    <Input type="date" value={validUntil} onChange={(e) => setValidUntil(e.target.value)} />
                </div>
            </div>
            <div className="grid gap-1.5">
                <Label>Extra terms (optional)</Label>
                <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="For example: probation of six months applies." />
            </div>
            <div className="flex flex-wrap items-center gap-2">
                <Button
                    disabled={save.isPending || !salary || !joining}
                    onClick={() =>
                        save.mutate({ id: applicant.id, designation, salary, joining_date: joining, valid_until: validUntil || null, notes })
                    }
                >
                    {save.isPending ? "Saving..." : hasTerms ? "Update terms" : "Save terms"}
                </Button>
                {hasTerms && (
                    <>
                        <Button asChild variant="outline">
                            <Link href={`/dashboard/hr/recruit/offer/${applicant.id}`} target="_blank">Print letter</Link>
                        </Button>
                        <Button
                            variant="outline"
                            disabled={send.isPending || !applicant.email}
                            title={applicant.email ? undefined : "This applicant has no email address"}
                            onClick={() => send.mutate(applicant.id)}
                        >
                            {send.isPending ? "Sending..." : applicant.offer_sent_at ? "Email again" : "Email to candidate"}
                        </Button>
                    </>
                )}
            </div>
            {hasTerms && (
                <p className="text-xs text-slate-500">
                    {applicant.offer_sent_at
                        ? `Emailed on ${new Date(applicant.offer_sent_at).toLocaleString()}.`
                        : "Not emailed yet. Changing the terms means the letter has to be sent again."}
                </p>
            )}
        </section>
    );
}
