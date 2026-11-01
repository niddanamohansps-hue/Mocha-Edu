"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { openResume, useMyInterviews, useSubmitFeedback } from "@/hooks/useRecruitment";
import { usePermissions } from "@/providers/PermissionProvider";
import type { Interview } from "@/types/Recruitment";

export default function MyInterviewsPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("record_interview_feedback")) return <Unauthorized />;
    return <MyInterviewsContent />;
}

function MyInterviewsContent() {
    const { data: interviews = [], isLoading } = useMyInterviews();
    const waiting = interviews.filter((i) => i.can_submit);
    const others = interviews.filter((i) => !i.can_submit);

    return (
        <div className="max-w-3xl mx-auto space-y-8">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">My interviews</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    Interviews you are a panelist on. Record your own score and comments; other panelists cannot see them until
                    the interview is complete.
                </p>
            </div>
            {isLoading ? (
                <LoadingState />
            ) : interviews.length === 0 ? (
                <EmptyState title="No interviews" description="You have not been placed on an interview panel." />
            ) : (
                <>
                    {waiting.length > 0 && (
                        <section className="space-y-4">
                            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Waiting for your feedback</h2>
                            {waiting.map((interview) => (
                                <InterviewCard key={interview.id} interview={interview} />
                            ))}
                        </section>
                    )}
                    {others.length > 0 && (
                        <section className="space-y-4">
                            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Other interviews</h2>
                            {others.map((interview) => (
                                <InterviewCard key={interview.id} interview={interview} />
                            ))}
                        </section>
                    )}
                </>
            )}
        </div>
    );
}

function InterviewCard({ interview }: { interview: Interview }) {
    const submit = useSubmitFeedback();
    const [score, setScore] = useState("");
    const [feedback, setFeedback] = useState("");
    const me = interview.panel.find((m) => m.is_me);
    const summary = interview.applicant_summary;

    return (
        <article className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-start justify-between gap-3">
                <div>
                    <h3 className="font-semibold text-slate-900 dark:text-white">{interview.applicant_name}</h3>
                    <p className="text-sm text-slate-500">
                        {summary.opening_title} - {interview.round_name} - {new Date(interview.scheduled_at).toLocaleString()}
                        {interview.location_or_url ? ` - ${interview.location_or_url}` : ""}
                    </p>
                </div>
                <Badge variant="outline">{interview.status}</Badge>
            </div>
            <p className="text-sm text-slate-600 dark:text-slate-400">
                {[summary.qualification, `${summary.experience_years} years experience`, summary.current_employer]
                    .filter(Boolean)
                    .join(" - ")}
            </p>
            {summary.resume_url && (
                <Button size="sm" variant="outline" onClick={() => openResume(summary.resume_url!)}>
                    View resume
                </Button>
            )}
            {interview.can_submit ? (
                <div className="space-y-3 rounded-lg border border-slate-200 p-3 dark:border-slate-800">
                    <div className="grid gap-1.5">
                        <Label>Your score (0-10)</Label>
                        <Input type="number" min={0} max={10} step="0.5" value={score} onChange={(e) => setScore(e.target.value)} />
                    </div>
                    <div className="grid gap-1.5">
                        <Label>Comments</Label>
                        <Textarea rows={3} maxLength={2000} value={feedback} onChange={(e) => setFeedback(e.target.value)} />
                    </div>
                    <Button disabled={score === "" || submit.isPending} onClick={() => submit.mutate({ id: interview.id, score, feedback })}>
                        {submit.isPending ? "Saving..." : "Submit feedback"}
                    </Button>
                    <p className="text-xs text-slate-500">You can only submit once.</p>
                </div>
            ) : (
                me?.submitted && (
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                        You scored {me.score}/10{me.feedback ? ` - ${me.feedback}` : ""}.
                        {interview.status === "completed" && interview.score ? ` Panel average: ${interview.score}/10.` : ""}
                    </p>
                )
            )}
        </article>
    );
}
