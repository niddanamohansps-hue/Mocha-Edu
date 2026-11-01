"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCreateApplicant } from "@/hooks/useRecruitment";
import type { JobOpening } from "@/types/Recruitment";

const selectClass =
    "h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";

export function AddApplicantDialog({
    openings,
    defaultOpening,
    onClose,
}: {
    openings: JobOpening[];
    defaultOpening?: string;
    onClose: () => void;
}) {
    const create = useCreateApplicant();
    const accepting = openings.filter((o) => o.accepting_applications);
    const [opening, setOpening] = useState(
        accepting.find((o) => o.id === defaultOpening)?.id ?? accepting[0]?.id ?? "",
    );
    const [values, setValues] = useState<Record<string, string>>({ experience_years: "0" });
    const [resume, setResume] = useState<File | null>(null);
    const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
        setValues((v) => ({ ...v, [key]: e.target.value }));

    const submit = () => {
        const form = new FormData();
        form.append("opening", opening);
        Object.entries(values).forEach(([key, value]) => value !== "" && form.append(key, value));
        if (resume) form.append("resume", resume);
        create.mutate(form, { onSuccess: onClose });
    };

    return (
        <Dialog open onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Add applicant</DialogTitle>
                </DialogHeader>
                {accepting.length === 0 ? (
                    <p className="text-sm text-slate-500">
                        No opening is accepting applications. Publish an opening first (and check its last date).
                    </p>
                ) : (
                    <div className="grid gap-4">
                        <div className="grid gap-1.5">
                            <Label>Opening</Label>
                            <select className={selectClass} value={opening} onChange={(e) => setOpening(e.target.value)}>
                                {accepting.map((o) => (
                                    <option key={o.id} value={o.id}>
                                        {o.title}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="grid gap-1.5">
                                <Label>First name</Label>
                                <Input onChange={set("first_name")} />
                            </div>
                            <div className="grid gap-1.5">
                                <Label>Last name</Label>
                                <Input onChange={set("last_name")} />
                            </div>
                            <div className="grid gap-1.5">
                                <Label>Email</Label>
                                <Input type="email" onChange={set("email")} />
                            </div>
                            <div className="grid gap-1.5">
                                <Label>Phone</Label>
                                <Input onChange={set("phone")} />
                            </div>
                            <div className="grid gap-1.5">
                                <Label>Gender</Label>
                                <select className={selectClass} defaultValue="" onChange={set("gender")}>
                                    <option value="">Not stated</option>
                                    <option value="male">Male</option>
                                    <option value="female">Female</option>
                                    <option value="other">Other</option>
                                </select>
                            </div>
                            <div className="grid gap-1.5">
                                <Label>Date of birth</Label>
                                <Input type="date" onChange={set("date_of_birth")} />
                            </div>
                            <div className="grid gap-1.5">
                                <Label>Qualification</Label>
                                <Input onChange={set("qualification")} />
                            </div>
                            <div className="grid gap-1.5">
                                <Label>Experience (years)</Label>
                                <Input type="number" min={0} defaultValue={0} onChange={set("experience_years")} />
                            </div>
                            <div className="grid gap-1.5">
                                <Label>Current employer</Label>
                                <Input onChange={set("current_employer")} />
                            </div>
                            <div className="grid gap-1.5">
                                <Label>Expected salary</Label>
                                <Input type="number" min={0} onChange={set("expected_salary")} />
                            </div>
                        </div>
                        <div className="grid gap-1.5">
                            <Label>Source</Label>
                            <Input placeholder="Newspaper, referral, walk-in..." onChange={set("source")} />
                        </div>
                        <div className="grid gap-1.5">
                            <Label>Notes</Label>
                            <Textarea rows={2} onChange={set("cover_note")} />
                        </div>
                        <div className="grid gap-1.5">
                            <Label>Resume (PDF, DOC or DOCX, up to 5 MB)</Label>
                            <Input type="file" accept=".pdf,.doc,.docx" onChange={(e) => setResume(e.target.files?.[0] ?? null)} />
                        </div>
                    </div>
                )}
                <DialogFooter>
                    <Button variant="outline" onClick={onClose}>
                        Cancel
                    </Button>
                    <Button
                        onClick={submit}
                        disabled={!opening || !values.first_name?.trim() || !values.last_name?.trim() || create.isPending}
                    >
                        {create.isPending ? "Saving..." : "Add applicant"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
