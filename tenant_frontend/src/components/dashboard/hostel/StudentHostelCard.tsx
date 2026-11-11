"use client";

import { BedDouble } from "lucide-react";
import { showDate, useStudentHostel } from "@/hooks/useHostel";

/** The student's current hostel room, if they board. Renders nothing for day scholars or without access. */
export function StudentHostelCard({ studentId }: { studentId: string }) {
    const { data } = useStudentHostel(studentId);
    const stay = data?.current;
    if (!stay) return null;
    return (
        <section className="flex items-start gap-3 rounded-xl border border-slate-200 p-4 text-sm dark:border-slate-800">
            <BedDouble className="mt-0.5 h-5 w-5 text-sky-600" />
            <div>
                <div className="font-semibold">Hostel: {stay.hostel_name}, room {stay.room_number}</div>
                <div className="text-slate-500">
                    Since {showDate(stay.start_date)}
                    {stay.warden_phone && (
                        <> · Warden <a className="text-sky-600 hover:underline" href={`tel:${stay.warden_phone}`}>{stay.warden_phone}</a></>
                    )}
                </div>
            </div>
        </section>
    );
}
