"use client";

import { useState } from "react";
import Link from "next/link";
import { Printer } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import {
    useAllocateInvigilators,
    useAllocateRooms,
    useMoveSeat,
    useReplaceInvigilator,
    useSittingPlan,
    useSittings,
    useSyncSittings,
} from "@/hooks/useExamAllocation";
import { useExaminations } from "@/hooks/useExaminations";
import { useStaffMembers } from "@/hooks/useStaff";
import { useRooms } from "@/hooks/useTimetable";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { usePermissions } from "@/providers/PermissionProvider";
import type { PlanRoom, PlanSeat } from "@/types/ExamAllocation";
import type { Room } from "@/types/Timetable";

const selectClass =
    "h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";
const time = (t: string) => t.slice(0, 5);

export default function ExamAllocationPage() {
    const { can, isOwner } = usePermissions();
    const canManage = isOwner || can("manage_exam_allocation");
    if (!canManage && !(isOwner || can("view_examinations"))) return <Unauthorized />;
    return <AllocationContent canManage={canManage} />;
}

function AllocationContent({ canManage }: { canManage: boolean }) {
    const { selectedYear } = useAcademicYear();
    const { data: examinations = [] } = useExaminations(selectedYear?.name || undefined);
    const [examination, setExamination] = useState("");
    const [sittingId, setSittingId] = useState<string | undefined>();
    const { data: sittings = [], isLoading } = useSittings(examination || undefined);
    const sync = useSyncSittings();

    return (
        <div className="max-w-5xl mx-auto space-y-6">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Exam rooms and invigilators</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    Seat students in exam rooms and put staff on invigilation duty. Papers that start at the same time are
                    one sitting, so different classes can share rooms.
                </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
                <select
                    className={selectClass}
                    value={examination}
                    onChange={(e) => { setExamination(e.target.value); setSittingId(undefined); }}
                >
                    <option value="">Choose an examination</option>
                    {examinations.map((exam) => (
                        <option key={exam.id} value={exam.id}>{exam.name}</option>
                    ))}
                </select>
                {canManage && examination && (
                    <Button variant="outline" disabled={sync.isPending} onClick={() => sync.mutate(examination)}>
                        Refresh from exam schedule
                    </Button>
                )}
            </div>

            {!examination ? (
                <EmptyState title="Choose an examination" description="Its sittings will be listed here." />
            ) : isLoading ? (
                <LoadingState />
            ) : sittings.length === 0 ? (
                <EmptyState
                    title="No sittings yet"
                    description={canManage ? 'Add papers to the examination, then press "Refresh from exam schedule".' : "No papers are scheduled."}
                />
            ) : (
                <div className="space-y-3">
                    {sittings.map((sitting) => (
                        <button
                            key={sitting.id}
                            onClick={() => setSittingId(sitting.id === sittingId ? undefined : sitting.id)}
                            className={`w-full rounded-2xl border p-4 text-left transition ${
                                sitting.id === sittingId
                                    ? "border-indigo-400 bg-indigo-50/50 dark:bg-indigo-950/20"
                                    : "border-slate-200 bg-white hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900"
                            }`}
                        >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="font-semibold">
                                    {sitting.date} - {time(sitting.start_time)} to {time(sitting.end_time)}
                                </span>
                                <span className="flex gap-2">
                                    <Badge variant="outline">{sitting.seated} seated</Badge>
                                    <Badge variant="outline">{sitting.rooms_used} rooms</Badge>
                                    <Badge variant="outline">{sitting.invigilators} invigilators</Badge>
                                </span>
                            </div>
                            <p className="mt-1 text-sm text-slate-500">
                                {sitting.papers.map((p) => `${p.class}: ${p.subject}`).join("  |  ")}
                            </p>
                        </button>
                    ))}
                </div>
            )}

            {sittingId && <SittingDetail key={sittingId} sittingId={sittingId} canManage={canManage} />}
        </div>
    );
}

function SittingDetail({ sittingId, canManage }: { sittingId: string; canManage: boolean }) {
    const { data: plan, isLoading } = useSittingPlan(sittingId);
    const { data: rooms = [] } = useRooms();
    const { data: staffPage } = useStaffMembers({ pageSize: 200, isActive: true });
    const allocateRooms = useAllocateRooms();
    const allocateInvigilators = useAllocateInvigilators();
    const replace = useReplaceInvigilator();

    const [mix, setMix] = useState(true);
    const [chosenRooms, setChosenRooms] = useState<string[]>([]);
    const [perRoom, setPerRoom] = useState("2");
    const [avoidOwn, setAvoidOwn] = useState(true);
    const [nonTeaching, setNonTeaching] = useState(false);
    const [moving, setMoving] = useState<{ seat: PlanSeat; room: PlanRoom } | null>(null);

    if (isLoading || !plan) return <LoadingState />;
    const staff = staffPage?.results ?? [];

    return (
        <section className="space-y-6 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            {canManage && (
                <div className="grid gap-6 md:grid-cols-2">
                    <div className="space-y-3">
                        <h3 className="font-semibold">1. Rooms</h3>
                        <label className="flex items-center gap-2 text-sm">
                            <input type="checkbox" checked={mix} onChange={(e) => setMix(e.target.checked)} />
                            Mix classes so neighbours sit different papers
                        </label>
                        <div className="grid max-h-32 grid-cols-2 gap-1 overflow-y-auto rounded-lg border border-slate-200 p-2 text-sm dark:border-slate-800">
                            {(rooms as Room[]).map((room) => (
                                <label key={room.id} className="flex items-center gap-2">
                                    <input
                                        type="checkbox"
                                        checked={chosenRooms.includes(room.id)}
                                        onChange={(e) =>
                                            setChosenRooms((c) => (e.target.checked ? [...c, room.id] : c.filter((id) => id !== room.id)))
                                        }
                                    />
                                    {room.name} <span className="text-xs text-slate-400">({room.capacity})</span>
                                </label>
                            ))}
                        </div>
                        <p className="text-xs text-slate-500">
                            Leave all unticked to use the biggest free rooms. Rooms with no capacity set, or already used by
                            another exam at that time, are skipped.
                        </p>
                        <Button
                            disabled={allocateRooms.isPending}
                            onClick={() => allocateRooms.mutate({ sitting: sittingId, mix, rooms: chosenRooms.length ? chosenRooms : undefined })}
                        >
                            {plan.rooms.length ? "Re-allocate rooms" : "Allocate rooms"}
                        </Button>
                    </div>
                    <div className="space-y-3">
                        <h3 className="font-semibold">2. Invigilators</h3>
                        <div className="flex items-center gap-2 text-sm">
                            <Label>Per room</Label>
                            <Input className="w-20" type="number" min={1} max={4} value={perRoom} onChange={(e) => setPerRoom(e.target.value)} />
                        </div>
                        <label className="flex items-center gap-2 text-sm">
                            <input type="checkbox" checked={avoidOwn} onChange={(e) => setAvoidOwn(e.target.checked)} />
                            Not in a room with a class they teach
                        </label>
                        <label className="flex items-center gap-2 text-sm">
                            <input type="checkbox" checked={nonTeaching} onChange={(e) => setNonTeaching(e.target.checked)} />
                            Include non-teaching staff
                        </label>
                        <p className="text-xs text-slate-500">
                            Staff on approved leave or already on duty at that time are skipped, and duties are spread evenly.
                        </p>
                        <Button
                            variant="outline"
                            disabled={allocateInvigilators.isPending || plan.rooms.length === 0}
                            onClick={() =>
                                allocateInvigilators.mutate({
                                    sitting: sittingId,
                                    per_room: Number(perRoom) || 2,
                                    avoid_own_class: avoidOwn,
                                    include_non_teaching: nonTeaching,
                                })
                            }
                        >
                            {plan.rooms.some((r) => r.invigilators.length) ? "Re-allocate invigilators" : "Allocate invigilators"}
                        </Button>
                    </div>
                </div>
            )}

            {plan.unseated > 0 && (
                <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
                    {plan.unseated} student(s) in these papers have no seat (for example enrolled after the allocation). Re-allocate rooms.
                </p>
            )}

            {plan.rooms.length > 0 && (
                <div className="flex justify-end">
                    <Button asChild variant="outline">
                        <Link href={`/dashboard/examinations/allocation/${sittingId}/print`}>
                            <Printer className="mr-2 h-4 w-4" /> Print room sheets
                        </Link>
                    </Button>
                </div>
            )}

            {plan.rooms.map((entry) => (
                <div key={entry.room.id} className="space-y-3 rounded-xl border border-slate-200 p-4 dark:border-slate-800">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                        <h4 className="font-semibold">
                            {entry.room.name} <span className="text-sm font-normal text-slate-500">- {entry.seats.length} of {entry.room.capacity} seats</span>
                        </h4>
                        {canManage && (
                            <Button asChild size="sm" variant="outline">
                                <Link href={`/dashboard/examinations/hall-attendance?sitting=${sittingId}&room=${entry.room.id}`}>Attendance</Link>
                            </Button>
                        )}
                    </div>
                    <div className="space-y-1 text-sm">
                        {entry.invigilators.length === 0 && <p className="text-slate-500">No invigilators yet.</p>}
                        {entry.invigilators.map((duty) => (
                            <div key={duty.id} className="flex flex-wrap items-center gap-2">
                                <span className="font-medium">{duty.name}</span>
                                <span className="text-xs text-slate-400">{duty.employee_id}</span>
                                <Badge variant="outline">{duty.role === "chief" ? "Chief" : duty.role}</Badge>
                                {canManage && (
                                    <select
                                        className="h-8 rounded-md border border-slate-200 bg-white px-2 text-xs dark:border-slate-800 dark:bg-slate-950"
                                        value=""
                                        onChange={(e) => e.target.value && replace.mutate({ duty: duty.id, staff: e.target.value })}
                                    >
                                        <option value="">Replace with...</option>
                                        {staff.map((member) => (
                                            <option key={member.id} value={member.id}>
                                                {member.profile_details?.first_name} {member.profile_details?.last_name}
                                            </option>
                                        ))}
                                    </select>
                                )}
                            </div>
                        ))}
                    </div>
                    <div className="grid grid-cols-1 gap-x-6 gap-y-1 text-sm md:grid-cols-2">
                        {entry.seats.map((seat) => (
                            <div key={seat.student_id} className="flex items-center justify-between gap-2 border-b border-slate-100 py-1 dark:border-slate-800">
                                <span>
                                    <span className="mr-2 inline-block w-6 text-right font-mono text-slate-400">{seat.seat}</span>
                                    {seat.student} <span className="text-xs text-slate-400">{seat.class} - {seat.subject}</span>
                                </span>
                                {canManage && (
                                    <Button size="sm" variant="ghost" onClick={() => setMoving({ seat, room: entry })}>
                                        Move
                                    </Button>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            ))}

            {moving && (
                <MoveDialog
                    sittingId={sittingId}
                    seat={moving.seat}
                    rooms={rooms as Room[]}
                    currentRoom={moving.room.room.id}
                    onClose={() => setMoving(null)}
                />
            )}
        </section>
    );
}

function MoveDialog({
    sittingId, seat, rooms, currentRoom, onClose,
}: { sittingId: string; seat: PlanSeat; rooms: Room[]; currentRoom: string; onClose: () => void }) {
    const move = useMoveSeat();
    const [room, setRoom] = useState(currentRoom);
    const [number, setNumber] = useState(String(seat.seat));
    return (
        <Dialog open onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-sm">
                <DialogHeader>
                    <DialogTitle>Move {seat.student}</DialogTitle>
                </DialogHeader>
                <div className="grid gap-3">
                    <div className="grid gap-1.5">
                        <Label>Room</Label>
                        <select className={selectClass} value={room} onChange={(e) => setRoom(e.target.value)}>
                            {rooms.filter((r) => r.capacity > 0).map((r) => (
                                <option key={r.id} value={r.id}>{r.name} ({r.capacity})</option>
                            ))}
                        </select>
                    </div>
                    <div className="grid gap-1.5">
                        <Label>Seat number</Label>
                        <Input type="number" min={1} value={number} onChange={(e) => setNumber(e.target.value)} />
                    </div>
                    <p className="text-xs text-slate-500">If someone is in that seat, the two students swap.</p>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={onClose}>Cancel</Button>
                    <Button
                        disabled={move.isPending || !number}
                        onClick={() => move.mutate({ sitting: sittingId, student: seat.student_id, room, seat: Number(number) }, { onSuccess: onClose })}
                    >
                        Move
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
