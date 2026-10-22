"use client";

import { ResponsiveList } from "@/components/common/ResponsiveList";
import { useState } from "react";
import { LoaderCircle } from "lucide-react";
import { useSections } from "@/hooks/useAcademics";
import { useInstructors } from "@/hooks/useStaff";
import { useCreateSubstitution, useSectionTimetable, useSubstitutions } from "@/hooks/useTimetable";
import { DAY_LABELS } from "@/types/Timetable";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import Unauthorized from "@/components/Unauthorized";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

export default function SubstitutionsPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("manage_substitutions")) {
        return <Unauthorized />;
    }

    const { data: sections } = useSections();
    const [sectionId, setSectionId] = useState("");
    const { data: entries } = useSectionTimetable(sectionId || undefined);
    const { data: substitutions, isLoading: loadingSubs, isError: subsError, refetch: refetchSubs } = useSubstitutions();

    const [entryId, setEntryId] = useState("");
    const [date, setDate] = useState("");
    const [substituteInstructor, setSubstituteInstructor] = useState("");
    const [reason, setReason] = useState("");

    const { data: instructorsData } = useInstructors();
    const instructors = instructorsData?.results;

    const { mutate: createSubstitution, isPending } = useCreateSubstitution();

    const handleSubmit = () => {
        if (!entryId || !date || !substituteInstructor) return;
        createSubstitution(
            { entryId, data: { date, substitute_instructor: substituteInstructor, reason } },
            {
                onSuccess: () => {
                    setDate("");
                    setSubstituteInstructor("");
                    setReason("");
                },
            }
        );
    };

    return (
        <div className="space-y-8">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Substitutions</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Assign a substitute instructor for a specific date
                </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl">
                <div>
                    <label className="text-xs font-medium text-slate-500 mb-1 block">Section</label>
                    <Select value={sectionId} onValueChange={(v) => { setSectionId(v); setEntryId(""); }}>
                        <SelectTrigger>
                            <SelectValue placeholder="Select a section" />
                        </SelectTrigger>
                        <SelectContent>
                            {sections?.map((s) => (
                                <SelectItem key={s.id} value={s.id}>{s.level_name} - {s.name}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
                <div>
                    <label className="text-xs font-medium text-slate-500 mb-1 block">Timetable Entry</label>
                    <Select value={entryId} onValueChange={setEntryId} disabled={!sectionId}>
                        <SelectTrigger>
                            <SelectValue placeholder="Select a slot" />
                        </SelectTrigger>
                        <SelectContent>
                            {entries?.map((e) => (
                                <SelectItem key={e.id} value={e.id}>
                                    {DAY_LABELS[e.day_of_week]} - {e.period_name} - {e.subject_name}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
                <div>
                    <label htmlFor="f-date" className="text-xs font-medium text-slate-500 mb-1 block">Date</label>
                    <Input id="f-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
                </div>
                <div>
                    <label className="text-xs font-medium text-slate-500 mb-1 block">Substitute Instructor</label>
                    <Select value={substituteInstructor} onValueChange={setSubstituteInstructor}>
                        <SelectTrigger>
                            <SelectValue placeholder="Select instructor" />
                        </SelectTrigger>
                        <SelectContent>
                            {instructors?.map((i: any) => (
                                <SelectItem key={i.id} value={i.id}>
                                    {i.staff_member_name || i.id}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
                <div className="md:col-span-2">
                    <label htmlFor="f-reason-optional" className="text-xs font-medium text-slate-500 mb-1 block">Reason (optional)</label>
                    <Input id="f-reason-optional" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. sick leave" />
                </div>
            </div>

            <Button onClick={handleSubmit} disabled={!entryId || !date || !substituteInstructor || isPending} className="gap-2">
                {isPending && <LoaderCircle className="h-4 w-4 animate-spin" />}
                Submit Substitution
            </Button>

            <div>
                <h2 className="text-lg font-bold text-slate-900 dark:text-white mb-3">Existing Substitutions</h2>
                {loadingSubs ? (
                    <LoaderCircle className="h-6 w-6 animate-spin text-indigo-600" />
                ) : subsError ? (
                    <ErrorState onRetry={refetchSubs} />
                ) : !substitutions || substitutions.length === 0 ? (
                    <EmptyState title="No substitutions recorded yet." className="py-6 text-slate-500 text-sm" />
                ) : (
                        <ResponsiveList
                            rows={substitutions}
                            rowKey={(s) => String(s.id)}
                            columns={[
                                { key: "c0", header: "Date", primary: true, cell: (s) => (<>{s.date}</>), },
                                { key: "c1", header: "Reason", className: "text-slate-500", cell: (s) => (<>{s.reason || "—"}</>), },
                            ]}
                        />
                )}
            </div>
        </div>
    );
}
