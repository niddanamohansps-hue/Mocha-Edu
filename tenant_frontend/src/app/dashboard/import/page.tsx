"use client";

import { useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Download, FileSpreadsheet, Loader2, Upload } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import Unauthorized from "@/components/Unauthorized";
import axiosInstance from "@/lib/axios";
import { usePermissions } from "@/providers/PermissionProvider";

type Kind = "students" | "staff" | "opening-fees";

interface ImportResult {
    rows: number;
    errors: { row: number; column: string; message: string }[];
    error_count: number;
    preview: Record<string, string | number>[];
    saved: number;
    error?: string;
}

const KINDS: { kind: Kind; label: string; permission: string; help: string }[] = [
    { kind: "students", label: "Students & parents", permission: "add_student",
      help: "One row per student, with father, mother or guardian. Brothers and sisters with the same parent mobile number are linked to the same parent. Classes and sections must already exist." },
    { kind: "staff", label: "Staff", permission: "add_staff",
      help: "One row per staff member. Mark teachers with is_teacher = Yes so they can be given classes and subjects." },
    { kind: "opening-fees", label: "Opening fee balances", permission: "manage_fee_structures",
      help: "Fees students still owe when you start using EduSekai. Import students first; fee heads must exist in Fees." },
];

const PREVIEW_LABELS: Record<string, string> = {
    row: "Row", name: "Name", class: "Class", admission_no: "Admission no.", parents: "Parents",
    employee_id: "Employee ID", designation: "Designation", teacher: "Teacher",
    student: "Student", fee: "Fee", amount_due: "Amount due", academic_year: "Year",
};

function ImportPanel({ kind, help }: { kind: Kind; help: string }) {
    const input = useRef<HTMLInputElement>(null);
    const [file, setFile] = useState<File | null>(null);
    const [result, setResult] = useState<ImportResult | null>(null);
    const [busy, setBusy] = useState<"check" | "save" | "template" | null>(null);
    const [message, setMessage] = useState("");

    const send = async (confirm: boolean) => {
        if (!file) return;
        setBusy(confirm ? "save" : "check");
        setMessage("");
        const form = new FormData();
        form.append("file", file);
        form.append("confirm", confirm ? "true" : "");
        try {
            const response = await axiosInstance.post<ImportResult>(`/imports/${kind}/`, form, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            setResult(response.data);
            if (confirm) {
                toast.success(`Imported ${response.data.saved} ${response.data.saved === 1 ? "row" : "rows"}.`);
                setFile(null);
                if (input.current) input.current.value = "";
            }
        } catch (error) {
            const data = (error as { response?: { data?: ImportResult & { error?: string } } })?.response?.data;
            if (data?.errors) setResult(data);
            setMessage(data?.error ?? (data?.errors ? "" : "The file could not be checked."));
        } finally {
            setBusy(null);
        }
    };

    const downloadTemplate = async () => {
        setBusy("template");
        try {
            const response = await axiosInstance.get(`/imports/${kind}/template/`, { responseType: "blob" });
            const url = URL.createObjectURL(response.data as Blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = `edusekai-${kind}-template.xlsx`;
            link.click();
            URL.revokeObjectURL(url);
        } catch {
            toast.error("Could not download the template.");
        } finally {
            setBusy(null);
        }
    };

    const ready = result && result.error_count === 0 && result.saved === 0 && result.rows > 0;
    const columns = result?.preview[0] ? Object.keys(result.preview[0]) : [];

    return (
        <div className="space-y-5">
            <p className="text-sm text-slate-600 dark:text-slate-400">{help}</p>
            <ol className="grid gap-3 sm:grid-cols-3">
                <li className="rounded-xl border border-slate-200 dark:border-slate-800 p-4 space-y-2">
                    <p className="text-sm font-semibold">1. Download the template</p>
                    <Button variant="outline" size="sm" onClick={downloadTemplate} disabled={busy !== null}>
                        {busy === "template" ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Download className="h-4 w-4 mr-2" />} Excel template
                    </Button>
                    <p className="text-xs text-slate-500">The &quot;How to fill&quot; sheet explains every column.</p>
                </li>
                <li className="rounded-xl border border-slate-200 dark:border-slate-800 p-4 space-y-2">
                    <p className="text-sm font-semibold">2. Fill it and choose the file</p>
                    <input ref={input} type="file" accept=".xlsx,.csv" className="text-sm w-full"
                        onChange={(e) => { setFile(e.target.files?.[0] ?? null); setResult(null); setMessage(""); }} />
                    <p className="text-xs text-slate-500">Excel (.xlsx) or CSV, up to 5,000 rows.</p>
                </li>
                <li className="rounded-xl border border-slate-200 dark:border-slate-800 p-4 space-y-2">
                    <p className="text-sm font-semibold">3. Check, then import</p>
                    <div className="flex flex-wrap gap-2">
                        <Button size="sm" variant="outline" onClick={() => send(false)} disabled={!file || busy !== null}>
                            {busy === "check" ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <FileSpreadsheet className="h-4 w-4 mr-2" />} Check file
                        </Button>
                        <Button size="sm" onClick={() => send(true)} disabled={!ready || busy !== null}>
                            {busy === "save" ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Upload className="h-4 w-4 mr-2" />} Import {result?.rows ?? ""}
                        </Button>
                    </div>
                    <p className="text-xs text-slate-500">Nothing is saved until you press Import. If any row has a problem, nothing is saved.</p>
                </li>
            </ol>

            {message && <p className="text-sm text-red-600 flex items-center gap-2"><AlertTriangle className="h-4 w-4" /> {message}</p>}

            {result && result.saved > 0 && (
                <p className="flex items-center gap-2 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 text-emerald-800 dark:text-emerald-300 px-4 py-3 text-sm">
                    <CheckCircle2 className="h-5 w-5" /> {result.saved} imported.
                </p>
            )}

            {result && result.error_count > 0 && (
                <div className="space-y-2">
                    <p className="text-sm font-semibold text-red-700 dark:text-red-400">
                        {result.error_count} {result.error_count === 1 ? "problem" : "problems"} to fix in the file, then check it again:
                    </p>
                    <div className="max-h-80 overflow-auto rounded-xl border border-red-200 dark:border-red-900">
                        <table className="w-full text-sm">
                            <thead className="bg-red-50 dark:bg-red-500/10 sticky top-0"><tr><th className="text-left px-3 py-2 w-16">Row</th><th className="text-left px-3 py-2 w-44">Column</th><th className="text-left px-3 py-2">Problem</th></tr></thead>
                            <tbody>{result.errors.map((e, i) => (
                                <tr key={i} className="border-t border-red-100 dark:border-red-900/50"><td className="px-3 py-1.5">{e.row}</td><td className="px-3 py-1.5 font-mono text-xs">{e.column}</td><td className="px-3 py-1.5">{e.message}</td></tr>
                            ))}</tbody>
                        </table>
                    </div>
                </div>
            )}

            {ready && (
                <div className="space-y-2">
                    <p className="text-sm font-semibold text-emerald-700 dark:text-emerald-400">
                        All {result.rows} rows are fine. {result.rows > result.preview.length ? `The first ${result.preview.length} are shown.` : ""} Press Import to save them.
                    </p>
                    <div className="max-h-96 overflow-auto rounded-xl border border-slate-200 dark:border-slate-800">
                        <table className="w-full text-sm">
                            <thead className="bg-slate-50 dark:bg-slate-900 sticky top-0"><tr>{columns.map((c) => <th key={c} className="text-left px-3 py-2 whitespace-nowrap">{PREVIEW_LABELS[c] ?? c}</th>)}</tr></thead>
                            <tbody>{result.preview.map((r, i) => (
                                <tr key={i} className="border-t border-slate-100 dark:border-slate-800">{columns.map((c) => <td key={c} className="px-3 py-1.5">{String(r[c] ?? "")}</td>)}</tr>
                            ))}</tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}

export default function ImportPage() {
    const { can } = usePermissions();
    const available = KINDS.filter((k) => can(k.permission));
    const [active, setActive] = useState<Kind | null>(null);
    if (available.length === 0) return <Unauthorized />;
    const current = available.find((k) => k.kind === active) ?? available[0];

    return (
        <div className="space-y-6 max-w-6xl">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Import data</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Bring your school&apos;s existing records in from Excel instead of typing them one by one.</p>
            </div>
            <div className="flex flex-wrap gap-2 border-b border-slate-200 dark:border-slate-800">
                {available.map((k) => (
                    <button key={k.kind} onClick={() => setActive(k.kind)}
                        className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${current.kind === k.kind ? "border-sky-600 text-sky-700 dark:text-sky-400" : "border-transparent text-slate-500"}`}>
                        {k.label}
                    </button>
                ))}
            </div>
            <ImportPanel key={current.kind} kind={current.kind} help={current.help} />
        </div>
    );
}
