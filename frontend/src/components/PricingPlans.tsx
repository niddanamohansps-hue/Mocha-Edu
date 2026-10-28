"use client";

import Link from "next/link";
import { useState } from "react";
import { CheckCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { BillingCycle, CYCLE_LABEL, oneTimeTerm, priceFor, rupees, usePlans } from "@/hooks/billing";

const CYCLES: BillingCycle[] = ["monthly", "yearly", "one_time"];

/** The pricing cards, from the live plans (prices are set by the platform owner in the admin). */
export function PricingPlans() {
    const { data: plans = [], isLoading, isError } = usePlans();
    const [cycle, setCycle] = useState<BillingCycle>("yearly");

    if (isLoading) return <div className="flex justify-center py-12"><Loader2 className="h-8 w-8 animate-spin text-blue-600" /></div>;
    if (isError || plans.length === 0) {
        return <p className="text-center text-slate-500 py-12">Pricing is not available right now. Please contact us.</p>;
    }
    const popular = plans.length >= 3 ? plans[1].code : "";

    return (
        <div className="space-y-10">
            <div className="flex justify-center">
                <div className="inline-flex rounded-full border border-slate-200 bg-white p-1 shadow-sm">
                    {CYCLES.map((c) => (
                        <button
                            key={c}
                            type="button"
                            onClick={() => setCycle(c)}
                            className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${cycle === c ? "bg-blue-600 text-white" : "text-slate-600 hover:text-slate-900"}`}
                        >
                            {CYCLE_LABEL[c]}
                            {c === "yearly" && <span className={`ml-1 text-xs ${cycle === c ? "text-blue-100" : "text-emerald-600"}`}>save more</span>}
                        </button>
                    ))}
                </div>
            </div>

            <div className="grid gap-8 md:grid-cols-3 max-w-6xl mx-auto">
                {plans.map((plan) => {
                    const price = priceFor(plan, cycle);
                    const isPopular = plan.code === popular;
                    return (
                        <div
                            key={plan.code}
                            className={`flex flex-col rounded-2xl p-8 shadow-sm border ${isPopular ? "border-blue-600 bg-gradient-to-br from-blue-600 to-teal-600 text-white shadow-xl md:scale-105" : "border-slate-200 bg-white"}`}
                        >
                            {isPopular && <span className="mb-3 self-start rounded-full bg-white px-3 py-1 text-xs font-bold text-blue-700">Most popular</span>}
                            <h3 className="text-2xl font-bold">{plan.name}</h3>
                            <p className={`mt-1 text-sm ${isPopular ? "text-blue-100" : "text-slate-500"}`}>{plan.description}</p>
                            <div className="mt-6 min-h-[72px]">
                                {price ? (
                                    <>
                                        <span className="text-4xl font-bold">{rupees(price)}</span>
                                        <span className={`text-sm ${isPopular ? "text-blue-100" : "text-slate-500"}`}>
                                            {cycle === "monthly" ? " / month" : cycle === "yearly" ? " / year" : ` once, ${oneTimeTerm(plan)}`}
                                        </span>
                                        <p className={`text-xs mt-1 ${isPopular ? "text-blue-100" : "text-slate-500"}`}>+ {Number(plan.gst_percent)}% GST</p>
                                    </>
                                ) : (
                                    <p className={`text-sm ${isPopular ? "text-blue-100" : "text-slate-500"}`}>Not offered {CYCLE_LABEL[cycle].toLowerCase()}.</p>
                                )}
                            </div>
                            <ul className="mt-6 space-y-3 flex-1">
                                {plan.features.map((feature) => (
                                    <li key={feature} className="flex items-start gap-2 text-sm">
                                        <CheckCircle className={`h-5 w-5 shrink-0 ${isPopular ? "text-white" : "text-emerald-600"}`} /> {feature}
                                    </li>
                                ))}
                                {plan.trial_days > 0 && (
                                    <li className="flex items-start gap-2 text-sm font-semibold">
                                        <CheckCircle className={`h-5 w-5 shrink-0 ${isPopular ? "text-white" : "text-emerald-600"}`} /> {plan.trial_days}-day free trial
                                    </li>
                                )}
                            </ul>
                            {price ? (
                                <Link href={`/get-started?plan=${plan.code}&cycle=${cycle}`} className="mt-8">
                                    <Button className={`w-full ${isPopular ? "bg-white text-blue-700 hover:bg-blue-50" : ""}`}>
                                        {plan.trial_days > 0 ? "Start free trial" : "Choose plan"}
                                    </Button>
                                </Link>
                            ) : (
                                <Button disabled className="mt-8 w-full">Choose another option</Button>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
