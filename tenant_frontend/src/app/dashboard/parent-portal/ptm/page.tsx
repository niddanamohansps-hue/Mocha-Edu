"use client";

import { useState } from "react";
import {
    Calendar,
    Clock,
    User,
    Video,
    MapPin,
    CheckCircle2,
    XCircle,
    CalendarCheck,
    AlertCircle,
    MessageSquare,
    LoaderCircle,
    X,
} from "lucide-react";
import { useLinkedChildren } from "@/hooks/useParentPortal";
import {
    useParentPTMSessions,
    useParentAvailableSlots,
    useParentBookSlot,
    useParentCancelBooking,
    useParentMyBookings,
    PTMSession,
} from "@/hooks/usePTM";
import ChildSwitcher from "@/components/parent-portal/ChildSwitcher";
import { Card, CardContent } from "@/components/ui/card";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { Button } from "@/components/ui/button";

export default function ParentPTMPage() {
    const { data: children = [], isLoading: loadingChildren } = useLinkedChildren();
    const [selectedChildId, setSelectedChildId] = useState<string | undefined>(undefined);

    const effectiveChildId = selectedChildId || children[0]?.student_id;
    const selectedChild = children.find((c) => c.student_id === effectiveChildId);

    // Queries
    const { data: sessions = [], isLoading: loadingSessions } = useParentPTMSessions();
    const { data: myBookings = [], isLoading: loadingBookings } = useParentMyBookings();

    const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);

    // Slots for selected session and child
    const {
        data: slotData,
        isLoading: loadingSlots,
    } = useParentAvailableSlots(selectedSessionId, effectiveChildId || null);

    // Booking modal
    const [bookingSlot, setBookingSlot] = useState<{
        id: string;
        teacherName: string;
        time: string;
    } | null>(null);
    const [parentNotes, setParentNotes] = useState("");

    const bookMutation = useParentBookSlot();
    const cancelMutation = useParentCancelBooking();

    const handleConfirmBooking = () => {
        if (!bookingSlot || !effectiveChildId) return;
        bookMutation.mutate(
            {
                slotId: bookingSlot.id,
                studentId: effectiveChildId,
                notes: parentNotes,
            },
            {
                onSuccess: () => {
                    setBookingSlot(null);
                    setParentNotes("");
                },
            }
        );
    };

    const handleCancelBooking = (slotId: string) => {
        if (confirm("Are you sure you want to cancel this meeting booking?")) {
            cancelMutation.mutate(slotId);
        }
    };

    // Filter my bookings for the active child (or show all)
    const activeChildBookings = myBookings.filter(
        (b) => b.student === effectiveChildId || b.student_detail?.id === effectiveChildId
    );

    return (
        <div className="space-y-6 max-w-6xl mx-auto pb-12">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2.5">
                    <CalendarCheck className="h-7 w-7 text-indigo-600 dark:text-indigo-400" />
                    Parent-Teacher Meetings (PTM)
                </h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Book dedicated one-on-one discussion slots with your child's teachers and view meeting schedules.
                </p>
            </div>

            <ChildSwitcher
                childOptions={children}
                selectedId={effectiveChildId}
                onChange={setSelectedChildId}
            />

            {/* My Scheduled Meetings */}
            <div className="space-y-3">
                <h2 className="text-base font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                    My Scheduled Meetings ({activeChildBookings.length})
                </h2>

                {loadingBookings ? (
                    <LoadingState className="py-6" />
                ) : activeChildBookings.length === 0 ? (
                    <Card className="border border-dashed border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/40">
                        <CardContent className="p-5 text-center text-sm text-slate-500">
                            No meetings booked yet for {selectedChild?.full_name || "this child"}. Select an upcoming PTM session below to book a time slot.
                        </CardContent>
                    </Card>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {activeChildBookings.map((b) => (
                            <Card key={b.id} className="border border-indigo-100 dark:border-indigo-950/40 bg-white dark:bg-slate-900 shadow-sm hover:shadow transition">
                                <CardContent className="p-4 space-y-3">
                                    <div className="flex items-start justify-between">
                                        <div>
                                            <p className="font-semibold text-slate-900 dark:text-white text-base">
                                                {b.teacher_detail?.full_name || "Assigned Teacher"}
                                            </p>
                                            <p className="text-xs text-indigo-600 dark:text-indigo-400 font-medium">
                                                {b.teacher_detail?.designation || "Faculty"} • {b.teacher_detail?.department || "Academic"}
                                            </p>
                                        </div>
                                        <span className={`px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wider ${
                                            b.status === "completed"
                                                ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                                                : "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300"
                                        }`}>
                                            {b.status}
                                        </span>
                                    </div>

                                    <div className="grid grid-cols-2 gap-2 text-xs text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/60 p-2.5 rounded-lg">
                                        <div className="flex items-center gap-1.5">
                                            <Clock className="h-3.5 w-3.5 text-slate-400" />
                                            <span>{b.start_time.slice(0, 5)} - {b.end_time.slice(0, 5)}</span>
                                        </div>
                                        <div className="flex items-center gap-1.5">
                                            <User className="h-3.5 w-3.5 text-slate-400" />
                                            <span className="truncate">{b.student_detail?.full_name}</span>
                                        </div>
                                    </div>

                                    {b.parent_notes && (
                                        <div className="text-xs text-slate-600 dark:text-slate-400 bg-amber-50/50 dark:bg-amber-950/20 p-2 rounded border border-amber-200/50 dark:border-amber-900/30">
                                            <span className="font-medium text-amber-800 dark:text-amber-400">Discussion Agenda:</span> {b.parent_notes}
                                        </div>
                                    )}

                                    {b.teacher_feedback && (
                                        <div className="text-xs text-slate-700 dark:text-slate-300 bg-emerald-50 dark:bg-emerald-950/30 p-2.5 rounded border border-emerald-200 dark:border-emerald-900/40">
                                            <p className="font-semibold text-emerald-800 dark:text-emerald-300">Teacher Remarks & Action Items:</p>
                                            <p className="mt-1">{b.teacher_feedback}</p>
                                        </div>
                                    )}

                                    {b.status === "booked" && (
                                        <div className="pt-1 flex justify-end">
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => handleCancelBooking(b.id)}
                                                disabled={cancelMutation.isPending}
                                                className="text-xs text-rose-600 hover:text-rose-700 hover:bg-rose-50 dark:hover:bg-rose-950/30 border-rose-200 h-7"
                                            >
                                                Cancel Slot
                                            </Button>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                )}
            </div>

            {/* Upcoming PTM Sessions */}
            <div className="space-y-4 pt-4 border-t border-slate-200 dark:border-slate-800">
                <div>
                    <h2 className="text-base font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                        <Calendar className="h-5 w-5 text-indigo-600" />
                        Upcoming PTM Sessions
                    </h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                        Choose a session to view participating teachers and book an open discussion slot.
                    </p>
                </div>

                {loadingSessions ? (
                    <LoadingState className="py-10" />
                ) : sessions.length === 0 ? (
                    <EmptyState
                        title="No PTM Sessions currently scheduled"
                        description="Your school has not scheduled any open parent-teacher meetings for this class at this time."
                    />
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {sessions.map((sess) => {
                            const isSelected = selectedSessionId === sess.id;
                            return (
                                <div
                                    key={sess.id}
                                    onClick={() => setSelectedSessionId(sess.id)}
                                    className={`cursor-pointer rounded-xl border p-4 transition text-left ${
                                        isSelected
                                            ? "border-indigo-600 ring-2 ring-indigo-600/20 bg-indigo-50/20 dark:bg-indigo-950/20"
                                            : "border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-slate-300"
                                    }`}
                                >
                                    <div className="flex items-start justify-between">
                                        <div>
                                            <h3 className="font-semibold text-slate-900 dark:text-white text-base">
                                                {sess.title}
                                            </h3>
                                            <p className="text-xs text-slate-500 mt-0.5">
                                                {sess.level_name ? `Grade: ${sess.level_name}` : "School-wide"}
                                                {sess.section_name ? ` - Section ${sess.section_name}` : ""}
                                            </p>
                                        </div>
                                        <span className="px-2 py-0.5 rounded text-xs font-medium bg-indigo-50 text-indigo-700 dark:bg-indigo-950/50 dark:text-indigo-300">
                                            {sess.mode === "in_person" ? "In-Person" : "Online Video"}
                                        </span>
                                    </div>

                                    <div className="mt-3 flex flex-wrap gap-y-1.5 gap-x-4 text-xs text-slate-600 dark:text-slate-400">
                                        <div className="flex items-center gap-1">
                                            <Calendar className="h-3.5 w-3.5 text-slate-400" />
                                            <span>{sess.meeting_date}</span>
                                        </div>
                                        <div className="flex items-center gap-1">
                                            <Clock className="h-3.5 w-3.5 text-slate-400" />
                                            <span>{sess.start_time.slice(0, 5)} - {sess.end_time.slice(0, 5)} ({sess.slot_duration_minutes}m slots)</span>
                                        </div>
                                        {sess.location_or_url && (
                                            <div className="flex items-center gap-1">
                                                {sess.mode === "online" ? (
                                                    <Video className="h-3.5 w-3.5 text-indigo-500" />
                                                ) : (
                                                    <MapPin className="h-3.5 w-3.5 text-emerald-500" />
                                                )}
                                                <span className="truncate max-w-[200px]">{sess.location_or_url}</span>
                                            </div>
                                        )}
                                    </div>

                                    {sess.instructions && (
                                        <p className="mt-2.5 text-xs text-slate-500 bg-slate-50 dark:bg-slate-800/50 p-2 rounded line-clamp-2">
                                            {sess.instructions}
                                        </p>
                                    )}

                                    <div className="mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs">
                                        <span className="text-slate-500">
                                            {sess.teachers_detail?.length || 0} Participating Faculty
                                        </span>
                                        <span className="font-semibold text-indigo-600 dark:text-indigo-400">
                                            {isSelected ? "Slots Loaded Below ↓" : "Click to View Slots →"}
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Slots Matrix for Selected Session */}
            {selectedSessionId && (
                <div className="space-y-4 pt-6 border-t border-slate-200 dark:border-slate-800">
                    <div className="flex items-center justify-between">
                        <div>
                            <h2 className="text-base font-semibold text-slate-900 dark:text-white">
                                Available Time Slots: {slotData?.session?.title}
                            </h2>
                            <p className="text-xs text-slate-500">
                                Click an available slot to book your meeting with the designated teacher.
                            </p>
                        </div>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSelectedSessionId(null)}
                            className="text-xs text-slate-500"
                        >
                            Close Slots
                        </Button>
                    </div>

                    {loadingSlots ? (
                        <LoadingState className="py-12" />
                    ) : !slotData?.slots || slotData.slots.length === 0 ? (
                        <EmptyState
                            title="No slots generated for this session yet"
                            description="Please check back shortly or contact school administration."
                        />
                    ) : (
                        <div className="space-y-6">
                            {/* Group slots by teacher */}
                            {Array.from(
                                new Set(slotData.slots.map((s) => s.teacher.id))
                            ).map((teacherId) => {
                                const teacherSlots = slotData.slots.filter((s) => s.teacher.id === teacherId);
                                const teacher = teacherSlots[0].teacher;

                                return (
                                    <div
                                        key={teacherId}
                                        className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 space-y-3"
                                    >
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-3">
                                                <div className="w-9 h-9 rounded-full bg-indigo-50 dark:bg-indigo-950 flex items-center justify-center text-indigo-600 dark:text-indigo-400 font-bold text-sm">
                                                    {teacher.full_name.slice(0, 2).toUpperCase()}
                                                </div>
                                                <div>
                                                    <p className="font-semibold text-slate-900 dark:text-white text-sm">
                                                        {teacher.full_name}
                                                    </p>
                                                    <p className="text-xs text-slate-500">
                                                        {teacher.designation} • {teacher.department || "Faculty"}
                                                    </p>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Slot Buttons Grid */}
                                        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2 pt-2">
                                            {teacherSlots.map((slot) => {
                                                const isAvailable = slot.status === "available";
                                                const isMine = slot.is_booked_for_this_child;

                                                let buttonClass = "border text-xs font-medium py-2 px-2.5 rounded-lg transition flex flex-col items-center justify-center gap-0.5 ";
                                                if (isMine) {
                                                    buttonClass += "bg-emerald-50 border-emerald-300 text-emerald-800 dark:bg-emerald-950 dark:border-emerald-800 dark:text-emerald-300";
                                                } else if (isAvailable) {
                                                    buttonClass += "bg-slate-50 hover:bg-indigo-50 hover:border-indigo-300 border-slate-200 text-slate-800 dark:bg-slate-800/60 dark:hover:bg-indigo-950 dark:border-slate-700 dark:text-slate-200 cursor-pointer";
                                                } else {
                                                    buttonClass += "bg-slate-100 border-slate-200 text-slate-400 dark:bg-slate-800/30 dark:border-slate-800 dark:text-slate-600 cursor-not-allowed line-through";
                                                }

                                                return (
                                                    <button
                                                        key={slot.id}
                                                        disabled={!isAvailable && !isMine}
                                                        onClick={() => {
                                                            if (isMine) {
                                                                handleCancelBooking(slot.id);
                                                            } else if (isAvailable) {
                                                                setBookingSlot({
                                                                    id: slot.id,
                                                                    teacherName: teacher.full_name,
                                                                    time: `${slot.start_time} - ${slot.end_time}`,
                                                                });
                                                            }
                                                        }}
                                                        className={buttonClass}
                                                    >
                                                        <span>{slot.start_time} - {slot.end_time}</span>
                                                        <span className="text-[10px] font-normal opacity-80">
                                                            {isMine ? "Your Booking (Cancel)" : isAvailable ? "Available" : slot.status}
                                                        </span>
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            )}

            {/* Booking Modal */}
            {bookingSlot && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
                    <div className="bg-white dark:bg-slate-900 rounded-xl max-w-md w-full p-5 space-y-4 shadow-xl border border-slate-200 dark:border-slate-800">
                        <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                            <h3 className="font-semibold text-slate-900 dark:text-white">
                                Confirm Meeting Booking
                            </h3>
                            <button
                                onClick={() => setBookingSlot(null)}
                                className="text-slate-400 hover:text-slate-600"
                            >
                                <X className="h-5 w-5" />
                            </button>
                        </div>

                        <div className="space-y-2 text-xs text-slate-600 dark:text-slate-400">
                            <div className="p-3 bg-indigo-50/60 dark:bg-indigo-950/40 rounded-lg space-y-1">
                                <p><strong className="text-slate-800 dark:text-slate-200">Teacher:</strong> {bookingSlot.teacherName}</p>
                                <p><strong className="text-slate-800 dark:text-slate-200">Time Slot:</strong> {bookingSlot.time}</p>
                                <p><strong className="text-slate-800 dark:text-slate-200">Student:</strong> {selectedChild?.full_name}</p>
                            </div>

                            <div className="space-y-1 pt-1">
                                <label className="font-medium text-slate-700 dark:text-slate-300">
                                    Discussion Points / Questions (Optional):
                                </label>
                                <textarea
                                    value={parentNotes}
                                    onChange={(e) => setParentNotes(e.target.value)}
                                    placeholder="e.g. Questions regarding midterm exam scores, classroom engagement, homework..."
                                    rows={3}
                                    className="w-full text-xs p-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
                                />
                            </div>
                        </div>

                        <div className="flex justify-end gap-2 pt-2">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setBookingSlot(null)}
                                className="text-xs"
                            >
                                Cancel
                            </Button>
                            <Button
                                size="sm"
                                onClick={handleConfirmBooking}
                                disabled={bookMutation.isPending}
                                className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white"
                            >
                                {bookMutation.isPending ? "Booking..." : "Confirm & Book Slot"}
                            </Button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

