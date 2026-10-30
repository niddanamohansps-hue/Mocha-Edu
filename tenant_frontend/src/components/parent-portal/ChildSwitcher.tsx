"use client";

import { useEffect } from "react";
import { LinkedChild } from "@/types/ParentPortal";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const STORAGE_KEY = "parent-portal-selected-child";

interface ChildSwitcherProps {
    childOptions: LinkedChild[];
    selectedId: string | undefined;
    onChange: (studentId: string) => void;
}

/**
 * Reusable child selector shared by every Parent Portal page. Remembering
 * the selection (state + localStorage) is a UI convenience only - every
 * page still calls the backend with whatever student_id is selected, and
 * the backend independently re-verifies the parent-child relationship on
 * every request regardless of what was "remembered" here.
 */
export default function ChildSwitcher({ childOptions, selectedId, onChange }: ChildSwitcherProps) {
    useEffect(() => {
        if (selectedId || childOptions.length === 0) return;

        let remembered: string | null = null;
        try {
            remembered = localStorage.getItem(STORAGE_KEY);
        } catch {
            remembered = null;
        }
        const isValid = remembered && childOptions.some((c) => c.student_id === remembered);
        onChange(isValid ? (remembered as string) : childOptions[0].student_id);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [childOptions, selectedId]);

    const handleChange = (value: string) => {
        onChange(value);
        try {
            localStorage.setItem(STORAGE_KEY, value);
        } catch {
            // localStorage may be unavailable (private mode, blocked site data) -
            // selection still works for this session via React state.
        }
    };

    if (childOptions.length === 0) return null;

    return (
        <div className="w-full sm:w-72">
            <Select value={selectedId} onValueChange={handleChange}>
                <SelectTrigger className="h-10 text-xs font-semibold rounded-xl border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs">
                    <SelectValue placeholder="Select child" />
                </SelectTrigger>
                <SelectContent>
                    {childOptions.map((c) => (
                        <SelectItem key={c.student_id} value={c.student_id} className="text-xs">
                            <span className="font-bold">{c.full_name}</span>
                            {c.level || c.section ? (
                                <span className="text-slate-400 ml-1.5 font-normal">
                                    ({[c.level, c.section].filter(Boolean).join(" - ")})
                                </span>
                            ) : null}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
        </div>
    );
}
