"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Field, FormDialog, SELECT_CLASS } from "@/components/dashboard/library/shared";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { useAvailableCopies, useIssueBook } from "@/hooks/useLibrary";
import { useStaffMembers } from "@/hooks/useStaff";
import { useStudents } from "@/hooks/useStudents";
import { BorrowerType } from "@/types/Library";

export function IssueDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
    return open ? <IssueForm onClose={onClose} /> : null;
}

function IssueForm({ onClose }: { onClose: () => void }) {
    const issue = useIssueBook();
    const [type, setType] = useState<BorrowerType>("student");
    const [bookSearch, setBookSearch] = useState("");
    const [copy, setCopy] = useState("");
    const [personSearch, setPersonSearch] = useState("");
    const [person, setPerson] = useState("");
    const [error, setError] = useState<string | null>(null);

    const copies = useAvailableCopies(bookSearch.trim());
    const students = useStudents({ pageSize: 50, search: personSearch, status: "active" });
    const staff = useStaffMembers({ pageSize: 50, search: personSearch, isActive: true });

    return (
        <FormDialog
            open
            onOpenChange={(o) => !o && onClose()}
            title="Issue a book"
            description="The due date and the number of books allowed come from the library settings."
            submitLabel="Issue book"
            pending={issue.isPending}
            error={error}
            onSubmit={() => {
                if (!copy) return setError("Choose the book copy.");
                if (!person) return setError(type === "student" ? "Choose the student." : "Choose the staff member.");
                setError(null);
                issue.mutate(
                    { copy, ...(type === "student" ? { student: person } : { staff: person }) },
                    { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not issue the book")) }
                );
            }}
        >
            <Field label="Book" htmlFor="is-book">
                <div className="space-y-2">
                    <Input id="is-book" placeholder="Search by title or accession number" value={bookSearch} onChange={(e) => { setBookSearch(e.target.value); setCopy(""); }} />
                    <select aria-label="Book copy" className={SELECT_CLASS} value={copy} onChange={(e) => setCopy(e.target.value)}>
                        <option value="">Choose a copy on the shelf</option>
                        {(copies.data?.results ?? []).map((c) => <option key={c.id} value={c.id}>{c.book_title} ({c.accession_number})</option>)}
                    </select>
                </div>
            </Field>
            <Field label="Lend to" htmlFor="is-type">
                <select id="is-type" className={SELECT_CLASS} value={type} onChange={(e) => { setType(e.target.value as BorrowerType); setPerson(""); }}>
                    <option value="student">A student</option>
                    <option value="staff">A staff member</option>
                </select>
            </Field>
            <Field label={type === "student" ? "Student" : "Staff member"} htmlFor="is-person">
                <div className="space-y-2">
                    <Input id="is-person" placeholder="Search by name or ID" value={personSearch} onChange={(e) => setPersonSearch(e.target.value)} />
                    <select aria-label="Borrower" className={SELECT_CLASS} value={person} onChange={(e) => setPerson(e.target.value)}>
                        <option value="">Choose a person</option>
                        {type === "student"
                            ? (students.data?.results ?? []).map((s) => <option key={s.id} value={s.id}>{s.full_name} ({s.enrollment_id})</option>)
                            : (staff.data?.results ?? []).map((s) => (
                                <option key={s.id} value={s.id}>{s.profile_details.first_name} {s.profile_details.last_name} ({s.employee_id})</option>
                            ))}
                    </select>
                </div>
            </Field>
        </FormDialog>
    );
}
