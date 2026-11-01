"use client";

import { useState } from "react";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCreateExamScheduleComponent, useDeleteExamScheduleComponent } from "@/hooks/useExaminations";
import type { ExamSchedule } from "@/types/Examinations";

/**
 * The parts one paper's marks are split into (for example Theory 80 + Practical 20). Marks entry then asks for each
 * part separately, and a part can have its own pass mark.
 */
export function ScheduleComponentsDialog({
    schedule,
    canEdit,
    onClose,
}: {
    schedule: ExamSchedule;
    canEdit: boolean;
    onClose: () => void;
}) {
    const create = useCreateExamScheduleComponent();
    const remove = useDeleteExamScheduleComponent();
    const parts = schedule.components ?? [];
    const total = parts.reduce((sum, c) => sum + Number(c.max_marks), 0);
    const max = Number(schedule.max_marks);

    const [name, setName] = useState("");
    const [code, setCode] = useState("");
    const [maxMarks, setMaxMarks] = useState("");
    const [passMarks, setPassMarks] = useState("");
    const [isTheory, setIsTheory] = useState(true);
    const [separatePass, setSeparatePass] = useState(false);

    const add = () => {
        create.mutate(
            {
                exam_schedule: schedule.id,
                name: name.trim(),
                code: code.trim().toUpperCase(),
                max_marks: maxMarks,
                pass_marks: passMarks || "0",
                is_theory: isTheory,
                requires_separate_pass: separatePass,
                order: parts.length + 1,
            },
            {
                onSuccess: () => {
                    setName(""); setCode(""); setMaxMarks(""); setPassMarks(""); setSeparatePass(false);
                },
            },
        );
    };

    return (
        <Dialog open onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Score parts: {schedule.subject_name} ({schedule.section_name})</DialogTitle>
                    <DialogDescription>
                        Split this paper&apos;s {max} marks into parts such as Theory and Practical. Leave empty for a single mark.
                    </DialogDescription>
                </DialogHeader>

                {parts.length > 0 && (
                    <div className="space-y-2">
                        {parts.map((part) => (
                            <div key={part.id} className="flex items-center justify-between rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-800">
                                <span>
                                    <span className="font-medium">{part.name}</span>{" "}
                                    <span className="text-slate-500">({part.code})</span>
                                    <span className="block text-xs text-slate-500">
                                        Out of {Number(part.max_marks)}, pass {Number(part.pass_marks)}
                                        {part.requires_separate_pass ? ", must pass this part separately" : ""}
                                    </span>
                                </span>
                                {canEdit && (
                                    <Button size="icon" variant="ghost" disabled={remove.isPending} onClick={() => remove.mutate(part.id)}>
                                        <Trash2 className="h-4 w-4 text-red-500" />
                                    </Button>
                                )}
                            </div>
                        ))}
                        <p className={`text-sm ${total === max ? "text-emerald-600" : "text-amber-600"}`}>
                            Parts add up to {total} of {max} marks
                            {total === max ? "." : ". They should add up to the paper's maximum marks."}
                        </p>
                    </div>
                )}

                {canEdit ? (
                    <div className="space-y-3 border-t border-slate-200 pt-4 dark:border-slate-800">
                        <h4 className="text-sm font-semibold">Add a part</h4>
                        <div className="grid grid-cols-2 gap-3">
                            <div className="grid gap-1.5">
                                <Label>Name</Label>
                                <Input placeholder="Theory" value={name} onChange={(e) => setName(e.target.value)} />
                            </div>
                            <div className="grid gap-1.5">
                                <Label>Short code</Label>
                                <Input placeholder="TH" maxLength={20} value={code} onChange={(e) => setCode(e.target.value)} />
                            </div>
                            <div className="grid gap-1.5">
                                <Label>Maximum marks</Label>
                                <Input type="number" min={1} value={maxMarks} onChange={(e) => setMaxMarks(e.target.value)} />
                            </div>
                            <div className="grid gap-1.5">
                                <Label>Pass marks</Label>
                                <Input type="number" min={0} value={passMarks} onChange={(e) => setPassMarks(e.target.value)} />
                            </div>
                        </div>
                        <label className="flex items-center gap-2 text-sm">
                            <input type="checkbox" checked={isTheory} onChange={(e) => setIsTheory(e.target.checked)} />
                            This is a written (theory) part
                        </label>
                        <label className="flex items-center gap-2 text-sm">
                            <input type="checkbox" checked={separatePass} onChange={(e) => setSeparatePass(e.target.checked)} />
                            Student must pass this part on its own to pass the subject
                        </label>
                        <Button disabled={create.isPending || !name.trim() || !code.trim() || !maxMarks} onClick={add}>
                            Add part
                        </Button>
                    </div>
                ) : (
                    <p className="text-sm text-slate-500">
                        {schedule.is_locked ? "" : "Parts cannot be changed once the results are published."}
                    </p>
                )}
            </DialogContent>
        </Dialog>
    );
}
