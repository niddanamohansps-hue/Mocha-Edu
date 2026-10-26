"use client";

import { ReactNode } from "react";
import { QuestionBankNav } from "@/components/dashboard/question-bank/shared";

export default function QuestionBankLayout({ children }: { children: ReactNode }) {
    return (
        <div className="space-y-6">
            <QuestionBankNav />
            {children}
        </div>
    );
}
