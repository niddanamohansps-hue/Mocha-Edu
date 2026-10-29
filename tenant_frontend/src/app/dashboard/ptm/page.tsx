"use client";

import React, { useState } from "react";
import {
    Calendar,
    Clock,
    User,
    Users,
    CheckCircle2,
    XCircle,
    Plus,
    Search,
    Filter,
    CalendarCheck,
    MapPin,
    Video,
    AlertCircle,
    MessageSquare,
    Lock,
    Unlock,
    ChevronRight,
    Sparkles,
    X,
} from "lucide-react";
import {
    usePTMSessions,
    usePTMSessionRoster,
    useCreatePTMSession,
    useGenerateSlots,
    usePublishPTMSession,
    useCancelPTMSession,
    useBlockSlot,
    useUnblockSlot,
    useRecordSlotFeedback,
    useTeacherSchedule,
    PTMSession,
    PTMSlot,
} from "@/hooks/usePTM";
import { useStaffMembers } from "@/hooks/useStaff";
import { useAcademicYears, useAcademicLevels, useSections } from "@/hooks/useAcademics";
import { usePermissions } from "@/providers/PermissionProvider";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";

export default function PTMAdminPage() {
    const { can, isOwner } = usePermissions();
    const canManagePTM = isOwner || can("manage_ptm");
    const canRecordFeedback = isOwner || can("record_ptm_feedback") || can("manage_ptm");

    const [activeTab, setActiveTab] = useState<"sessions" | "roster" | "my_schedule">("sessions");

    // Filter states
    const [selectedStatus, setSelectedStatus] = useState<string>("");
    const [selectedLevel, setSelectedLevel] = useState<string>("");
    const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);

    // Queries
    const { data: sessions = [], isLoading: isLoadingSessions } = usePTMSessions({
        status: selectedStatus || undefined,
        level: selectedLevel || undefined,
    });

    const effectiveRosterSessionId = selectedSessionId || sessions[0]?.id || null;
    const { data: rosterData, isLoading: isLoadingRoster } = usePTMSessionRoster(effectiveRosterSessionId);
    const { data: teacherSchedule, isLoading: isLoadingSchedule } = useTeacherSchedule();

    const { data: staffData } = useStaffMembers({ pageSize: 100, isActive: true });
    const staffMembers = staffData?.results || [];
    const { data: academicYears = [] } = useAcademicYears();
    const { data: levels = [] } = useAcademicLevels();

    // Mutations
    const createSessionMutation = useCreatePTMSession();
    const generateSlotsMutation = useGenerateSlots();
    const publishSessionMutation = usePublishPTMSession();
    const cancelSessionMutation = useCancelPTMSession();
    const blockSlotMutation = useBlockSlot();
    const unblockSlotMutation = useUnblockSlot();
    const recordFeedbackMutation = useRecordSlotFeedback();

    // Modals
    const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
    const [feedbackModalSlot, setFeedbackModalSlot] = useState<PTMSlot | null>(null);
    const [feedbackNotes, setFeedbackNotes] = useState("");
    const [attendedCheck, setAttendedCheck] = useState(true);

    // Create session form state
    const [newTitle, setNewTitle] = useState("");
    const [newAcademicYear, setNewAcademicYear] = useState("");
    const [newMeetingDate, setNewMeetingDate] = useState("");
    const [newStartTime, setNewStartTime] = useState("09:00");
    const [newEndTime, setNewEndTime] = useState("13:00");
    const [newSlotDuration, setNewSlotDuration] = useState(15);
    const [newBufferMinutes, setNewBufferMinutes] = useState(0);
    const [newMode, setNewMode] = useState<"in_person" | "online">("in_person");
    const [newLocationOrUrl, setNewLocationOrUrl] = useState("");
    const [newLevel, setNewLevel] = useState("");
    const [newSelectedTeachers, setNewSelectedTeachers] = useState<string[]>([]);
    const [newInstructions, setNewInstructions] = useState("");

    // Roster filter
    const [rosterTeacherFilter, setRosterTeacherFilter] = useState<string>("");
    const [rosterStatusFilter, setRosterStatusFilter] = useState<string>("");
    const [rosterSearch, setRosterSearch] = useState<string>("");

    const handleCreateSession = (e: React.FormEvent) => {
        e.preventDefault();
        createSessionMutation.mutate(
            {
                title: newTitle,
                academic_year: newAcademicYear || undefined,
                meeting_date: newMeetingDate,
                start_time: newStartTime,
                end_time: newEndTime,
                slot_duration_minutes: Number(newSlotDuration),
                buffer_minutes: Number(newBufferMinutes),
                mode: newMode,
                location_or_url: newLocationOrUrl,
                level: newLevel || undefined,
                teacher_ids: newSelectedTeachers,
                instructions: newInstructions,
            },
            {
                onSuccess: () => {
                    setIsCreateModalOpen(false);
                    // Reset form
                    setNewTitle("");
                    setNewMeetingDate("");
                    setNewSelectedTeachers([]);
                    setNewInstructions("");
                },
            }
        );
    };

    const handleOpenFeedbackModal = (slot: PTMSlot) => {
        setFeedbackModalSlot(slot);
        setFeedbackNotes(slot.teacher_feedback || "");
        setAttendedCheck(slot.attended || false);
    };

    const handleSaveFeedback = () => {
        if (!feedbackModalSlot) return;
        recordFeedbackMutation.mutate(
            {
                slotId: feedbackModalSlot.id,
                feedback: feedbackNotes,
                attended: attendedCheck,
            },
            {
                onSuccess: () => {
                    setFeedbackModalSlot(null);
                },
            }
        );
    };

    // Filter roster slots
    const filteredRosterSlots = (rosterData?.slots || []).filter((s) => {
        if (rosterTeacherFilter && s.teacher !== rosterTeacherFilter) return false;
        if (rosterStatusFilter && s.status !== rosterStatusFilter) return false;
        if (rosterSearch) {
            const term = rosterSearch.toLowerCase();
            const studentMatch = s.student_detail?.full_name?.toLowerCase().includes(term);
            const parentMatch = s.parent_detail?.full_name?.toLowerCase().includes(term);
            const teacherMatch = s.teacher_detail?.full_name?.toLowerCase().includes(term);
            if (!studentMatch && !parentMatch && !teacherMatch) return false;
        }
        return true;
    });

    // Summary calculations
    const totalSessions = sessions.length;
    const activeSessions = sessions.filter((s) => s.status === "published").length;
    const totalSlotsCount = sessions.reduce((acc, s) => acc + (s.total_slots || 0), 0);
    const totalBookedCount = sessions.reduce((acc, s) => acc + (s.booked_slots_count || 0), 0);

    return (
        <div className="space-y-6 max-w-7xl mx-auto pb-16">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-2.5">
                        <CalendarCheck className="h-7 w-7 text-indigo-600 dark:text-indigo-400" />
                        Parent-Teacher Meetings (PTM)
                    </h1>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Schedule school-wide or class PTM sessions, auto-generate teacher slots, and monitor meeting rosters.
                    </p>
                </div>

                {canManagePTM && (
                    <Button
                        onClick={() => setIsCreateModalOpen(true)}
                        className="bg-indigo-600 hover:bg-indigo-700 text-white gap-2 shadow-sm"
                    >
                        <Plus className="h-4 w-4" />
                        Create PTM Session
                    </Button>
                )}
            </div>

            {/* Metrics Overview Cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <Card className="border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
                    <CardContent className="p-4 space-y-1">
                        <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">Active PTM Events</p>
                        <p className="text-2xl font-black text-slate-900 dark:text-white">{activeSessions}</p>
                        <p className="text-[11px] text-slate-400">{totalSessions} total events scheduled</p>
                    </CardContent>
                </Card>

                <Card className="border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
                    <CardContent className="p-4 space-y-1">
                        <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">Generated Time Slots</p>
                        <p className="text-2xl font-black text-indigo-600 dark:text-indigo-400">{totalSlotsCount}</p>
                        <p className="text-[11px] text-slate-400">Discrete 1-on-1 meeting slots</p>
                    </CardContent>
                </Card>

                <Card className="border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
                    <CardContent className="p-4 space-y-1">
                        <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">Parent Bookings</p>
                        <p className="text-2xl font-black text-emerald-600 dark:text-emerald-400">{totalBookedCount}</p>
                        <p className="text-[11px] text-slate-400">
                            {totalSlotsCount > 0 ? `${Math.round((totalBookedCount / totalSlotsCount) * 100)}% slot booking rate` : "Awaiting bookings"}
                        </p>
                    </CardContent>
                </Card>

                <Card className="border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
                    <CardContent className="p-4 space-y-1">
                        <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">Available Capacity</p>
                        <p className="text-2xl font-black text-amber-600 dark:text-amber-400">
                            {Math.max(0, totalSlotsCount - totalBookedCount)}
                        </p>
                        <p className="text-[11px] text-slate-400">Open slots ready for parents</p>
                    </CardContent>
                </Card>
            </div>

            {/* Navigation Tabs */}
            <div className="flex border-b border-slate-200 dark:border-slate-800 gap-6 text-sm font-semibold">
                <button
                    onClick={() => setActiveTab("sessions")}
                    className={`pb-3 relative transition ${
                        activeTab === "sessions"
                            ? "text-indigo-600 dark:text-indigo-400 border-b-2 border-indigo-600 dark:border-indigo-400"
                            : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                    }`}
                >
                    PTM Sessions & Events ({sessions.length})
                </button>

                <button
                    onClick={() => setActiveTab("roster")}
                    className={`pb-3 relative transition ${
                        activeTab === "roster"
                            ? "text-indigo-600 dark:text-indigo-400 border-b-2 border-indigo-600 dark:border-indigo-400"
                            : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                    }`}
                >
                    Master Meeting Roster
                </button>

                {teacherSchedule?.slots && (
                    <button
                        onClick={() => setActiveTab("my_schedule")}
                        className={`pb-3 relative transition ${
                            activeTab === "my_schedule"
                                ? "text-indigo-600 dark:text-indigo-400 border-b-2 border-indigo-600 dark:border-indigo-400"
                                : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                        }`}
                    >
                        My Meeting Schedule ({teacherSchedule.slots.length})
                    </button>
                )}
            </div>

            {/* TAB 1: PTM SESSIONS & EVENTS */}
            {activeTab === "sessions" && (
                <div className="space-y-4">
                    {/* Filters bar */}
                    <div className="flex flex-wrap gap-3 items-center justify-between">
                        <div className="flex flex-wrap gap-3 items-center">
                            <select
                                value={selectedStatus}
                                onChange={(e) => setSelectedStatus(e.target.value)}
                                className="text-xs rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 py-1.5 px-2.5 text-slate-700 dark:text-slate-300"
                            >
                                <option value="">All Statuses</option>
                                <option value="draft">Draft</option>
                                <option value="published">Published</option>
                                <option value="completed">Completed</option>
                                <option value="cancelled">Cancelled</option>
                            </select>

                            <select
                                value={selectedLevel}
                                onChange={(e) => setSelectedLevel(e.target.value)}
                                className="text-xs rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 py-1.5 px-2.5 text-slate-700 dark:text-slate-300"
                            >
                                <option value="">All Grades</option>
                                {levels.map((lvl) => (
                                    <option key={lvl.id} value={lvl.id}>{lvl.name}</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    {isLoadingSessions ? (
                        <LoadingState className="py-12" />
                    ) : sessions.length === 0 ? (
                        <EmptyState
                            title="No PTM Sessions found"
                            description="Click '+ Create PTM Session' above to schedule your first parent-teacher meeting."
                        />
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {sessions.map((sess) => {
                                const percentBooked = sess.total_slots > 0
                                    ? Math.round((sess.booked_slots_count / sess.total_slots) * 100)
                                    : 0;

                                return (
                                    <div
                                        key={sess.id}
                                        className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm p-4 space-y-3 flex flex-col justify-between"
                                    >
                                        <div className="space-y-2">
                                            <div className="flex items-start justify-between gap-2">
                                                <div>
                                                    <h3 className="font-semibold text-slate-900 dark:text-white text-base">
                                                        {sess.title}
                                                    </h3>
                                                    <p className="text-xs text-slate-500">
                                                        {sess.level_name ? `Grade: ${sess.level_name}` : "School-wide"}
                                                        {sess.section_name ? ` - Sec ${sess.section_name}` : ""}
                                                    </p>
                                                </div>
                                                <span className={`px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wider ${
                                                    sess.status === "published"
                                                        ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                                                        : sess.status === "draft"
                                                        ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                                                        : "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300"
                                                }`}>
                                                    {sess.status}
                                                </span>
                                            </div>

                                            <div className="space-y-1 text-xs text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/50 p-2.5 rounded-lg">
                                                <div className="flex items-center gap-1.5">
                                                    <Calendar className="h-3.5 w-3.5 text-slate-400" />
                                                    <span className="font-medium text-slate-800 dark:text-slate-200">{sess.meeting_date}</span>
                                                </div>
                                                <div className="flex items-center gap-1.5">
                                                    <Clock className="h-3.5 w-3.5 text-slate-400" />
                                                    <span>{sess.start_time.slice(0, 5)} - {sess.end_time.slice(0, 5)} ({sess.slot_duration_minutes}m per slot)</span>
                                                </div>
                                                <div className="flex items-center gap-1.5">
                                                    {sess.mode === "online" ? (
                                                        <Video className="h-3.5 w-3.5 text-indigo-500" />
                                                    ) : (
                                                        <MapPin className="h-3.5 w-3.5 text-emerald-500" />
                                                    )}
                                                    <span className="truncate">{sess.location_or_url || (sess.mode === "online" ? "Virtual Meeting" : "On Campus")}</span>
                                                </div>
                                            </div>

                                            {/* Slot progress bar */}
                                            <div className="space-y-1">
                                                <div className="flex justify-between text-[11px] text-slate-500">
                                                    <span>Booked: {sess.booked_slots_count} / {sess.total_slots} slots</span>
                                                    <span>{percentBooked}%</span>
                                                </div>
                                                <div className="w-full bg-slate-100 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
                                                    <div
                                                        className="bg-indigo-600 h-full rounded-full transition-all"
                                                        style={{ width: `${percentBooked}%` }}
                                                    />
                                                </div>
                                            </div>
                                        </div>

                                        {/* Action buttons */}
                                        <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between gap-2">
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => {
                                                    setSelectedSessionId(sess.id);
                                                    setActiveTab("roster");
                                                }}
                                                className="text-xs h-7 text-indigo-600 dark:text-indigo-400"
                                            >
                                                View Roster
                                            </Button>

                                            <div className="flex gap-1.5">
                                                {canManagePTM && sess.status === "draft" && (
                                                    <>
                                                        <Button
                                                            variant="outline"
                                                            size="sm"
                                                            onClick={() => generateSlotsMutation.mutate(sess.id)}
                                                            disabled={generateSlotsMutation.isPending}
                                                            className="text-xs h-7"
                                                        >
                                                            Generate Slots
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            onClick={() => publishSessionMutation.mutate(sess.id)}
                                                            disabled={publishSessionMutation.isPending}
                                                            className="text-xs h-7 bg-emerald-600 hover:bg-emerald-700 text-white"
                                                        >
                                                            Publish
                                                        </Button>
                                                    </>
                                                )}

                                                {canManagePTM && sess.status === "published" && (
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => {
                                                            if (confirm("Cancel this session? All open slots will be closed.")) {
                                                                cancelSessionMutation.mutate(sess.id);
                                                            }
                                                        }}
                                                        className="text-xs h-7 text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30"
                                                    >
                                                        Cancel
                                                    </Button>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            )}

            {/* TAB 2: MASTER MEETING ROSTER */}
            {activeTab === "roster" && (
                <div className="space-y-4">
                    {/* Session Selector & Filters */}
                    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 flex flex-wrap gap-3 items-center justify-between">
                        <div className="flex flex-wrap gap-3 items-center">
                            <div>
                                <label className="text-[11px] font-semibold text-slate-500 uppercase block mb-1">
                                    PTM Event:
                                </label>
                                <select
                                    value={effectiveRosterSessionId || ""}
                                    onChange={(e) => setSelectedSessionId(e.target.value)}
                                    className="text-xs rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 py-1.5 px-2.5 font-medium text-slate-800 dark:text-slate-200"
                                >
                                    {sessions.map((s) => (
                                        <option key={s.id} value={s.id}>{s.title} ({s.meeting_date})</option>
                                    ))}
                                </select>
                            </div>

                            <div>
                                <label className="text-[11px] font-semibold text-slate-500 uppercase block mb-1">
                                    Status:
                                </label>
                                <select
                                    value={rosterStatusFilter}
                                    onChange={(e) => setRosterStatusFilter(e.target.value)}
                                    className="text-xs rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 py-1.5 px-2.5 text-slate-700 dark:text-slate-300"
                                >
                                    <option value="">All Slots</option>
                                    <option value="available">Available</option>
                                    <option value="booked">Booked</option>
                                    <option value="completed">Completed</option>
                                    <option value="blocked">Blocked</option>
                                </select>
                            </div>

                            <div>
                                <label className="text-[11px] font-semibold text-slate-500 uppercase block mb-1">
                                    Search:
                                </label>
                                <div className="relative">
                                    <Search className="h-3.5 w-3.5 text-slate-400 absolute left-2.5 top-2.5" />
                                    <input
                                        type="text"
                                        placeholder="Student, Parent, Teacher..."
                                        value={rosterSearch}
                                        onChange={(e) => setRosterSearch(e.target.value)}
                                        className="text-xs pl-8 pr-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-800 dark:text-slate-200 focus:outline-none"
                                    />
                                </div>
                            </div>
                        </div>

                        {canManagePTM && rosterData?.session && rosterData.session.status === "draft" && (
                            <Button
                                size="sm"
                                onClick={() => generateSlotsMutation.mutate(rosterData.session.id)}
                                disabled={generateSlotsMutation.isPending}
                                className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white"
                            >
                                Re-Generate Slots
                            </Button>
                        )}
                    </div>

                    {isLoadingRoster ? (
                        <LoadingState className="py-16" />
                    ) : filteredRosterSlots.length === 0 ? (
                        <EmptyState
                            title="No slots in this roster"
                            description="Slots may not have been generated yet for this session, or no slots match the active filter."
                        />
                    ) : (
                        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm">
                            <div className="overflow-x-auto">
                                <table className="w-full text-left border-collapse text-xs">
                                    <thead>
                                        <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-500 font-semibold uppercase">
                                            <th className="py-3 px-4">Time Slot</th>
                                            <th className="py-3 px-4">Faculty / Teacher</th>
                                            <th className="py-3 px-4">Student & Class</th>
                                            <th className="py-3 px-4">Parent Details</th>
                                            <th className="py-3 px-4">Status</th>
                                            <th className="py-3 px-4">Discussion Agenda</th>
                                            <th className="py-3 px-4 text-right">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                        {filteredRosterSlots.map((slot) => {
                                            const isBooked = slot.status === "booked" || slot.status === "completed";

                                            return (
                                                <tr key={slot.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition">
                                                    <td className="py-3 px-4 font-semibold text-slate-800 dark:text-slate-200 whitespace-nowrap">
                                                        {slot.start_time.slice(0, 5)} - {slot.end_time.slice(0, 5)}
                                                    </td>
                                                    <td className="py-3 px-4">
                                                        <p className="font-semibold text-slate-900 dark:text-white">
                                                            {slot.teacher_detail?.full_name || "Teacher"}
                                                        </p>
                                                        <p className="text-[11px] text-slate-500">
                                                            {slot.teacher_detail?.designation}
                                                        </p>
                                                    </td>
                                                    <td className="py-3 px-4">
                                                        {slot.student_detail ? (
                                                            <div>
                                                                <p className="font-medium text-slate-900 dark:text-white">
                                                                    {slot.student_detail.full_name}
                                                                </p>
                                                                <p className="text-[11px] text-slate-500">
                                                                    Roll: {slot.student_detail.enrollment_id} • {slot.student_detail.current_class}
                                                                </p>
                                                            </div>
                                                        ) : (
                                                            <span className="text-slate-400">—</span>
                                                        )}
                                                    </td>
                                                    <td className="py-3 px-4">
                                                        {slot.parent_detail ? (
                                                            <div>
                                                                <p className="font-medium text-slate-800 dark:text-slate-200">
                                                                    {slot.parent_detail.full_name}
                                                                </p>
                                                                <p className="text-[11px] text-slate-500">
                                                                    {slot.parent_detail.phone_number || ""}
                                                                </p>
                                                            </div>
                                                        ) : (
                                                            <span className="text-slate-400">—</span>
                                                        )}
                                                    </td>
                                                    <td className="py-3 px-4 whitespace-nowrap">
                                                        <span className={`px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wider ${
                                                            slot.status === "completed"
                                                                ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                                                                : slot.status === "booked"
                                                                ? "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300"
                                                                : slot.status === "blocked"
                                                                ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                                                                : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                                                        }`}>
                                                            {slot.status}
                                                        </span>
                                                        {slot.attended && (
                                                            <span className="ml-1.5 text-[10px] text-emerald-600 font-semibold">
                                                                ✓ Attended
                                                            </span>
                                                        )}
                                                    </td>
                                                    <td className="py-3 px-4 max-w-xs">
                                                        {slot.parent_notes ? (
                                                            <p className="text-[11px] text-slate-600 dark:text-slate-300 truncate" title={slot.parent_notes}>
                                                                {slot.parent_notes}
                                                            </p>
                                                        ) : (
                                                            <span className="text-slate-400">—</span>
                                                        )}
                                                    </td>
                                                    <td className="py-3 px-4 text-right whitespace-nowrap">
                                                        <div className="flex items-center justify-end gap-1.5">
                                                            {isBooked && canRecordFeedback && (
                                                                <Button
                                                                    variant="outline"
                                                                    size="sm"
                                                                    onClick={() => handleOpenFeedbackModal(slot)}
                                                                    className="text-xs h-7 gap-1 text-indigo-600 border-indigo-200"
                                                                >
                                                                    <MessageSquare className="h-3 w-3" />
                                                                    Notes & Feedback
                                                                </Button>
                                                            )}

                                                            {slot.status === "available" && (
                                                                <Button
                                                                    variant="ghost"
                                                                    size="sm"
                                                                    onClick={() => blockSlotMutation.mutate(slot.id)}
                                                                    className="text-xs h-7 text-slate-500 hover:text-rose-600"
                                                                    title="Block Slot"
                                                                >
                                                                    <Lock className="h-3 w-3" />
                                                                </Button>
                                                            )}

                                                            {slot.status === "blocked" && (
                                                                <Button
                                                                    variant="ghost"
                                                                    size="sm"
                                                                    onClick={() => unblockSlotMutation.mutate(slot.id)}
                                                                    className="text-xs h-7 text-emerald-600"
                                                                    title="Unblock Slot"
                                                                >
                                                                    <Unlock className="h-3 w-3" />
                                                                </Button>
                                                            )}
                                                        </div>
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* TAB 3: MY MEETING SCHEDULE (TEACHER VIEW) */}
            {activeTab === "my_schedule" && teacherSchedule && (
                <div className="space-y-4">
                    <div className="bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-100 dark:border-indigo-900/40 rounded-xl p-4 flex items-center justify-between">
                        <div>
                            <h2 className="font-semibold text-slate-900 dark:text-white text-base">
                                Welcome, {teacherSchedule.teacher.full_name}
                            </h2>
                            <p className="text-xs text-slate-500">
                                Designation: {teacherSchedule.teacher.designation} • Review upcoming appointments and log post-meeting notes.
                            </p>
                        </div>
                    </div>

                    {teacherSchedule.slots.length === 0 ? (
                        <EmptyState
                            title="No slots assigned to you yet"
                            description="When an administrator schedules a PTM session that includes you, your meetings will appear here."
                        />
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {teacherSchedule.slots.map((slot) => {
                                const isBooked = slot.status === "booked" || slot.status === "completed";

                                return (
                                    <div
                                        key={slot.id}
                                        className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 space-y-3 shadow-sm"
                                    >
                                        <div className="flex items-start justify-between">
                                            <div className="flex items-center gap-1.5 font-semibold text-slate-800 dark:text-slate-200 text-sm">
                                                <Clock className="h-4 w-4 text-indigo-500" />
                                                <span>{slot.start_time.slice(0, 5)} - {slot.end_time.slice(0, 5)}</span>
                                            </div>
                                            <span className={`px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-wider ${
                                                slot.status === "completed"
                                                    ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                                                    : slot.status === "booked"
                                                    ? "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300"
                                                    : slot.status === "blocked"
                                                    ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                                                    : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                                            }`}>
                                                {slot.status}
                                            </span>
                                        </div>

                                        {slot.student_detail ? (
                                            <div className="bg-slate-50 dark:bg-slate-800/50 p-2.5 rounded-lg space-y-1 text-xs">
                                                <p><strong className="text-slate-700 dark:text-slate-300">Student:</strong> {slot.student_detail.full_name} ({slot.student_detail.enrollment_id})</p>
                                                <p><strong className="text-slate-700 dark:text-slate-300">Class:</strong> {slot.student_detail.current_class}</p>
                                                {slot.parent_detail && (
                                                    <p><strong className="text-slate-700 dark:text-slate-300">Parent:</strong> {slot.parent_detail.full_name} {slot.parent_detail.phone_number ? `(${slot.parent_detail.phone_number})` : ""}</p>
                                                )}
                                                {slot.parent_notes && (
                                                    <p className="pt-1 text-slate-500 italic">"{slot.parent_notes}"</p>
                                                )}
                                            </div>
                                        ) : (
                                            <div className="p-2.5 rounded-lg border border-dashed border-slate-200 text-center text-xs text-slate-400">
                                                {slot.status === "blocked" ? "You blocked this slot for break" : "Open for parent booking"}
                                            </div>
                                        )}

                                        {slot.teacher_feedback && (
                                            <div className="text-xs bg-emerald-50 dark:bg-emerald-950/30 p-2 rounded border border-emerald-200 dark:border-emerald-900/40 text-emerald-800 dark:text-emerald-300">
                                                <strong>Saved Notes:</strong> {slot.teacher_feedback}
                                            </div>
                                        )}

                                        <div className="pt-2 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
                                            {isBooked ? (
                                                <Button
                                                    size="sm"
                                                    onClick={() => handleOpenFeedbackModal(slot)}
                                                    className="w-full text-xs bg-indigo-600 hover:bg-indigo-700 text-white gap-1"
                                                >
                                                    <MessageSquare className="h-3.5 w-3.5" />
                                                    {slot.teacher_feedback ? "Edit Meeting Notes" : "Record Feedback & Attendance"}
                                                </Button>
                                            ) : slot.status === "available" ? (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => blockSlotMutation.mutate(slot.id)}
                                                    className="w-full text-xs text-rose-600 border-rose-200 hover:bg-rose-50"
                                                >
                                                    <Lock className="h-3 w-3 mr-1" />
                                                    Block for Break
                                                </Button>
                                            ) : (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    onClick={() => unblockSlotMutation.mutate(slot.id)}
                                                    className="w-full text-xs text-emerald-600 border-emerald-200 hover:bg-emerald-50"
                                                >
                                                    <Unlock className="h-3 w-3 mr-1" />
                                                    Unblock Slot
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            )}

            {/* CREATE PTM SESSION MODAL */}
            {isCreateModalOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
                    <div className="bg-white dark:bg-slate-900 rounded-xl max-w-2xl w-full p-6 space-y-4 shadow-xl border border-slate-200 dark:border-slate-800 max-h-[90vh] overflow-y-auto">
                        <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                            <div>
                                <h3 className="font-bold text-slate-900 dark:text-white text-base">
                                    Create New PTM Event
                                </h3>
                                <p className="text-xs text-slate-500">
                                    Define the meeting schedule, duration, and participating teachers.
                                </p>
                            </div>
                            <button
                                onClick={() => setIsCreateModalOpen(false)}
                                className="text-slate-400 hover:text-slate-600"
                            >
                                <X className="h-5 w-5" />
                            </button>
                        </div>

                        <form onSubmit={handleCreateSession} className="space-y-4 text-xs">
                            <div className="space-y-1">
                                <label className="font-semibold text-slate-700 dark:text-slate-300">
                                    Event Title *
                                </label>
                                <input
                                    type="text"
                                    required
                                    placeholder="e.g. Term 1 Mid-Term PTM, Board Class Review..."
                                    value={newTitle}
                                    onChange={(e) => setNewTitle(e.target.value)}
                                    className="w-full text-xs p-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
                                />
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                <div className="space-y-1">
                                    <label className="font-semibold text-slate-700 dark:text-slate-300">
                                        Academic Year
                                    </label>
                                    <select
                                        value={newAcademicYear}
                                        onChange={(e) => setNewAcademicYear(e.target.value)}
                                        className="w-full text-xs p-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                                    >
                                        <option value="">Select Academic Year</option>
                                        {academicYears.map((ay) => (
                                            <option key={ay.id} value={ay.id}>{ay.name}</option>
                                        ))}
                                    </select>
                                </div>

                                <div className="space-y-1">
                                    <label className="font-semibold text-slate-700 dark:text-slate-300">
                                        Target Grade / Level (Optional)
                                    </label>
                                    <select
                                        value={newLevel}
                                        onChange={(e) => setNewLevel(e.target.value)}
                                        className="w-full text-xs p-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                                    >
                                        <option value="">Open to All Grades</option>
                                        {levels.map((lvl) => (
                                            <option key={lvl.id} value={lvl.id}>{lvl.name}</option>
                                        ))}
                                    </select>
                                </div>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                <div className="space-y-1">
                                    <label className="font-semibold text-slate-700 dark:text-slate-300">
                                        Meeting Date *
                                    </label>
                                    <input
                                        type="date"
                                        required
                                        value={newMeetingDate}
                                        onChange={(e) => setNewMeetingDate(e.target.value)}
                                        className="w-full text-xs p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                                    />
                                </div>

                                <div className="space-y-1">
                                    <label className="font-semibold text-slate-700 dark:text-slate-300">
                                        Start Time *
                                    </label>
                                    <input
                                        type="time"
                                        required
                                        value={newStartTime}
                                        onChange={(e) => setNewStartTime(e.target.value)}
                                        className="w-full text-xs p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                                    />
                                </div>

                                <div className="space-y-1">
                                    <label className="font-semibold text-slate-700 dark:text-slate-300">
                                        End Time *
                                    </label>
                                    <input
                                        type="time"
                                        required
                                        value={newEndTime}
                                        onChange={(e) => setNewEndTime(e.target.value)}
                                        className="w-full text-xs p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                                    />
                                </div>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                <div className="space-y-1">
                                    <label className="font-semibold text-slate-700 dark:text-slate-300">
                                        Slot Duration (Minutes)
                                    </label>
                                    <select
                                        value={newSlotDuration}
                                        onChange={(e) => setNewSlotDuration(Number(e.target.value))}
                                        className="w-full text-xs p-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                                    >
                                        <option value={10}>10 Minutes per parent</option>
                                        <option value={15}>15 Minutes per parent</option>
                                        <option value={20}>20 Minutes per parent</option>
                                        <option value={30}>30 Minutes per parent</option>
                                    </select>
                                </div>

                                <div className="space-y-1">
                                    <label className="font-semibold text-slate-700 dark:text-slate-300">
                                        Buffer Gap Between Slots
                                    </label>
                                    <select
                                        value={newBufferMinutes}
                                        onChange={(e) => setNewBufferMinutes(Number(e.target.value))}
                                        className="w-full text-xs p-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                                    >
                                        <option value={0}>0 Minutes (Back-to-back)</option>
                                        <option value={5}>5 Minutes break between slots</option>
                                        <option value={10}>10 Minutes break between slots</option>
                                    </select>
                                </div>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                <div className="space-y-1">
                                    <label className="font-semibold text-slate-700 dark:text-slate-300">
                                        Meeting Format
                                    </label>
                                    <select
                                        value={newMode}
                                        onChange={(e) => setNewMode(e.target.value as "in_person" | "online")}
                                        className="w-full text-xs p-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                                    >
                                        <option value="in_person">In-Person (On Campus)</option>
                                        <option value="online">Online / Virtual Video</option>
                                    </select>
                                </div>

                                <div className="space-y-1">
                                    <label className="font-semibold text-slate-700 dark:text-slate-300">
                                        {newMode === "online" ? "Meeting Link / URL" : "Campus Location / Room Numbers"}
                                    </label>
                                    <input
                                        type="text"
                                        placeholder={newMode === "online" ? "https://meet.google.com/..." : "e.g. Senior Block Rooms 101-105"}
                                        value={newLocationOrUrl}
                                        onChange={(e) => setNewLocationOrUrl(e.target.value)}
                                        className="w-full text-xs p-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                                    />
                                </div>
                            </div>

                            {/* Teachers multi-select */}
                            <div className="space-y-1.5">
                                <label className="font-semibold text-slate-700 dark:text-slate-300 flex justify-between">
                                    <span>Participating Teachers ({newSelectedTeachers.length} selected) *</span>
                                    <button
                                        type="button"
                                        onClick={() => {
                                            if (newSelectedTeachers.length === staffMembers.length) {
                                                setNewSelectedTeachers([]);
                                            } else {
                                                setNewSelectedTeachers(staffMembers.map((s) => s.id));
                                            }
                                        }}
                                        className="text-indigo-600 hover:underline font-normal"
                                    >
                                        {newSelectedTeachers.length === staffMembers.length ? "Deselect All" : "Select All Faculty"}
                                    </button>
                                </label>
                                <div className="max-h-36 overflow-y-auto border border-slate-200 dark:border-slate-800 rounded-lg p-2 grid grid-cols-1 sm:grid-cols-2 gap-1.5 bg-slate-50/50 dark:bg-slate-800/30">
                                    {staffMembers.map((staff) => {
                                        const isChecked = newSelectedTeachers.includes(staff.id);
                                        return (
                                            <label
                                                key={staff.id}
                                                className="flex items-center gap-2 p-1.5 rounded hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer text-slate-800 dark:text-slate-200"
                                            >
                                                <input
                                                    type="checkbox"
                                                    checked={isChecked}
                                                    onChange={(e) => {
                                                        if (e.target.checked) {
                                                            setNewSelectedTeachers([...newSelectedTeachers, staff.id]);
                                                        } else {
                                                            setNewSelectedTeachers(newSelectedTeachers.filter((id) => id !== staff.id));
                                                        }
                                                    }}
                                                    className="rounded border-slate-300 text-indigo-600"
                                                />
                                                <span className="truncate">
                                                    {staff.profile_details?.first_name} {staff.profile_details?.last_name} ({staff.designation})
                                                </span>
                                            </label>
                                        );
                                    })}
                                </div>
                            </div>

                            <div className="space-y-1">
                                <label className="font-semibold text-slate-700 dark:text-slate-300">
                                    Instructions for Parents
                                </label>
                                <textarea
                                    rows={2}
                                    placeholder="e.g. Please be present 5 minutes before your time slot. Discussion duration is strictly observed."
                                    value={newInstructions}
                                    onChange={(e) => setNewInstructions(e.target.value)}
                                    className="w-full text-xs p-2 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
                                />
                            </div>

                            <div className="flex justify-end gap-2 pt-3 border-t border-slate-100 dark:border-slate-800">
                                <Button
                                    type="button"
                                    variant="outline"
                                    onClick={() => setIsCreateModalOpen(false)}
                                    className="text-xs"
                                >
                                    Cancel
                                </Button>
                                <Button
                                    type="submit"
                                    disabled={createSessionMutation.isPending || newSelectedTeachers.length === 0}
                                    className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white"
                                >
                                    {createSessionMutation.isPending ? "Creating..." : "Save PTM Session"}
                                </Button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* FEEDBACK & MEETING NOTES MODAL */}
            {feedbackModalSlot && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
                    <div className="bg-white dark:bg-slate-900 rounded-xl max-w-lg w-full p-5 space-y-4 shadow-xl border border-slate-200 dark:border-slate-800">
                        <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                            <h3 className="font-semibold text-slate-900 dark:text-white">
                                Record Meeting Notes & Attendance
                            </h3>
                            <button
                                onClick={() => setFeedbackModalSlot(null)}
                                className="text-slate-400 hover:text-slate-600"
                            >
                                <X className="h-5 w-5" />
                            </button>
                        </div>

                        <div className="space-y-3 text-xs">
                            <div className="bg-slate-50 dark:bg-slate-800/50 p-3 rounded-lg space-y-1">
                                <p><strong className="text-slate-700 dark:text-slate-300">Student:</strong> {feedbackModalSlot.student_detail?.full_name} ({feedbackModalSlot.student_detail?.enrollment_id})</p>
                                <p><strong className="text-slate-700 dark:text-slate-300">Time:</strong> {feedbackModalSlot.start_time.slice(0, 5)} - {feedbackModalSlot.end_time.slice(0, 5)}</p>
                                {feedbackModalSlot.parent_notes && (
                                    <p className="pt-1 text-slate-500 italic"><strong className="not-italic text-slate-700 dark:text-slate-300">Parent Agenda:</strong> "{feedbackModalSlot.parent_notes}"</p>
                                )}
                            </div>

                            <label className="flex items-center gap-2 p-2 rounded bg-indigo-50/50 dark:bg-indigo-950/30 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={attendedCheck}
                                    onChange={(e) => setAttendedCheck(e.target.checked)}
                                    className="rounded border-slate-300 text-indigo-600"
                                />
                                <span className="font-medium text-slate-800 dark:text-slate-200">
                                    Mark as Attended (Parent & Student were present)
                                </span>
                            </label>

                            <div className="space-y-1">
                                <label className="font-medium text-slate-700 dark:text-slate-300">
                                    Academic Feedback, Discussion Remarks & Action Items:
                                </label>
                                <textarea
                                    rows={4}
                                    value={feedbackNotes}
                                    onChange={(e) => setFeedbackNotes(e.target.value)}
                                    placeholder="Enter points discussed, strengths observed, areas of academic improvement, and recommendations agreed upon with the parent..."
                                    className="w-full text-xs p-2.5 rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
                                />
                            </div>
                        </div>

                        <div className="flex justify-end gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setFeedbackModalSlot(null)}
                                className="text-xs"
                            >
                                Cancel
                            </Button>
                            <Button
                                size="sm"
                                onClick={handleSaveFeedback}
                                disabled={recordFeedbackMutation.isPending}
                                className="text-xs bg-indigo-600 hover:bg-indigo-700 text-white"
                            >
                                {recordFeedbackMutation.isPending ? "Saving..." : "Save Meeting Notes"}
                            </Button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
