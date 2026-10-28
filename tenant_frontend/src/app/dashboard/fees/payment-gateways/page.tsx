"use client";

import { useState } from "react";
import { CheckCircle2, Copy, CreditCard, ExternalLink, KeyRound, Loader2, PlugZap, XCircle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";
import Unauthorized from "@/components/Unauthorized";
import { usePaymentGateways, useSavePaymentGateway, useTestPaymentGateway } from "@/hooks/useFees";
import { usePermissions } from "@/providers/PermissionProvider";
import { PaymentGatewaySetup } from "@/types/Fees";

const PILL = "rounded-full px-2.5 py-0.5 text-xs font-medium";

function fieldErrors(error: unknown): Record<string, string> {
    const data = (error as { response?: { data?: Record<string, unknown> } })?.response?.data;
    if (!data || typeof data !== "object") return { form: "Could not save. Please try again." };
    return Object.fromEntries(
        Object.entries(data).map(([key, value]) => [key, Array.isArray(value) ? String(value[0]) : String(value)])
    );
}

function GatewayCard({ setup }: { setup: PaymentGatewaySetup }) {
    const save = useSavePaymentGateway();
    const check = useTestPaymentGateway();
    const [editing, setEditing] = useState(!setup.configured);
    const [merchantCode, setMerchantCode] = useState(setup.merchant_code);
    const [secret, setSecret] = useState("");
    const [webhookSecret, setWebhookSecret] = useState("");
    const [mode, setMode] = useState<"test" | "live">(setup.mode);
    const [active, setActive] = useState(setup.is_active || !setup.configured);
    const [errors, setErrors] = useState<Record<string, string>>({});
    const [checkResult, setCheckResult] = useState<{ ok: boolean; message: string } | null>(null);

    const submit = () => {
        setErrors({});
        save.mutate(
            { gateway: setup.gateway, merchant_code: merchantCode.trim(), secret, webhook_secret: webhookSecret, mode, is_active: active },
            {
                onSuccess: () => {
                    setSecret("");
                    setWebhookSecret("");
                    setEditing(false);
                    setCheckResult(null);
                },
                onError: (error) => setErrors(fieldErrors(error)),
            }
        );
    };

    const status = !setup.configured
        ? { text: "Not set up", style: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400" }
        : setup.is_active
            ? { text: setup.mode === "live" ? "On · Live" : "On · Test mode", style: setup.mode === "live" ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400" : "bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400" }
            : { text: "Off", style: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400" };

    return (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <div className="flex items-center gap-2">
                        <CreditCard className="h-5 w-5 text-slate-500" />
                        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">{setup.label}</h2>
                        <span className={`${PILL} bg-sky-100 text-sky-700 dark:bg-sky-500/10 dark:text-sky-400`}>{setup.country}</span>
                    </div>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{setup.methods}</p>
                </div>
                <span className={`${PILL} ${status.style}`}>{status.text}</span>
            </div>

            {!editing ? (
                <div className="space-y-3">
                    <dl className="grid gap-2 text-sm sm:grid-cols-2">
                        <div><dt className="text-slate-500">{setup.key_label}</dt><dd className="font-mono break-all">{setup.merchant_code}</dd></div>
                        <div><dt className="text-slate-500">Secret key</dt><dd>{setup.has_secret ? "Saved ✓" : "Missing"}</dd></div>
                        {setup.webhooks && (
                            <div className="sm:col-span-2"><dt className="text-slate-500">Webhook secret</dt><dd>{setup.has_webhook_secret ? "Saved ✓" : "Not set: payments still work, but a closed browser is only caught by the 5-minute check"}</dd></div>
                        )}
                    </dl>
                    {checkResult && (
                        <p className={`flex items-center gap-2 text-sm ${checkResult.ok ? "text-emerald-700 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>
                            {checkResult.ok ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />} {checkResult.message}
                        </p>
                    )}
                    <div className="flex flex-wrap gap-2">
                        <Button variant="outline" onClick={() => setEditing(true)}><KeyRound className="h-4 w-4 mr-2" /> Change keys</Button>
                        <Button variant="outline" disabled={check.isPending} onClick={() => check.mutate(setup.gateway, { onSuccess: setCheckResult })}>
                            {check.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <PlugZap className="h-4 w-4 mr-2" />} Check the keys
                        </Button>
                    </div>
                </div>
            ) : (
                <div className="space-y-4">
                    <div className="grid gap-4 sm:grid-cols-2">
                        <div className="space-y-1.5">
                            <Label htmlFor={`${setup.gateway}-key`}>{setup.key_label}</Label>
                            <Input id={`${setup.gateway}-key`} value={merchantCode} placeholder={setup.key_hint} onChange={(e) => setMerchantCode(e.target.value)} autoComplete="off" />
                            {errors.merchant_code && <p className="text-xs text-red-600">{errors.merchant_code}</p>}
                        </div>
                        <div className="space-y-1.5">
                            <Label htmlFor={`${setup.gateway}-secret`}>Secret key</Label>
                            <Input id={`${setup.gateway}-secret`} type="password" value={secret} autoComplete="new-password"
                                placeholder={setup.has_secret ? "Saved. Leave empty to keep it" : "Paste the secret key"} onChange={(e) => setSecret(e.target.value)} />
                            {errors.secret && <p className="text-xs text-red-600">{errors.secret}</p>}
                        </div>
                        {setup.webhooks && (
                            <div className="space-y-1.5 sm:col-span-2">
                                <Label htmlFor={`${setup.gateway}-webhook`}>Webhook secret (recommended)</Label>
                                <Input id={`${setup.gateway}-webhook`} type="password" value={webhookSecret} autoComplete="new-password"
                                    placeholder={setup.has_webhook_secret ? "Saved. Leave empty to keep it" : "The secret you set when adding the webhook in the gateway dashboard"}
                                    onChange={(e) => setWebhookSecret(e.target.value)} />
                            </div>
                        )}
                        <div className="space-y-1.5">
                            <Label>Mode</Label>
                            <div className="flex gap-2">
                                {(["test", "live"] as const).map((m) => (
                                    <Button key={m} type="button" variant={mode === m ? "default" : "outline"} size="sm" onClick={() => setMode(m)}>
                                        {m === "test" ? "Test (no real money)" : "Live"}
                                    </Button>
                                ))}
                            </div>
                            {errors.mode && <p className="text-xs text-red-600">{errors.mode}</p>}
                        </div>
                        <label className="flex items-center gap-2 text-sm self-end">
                            <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
                            Parents can pay with {setup.label}
                        </label>
                    </div>
                    {errors.form && <p className="text-sm text-red-600">{errors.form}</p>}
                    <div className="flex flex-wrap gap-2">
                        <Button onClick={submit} disabled={save.isPending || !merchantCode.trim()}>
                            {save.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />} Save
                        </Button>
                        {setup.configured && <Button variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>}
                        <a href={setup.docs} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-sky-700 dark:text-sky-400 self-center">
                            Where to find the keys <ExternalLink className="h-3.5 w-3.5" />
                        </a>
                    </div>
                </div>
            )}

            {setup.webhooks && setup.webhook_url && (
                <div className="rounded-xl bg-slate-50 dark:bg-slate-950 p-3 text-xs text-slate-600 dark:text-slate-400 space-y-1">
                    <p>In the {setup.label} dashboard, add a webhook to this address for <b>payment.captured</b> and <b>order.paid</b>:</p>
                    <div className="flex items-center gap-2">
                        <code className="break-all">{setup.webhook_url}</code>
                        <Button size="icon" variant="ghost" aria-label="Copy webhook address"
                            onClick={() => navigator.clipboard.writeText(setup.webhook_url).then(() => toast.success("Copied"))}>
                            <Copy className="h-3.5 w-3.5" />
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
}

export default function PaymentGatewaysPage() {
    const { can } = usePermissions();
    const { data, isLoading, isError, refetch } = usePaymentGateways();
    if (!can("manage_payment_gateways")) return <Unauthorized />;

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Payment Gateways</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Choose how parents pay fees online. Money goes straight to your school&apos;s own account with the gateway.
                    Start in Test mode, make a test payment, then switch to Live.
                </p>
            </div>
            {isLoading ? <LoadingState className="py-16" /> : isError || !data ? <ErrorState onRetry={refetch} /> : (
                <div className="grid gap-4 xl:grid-cols-2">
                    {data.map((setup) => <GatewayCard key={setup.gateway} setup={setup} />)}
                </div>
            )}
        </div>
    );
}
