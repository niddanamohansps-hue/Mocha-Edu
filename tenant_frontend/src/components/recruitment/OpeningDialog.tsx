"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useSaveOpening } from "@/hooks/useRecruitment";
import type { JobOpening, PositionType } from "@/types/Recruitment";

const selectClass =
    "h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";

export function OpeningDialog({ opening, onClose }: { opening: JobOpening | null; onClose: () => void }) {
    const save = useSaveOpening();
    const [title, setTitle] = useState(opening?.title ?? "");
    const [positionType, setPositionType] = useState<PositionType>(opening?.position_type ?? "instructor");
    const [department, setDepartment] = useState(opening?.department ?? "");
    const [specialization, setSpecialization] = useState(opening?.specialization ?? "");
    const [vacancies, setVacancies] = useState(String(opening?.vacancies ?? 1));
    const [minExperience, setMinExperience] = useState(String(opening?.min_experience_years ?? 0));
    const [lastDate, setLastDate] = useState(opening?.last_date ?? "");
    const [description, setDescription] = useState(opening?.description ?? "");
    const [requirements, setRequirements] = useState(opening?.requirements ?? "");

    const submit = () => {
        save.mutate(
            {
                id: opening?.id,
                data: {
                    title,
                    position_type: positionType,
                    department,
                    specialization,
                    vacancies: Number(vacancies) || 1,
                    min_experience_years: Number(minExperience) || 0,
                    last_date: lastDate || null,
                    description,
                    requirements,
                },
            },
            { onSuccess: onClose },
        );
    };

    return (
        <Dialog open onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>{opening ? "Edit opening" : "New job opening"}</DialogTitle>
                </DialogHeader>
                <div className="grid gap-4">
                    <div className="grid gap-1.5">
                        <Label>Title</Label>
                        <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Mathematics Teacher (Grades 6-8)" />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="grid gap-1.5">
                            <Label>Position type</Label>
                            <select className={selectClass} value={positionType} onChange={(e) => setPositionType(e.target.value as PositionType)}>
                                <option value="instructor">Instructor (teaching)</option>
                                <option value="staff">General staff</option>
                            </select>
                        </div>
                        <div className="grid gap-1.5">
                            <Label>Vacancies</Label>
                            <Input type="number" min={1} value={vacancies} onChange={(e) => setVacancies(e.target.value)} />
                        </div>
                        <div className="grid gap-1.5">
                            <Label>Department</Label>
                            <Input value={department} onChange={(e) => setDepartment(e.target.value)} />
                        </div>
                        <div className="grid gap-1.5">
                            <Label>{positionType === "instructor" ? "Subject / specialization" : "Area"}</Label>
                            <Input value={specialization} onChange={(e) => setSpecialization(e.target.value)} />
                        </div>
                        <div className="grid gap-1.5">
                            <Label>Minimum experience (years)</Label>
                            <Input type="number" min={0} value={minExperience} onChange={(e) => setMinExperience(e.target.value)} />
                        </div>
                        <div className="grid gap-1.5">
                            <Label>Last date to apply</Label>
                            <Input type="date" value={lastDate} onChange={(e) => setLastDate(e.target.value)} />
                        </div>
                    </div>
                    <div className="grid gap-1.5">
                        <Label>Description</Label>
                        <Textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
                    </div>
                    <div className="grid gap-1.5">
                        <Label>Requirements</Label>
                        <Textarea rows={3} value={requirements} onChange={(e) => setRequirements(e.target.value)} />
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={onClose}>
                        Cancel
                    </Button>
                    <Button onClick={submit} disabled={!title.trim() || save.isPending}>
                        {save.isPending ? "Saving..." : "Save"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
