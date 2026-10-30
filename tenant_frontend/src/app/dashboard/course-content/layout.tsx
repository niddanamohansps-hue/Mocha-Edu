"use client";

import { ReactNode } from "react";
import { CourseContentNav } from "@/components/dashboard/course-content/CourseContentNav";

export default function CourseContentLayout({ children }: { children: ReactNode }) {
    return (
        <div className="space-y-6">
            <CourseContentNav />
            {children}
        </div>
    );
}

