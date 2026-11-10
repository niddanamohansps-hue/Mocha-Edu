"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Briefcase, CheckCircle2, Loader2 } from "lucide-react";
import axiosInstance from "@/lib/axios";
import { recruitmentError } from "@/hooks/useRecruitment";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

interface Receipt {
    reference: string;
    access_code: string;
}

const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "";

interface TurnstileApi {
    render: (el: HTMLElement, options: { sitekey: string; callback: (token: string) => void; "expired-callback": () => void }) => string;
    reset: (id?: string) => void;
}

/** Cloudflare Turnstile. Renders only when a site key is configured; the server enforces it only when it has a secret. */
function CaptchaWidget({ onToken }: { onToken: (token: string) => void }) {
    const box = useRef<HTMLDivElement>(null);
    useEffect(() => {
        if (!TURNSTILE_SITE_KEY || !box.current) return;
        const el = box.current;
        const win = window as unknown as { turnstile?: TurnstileApi };
        const render = () => {
            if (win.turnstile && !el.hasChildNodes()) {
                win.turnstile.render(el, { sitekey: TURNSTILE_SITE_KEY, callback: onToken, "expired-callback": () => onToken("") });
            }
        };
        if (win.turnstile) {
            render();
            return;
        }
        let script = document.querySelector<HTMLScriptElement>("script[data-turnstile]");
        if (!script) {
            script = document.createElement("script");
            script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
            script.async = true;
            script.dataset.turnstile = "1";
            document.head.appendChild(script);
        }
        script.addEventListener("load", render);
        return () => script?.removeEventListener("load", render);
    }, [onToken]);
    return TURNSTILE_SITE_KEY ? <div ref={box} /> : null;
}

interface PublicOpening {
    id: string;
    title: string;
    position_type: "instructor" | "staff";
    department: string;
    specialization: string;
    description: string;
    requirements: string;
    min_experience_years: number;
    last_date: string | null;
}

export default function CareersPage() {
    const { data: openings = [], isLoading, isError } = useQuery({
        queryKey: ["careers", "openings"],
        queryFn: async () => (await axiosInstance.get<PublicOpening[]>("/recruitment/public/openings/")).data,
        staleTime: 5 * 60 * 1000,
    });
    const [applyingTo, setApplyingTo] = useState<PublicOpening | null>(null);
    const [done, setDone] = useState<Receipt | null>(null);

    return (
        <main className="h-screen overflow-y-auto bg-slate-50 px-4 py-10 dark:bg-slate-950">
            <div className="mx-auto max-w-3xl space-y-8">
                <header className="space-y-2">
                    <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Careers</h1>
                    <p className="text-slate-500 dark:text-slate-400">Join our team. These are the positions open right now.</p>
                </header>

                {done ? (
                    <div className="rounded-2xl border border-emerald-200 bg-white p-8 text-center dark:border-emerald-900 dark:bg-slate-900">
                        <CheckCircle2 className="mx-auto mb-3 h-10 w-10 text-emerald-500" />
                        <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Application received</h2>
                        <p className="mt-1 text-slate-500">Thank you. The school will contact you if your profile is shortlisted.</p>
                        <div className="mx-auto mt-5 max-w-sm space-y-1 rounded-xl bg-slate-50 p-4 text-left text-sm dark:bg-slate-800">
                            <p>
                                <span className="text-slate-500">Reference: </span>
                                <span className="font-mono font-semibold">{done.reference}</span>
                            </p>
                            <p>
                                <span className="text-slate-500">Access code: </span>
                                <span className="break-all font-mono font-semibold">{done.access_code}</span>
                            </p>
                            <p className="pt-1 text-xs text-slate-500">
                                Save these now. A copy is also emailed to you. You need both to check your application on the{" "}
                                <Link href="/careers/status" className="underline">
                                    status page
                                </Link>
                                .
                            </p>
                        </div>
                        <Button className="mt-5" variant="outline" onClick={() => setDone(null)}>
                            Back to positions
                        </Button>
                    </div>
                ) : applyingTo ? (
                    <ApplyForm opening={applyingTo} onBack={() => setApplyingTo(null)} onDone={(receipt) => { setApplyingTo(null); setDone(receipt); }} />
                ) : isLoading ? (
                    <div className="flex justify-center py-16">
                        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
                    </div>
                ) : isError ? (
                    <p className="text-center text-slate-500">Positions could not be loaded. Please try again later.</p>
                ) : openings.length === 0 ? (
                    <p className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-slate-500 dark:border-slate-800 dark:bg-slate-900">
                        There are no open positions at the moment. Please check back later.
                    </p>
                ) : (
                    <div className="space-y-4">
                        {openings.map((opening) => (
                            <article
                                key={opening.id}
                                className="space-y-3 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
                            >
                                <div className="flex items-start justify-between gap-4">
                                    <div>
                                        <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-900 dark:text-white">
                                            <Briefcase className="h-4 w-4 text-slate-400" /> {opening.title}
                                        </h2>
                                        <p className="text-sm text-slate-500">
                                            {[opening.department, opening.specialization].filter(Boolean).join(" - ") ||
                                                (opening.position_type === "instructor" ? "Teaching" : "Non-teaching")}
                                            {opening.min_experience_years > 0 && ` - ${opening.min_experience_years}+ years experience`}
                                            {opening.last_date && ` - apply by ${opening.last_date}`}
                                        </p>
                                    </div>
                                    <Button onClick={() => setApplyingTo(opening)}>Apply</Button>
                                </div>
                                {opening.description && <p className="whitespace-pre-line text-sm text-slate-600 dark:text-slate-300">{opening.description}</p>}
                                {opening.requirements && (
                                    <div className="text-sm">
                                        <span className="font-medium text-slate-700 dark:text-slate-200">Requirements: </span>
                                        <span className="whitespace-pre-line text-slate-600 dark:text-slate-300">{opening.requirements}</span>
                                    </div>
                                )}
                            </article>
                        ))}
                    </div>
                )}
            </div>
        </main>
    );
}

function ApplyForm({ opening, onBack, onDone }: { opening: PublicOpening; onBack: () => void; onDone: (receipt: Receipt) => void }) {
    const [values, setValues] = useState<Record<string, string>>({});
    const [resume, setResume] = useState<File | null>(null);
    const [error, setError] = useState("");
    const [captcha, setCaptcha] = useState("");
    const set = (key: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
        setValues((v) => ({ ...v, [key]: e.target.value }));

    const apply = useMutation({
        mutationFn: async () => {
            const form = new FormData();
            form.append("opening", opening.id);
            Object.entries(values).forEach(([key, value]) => value !== "" && form.append(key, value));
            if (resume) form.append("resume", resume);
            if (captcha) form.append("cf-turnstile-response", captcha);
            const response = await axiosInstance.post<Receipt>("/recruitment/public/apply/", form, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            return response.data;
        },
        onSuccess: (receipt) => onDone({ reference: receipt.reference, access_code: receipt.access_code }),
        onError: (e: unknown) => setError(recruitmentError(e, "Your application could not be sent. Please try again.")),
    });

    const ready = ["first_name", "last_name", "email", "phone"].every((k) => values[k]?.trim()) && (!TURNSTILE_SITE_KEY || !!captcha);

    return (
        <section className="space-y-5 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
            <div>
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Apply: {opening.title}</h2>
                <button className="text-sm text-slate-500 underline" onClick={onBack}>
                    Back to positions
                </button>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="First name *"><Input onChange={set("first_name")} /></Field>
                <Field label="Last name *"><Input onChange={set("last_name")} /></Field>
                <Field label="Email *"><Input type="email" onChange={set("email")} /></Field>
                <Field label="Phone *"><Input type="tel" onChange={set("phone")} /></Field>
                <Field label="Highest qualification"><Input onChange={set("qualification")} /></Field>
                <Field label="Experience (years)"><Input type="number" min={0} max={60} onChange={set("experience_years")} /></Field>
                <Field label="Current employer"><Input onChange={set("current_employer")} /></Field>
                <Field label="Expected salary"><Input type="number" min={0} onChange={set("expected_salary")} /></Field>
            </div>
            <Field label="Anything else you would like us to know">
                <Textarea rows={3} maxLength={2000} onChange={set("cover_note")} />
            </Field>
            <Field label="Resume (PDF, DOC or DOCX, up to 5 MB)">
                <Input type="file" accept=".pdf,.doc,.docx" onChange={(e) => setResume(e.target.files?.[0] ?? null)} />
            </Field>
            {/* Hidden from people; automated form-fillers tend to complete it, and such submissions are discarded. */}
            <div aria-hidden="true" className="absolute -left-[9999px] h-0 w-0 overflow-hidden">
                <label>
                    Website
                    <input type="text" tabIndex={-1} autoComplete="off" onChange={set("website")} />
                </label>
            </div>
            <CaptchaWidget onToken={setCaptcha} />
            {error && <p className="text-sm text-red-600">{error}</p>}
            <Button disabled={!ready || apply.isPending} onClick={() => { setError(""); apply.mutate(); }}>
                {apply.isPending ? "Sending..." : "Submit application"}
            </Button>
        </section>
    );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
    // The <label> wraps its input, so the two are tied together: screen readers announce the label, and
    // tapping the label focuses the box.
    return (
        <label className="grid gap-1.5">
            <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 tracking-tight">{label}</span>
            {children}
        </label>
    );
}
