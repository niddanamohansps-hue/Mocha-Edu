"use client";

import { ReactNode } from "react";
import { PayrollNav } from "@/components/dashboard/payroll/shared";

export default function PayrollLayout({ children }: { children: ReactNode }) {
    return (
        <div className="space-y-6">
            <PayrollNav />
            {children}
        </div>
    );
}
