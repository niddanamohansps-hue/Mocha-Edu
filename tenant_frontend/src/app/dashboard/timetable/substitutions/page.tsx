"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { LoaderCircle } from "lucide-react";
import axiosInstance from "@/lib/axios";
import { useSections } from "@/hooks/useAcademics";
import { useCreateSubstitution, useSectionTimetable, useSubstitutions } from "@/hooks/useTimetable";
import { DAY_LABELS } from "@/types/Timetable";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import Unauthorized from "@/components/Unauthorized";

export default function SubstitutionsPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("manage_substitutions")) {
        return <Unauthorized />;
    }

    const { data: sections } = useSections();
    const [sectionId, setSectionId] = useState("");
    const { data: entries } = useSectionTimetable(sectionId || undefined);
    const { data: substitutions, isLoading: loadingSubs } = useSubstitutions();

    const [entryId, setEntryId] = useState("");
    const [date, setDate] = useState("");
    const [substituteInstructor, setSubstituteInstructor] = useState("");
    const [reason, setReason] = useState("");

    const { data: instructors } = useQuery({
        queryKey: ["staff", "instructors", "all"],
        queryFn: async () => {
            const response = await axiosInstance.get("/staff/instructors/");
            return response.data as any[];
        },
    });

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
                    <label className="text-xs font-medium text-slate-500 mb-1 block">Date</label>
                    <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
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
                    <label className="text-xs font-medium text-slate-500 mb-1 block">Reason (optional)</label>
                    <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. sick leave" />
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
                ) : !substitutions || substitutions.length === 0 ? (
                    <p className="text-sm text-slate-500 py-6">No substitutions recorded yet.</p>
                ) : (
                    <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                        <table className="w-full text-sm">
                            <thead className="bg-slate-50 dark:bg-slate-900">
                                <tr className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                    <th className="px-4 py-3">Date</th>
                                    <th className="px-4 py-3">Reason</th>
                                </tr>
                            </thead>
                            <tbody>
                                {substitutions.map((s) => (
                                    <tr key={s.id} className="border-t border-slate-100 dark:border-slate-800">
                                        <td className="px-4 py-2">{s.date}</td>
                                        <td className="px-4 py-2 text-slate-500">{s.reason || "—"}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}
