"use client";

import { useRef, useState, DragEvent } from "react";
import {
    AlertTriangle,
    CheckCircle2,
    Download,
    FileSpreadsheet,
    Loader2,
    Upload,
    GraduationCap,
    Users,
    Receipt,
    FileCheck,
    FileUp,
    ShieldCheck,
    Info,
    X,
    ArrowRight,
    Sparkles,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TableShell } from "@/components/common/table/TableShell";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
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

interface KindConfig {
    kind: Kind;
    label: string;
    permission: string;
    icon: typeof GraduationCap;
    help: string;
    details: string;
    viewRoute: string;
    viewLabel: string;
}

const KINDS: KindConfig[] = [
    {
        kind: "students",
        label: "Students & Parents",
        permission: "add_student",
        icon: GraduationCap,
        help: "One row per student, with father, mother or guardian. Siblings sharing parent mobile numbers are automatically linked to the same household.",
        details: "Ensure academic classes and sections are configured in Academic Settings before importing students.",
        viewRoute: "/dashboard/students",
        viewLabel: "Go to Student Directory",
    },
    {
        kind: "staff",
        label: "Faculty & Staff",
        permission: "add_staff",
        icon: Users,
        help: "One row per staff member. Set is_teacher = Yes to enable classroom and subject assignment in the academic master.",
        details: "Employee IDs must be unique across all active and inactive faculty records.",
        viewRoute: "/dashboard/staff",
        viewLabel: "Go to Staff Directory",
    },
    {
        kind: "opening-fees",
        label: "Opening Fee Balances",
        permission: "manage_fee_structures",
        icon: Receipt,
        help: "Import past balances and pending dues carried forward into EduSekai. Fee heads must already be created.",
        details: "Students must already exist in the database (matching admission numbers) before mapping fee arrears.",
        viewRoute: "/dashboard/fees",
        viewLabel: "Go to Fees Desk",
    },
];

const PREVIEW_LABELS: Record<string, string> = {
    row: "Row #",
    name: "Full Name",
    class: "Class / Grade",
    admission_no: "Admission #",
    parents: "Parent / Guardian",
    employee_id: "Employee ID",
    designation: "Designation",
    teacher: "Teacher Flag",
    student: "Student Admission",
    fee: "Fee Head",
    amount_due: "Amount Due (₹)",
    academic_year: "Academic Year",
};

function formatFileSize(bytes: number) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function ImportPanel({ config }: { config: KindConfig }) {
    const { kind, help, details, viewRoute, viewLabel } = config;
    const inputRef = useRef<HTMLInputElement>(null);
    const [file, setFile] = useState<File | null>(null);
    const [isDragging, setIsDragging] = useState(false);
    const [result, setResult] = useState<ImportResult | null>(null);
    const [busy, setBusy] = useState<"check" | "save" | "template" | null>(null);
    const [serverError, setServerError] = useState("");

    const send = async (confirm: boolean) => {
        if (!file) return;
        setBusy(confirm ? "save" : "check");
        setServerError("");
        const form = new FormData();
        form.append("file", file);
        form.append("confirm", confirm ? "true" : "");
        try {
            const response = await axiosInstance.post<ImportResult>(`/imports/${kind}/`, form, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            setResult(response.data);
            if (confirm) {
                toast.success(`Successfully imported ${response.data.saved} ${response.data.saved === 1 ? "record" : "records"}!`);
                setFile(null);
                if (inputRef.current) inputRef.current.value = "";
            } else {
                if (response.data.error_count === 0) {
                    toast.success(`Audit passed: ${response.data.rows} rows verified without issues!`);
                } else {
                    toast.error(`Audit found ${response.data.error_count} issues in the spreadsheet.`);
                }
            }
        } catch (error) {
            const data = (error as { response?: { data?: ImportResult & { error?: string } } })?.response?.data;
            if (data?.errors) {
                setResult(data);
                toast.error(`Audit failed: ${data.errors.length} formatting errors detected.`);
            }
            setServerError(data?.error ?? (data?.errors ? "" : "The file could not be parsed by the server. Please check the Excel file format."));
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
            toast.success("Excel template downloaded.");
        } catch {
            toast.error("Could not download the specification template.");
        } finally {
            setBusy(null);
        }
    };

    const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = () => {
        setIsDragging(false);
    };

    const handleDrop = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDragging(false);
        const droppedFile = e.dataTransfer.files?.[0];
        if (droppedFile) {
            if (droppedFile.name.endsWith(".xlsx") || droppedFile.name.endsWith(".csv")) {
                setFile(droppedFile);
                setResult(null);
                setServerError("");
            } else {
                toast.error("Only .xlsx and .csv files are supported.");
            }
        }
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const selected = e.target.files?.[0] ?? null;
        setFile(selected);
        setResult(null);
        setServerError("");
    };

    const clearFile = () => {
        setFile(null);
        setResult(null);
        setServerError("");
        if (inputRef.current) inputRef.current.value = "";
    };

    const ready = Boolean(result && result.error_count === 0 && result.saved === 0 && result.rows > 0);
    const columns = result?.preview[0] ? Object.keys(result.preview[0]) : [];

    // Pipeline Step Status
    const step1Done = true;
    const step2Done = Boolean(file);
    const step3Done = Boolean(result && result.saved > 0);

    return (
        <div className="space-y-6">
            {/* Context & Requirements Header Banner */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-2xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800">
                <div className="flex items-start gap-3">
                    <div className="p-2.5 rounded-xl bg-sky-100 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-900 shrink-0 mt-0.5">
                        <Info className="h-5 w-5" />
                    </div>
                    <div>
                        <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Import Guidelines</h3>
                        <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5 leading-relaxed">{help}</p>
                        <p className="text-xs text-sky-700 dark:text-sky-400 font-medium mt-1">{details}</p>
                    </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={downloadTemplate}
                        disabled={busy !== null}
                    >
                        {busy === "template" ? (
                            <Loader2 className="h-4 w-4 mr-2 animate-spin text-sky-600" />
                        ) : (
                            <Download className="h-4 w-4 mr-2 text-sky-600" />
                        )}
                        Download Excel Specification
                    </Button>
                </div>
            </div>

            {/* 3-Step Visual Execution Pipeline */}
            <div className="grid gap-4 md:grid-cols-3">
                {/* Step 1: Template Specification */}
                <div className="relative rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 flex flex-col justify-between shadow-sm transition hover:shadow-md">
                    <div>
                        <div className="flex items-center justify-between mb-3">
                            <span className="flex items-center justify-center w-7 h-7 rounded-lg text-xs font-bold bg-sky-100 dark:bg-sky-950/70 text-sky-700 dark:text-sky-300 border border-sky-300/60 dark:border-sky-800">
                                01
                            </span>
                            <Badge variant="outline" className="text-[10px] bg-slate-50 text-slate-600 dark:bg-slate-800 dark:text-slate-300 font-medium">
                                Specification
                            </Badge>
                        </div>
                        <h4 className="text-sm font-semibold text-slate-900 dark:text-white">Get Official Template</h4>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1.5 leading-relaxed">
                            Pre-configured Excel file (.xlsx) with strictly typed headers and a dedicated instructions sheet.
                        </p>
                    </div>
                    <div className="pt-4 mt-4 border-t border-slate-100 dark:border-slate-800">
                        <Button
                            variant="secondary"
                            size="sm"
                            onClick={downloadTemplate}
                            disabled={busy !== null}
                            className="w-full text-xs font-medium justify-center h-8"
                        >
                            {busy === "template" ? (
                                <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
                            ) : (
                                <Download className="h-3.5 w-3.5 mr-2" />
                            )}
                            Template (.xlsx)
                        </Button>
                    </div>
                </div>

                {/* Step 2: File Ingestion Dropzone */}
                <div
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    className={`relative rounded-2xl border transition-all p-5 flex flex-col justify-between shadow-sm ${
                        isDragging
                            ? "border-sky-500 bg-sky-50/50 dark:bg-sky-950/20 ring-2 ring-sky-500/20"
                            : file
                            ? "border-emerald-200 dark:border-emerald-900 bg-emerald-50/30 dark:bg-emerald-950/10"
                            : "border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 hover:shadow-md"
                    }`}
                >
                    <div>
                        <div className="flex items-center justify-between mb-3">
                            <span className={`flex items-center justify-center w-7 h-7 rounded-lg text-xs font-bold ${
                                file
                                    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/70 dark:text-emerald-300"
                                    : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                            }`}>
                                02
                            </span>
                            {file ? (
                                <Badge variant="outline" className="text-[10px] bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300">
                                    File Attached
                                </Badge>
                            ) : (
                                <Badge variant="outline" className="text-[10px] text-slate-500">
                                    Awaiting File
                                </Badge>
                            )}
                        </div>

                        <h4 className="text-sm font-semibold text-slate-900 dark:text-white">Choose Spreadsheet</h4>

                        {file ? (
                            <div className="mt-2.5 p-3 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 flex items-center justify-between">
                                <div className="flex items-center gap-2.5 min-w-0">
                                    <FileSpreadsheet className="h-5 w-5 text-emerald-600 shrink-0" />
                                    <div className="min-w-0">
                                        <p className="text-xs font-medium text-slate-900 dark:text-white truncate">{file.name}</p>
                                        <p className="text-[11px] text-slate-500">{formatFileSize(file.size)}</p>
                                    </div>
                                </div>
                                <button
                                    type="button"
                                    onClick={clearFile}
                                    className="p-1 rounded-md text-slate-400 hover:text-rose-600 hover:bg-slate-100 dark:hover:bg-slate-700 transition"
                                >
                                    <X className="h-4 w-4" />
                                </button>
                            </div>
                        ) : (
                            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1.5 leading-relaxed">
                                Drag and drop your completed .xlsx or .csv workbook here, up to 5,000 rows.
                            </p>
                        )}
                    </div>

                    <div className="pt-4 mt-4 border-t border-slate-100 dark:border-slate-800">
                        <input
                            ref={inputRef}
                            type="file"
                            accept=".xlsx,.csv"
                            onChange={handleFileChange}
                            className="hidden"
                            id="spreadsheet-file-upload"
                        />
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => inputRef.current?.click()}
                            className="w-full text-xs font-medium justify-center h-8"
                        >
                            <FileUp className="h-3.5 w-3.5 mr-2 text-slate-500" />
                            {file ? "Change File" : "Browse Files"}
                        </Button>
                    </div>
                </div>

                {/* Step 3: Verification & Database Commit */}
                <div className={`relative rounded-2xl border transition-all p-5 flex flex-col justify-between shadow-sm ${
                    ready
                        ? "border-emerald-300 dark:border-emerald-800 bg-emerald-50/20 dark:bg-emerald-950/10"
                        : "border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900"
                }`}>
                    <div>
                        <div className="flex items-center justify-between mb-3">
                            <span className={`flex items-center justify-center w-7 h-7 rounded-lg text-xs font-bold ${
                                ready
                                    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/70 dark:text-emerald-300"
                                    : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                            }`}>
                                03
                            </span>
                            {ready ? (
                                <Badge className="text-[10px] bg-emerald-600 text-white font-medium hover:bg-emerald-700">
                                    Audit Verified
                                </Badge>
                            ) : (
                                <Badge variant="outline" className="text-[10px] text-slate-500">
                                    Simulate & Commit
                                </Badge>
                            )}
                        </div>

                        <h4 className="text-sm font-semibold text-slate-900 dark:text-white">Verify & Commit</h4>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1.5 leading-relaxed">
                            Dry-run check ensures zero duplicate or invalid records. Nothing is written until committed.
                        </p>
                    </div>

                    <div className="pt-4 mt-4 border-t border-slate-100 dark:border-slate-800 flex flex-col gap-2">
                        <Button
                            variant={ready ? "outline" : "default"}
                            size="sm"
                            onClick={() => send(false)}
                            disabled={!file || busy !== null}
                            className="w-full text-xs font-medium justify-center h-8"
                        >
                            {busy === "check" ? (
                                <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
                            ) : (
                                <ShieldCheck className="h-3.5 w-3.5 mr-2" />
                            )}
                            Dry-Run Audit File
                        </Button>

                        <Button
                            size="sm"
                            onClick={() => send(true)}
                            disabled={!ready || busy !== null}
                            className={`w-full text-xs font-semibold justify-center h-8 shadow-sm transition ${
                                ready
                                    ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                                    : "bg-slate-200 dark:bg-slate-800 text-slate-400 cursor-not-allowed"
                            }`}
                        >
                            {busy === "save" ? (
                                <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
                            ) : (
                                <Upload className="h-3.5 w-3.5 mr-2" />
                            )}
                            Commit {result && result.rows > 0 ? `${result.rows} Records` : "Data"}
                        </Button>
                    </div>
                </div>
            </div>

            {/* General Server Error Banner */}
            {serverError && (
                <div className="p-4 rounded-2xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 flex items-start gap-3">
                    <AlertTriangle className="h-5 w-5 text-rose-600 shrink-0 mt-0.5" />
                    <div>
                        <h4 className="text-sm font-semibold text-rose-800 dark:text-rose-300">File Ingestion Issue</h4>
                        <p className="text-xs text-rose-700 dark:text-rose-400 mt-0.5">{serverError}</p>
                    </div>
                </div>
            )}

            {/* Post-Import Success State */}
            {result && result.saved > 0 && (
                <div className="p-6 rounded-2xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-center space-y-3">
                    <div className="mx-auto w-12 h-12 rounded-2xl bg-emerald-100 dark:bg-emerald-900/60 text-emerald-600 flex items-center justify-center">
                        <CheckCircle2 className="h-7 w-7" />
                    </div>
                    <div>
                        <h3 className="text-base font-bold text-emerald-900 dark:text-emerald-200">
                            Batch Ingestion Completed Successfully!
                        </h3>
                        <p className="text-xs text-emerald-700 dark:text-emerald-400 mt-1 max-w-md mx-auto">
                            A total of <span className="font-semibold text-emerald-800 dark:text-emerald-200">{result.saved} {result.saved === 1 ? "record" : "records"}</span> were committed to the school database.
                        </p>
                    </div>
                    <div className="pt-2 flex items-center justify-center gap-3">
                        <Link href={viewRoute}>
                            <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-xs">
                                {viewLabel} <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
                            </Button>
                        </Link>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                                setResult(null);
                                setFile(null);
                                if (inputRef.current) inputRef.current.value = "";
                            }}
                            className="text-xs border-emerald-300 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300"
                        >
                            Upload Another File
                        </Button>
                    </div>
                </div>
            )}

            {/* Validation Errors Inspector */}
            {result && result.error_count > 0 && (
                <div className="space-y-3">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <AlertTriangle className="h-5 w-5 text-rose-600" />
                            <h3 className="text-sm font-bold text-rose-900 dark:text-rose-200">
                                {result.error_count} Rule {result.error_count === 1 ? "Violation" : "Violations"} Detected
                            </h3>
                            <Badge variant="outline" className="bg-rose-50 text-rose-700 border-rose-300 dark:bg-rose-950 dark:text-rose-300 text-xs">
                                Fix and re-audit
                            </Badge>
                        </div>
                        <p className="text-xs text-slate-500">
                            No rows have been saved. Correct these rows in Excel and check again.
                        </p>
                    </div>

                    <TableShell>
                        <Table>
                            <TableHeader>
                                <TableRow className="bg-rose-50/50 dark:bg-rose-950/20">
                                    <TableHead className="w-24 font-semibold text-rose-900 dark:text-rose-300">Sheet Row</TableHead>
                                    <TableHead className="w-48 font-semibold text-rose-900 dark:text-rose-300">Target Field</TableHead>
                                    <TableHead className="font-semibold text-rose-900 dark:text-rose-300">Validation Issue</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {result.errors.map((e, i) => (
                                    <TableRow key={i} className="hover:bg-rose-50/20 dark:hover:bg-rose-950/10">
                                        <TableCell>
                                            <Badge variant="outline" className="font-mono text-xs bg-slate-100 dark:bg-slate-800">
                                                Row {e.row}
                                            </Badge>
                                        </TableCell>
                                        <TableCell>
                                            <span className="font-mono text-xs text-slate-800 dark:text-slate-200 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded">
                                                {e.column}
                                            </span>
                                        </TableCell>
                                        <TableCell className="text-xs text-rose-700 dark:text-rose-300">
                                            {e.message}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableShell>
                </div>
            )}

            {/* Validation Passed: Preview Matrix */}
            {ready && result && (
                <div className="space-y-3">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800">
                        <div className="flex items-center gap-2">
                            <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0" />
                            <div>
                                <h4 className="text-xs font-bold text-emerald-900 dark:text-emerald-200">
                                    Spreadsheet Audit Passed: Ready to Import
                                </h4>
                                <p className="text-[11px] text-emerald-700 dark:text-emerald-400">
                                    All {result.rows} rows verified without format errors.
                                    {result.rows > result.preview.length && ` (Showing first ${result.preview.length} sample rows below)`}
                                </p>
                            </div>
                        </div>

                        <Button
                            size="sm"
                            onClick={() => send(true)}
                            disabled={busy !== null}
                            className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs h-8 shrink-0 shadow-sm"
                        >
                            {busy === "save" ? (
                                <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
                            ) : (
                                <Upload className="h-3.5 w-3.5 mr-2" />
                            )}
                            Confirm & Ingest All {result.rows} Records
                        </Button>
                    </div>

                    <TableShell>
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    {columns.map((c) => (
                                        <TableHead key={c} className="font-semibold text-xs whitespace-nowrap">
                                            {PREVIEW_LABELS[c] ?? c}
                                        </TableHead>
                                    ))}
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {result.preview.map((r, i) => (
                                    <TableRow key={i} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                                        {columns.map((c) => (
                                            <TableCell key={c} className="text-xs py-2.5 whitespace-nowrap">
                                                {String(r[c] ?? "")}
                                            </TableCell>
                                        ))}
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableShell>
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
            {/* Header Title Section */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200/80 dark:border-slate-800 pb-5">
                <div>
                    <div className="flex items-center gap-2">
                        <div className="p-2 rounded-xl bg-sky-600 text-white shadow-sm">
                            <FileSpreadsheet className="h-5 w-5" />
                        </div>
                        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                            Data Ingestion Studio
                        </h1>
                        <Badge variant="outline" className="border-sky-300 dark:border-sky-800 text-sky-700 dark:text-sky-300 bg-sky-50 dark:bg-sky-950/50 text-xs">
                            Bulk Loader
                        </Badge>
                    </div>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        High-speed bulk import for students, faculty records, and legacy opening fee ledger balances from Excel spreadsheets.
                    </p>
                </div>
            </div>

            {/* Ingestion Stream Selector Pills */}
            <div className="flex flex-wrap gap-2 border-b border-slate-200/80 dark:border-slate-800 pb-3">
                {available.map((k) => {
                    const Icon = k.icon;
                    const isActive = current.kind === k.kind;
                    return (
                        <button
                            key={k.kind}
                            onClick={() => setActive(k.kind)}
                            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-medium transition ${
                                isActive
                                    ? "bg-sky-600 text-white shadow-sm"
                                    : "bg-slate-100 hover:bg-slate-200/80 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300"
                            }`}
                        >
                            <Icon className={`h-4 w-4 ${isActive ? "text-white" : "text-slate-500 dark:text-slate-400"}`} />
                            <span>{k.label}</span>
                        </button>
                    );
                })}
            </div>

            {/* Ingestion Panel for Selected Category */}
            <ImportPanel key={current.kind} config={current} />
        </div>
    );
}
