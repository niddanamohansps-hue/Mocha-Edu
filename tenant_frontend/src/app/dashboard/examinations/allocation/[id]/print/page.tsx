"use client";

import { use } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { useSittingPlan } from "@/hooks/useExamAllocation";
import { usePermissions } from "@/providers/PermissionProvider";

const time = (t: string) => t.slice(0, 5);

export default function RoomSheetsPrintPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const router = useRouter();
    const { can, isOwner } = usePermissions();
    const { data: plan, isLoading, isError, refetch } = useSittingPlan(id);

    if (!isOwner && !can("view_examinations")) return <Unauthorized />;
    if (isLoading) return <LoadingState className="py-20" />;
    if (isError || !plan) return <ErrorState onRetry={refetch} />;

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 p-4 print:hidden dark:border-slate-800 dark:bg-slate-900">
                <Button variant="outline" onClick={() => router.back()}>Back</Button>
                <Button onClick={() => window.print()}>Print</Button>
            </div>
            <style jsx global>{`
                @media print {
                    @page { size: A4 portrait; margin: 12mm 15mm; }
                    body { background: white !important; color: black !important; }
                    nav, header, aside, .no-print { display: none !important; }
                    .room-sheet { page-break-after: always; border: none !important; box-shadow: none !important; }
                    .room-sheet:last-child { page-break-after: auto; }
                }
            `}</style>
            {plan.rooms.map((entry) => (
                <section key={entry.room.id} className="room-sheet mx-auto max-w-[210mm] rounded-xl border border-slate-200 bg-white p-8 text-slate-900">
                    <h1 className="text-2xl font-bold">Room {entry.room.name}</h1>
                    <p className="mb-1 text-sm">
                        {plan.sitting.date}, {time(plan.sitting.start_time)} to {time(plan.sitting.end_time)}
                    </p>
                    <p className="mb-3 text-sm text-slate-600">
                        {plan.sitting.papers.map((p) => `${p.class}: ${p.subject}`).join("  |  ")}
                    </p>
                    <p className="mb-4 text-sm">
                        <strong>Invigilators: </strong>
                        {entry.invigilators.length
                            ? entry.invigilators.map((i) => `${i.name}${i.role === "chief" ? " (chief)" : ""}`).join(", ")
                            : "not allocated"}
                    </p>
                    <table className="w-full border-collapse text-sm">
                        <thead>
                            <tr className="border-b-2 border-slate-900 text-left">
                                <th className="py-1 pr-2">Seat</th>
                                <th className="py-1 pr-2">Student</th>
                                <th className="py-1 pr-2">Enrollment no.</th>
                                <th className="py-1 pr-2">Class</th>
                                <th className="py-1 pr-2">Paper</th>
                                <th className="py-1">Signature</th>
                            </tr>
                        </thead>
                        <tbody>
                            {entry.seats.map((seat) => (
                                <tr key={seat.student_id} className="border-b border-slate-300">
                                    <td className="py-1.5 pr-2 font-mono">{seat.seat}</td>
                                    <td className="py-1.5 pr-2">{seat.student}</td>
                                    <td className="py-1.5 pr-2">{seat.enrollment_id}</td>
                                    <td className="py-1.5 pr-2">{seat.class}</td>
                                    <td className="py-1.5 pr-2">{seat.subject}</td>
                                    <td className="py-1.5 w-32"></td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </section>
            ))}
        </div>
    );
}
