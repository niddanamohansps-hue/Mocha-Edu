"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
    openResume,
    useApplicantHistory,
    useHireApplicant,
    useInterviewAction,
    useInterviews,
    useMoveApplicant,
    usePanelOptions,
    useScheduleInterview,
} from "@/hooks/useRecruitment";
import { OfferPanel } from "@/components/recruitment/OfferPanel";
import { NEXT_STAGES, STAGES, type Applicant } from "@/types/Recruitment";

const stageLabel = (value: string) => STAGES.find((s) => s.value === value)?.label ?? value;
const when = (iso: string) => new Date(iso).toLocaleString();

export function ApplicantDialog({
    applicant,
    canManage,
    canHire,
    onClose,
}: {
    applicant: Applicant;
    canManage: boolean;
    canHire: boolean;
    onClose: () => void;
}) {
    const move = useMoveApplicant();
    const hire = useHireApplicant();
    const schedule = useScheduleInterview();
    const interviewAction = useInterviewAction();
    const { data: history = [] } = useApplicantHistory(applicant.id);
    const { data: interviews = [] } = useInterviews(applicant.id);

    const [reason, setReason] = useState("");
    const [joiningDate, setJoiningDate] = useState("");
    const [gender, setGender] = useState("");
    const { data: panelOptions = [] } = usePanelOptions(canManage);
    const [panel, setPanel] = useState<string[]>([]);
    const [round, setRound] = useState("Interview");
    const [scheduledAt, setScheduledAt] = useState("");
    const [scoreFor, setScoreFor] = useState<string | null>(null);
    const [score, setScore] = useState("");
    const [feedback, setFeedback] = useState("");

    const closed = applicant.stage === "hired";
    const nextStages = NEXT_STAGES[applicant.stage];
    const canSchedule = canManage && !closed && applicant.stage !== "rejected";

    return (
        <Dialog open onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-3">
                        {applicant.full_name}
                        <Badge variant="outline">{stageLabel(applicant.stage)}</Badge>
                    </DialogTitle>
                </DialogHeader>

                <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
                    <span className="text-slate-500">Applied for</span>
                    <span>{applicant.opening_title}</span>
                    <span className="text-slate-500">Email</span>
                    <span>{applicant.email || "-"}</span>
                    <span className="text-slate-500">Phone</span>
                    <span>{applicant.phone || "-"}</span>
                    <span className="text-slate-500">Qualification</span>
                    <span>{applicant.qualification || "-"}</span>
                    <span className="text-slate-500">Experience</span>
                    <span>{applicant.experience_years} years</span>
                    <span className="text-slate-500">Expected salary</span>
                    <span>{applicant.expected_salary ?? "-"}</span>
                    <span className="text-slate-500">Interview score</span>
                    <span>{applicant.average_score ?? "-"}</span>
                    {applicant.rejection_reason && (
                        <>
                            <span className="text-slate-500">Rejected because</span>
                            <span>{applicant.rejection_reason}</span>
                        </>
                    )}
                </div>
                {applicant.resume_url && (
                    <div>
                        <Button variant="outline" size="sm" onClick={() => openResume(applicant.resume_url!)}>
                            View resume
                        </Button>
                    </div>
                )}

                {canManage && nextStages.length > 0 && (
                    <section className="space-y-3">
                        <h3 className="text-sm font-semibold">Move to</h3>
                        <div className="flex flex-wrap gap-2">
                            {nextStages
                                .filter((stage) => stage !== "rejected")
                                .map((stage) => (
                                    <Button
                                        key={stage}
                                        size="sm"
                                        variant="outline"
                                        disabled={move.isPending}
                                        onClick={() => move.mutate({ id: applicant.id, stage }, { onSuccess: onClose })}
                                    >
                                        {stageLabel(stage)}
                                    </Button>
                                ))}
                        </div>
                        {nextStages.includes("rejected") && (
                            <div className="flex gap-2">
                                <Input placeholder="Reason for rejecting" value={reason} onChange={(e) => setReason(e.target.value)} />
                                <Button
                                    size="sm"
                                    variant="destructive"
                                    disabled={!reason.trim() || move.isPending}
                                    onClick={() =>
                                        move.mutate({ id: applicant.id, stage: "rejected", rejection_reason: reason }, { onSuccess: onClose })
                                    }
                                >
                                    Reject
                                </Button>
                            </div>
                        )}
                    </section>
                )}

                {canManage && applicant.stage === "offered" && (
                    <OfferPanel key={`${applicant.id}-${applicant.offered_salary}-${applicant.offer_sent_at}`} applicant={applicant} />
                )}

                {canHire && applicant.stage === "offered" && (
                    <section className="space-y-3 rounded-lg border border-emerald-200 p-4 dark:border-emerald-900">
                        <h3 className="text-sm font-semibold">Hire</h3>
                        <p className="text-xs text-slate-500">
                            Creates the staff record from this application. Login access is given afterwards from the staff page.
                        </p>
                        <div className="grid grid-cols-2 gap-3">
                            <div className="grid gap-1.5">
                                <Label>Joining date</Label>
                                <Input
                                    type="date"
                                    value={joiningDate || applicant.offered_joining_date || ""}
                                    onChange={(e) => setJoiningDate(e.target.value)}
                                />
                            </div>
                            {!applicant.gender && (
                                <div className="grid gap-1.5">
                                    <Label>Gender (required)</Label>
                                    <select
                                        className="h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950"
                                        value={gender}
                                        onChange={(e) => setGender(e.target.value)}
                                    >
                                        <option value="">Select</option>
                                        <option value="male">Male</option>
                                        <option value="female">Female</option>
                                        <option value="other">Other</option>
                                    </select>
                                </div>
                            )}
                        </div>
                        <Button
                            disabled={hire.isPending || (!applicant.gender && !gender)}
                            onClick={() =>
                                hire.mutate(
                                    { id: applicant.id, joining_date: joiningDate || applicant.offered_joining_date || null, gender: gender || undefined },
                                    { onSuccess: onClose },
                                )
                            }
                        >
                            {hire.isPending ? "Hiring..." : "Hire applicant"}
                        </Button>
                    </section>
                )}

                <section className="space-y-3">
                    <h3 className="text-sm font-semibold">Interviews</h3>
                    {interviews.length === 0 && <p className="text-sm text-slate-500">None scheduled.</p>}
                    {interviews.map((interview) => (
                        <div key={interview.id} className="rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-800">
                            <div className="flex items-center justify-between gap-2">
                                <span className="font-medium">
                                    {interview.round_name} - {when(interview.scheduled_at)}
                                </span>
                                <Badge variant="outline">{interview.status}</Badge>
                            </div>
                            {interview.status === "completed" && (
                                <p className="mt-1 text-slate-600 dark:text-slate-400">
                                    {interview.panel.length > 0 ? "Average score" : "Score"} {interview.score}/10
                                    {interview.feedback ? ` - ${interview.feedback}` : ""}
                                </p>
                            )}
                            {interview.panel.length > 0 && (
                                <ul className="mt-2 space-y-1 text-slate-600 dark:text-slate-400">
                                    {interview.panel.map((member) => (
                                        <li key={member.id}>
                                            <span className="font-medium">{member.name}</span>
                                            {member.submitted
                                                ? `: ${member.score ?? "submitted"}/10${member.feedback ? ` - ${member.feedback}` : ""}`
                                                : ": waiting"}
                                        </li>
                                    ))}
                                </ul>
                            )}
                            {canManage && interview.status === "scheduled" && interview.panel.length > 0 && (
                                <div className="mt-2 flex gap-2">
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        disabled={interviewAction.isPending || !interview.panel.some((m) => m.submitted)}
                                        onClick={() => interviewAction.mutate({ id: interview.id, action: "complete" })}
                                    >
                                        Close with scores so far
                                    </Button>
                                    <Button
                                        size="sm"
                                        variant="ghost"
                                        onClick={() => interviewAction.mutate({ id: interview.id, action: "cancel" })}
                                    >
                                        Cancel
                                    </Button>
                                </div>
                            )}
                            {canManage && interview.status === "scheduled" && interview.panel.length === 0 && (
                                <div className="mt-2 space-y-2">
                                    {scoreFor === interview.id ? (
                                        <>
                                            <div className="flex gap-2">
                                                <Input
                                                    type="number"
                                                    min={0}
                                                    max={10}
                                                    step="0.5"
                                                    placeholder="Score (0-10)"
                                                    value={score}
                                                    onChange={(e) => setScore(e.target.value)}
                                                />
                                            </div>
                                            <Textarea rows={2} placeholder="Feedback" value={feedback} onChange={(e) => setFeedback(e.target.value)} />
                                            <Button
                                                size="sm"
                                                disabled={score === "" || interviewAction.isPending}
                                                onClick={() =>
                                                    interviewAction.mutate(
                                                        { id: interview.id, action: "complete", score, feedback },
                                                        { onSuccess: () => setScoreFor(null) },
                                                    )
                                                }
                                            >
                                                Save result
                                            </Button>
                                        </>
                                    ) : (
                                        <div className="flex gap-2">
                                            <Button size="sm" variant="outline" onClick={() => setScoreFor(interview.id)}>
                                                Record result
                                            </Button>
                                            <Button
                                                size="sm"
                                                variant="ghost"
                                                onClick={() => interviewAction.mutate({ id: interview.id, action: "cancel" })}
                                            >
                                                Cancel
                                            </Button>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    ))}
                    {canSchedule && (
                        <div className="flex flex-wrap items-end gap-2">
                            <div className="grid gap-1.5">
                                <Label>Round</Label>
                                <Input value={round} onChange={(e) => setRound(e.target.value)} />
                            </div>
                            <div className="grid gap-1.5">
                                <Label>When</Label>
                                <Input type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} />
                            </div>
                            <Button
                                size="sm"
                                disabled={!scheduledAt || schedule.isPending}
                                onClick={() =>
                                    schedule.mutate(
                                        {
                                            applicant: applicant.id,
                                            round_name: round || "Interview",
                                            scheduled_at: new Date(scheduledAt).toISOString(),
                                            panelist_ids: panel,
                                        },
                                        { onSuccess: () => { setScheduledAt(""); setPanel([]); } },
                                    )
                                }
                            >
                                Schedule
                            </Button>
                        </div>
                    )}
                    {canSchedule && panelOptions.length > 0 && (
                        <div className="space-y-1.5">
                            <Label>Panel (optional): each panelist records their own score</Label>
                            <div className="grid max-h-36 grid-cols-2 gap-1 overflow-y-auto rounded-lg border border-slate-200 p-2 text-sm dark:border-slate-800">
                                {panelOptions.map((option) => (
                                    <label key={option.id} className="flex items-center gap-2">
                                        <input
                                            type="checkbox"
                                            checked={panel.includes(option.id)}
                                            onChange={(e) =>
                                                setPanel((current) =>
                                                    e.target.checked ? [...current, option.id] : current.filter((id) => id !== option.id),
                                                )
                                            }
                                        />
                                        {option.name}
                                        <span className="text-xs text-slate-400">{option.designation}</span>
                                    </label>
                                ))}
                            </div>
                        </div>
                    )}
                </section>

                <section className="space-y-2">
                    <h3 className="text-sm font-semibold">History</h3>
                    <ul className="space-y-1 text-sm text-slate-600 dark:text-slate-400">
                        {history.map((event) => (
                            <li key={event.id}>
                                {when(event.created_at)} - {event.from_stage ? `${stageLabel(event.from_stage)} to ` : ""}
                                {stageLabel(event.to_stage)}
                                {event.actor_name ? ` by ${event.actor_name}` : ""}
                                {event.note ? ` (${event.note})` : ""}
                            </li>
                        ))}
                    </ul>
                </section>
            </DialogContent>
        </Dialog>
    );
}
