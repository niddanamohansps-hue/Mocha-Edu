"use client";

import { useEffect, useState } from "react";
import { useStudents } from "@/hooks/useStudents";
import { useStaffMembers } from "@/hooks/useStaff";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const SELECT_CLASS = "w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-transparent px-3 py-2 text-sm";
const PAGE_SIZE = 20;

/**
 * Server-side search + pagination (20 per page): the browser never holds the
 * whole student or staff list, and a record is found by typing part of its
 * name or id, however large the school. The backend applies the usual
 * view_student / view_staff permission and tenant scoping.
 *
 * `studentStatus` / `staffActive` narrow the list on the server (for example
 * a transfer certificate only lists students who have left). Callers give the
 * picker a `key` that changes with those filters, so a different list always
 * starts again from page 1.
 */
export function PersonPicker({
    kind,
    value,
    onChange,
    error,
    studentStatus = "",
    staffActive,
}: {
    kind: "student" | "staff";
    value: string;
    onChange: (id: string) => void;
    error?: string;
    studentStatus?: string;
    staffActive?: boolean;
}) {
    const [text, setText] = useState("");
    const [search, setSearch] = useState("");
    const [page, setPage] = useState(1);

    // Debounce typing so each keystroke does not hit the API.
    useEffect(() => {
        const timer = setTimeout(() => {
            setSearch(text.trim());
            setPage(1);
        }, 300);
        return () => clearTimeout(timer);
    }, [text]);

    const students = useStudents({ page, pageSize: PAGE_SIZE, search, status: studentStatus });
    const staff = useStaffMembers({ page, pageSize: PAGE_SIZE, search, isActive: staffActive });
    const query = kind === "student" ? students : staff;
    const data = query.data;

    const options =
        kind === "student"
            ? (students.data?.results ?? []).map((s) => ({ id: s.id, label: `${s.full_name} (${s.enrollment_id})` }))
            : (staff.data?.results ?? []).map((s) => ({
                  id: s.id,
                  label: `${s.profile_details.first_name} ${s.profile_details.last_name} (${s.employee_id})`,
              }));

    return (
        <div className="space-y-2">
            <Label htmlFor="person">{kind === "student" ? "Student" : "Staff member"}</Label>
            <Input
                placeholder={kind === "student" ? "Search by name or admission number" : "Search by name or employee ID"}
                value={text}
                onChange={(e) => setText(e.target.value)}
            />
            {query.isLoading ? (
                <p className="text-xs text-slate-500">Loading...</p>
            ) : query.isError ? (
                <p className="text-xs text-red-600">Could not load the list. You may not have access to it.</p>
            ) : options.length === 0 ? (
                <p className="text-xs text-slate-500">No matches. Try a different name or number.</p>
            ) : (
                <select id="person" className={SELECT_CLASS} value={value} onChange={(e) => onChange(e.target.value)}>
                    <option value="">Select...</option>
                    {options.map((o) => (
                        <option key={o.id} value={o.id}>
                            {o.label}
                        </option>
                    ))}
                </select>
            )}
            {data && (data.next || data.previous) && (
                <div className="flex flex-wrap items-center justify-between gap-2">
                    <Button type="button" variant="outline" size="sm" disabled={!data.previous} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                        Previous
                    </Button>
                    <span className="text-xs text-slate-500">
                        Page {page} of {Math.max(1, Math.ceil(data.count / PAGE_SIZE))} ({data.count} found)
                    </span>
                    <Button type="button" variant="outline" size="sm" disabled={!data.next} onClick={() => setPage((p) => p + 1)}>
                        Next
                    </Button>
                </div>
            )}
            {error && <p className="text-xs text-red-600">{error}</p>}
        </div>
    );
}
