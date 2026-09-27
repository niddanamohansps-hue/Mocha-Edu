"use client";

import { useMemo, useState } from "react";
import { LoaderCircle, ArrowRight, RotateCcw } from "lucide-react";
import { useAcademicLevels, useSections } from "@/hooks/useAcademics";
import {
    useExecutePromotion,
    usePreviewPromotion,
    usePromotionCandidates,
    usePromotionHistory,
    useReversePromotion,
} from "@/hooks/usePromotion";
import {
    PROMOTION_ACTION_LABELS,
    PromotionAction,
    PromotionEntryInput,
} from "@/types/Promotion";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import Unauthorized from "@/components/Unauthorized";

function currentYear() {
    return String(new Date().getFullYear());
}

function nextYear(year: string) {
    const n = parseInt(year, 10);
    return Number.isFinite(n) ? String(n + 1) : year;
}

const ACTIONS: PromotionAction[] = ["promoted", "retained", "withdrawn", "transferred", "graduated"];

export default function PromotionPage() {
    const { can, isOwner } = usePermissions();
    const canManage = isOwner || can("manage_student_promotion");

    // Step 1-3: source selection
    const [sourceYear, setSourceYear] = useState(currentYear());
    const [levelId, setLevelId] = useState("");
    const [sectionId, setSectionId] = useState("");

    const { data: levels } = useAcademicLevels();
    const { data: sections } = useSections();
    const sectionsForLevel = useMemo(
        () => (sections || []).filter((s) => s.level === levelId),
        [sections, levelId]
    );

    // Step 4-5: candidates + selection
    const { data: candidates, isLoading: loadingCandidates } = usePromotionCandidates(
        sourceYear,
        levelId,
        sectionId || undefined
    );
    const [selected, setSelected] = useState<Record<string, boolean>>({});
    const [actionByStudent, setActionByStudent] = useState<Record<string, PromotionAction>>({});

    // Step 6-8: target
    const [targetYear, setTargetYear] = useState(nextYear(currentYear()));
    const [targetLevelId, setTargetLevelId] = useState("");
    const [targetSectionId, setTargetSectionId] = useState("");
    const targetSectionsForLevel = useMemo(
        () => (sections || []).filter((s) => s.level === targetLevelId),
        [sections, targetLevelId]
    );

    const { mutate: preview, data: previewResults, isPending: previewing } = usePreviewPromotion();
    const { mutate: execute, data: executeResponse, isPending: executing } = useExecutePromotion();
    const { mutate: reverse } = useReversePromotion();
    const { data: history } = usePromotionHistory({ academic_year: sourceYear });

    const [showPreview, setShowPreview] = useState(false);

    if (!canManage) {
        return <Unauthorized />;
    }

    const toggleAll = (checked: boolean) => {
        const next: Record<string, boolean> = {};
        (candidates || []).forEach((c) => (next[c.student_id] = checked));
        setSelected(next);
    };

    const buildEntries = (): PromotionEntryInput[] => {
        return (candidates || [])
            .filter((c) => selected[c.student_id])
            .map((c) => {
                const action = actionByStudent[c.student_id] || "promoted";
                const entry: PromotionEntryInput = { student: c.student_id, action };
                if (action === "promoted" || action === "retained") {
                    entry.target_academic_year = targetYear;
                    if (action === "promoted" && targetLevelId) entry.target_level = targetLevelId;
                    if (targetSectionId) entry.target_section = targetSectionId;
                }
                return entry;
            });
    };

    const handlePreview = () => {
        const entries = buildEntries();
        if (entries.length === 0) return;
        preview({ source_academic_year: sourceYear, entries }, { onSuccess: () => setShowPreview(true) });
    };

    const handleConfirm = () => {
        const entries = buildEntries();
        if (entries.length === 0) return;
        execute({ source_academic_year: sourceYear, entries }, { onSuccess: () => setShowPreview(false) });
    };

    const selectedCount = Object.values(selected).filter(Boolean).length;

    return (
        <div className="space-y-8 max-w-5xl">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Promotion &amp; Transfer</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Promote, retain, withdraw, transfer, or graduate students at year end.
                </p>
            </div>

            {/* Step 1-3: source selection */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl">
                <div>
                    <label className="text-xs font-medium text-slate-500 mb-1 block">Academic Year</label>
                    <Input value={sourceYear} onChange={(e) => setSourceYear(e.target.value)} />
                </div>
                <div>
                    <label className="text-xs font-medium text-slate-500 mb-1 block">Level</label>
                    <Select value={levelId} onValueChange={(v) => { setLevelId(v); setSectionId(""); }}>
                        <SelectTrigger><SelectValue placeholder="Select level" /></SelectTrigger>
                        <SelectContent>
                            {levels?.map((l) => (
                                <SelectItem key={l.id} value={l.id}>{l.name}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
                <div>
                    <label className="text-xs font-medium text-slate-500 mb-1 block">Section (optional)</label>
                    <Select value={sectionId} onValueChange={setSectionId}>
                        <SelectTrigger><SelectValue placeholder="All sections" /></SelectTrigger>
                        <SelectContent>
                            {sectionsForLevel.map((s) => (
                                <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            </div>

            {/* Step 4-5: candidates */}
            {!levelId ? (
                <p className="text-sm text-slate-500 py-6">Select an academic year and level to load candidates.</p>
            ) : loadingCandidates ? (
                <div className="flex items-center justify-center py-16"><LoaderCircle className="h-8 w-8 animate-spin text-indigo-600" /></div>
            ) : !candidates || candidates.length === 0 ? (
                <p className="text-sm text-slate-500 py-6">No active students found for this year/level/section.</p>
            ) : (
                <div className="space-y-4">
                    <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                        <Table>
                            <TableHeader className="bg-slate-50 dark:bg-slate-900">
                                <TableRow>
                                    <TableHead className="w-10">
                                        <Checkbox
                                            checked={selectedCount === candidates.length && candidates.length > 0}
                                            onCheckedChange={(v) => toggleAll(!!v)}
                                        />
                                    </TableHead>
                                    <TableHead>Student</TableHead>
                                    <TableHead>Current</TableHead>
                                    <TableHead>Warnings</TableHead>
                                    <TableHead>Action</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {candidates.map((c) => (
                                    <TableRow key={c.student_id}>
                                        <TableCell>
                                            <Checkbox
                                                checked={!!selected[c.student_id]}
                                                onCheckedChange={(v) =>
                                                    setSelected((s) => ({ ...s, [c.student_id]: !!v }))
                                                }
                                            />
                                        </TableCell>
                                        <TableCell>
                                            <div className="font-medium">{c.full_name}</div>
                                            <div className="text-xs text-slate-500">{c.enrollment_id}</div>
                                        </TableCell>
                                        <TableCell className="text-sm">
                                            {c.current_level_name}
                                            {c.current_section_name ? ` - ${c.current_section_name}` : ""}
                                        </TableCell>
                                        <TableCell className="text-xs space-y-1">
                                            {c.fee_warning && (
                                                <div className="text-amber-600">Outstanding: {c.fee_warning}</div>
                                            )}
                                            {c.exam_warning && (
                                                <div className="text-amber-600">Failed: {c.exam_warning.join(", ")}</div>
                                            )}
                                            {!c.fee_warning && !c.exam_warning && <span className="text-slate-400">None</span>}
                                        </TableCell>
                                        <TableCell>
                                            <Select
                                                value={actionByStudent[c.student_id] || "promoted"}
                                                onValueChange={(v) =>
                                                    setActionByStudent((a) => ({ ...a, [c.student_id]: v as PromotionAction }))
                                                }
                                            >
                                                <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
                                                <SelectContent>
                                                    {ACTIONS.map((a) => (
                                                        <SelectItem key={a} value={a}>{PROMOTION_ACTION_LABELS[a]}</SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>

                    {/* Step 6-8: target (applies to any selected students whose action is Promote/Retain) */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl">
                        <div>
                            <label className="text-xs font-medium text-slate-500 mb-1 block">Target Academic Year</label>
                            <Input value={targetYear} onChange={(e) => setTargetYear(e.target.value)} />
                        </div>
                        <div>
                            <label className="text-xs font-medium text-slate-500 mb-1 block">
                                Target Level <span className="text-slate-400">(Promote only - default: next level)</span>
                            </label>
                            <Select value={targetLevelId} onValueChange={(v) => { setTargetLevelId(v); setTargetSectionId(""); }}>
                                <SelectTrigger><SelectValue placeholder="Default (next level)" /></SelectTrigger>
                                <SelectContent>
                                    {levels?.map((l) => (
                                        <SelectItem key={l.id} value={l.id}>{l.name}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div>
                            <label className="text-xs font-medium text-slate-500 mb-1 block">Target Section (optional)</label>
                            <Select value={targetSectionId} onValueChange={setTargetSectionId}>
                                <SelectTrigger><SelectValue placeholder="Unassigned" /></SelectTrigger>
                                <SelectContent>
                                    {targetSectionsForLevel.map((s) => (
                                        <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>

                    <div className="flex gap-3">
                        <Button onClick={handlePreview} disabled={previewing || selectedCount === 0} className="gap-2">
                            {previewing && <LoaderCircle className="h-4 w-4 animate-spin" />}
                            Preview ({selectedCount} selected)
                        </Button>
                    </div>
                </div>
            )}

            {/* Step 9-11: preview + confirm */}
            {showPreview && previewResults && (
                <div className="space-y-4 p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl">
                    <h2 className="text-lg font-bold">Preview</h2>
                    <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                        <Table>
                            <TableHeader className="bg-slate-50 dark:bg-slate-900">
                                <TableRow>
                                    <TableHead>Student</TableHead>
                                    <TableHead>Action</TableHead>
                                    <TableHead>Target</TableHead>
                                    <TableHead>Warnings</TableHead>
                                    <TableHead>Status</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {previewResults.map((r, i) => (
                                    <TableRow key={i}>
                                        <TableCell className="font-mono text-xs">{r.student}</TableCell>
                                        <TableCell className="capitalize">{r.action}</TableCell>
                                        <TableCell>{r.target_academic_year || "-"}</TableCell>
                                        <TableCell className="text-xs text-amber-600">
                                            {r.warnings.join("; ") || "-"}
                                        </TableCell>
                                        <TableCell>
                                            {r.eligible ? (
                                                <span className="text-xs font-semibold px-2 py-1 rounded-full bg-emerald-100 text-emerald-700">
                                                    Ready
                                                </span>
                                            ) : (
                                                <span className="text-xs font-semibold px-2 py-1 rounded-full bg-red-100 text-red-700">
                                                    {r.conflicts.join("; ")}
                                                </span>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>
                    <Button onClick={handleConfirm} disabled={executing} className="gap-2">
                        {executing && <LoaderCircle className="h-4 w-4 animate-spin" />}
                        <ArrowRight className="h-4 w-4" /> Confirm &amp; Execute
                    </Button>
                </div>
            )}

            {/* Step 12-13: success/skipped summary */}
            {executeResponse && (
                <Card className="border-none shadow-md">
                    <CardContent className="p-6 space-y-3">
                        <h2 className="text-lg font-bold">Execution Summary</h2>
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <p className="text-xs text-slate-500 uppercase font-bold">Successful</p>
                                <p className="text-2xl font-black text-emerald-600">
                                    {executeResponse.results.filter((r) => r.status === "success").length}
                                </p>
                            </div>
                            <div>
                                <p className="text-xs text-slate-500 uppercase font-bold">Skipped</p>
                                <p className="text-2xl font-black text-red-600">
                                    {executeResponse.results.filter((r) => r.status === "skipped").length}
                                </p>
                            </div>
                        </div>
                        {executeResponse.results.filter((r) => r.status === "skipped").length > 0 && (
                            <ul className="text-xs text-red-600 space-y-1">
                                {executeResponse.results
                                    .filter((r) => r.status === "skipped")
                                    .map((r, i) => (
                                        <li key={i}>{r.student}: {r.error}</li>
                                    ))}
                            </ul>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* Recent history for this year, with reversal */}
            {history && history.length > 0 && (
                <div className="space-y-3 pt-4 border-t border-slate-200 dark:border-slate-800">
                    <h2 className="text-lg font-bold">Recent Promotion History ({sourceYear})</h2>
                    <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                        <Table>
                            <TableHeader className="bg-slate-50 dark:bg-slate-900">
                                <TableRow>
                                    <TableHead>Student</TableHead>
                                    <TableHead>Action</TableHead>
                                    <TableHead>Year</TableHead>
                                    <TableHead>Level</TableHead>
                                    <TableHead></TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {history.map((r) => (
                                    <TableRow key={r.id}>
                                        <TableCell>{r.student_name}</TableCell>
                                        <TableCell className="capitalize">{r.action}</TableCell>
                                        <TableCell>{r.source_academic_year} → {r.target_academic_year || "-"}</TableCell>
                                        <TableCell>{r.source_level_name} → {r.target_level_name || "-"}</TableCell>
                                        <TableCell>
                                            {(r.action === "promoted" || r.action === "retained") && !r.is_reversed && (
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    onClick={() => reverse({ recordId: r.id })}
                                                    className="gap-1"
                                                >
                                                    <RotateCcw className="h-3 w-3" /> Reverse
                                                </Button>
                                            )}
                                            {r.is_reversed && <span className="text-xs text-slate-400">Reversed</span>}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>
                </div>
            )}
        </div>
    );
}
