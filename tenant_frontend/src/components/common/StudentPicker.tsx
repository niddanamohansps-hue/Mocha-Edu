"use client";

import { useEffect, useId, useState } from "react";
import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useStudents, Student } from "@/hooks/useStudents";

/**
 * Pick a student by name or enrollment number (searches the student directory as you type).
 * Staff never type or paste internal ids: the chosen student's id is handed to `onChange`.
 */
export function StudentPicker({
    id,
    value,
    onChange,
    required,
}: {
    id?: string;
    /** The chosen student, or null. */
    value: Student | null;
    onChange: (student: Student | null) => void;
    required?: boolean;
}) {
    const listId = useId();
    const [query, setQuery] = useState("");
    const [debounced, setDebounced] = useState("");
    const [open, setOpen] = useState(false);

    useEffect(() => {
        const t = setTimeout(() => setDebounced(query.trim()), 250);
        return () => clearTimeout(t);
    }, [query]);

    const searching = debounced.length >= 2;
    const { data, isFetching } = useStudents({ search: searching ? debounced : "", pageSize: 8 });
    const results = searching ? data?.results ?? [] : [];

    if (value) {
        return (
            <div className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 px-3 py-2 text-sm">
                <div className="min-w-0">
                    <p className="font-medium text-slate-900 dark:text-white truncate">{value.full_name}</p>
                    <p className="text-xs text-slate-500">
                        {value.enrollment_id}
                        {value.level ? ` · ${value.level}` : ""}
                    </p>
                </div>
                <button
                    type="button"
                    onClick={() => {
                        onChange(null);
                        setQuery("");
                    }}
                    className="p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 dark:hover:bg-slate-800"
                    aria-label="Choose a different student"
                >
                    <X className="h-4 w-4" />
                </button>
            </div>
        );
    }

    return (
        <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400 pointer-events-none" aria-hidden="true" />
            <Input
                id={id}
                type="search"
                role="combobox"
                aria-expanded={open && searching}
                aria-controls={listId}
                aria-autocomplete="list"
                autoComplete="off"
                required={required}
                placeholder="Type a student's name or enrollment number"
                value={query}
                onChange={(e) => {
                    setQuery(e.target.value);
                    setOpen(true);
                }}
                onFocus={() => setOpen(true)}
                onBlur={() => setTimeout(() => setOpen(false), 150)}
                className="pl-8"
            />
            {open && searching && (
                <ul
                    id={listId}
                    role="listbox"
                    className="absolute z-20 mt-1 w-full max-h-64 overflow-y-auto rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-lg text-sm"
                >
                    {results.length === 0 ? (
                        <li className="px-3 py-2 text-slate-500">{isFetching ? "Searching…" : "No student found"}</li>
                    ) : (
                        results.map((s) => (
                            <li key={s.id} role="option" aria-selected={false}>
                                <button
                                    type="button"
                                    onMouseDown={(e) => e.preventDefault()}
                                    onClick={() => {
                                        onChange(s);
                                        setOpen(false);
                                    }}
                                    className="w-full text-left px-3 py-2 hover:bg-slate-50 dark:hover:bg-slate-800"
                                >
                                    <span className="font-medium text-slate-900 dark:text-white">{s.full_name}</span>
                                    <span className="ml-2 text-xs text-slate-500">
                                        {s.enrollment_id}
                                        {s.level ? ` · ${s.level}` : ""}
                                    </span>
                                </button>
                            </li>
                        ))
                    )}
                </ul>
            )}
        </div>
    );
}
