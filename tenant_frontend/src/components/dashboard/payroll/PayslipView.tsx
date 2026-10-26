"use client";

import { CURRENCY } from "@/lib/currency";
import { Button } from "@/components/ui/button";
import { formatMoney } from "@/components/dashboard/payroll/shared";
import { PayslipDetail } from "@/types/Payroll";

/** A payslip laid out the way people read one: who, then earnings, then deductions, then net pay. */
export function PayslipView({ payslip, onPdf }: { payslip: PayslipDetail; onPdf: () => void }) {
    const earnings = payslip.lines.filter((l) => l.kind === "basic" || l.kind === "earning");
    const deductions = payslip.lines.filter((l) => l.kind === "deduction");
    const unpaid = Number(payslip.unpaid_days);
    return (
        <article className="space-y-5" aria-label={`Payslip for ${payslip.month_label}`}>
            <header className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h2 className="text-xl font-bold text-slate-900 dark:text-white">{payslip.month_label}</h2>
                    <p className="text-sm text-slate-500">
                        {payslip.staff_name} ({payslip.employee_id})
                        {payslip.designation ? ` · ${payslip.designation}` : ""}
                        {payslip.department ? ` · ${payslip.department}` : ""}
                    </p>
                </div>
                <Button variant="outline" onClick={onPdf}>Download PDF</Button>
            </header>

            <p className="text-sm text-slate-600 dark:text-slate-400">
                {payslip.working_days} working days this month
                {unpaid > 0 ? `, of which ${payslip.unpaid_days.replace(/\.0$/, "")} unpaid (leave without pay or absence)` : ", none unpaid"}.
            </p>

            <section className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                <h3 className="px-4 py-2 text-sm font-semibold bg-slate-50 dark:bg-slate-800/60">Earnings</h3>
                <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                    {earnings.map((line) => (
                        <li key={line.id} className="px-4 py-2 flex justify-between gap-3 text-sm">
                            <span>{line.name}{line.kind !== "basic" && line.detail ? <span className="block text-xs text-slate-500">{line.detail}</span> : null}</span>
                            <span className="font-medium">{formatMoney(line.amount)}</span>
                        </li>
                    ))}
                    <li className="px-4 py-2 flex justify-between text-sm font-bold bg-slate-50/60 dark:bg-slate-800/30">
                        <span>Total earnings</span><span>{formatMoney(payslip.gross_amount)}</span>
                    </li>
                </ul>
            </section>

            <section className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                <h3 className="px-4 py-2 text-sm font-semibold bg-slate-50 dark:bg-slate-800/60">Deductions</h3>
                <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                    {deductions.length === 0 && <li className="px-4 py-2 text-sm text-slate-500">Nothing was deducted.</li>}
                    {deductions.map((line) => (
                        <li key={line.id} className="px-4 py-2 flex justify-between gap-3 text-sm">
                            <span>{line.name}{line.detail ? <span className="block text-xs text-slate-500">{line.detail}</span> : null}</span>
                            <span className="font-medium text-red-600">−{formatMoney(line.amount)}</span>
                        </li>
                    ))}
                    <li className="px-4 py-2 flex justify-between text-sm font-bold bg-slate-50/60 dark:bg-slate-800/30">
                        <span>Total deductions</span><span>{formatMoney(payslip.deductions_amount)}</span>
                    </li>
                </ul>
            </section>

            <div className="rounded-2xl bg-slate-900 text-white px-5 py-4 flex items-center justify-between gap-3">
                <span className="font-semibold">Net pay ({CURRENCY})</span>
                <span className={`text-2xl font-bold ${payslip.net_is_negative ? "text-red-300" : ""}`}>{formatMoney(payslip.net_amount)}</span>
            </div>
        </article>
    );
}
