"use client";

import { useState } from "react";
import { BedDouble, Building2, LoaderCircle, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogBody, DialogContent, DialogFooter, ModalHeader } from "@/components/ui/dialog";
import { StudentPicker } from "@/components/common/StudentPicker";
import Unauthorized from "@/components/Unauthorized";
import { EmptyState } from "@/components/feedback/EmptyState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { usePermissions } from "@/providers/PermissionProvider";
import { useFeeStructures } from "@/hooks/useFees";
import type { Student } from "@/hooks/useStudents";
import { formatIndianCurrency } from "@/lib/currency";
import {
    Hostel,
    HostelGender,
    HostelRoom,
    useAllocate,
    useChargeHostel,
    useHostelChargePreview,
    useHostels,
    useRooms,
    useSaveHostel,
    useSaveRoom,
    useVacate,
    showDate,
} from "@/hooks/useHostel";

const selectClass =
    "h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";
const GENDER_LABEL: Record<HostelGender, string> = { boys: "Boys", girls: "Girls", mixed: "Mixed" };

export default function HostelPage() {
    const { can } = usePermissions();
    const canManage = can("manage_hostel");
    const hostels = useHostels();
    const [selected, setSelected] = useState<string | null>(null);
    if (!canManage && !can("view_hostel")) return <Unauthorized />;
    const current = hostels.data?.find((h) => h.id === selected) ?? hostels.data?.[0];

    return (
        <div className="space-y-6 p-4 md:p-6">
            <div>
                <h1 className="flex items-center gap-2 text-2xl font-bold"><Building2 className="h-6 w-6 text-sky-600" /> Hostel</h1>
                <p className="mt-1 max-w-3xl text-sm text-slate-500">
                    Hostels, rooms and which boarder lives where. Give a student a room, move them, or record that they left;
                    the history is kept. Link a hostel to a fee structure to charge its boarders the hostel fee.
                </p>
            </div>

            {canManage && <NewHostelForm />}

            {hostels.isLoading ? (
                <LoadingState />
            ) : !hostels.data?.length ? (
                <EmptyState title="No hostels yet" description={canManage ? "Add your first hostel above." : "The school has not set up a hostel."} />
            ) : (
                <>
                    <div className="flex flex-wrap gap-3">
                        {hostels.data.map((h) => (
                            <button
                                key={h.id}
                                type="button"
                                onClick={() => setSelected(h.id)}
                                aria-pressed={current?.id === h.id}
                                className={`rounded-xl border px-4 py-3 text-left text-sm transition ${current?.id === h.id ? "border-sky-500 bg-sky-50 dark:bg-sky-950/40" : "border-slate-200 dark:border-slate-800"}`}
                            >
                                <div className="font-semibold">{h.name}</div>
                                <div className="text-xs text-slate-500">{GENDER_LABEL[h.gender]} · {h.occupied}/{h.beds} beds filled</div>
                            </button>
                        ))}
                    </div>
                    {current && <HostelDetail key={current.id} hostel={current} canManage={canManage} canCharge={canManage && can("manage_fee_structures")} />}
                </>
            )}
        </div>
    );
}

function NewHostelForm() {
    const save = useSaveHostel();
    const [name, setName] = useState("");
    const [gender, setGender] = useState<HostelGender>("boys");
    return (
        <form
            className="grid gap-3 rounded-xl border border-slate-200 p-4 dark:border-slate-800 md:grid-cols-[2fr_1fr_auto] md:items-end"
            onSubmit={(e) => { e.preventDefault(); save.mutate({ name: name.trim(), gender }, { onSuccess: () => setName("") }); }}
        >
            <div className="grid gap-1.5">
                <Label htmlFor="hs-name">New hostel</Label>
                <Input id="hs-name" value={name} placeholder="Tagore House" onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
                <Label htmlFor="hs-gender">For</Label>
                <select id="hs-gender" className={selectClass} value={gender} onChange={(e) => setGender(e.target.value as HostelGender)}>
                    <option value="boys">Boys</option><option value="girls">Girls</option><option value="mixed">Mixed</option>
                </select>
            </div>
            <Button type="submit" disabled={!name.trim() || save.isPending}><Plus className="h-4 w-4" /> Add hostel</Button>
        </form>
    );
}

function HostelDetail({ hostel, canManage, canCharge }: { hostel: Hostel; canManage: boolean; canCharge: boolean }) {
    const rooms = useRooms(hostel.id);
    const [assignTo, setAssignTo] = useState<HostelRoom | null>(null);
    const [charging, setCharging] = useState(false);

    return (
        <div className="space-y-5">
            <HostelSettings hostel={hostel} canManage={canManage} onCharge={canCharge ? () => setCharging(true) : undefined} />
            {canManage && <NewRoomForm hostelId={hostel.id} />}
            {rooms.isLoading ? <LoadingState /> : !rooms.data?.length ? (
                <EmptyState title="No rooms yet" description={canManage ? "Add rooms above, with how many beds each has." : "No rooms have been added."} />
            ) : (
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    {rooms.data.map((r) => <RoomCard key={r.id} room={r} canManage={canManage} onAssign={() => setAssignTo(r)} />)}
                </div>
            )}
            {assignTo && <AssignDialog room={assignTo} hostel={hostel} onClose={() => setAssignTo(null)} />}
            {charging && <ChargeDialog hostel={hostel} onClose={() => setCharging(false)} />}
        </div>
    );
}

function HostelSettings({ hostel, canManage, onCharge }: { hostel: Hostel; canManage: boolean; onCharge?: () => void }) {
    const save = useSaveHostel();
    const structures = useFeeStructures();
    const [phone, setPhone] = useState(hostel.warden_phone);
    return (
        <div className="grid gap-3 rounded-xl border border-slate-200 p-4 text-sm dark:border-slate-800 md:grid-cols-[1fr_2fr_auto] md:items-end">
            <div className="grid gap-1.5">
                <Label htmlFor="hs-phone">Warden&apos;s phone</Label>
                <Input id="hs-phone" value={phone} disabled={!canManage} onChange={(e) => setPhone(e.target.value)}
                    onBlur={() => phone !== hostel.warden_phone && save.mutate({ id: hostel.id, warden_phone: phone })} />
            </div>
            <div className="grid gap-1.5">
                <Label htmlFor="hs-fee">Hostel fee</Label>
                <select id="hs-fee" className={selectClass} disabled={!canManage} value={hostel.fee_structure ?? ""}
                    onChange={(e) => save.mutate({ id: hostel.id, fee_structure: e.target.value || null })}>
                    <option value="">No hostel fee</option>
                    {(structures.data ?? []).map((s) => (
                        <option key={s.id} value={s.id}>{`${s.fee_head_name} · ${s.academic_year} · ${formatIndianCurrency(s.amount)}${s.level_name ? ` · ${s.level_name}` : ""}`}</option>
                    ))}
                </select>
            </div>
            {onCharge && <Button variant="outline" disabled={!hostel.fee_structure} onClick={onCharge}>Charge boarders</Button>}
        </div>
    );
}

function NewRoomForm({ hostelId }: { hostelId: string }) {
    const save = useSaveRoom();
    const [form, setForm] = useState({ number: "", floor: "", capacity: "2" });
    return (
        <form
            className="grid gap-3 md:grid-cols-[1fr_1fr_1fr_auto] md:items-end"
            onSubmit={(e) => {
                e.preventDefault();
                save.mutate({ hostel: hostelId, number: form.number.trim(), floor: form.floor.trim(), capacity: Number(form.capacity) },
                    { onSuccess: () => setForm({ ...form, number: "" }) });
            }}
        >
            <div className="grid gap-1.5"><Label htmlFor="rm-no">Room</Label><Input id="rm-no" value={form.number} placeholder="101" onChange={(e) => setForm({ ...form, number: e.target.value })} /></div>
            <div className="grid gap-1.5"><Label htmlFor="rm-floor">Floor</Label><Input id="rm-floor" value={form.floor} placeholder="Ground" onChange={(e) => setForm({ ...form, floor: e.target.value })} /></div>
            <div className="grid gap-1.5"><Label htmlFor="rm-beds">Beds</Label><Input id="rm-beds" type="number" min={1} value={form.capacity} onChange={(e) => setForm({ ...form, capacity: e.target.value })} /></div>
            <Button type="submit" disabled={!form.number.trim() || !(Number(form.capacity) >= 1) || save.isPending}><Plus className="h-4 w-4" /> Add room</Button>
        </form>
    );
}

function RoomCard({ room, canManage, onAssign }: { room: HostelRoom; canManage: boolean; onAssign: () => void }) {
    const vacate = useVacate();
    const full = room.occupied >= room.capacity;
    return (
        <div className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
            <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold"><BedDouble className="h-4 w-4 text-slate-400" /> Room {room.number}{room.floor && <span className="text-xs font-normal text-slate-500">· {room.floor}</span>}</div>
                <Badge variant="outline">{room.occupied}/{room.capacity}{full ? " · full" : ""}</Badge>
            </div>
            {room.occupants.length === 0 ? <p className="text-xs text-slate-500">Empty</p> : (
                <ul className="space-y-1.5 text-sm">
                    {room.occupants.map((o) => (
                        <li key={o.allocation} className="flex items-center justify-between gap-2">
                            <span>{o.name} <span className="text-xs text-slate-400">since {showDate(o.since)}</span></span>
                            {canManage && (
                                <Button variant="ghost" size="sm" className="h-7 text-xs" disabled={vacate.isPending}
                                    onClick={() => window.confirm(`${o.name} leaves room ${room.number} today?`) && vacate.mutate({ id: o.allocation })}>
                                    Moved out
                                </Button>
                            )}
                        </li>
                    ))}
                </ul>
            )}
            {canManage && !full && <Button variant="outline" size="sm" className="mt-3 w-full" onClick={onAssign}>Give a bed</Button>}
        </div>
    );
}

function AssignDialog({ room, hostel, onClose }: { room: HostelRoom; hostel: Hostel; onClose: () => void }) {
    const allocate = useAllocate();
    const [student, setStudent] = useState<Student | null>(null);
    const [start, setStart] = useState(() => new Date().toISOString().slice(0, 10));
    return (
        <Dialog open onOpenChange={(o) => !o && onClose()}>
            <DialogContent className="max-w-md p-0 rounded-2xl" showCloseButton={false}>
                <ModalHeader title={`Give a bed in room ${room.number}`} subtitle={`${hostel.name} · ${GENDER_LABEL[hostel.gender]}`} onClose={onClose} />
                <DialogBody className="space-y-4 px-6 py-5">
                    <div className="grid gap-1.5"><Label htmlFor="as-student">Student</Label><StudentPicker id="as-student" value={student} onChange={setStudent} /></div>
                    <div className="grid gap-1.5"><Label htmlFor="as-start">From</Label><Input id="as-start" type="date" value={start} onChange={(e) => setStart(e.target.value)} /></div>
                    <p className="text-xs text-slate-500">A student who already has a room is moved here; their old room is freed the day before.</p>
                </DialogBody>
                <DialogFooter className="px-6 py-4">
                    <Button variant="outline" onClick={onClose}>Cancel</Button>
                    <Button disabled={!student || allocate.isPending} onClick={() => student && allocate.mutate({ student: student.id, room: room.id, start_date: start }, { onSuccess: onClose })}>
                        {allocate.isPending && <LoaderCircle className="h-4 w-4 animate-spin" />} Give bed
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

function ChargeDialog({ hostel, onClose }: { hostel: Hostel; onClose: () => void }) {
    const preview = useHostelChargePreview(hostel.id, true);
    const charge = useChargeHostel(hostel.id);
    const p = preview.data;
    return (
        <Dialog open onOpenChange={(o) => !o && onClose()}>
            <DialogContent className="max-w-lg p-0 rounded-2xl" showCloseButton={false}>
                <ModalHeader title={`Charge the hostel fee: ${hostel.name}`} subtitle={hostel.fee_structure_label ?? ""} onClose={onClose} />
                <DialogBody className="space-y-3 px-6 py-5 text-sm">
                    {preview.isLoading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : !p ? (
                        <p className="text-rose-600">Could not load the preview.</p>
                    ) : (
                        <>
                            <p>{p.students_to_charge} of {p.students_total} boarders will be charged {formatIndianCurrency(p.amount_to_charge)} in total
                                {Number(p.concession_total) > 0 && `, after ${formatIndianCurrency(p.concession_total)} of concessions`}.</p>
                            {p.installments.length > 1 && <p className="text-slate-500">In {p.installments.length} instalments: {p.installments.map((i) => `${i.name} ${formatIndianCurrency(i.amount)}`).join(", ")}.</p>}
                            {p.students_already_charged > 0 && <p className="text-slate-500">{p.students_already_charged} already charged are skipped.</p>}
                            <p className="text-xs text-slate-500">Only boarders enrolled in {hostel.fee_structure_label?.split(" · ")[1]} are charged.</p>
                        </>
                    )}
                </DialogBody>
                <DialogFooter className="px-6 py-4">
                    <Button variant="outline" onClick={onClose}>Close</Button>
                    <Button disabled={!p || p.fees_to_create === 0 || charge.isPending} onClick={() => charge.mutate(undefined, { onSuccess: onClose })}>
                        {charge.isPending && <LoaderCircle className="h-4 w-4 animate-spin" />}
                        {p && p.fees_to_create > 0 ? `Charge ${p.students_to_charge} boarders` : "Nothing to charge"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
