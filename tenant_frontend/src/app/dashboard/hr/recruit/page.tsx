"use client";

import { useState } from "react";
import Link from "next/link";
import { Briefcase, Plus, School, UserPlus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AddApplicantDialog } from "@/components/recruitment/AddApplicantDialog";
import { ApplicantDialog } from "@/components/recruitment/ApplicantDialog";
import { OpeningDialog } from "@/components/recruitment/OpeningDialog";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { useApplicants, useOpeningAction, useOpenings, useRecruitmentSummary } from "@/hooks/useRecruitment";
import { usePermissions } from "@/providers/PermissionProvider";
import { STAGES, type Applicant, type JobOpening } from "@/types/Recruitment";

export default function RecruitPage() {
    const { can, isOwner } = usePermissions();
    const canView = isOwner || can("view_recruitment");
    const canAddStaff = isOwner || can("add_staff");
    if (!canView && !canAddStaff) return <Unauthorized />;
    return (
        <RecruitContent
            canView={canView}
            canManage={isOwner || can("manage_recruitment")}
            canHire={isOwner || (can("manage_recruitment") && can("add_staff"))}
            canAddStaff={canAddStaff}
        />
    );
}

function RecruitContent({
    canView,
    canManage,
    canHire,
    canAddStaff,
}: {
    canView: boolean;
    canManage: boolean;
    canHire: boolean;
    canAddStaff: boolean;
}) {
    return (
        <div className="max-w-6xl mx-auto space-y-8">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Recruitment</h1>
                <p className="text-slate-500 dark:text-slate-400 max-w-2xl">
                    Post openings, track applicants through interviews and offers, and hire them into the staff records.
                </p>
                {canView && (
                    <p className="text-sm text-slate-500">
                        Published openings are shown to candidates on your public{" "}
                        <Link href="/careers" target="_blank" className="underline">
                            careers page
                        </Link>
                        ; share that link to receive applications online.
                    </p>
                )}
            </div>

            {canView && <Pipeline canManage={canManage} canHire={canHire} />}

            {canAddStaff && (
                <section className="space-y-3">
                    <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide">Add someone directly</h2>
                    <p className="text-sm text-slate-500">For people already chosen outside this process.</p>
                    <div className="flex flex-wrap gap-3">
                        <Button asChild variant="outline">
                            <Link href="/dashboard/faculty/onboarding">
                                <School className="h-4 w-4 mr-2" /> Onboard instructor
                            </Link>
                        </Button>
                        <Button asChild variant="outline">
                            <Link href="/dashboard/staff/onboarding">
                                <Briefcase className="h-4 w-4 mr-2" /> Onboard general staff
                            </Link>
                        </Button>
                    </div>
                </section>
            )}
        </div>
    );
}

function Pipeline({ canManage, canHire }: { canManage: boolean; canHire: boolean }) {
    const { data: summary } = useRecruitmentSummary();
    const { data: openings = [], isLoading: openingsLoading } = useOpenings();

    const [openingFilter, setOpeningFilter] = useState("");
    const [stageFilter, setStageFilter] = useState("");
    const [search, setSearch] = useState("");
    const { data: applicants = [], isLoading: applicantsLoading } = useApplicants({
        opening: openingFilter || undefined,
        stage: stageFilter || undefined,
        search: search.trim() || undefined,
    });
    const openingAction = useOpeningAction();

    const [editing, setEditing] = useState<JobOpening | null | "new">(null);
    const [adding, setAdding] = useState(false);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    // The dialog reads the live row, so a stage change shows up without reopening it.
    const selected: Applicant | undefined = applicants.find((a) => a.id === selectedId);

    const selectClass =
        "h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";

    return (
        <>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
                <SummaryTile label="Open positions" value={summary?.open_openings} />
                {STAGES.filter((s) => s.value !== "rejected").map((s) => (
                    <SummaryTile key={s.value} label={s.label} value={summary?.applicants_by_stage[s.value]} />
                ))}
                <SummaryTile label="Interviews due" value={summary?.upcoming_interviews} />
            </div>

            <Tabs defaultValue="applicants">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <TabsList>
                        <TabsTrigger value="applicants">Applicants</TabsTrigger>
                        <TabsTrigger value="openings">Openings</TabsTrigger>
                    </TabsList>
                    {canManage && (
                        <div className="flex gap-2">
                            <Button variant="outline" onClick={() => setAdding(true)}>
                                <UserPlus className="h-4 w-4 mr-2" /> Add applicant
                            </Button>
                            <Button onClick={() => setEditing("new")}>
                                <Plus className="h-4 w-4 mr-2" /> New opening
                            </Button>
                        </div>
                    )}
                </div>

                <TabsContent value="applicants" className="space-y-4">
                    <div className="flex flex-wrap gap-3">
                        <Input
                            className="max-w-xs"
                            placeholder="Search name, email or phone"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                        <select className={selectClass} value={openingFilter} onChange={(e) => setOpeningFilter(e.target.value)}>
                            <option value="">All openings</option>
                            {openings.map((o) => (
                                <option key={o.id} value={o.id}>
                                    {o.title}
                                </option>
                            ))}
                        </select>
                        <select className={selectClass} value={stageFilter} onChange={(e) => setStageFilter(e.target.value)}>
                            <option value="">All stages</option>
                            {STAGES.map((s) => (
                                <option key={s.value} value={s.value}>
                                    {s.label}
                                </option>
                            ))}
                        </select>
                    </div>
                    {applicantsLoading ? (
                        <LoadingState />
                    ) : applicants.length === 0 ? (
                        <EmptyState title="No applicants" description="Applicants you add will appear here." />
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Name</TableHead>
                                    <TableHead>Opening</TableHead>
                                    <TableHead>Experience</TableHead>
                                    <TableHead>Score</TableHead>
                                    <TableHead>Stage</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {applicants.map((a) => (
                                    <TableRow key={a.id} className="cursor-pointer" onClick={() => setSelectedId(a.id)}>
                                        <TableCell className="font-medium">{a.full_name}</TableCell>
                                        <TableCell>{a.opening_title}</TableCell>
                                        <TableCell>{a.experience_years} yrs</TableCell>
                                        <TableCell>{a.average_score ?? "-"}</TableCell>
                                        <TableCell>
                                            <Badge variant="outline">{STAGES.find((s) => s.value === a.stage)?.label}</Badge>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    )}
                </TabsContent>

                <TabsContent value="openings" className="space-y-4">
                    {openingsLoading ? (
                        <LoadingState />
                    ) : openings.length === 0 ? (
                        <EmptyState title="No openings" description="Create an opening to start receiving applicants." />
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Title</TableHead>
                                    <TableHead>Type</TableHead>
                                    <TableHead>Vacancies</TableHead>
                                    <TableHead>Applicants</TableHead>
                                    <TableHead>Last date</TableHead>
                                    <TableHead>Status</TableHead>
                                    {canManage && <TableHead />}
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {openings.map((o) => (
                                    <TableRow key={o.id}>
                                        <TableCell className="font-medium">{o.title}</TableCell>
                                        <TableCell>{o.position_type === "instructor" ? "Instructor" : "Staff"}</TableCell>
                                        <TableCell>
                                            {o.hired_count}/{o.vacancies} filled
                                        </TableCell>
                                        <TableCell>{o.applicant_count}</TableCell>
                                        <TableCell>{o.last_date ?? "-"}</TableCell>
                                        <TableCell>
                                            <Badge variant="outline">{o.status}</Badge>
                                        </TableCell>
                                        {canManage && (
                                            <TableCell className="space-x-2 text-right">
                                                {o.status !== "closed" && (
                                                    <Button size="sm" variant="ghost" onClick={() => setEditing(o)}>
                                                        Edit
                                                    </Button>
                                                )}
                                                {o.status === "draft" && (
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        disabled={openingAction.isPending}
                                                        onClick={() => openingAction.mutate({ id: o.id, action: "publish" })}
                                                    >
                                                        Publish
                                                    </Button>
                                                )}
                                                {o.status === "open" && (
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        disabled={openingAction.isPending}
                                                        onClick={() => openingAction.mutate({ id: o.id, action: "close" })}
                                                    >
                                                        Close
                                                    </Button>
                                                )}
                                            </TableCell>
                                        )}
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    )}
                </TabsContent>
            </Tabs>

            {editing && (
                <OpeningDialog
                    key={editing === "new" ? "new" : editing.id}
                    opening={editing === "new" ? null : editing}
                    onClose={() => setEditing(null)}
                />
            )}
            {adding && (
                <AddApplicantDialog openings={openings} defaultOpening={openingFilter} onClose={() => setAdding(false)} />
            )}
            {selected && (
                <ApplicantDialog
                    key={selected.id}
                    applicant={selected}
                    canManage={canManage}
                    canHire={canHire}
                    onClose={() => setSelectedId(null)}
                />
            )}
        </>
    );
}

function SummaryTile({ label, value }: { label: string; value: number | undefined }) {
    return (
        <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
            <div className="text-2xl font-bold text-slate-900 dark:text-white">{value ?? "-"}</div>
            <div className="text-xs text-slate-500">{label}</div>
        </div>
    );
}
