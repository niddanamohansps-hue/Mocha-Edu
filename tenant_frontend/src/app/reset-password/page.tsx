"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { GraduationCap, Loader2, ArrowRight, CheckCircle, AlertCircle } from "lucide-react";
import { useResetPasswordConfirm } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { FloatingLabelInput } from "@/components/ui/floating-label-input";

export default function ResetPasswordPage() {
    return (
        <Suspense
            fallback={
                <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
                    <Loader2 className="h-10 w-10 animate-spin text-sky-600" />
                </div>
            }
        >
            <ResetPasswordContent />
        </Suspense>
    );
}

function ResetPasswordContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const uid = searchParams.get("uid");
    const token = searchParams.get("token");

    const { mutate: resetPassword, isPending, isSuccess, error } = useResetPasswordConfirm();
    const [newPassword, setNewPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [mismatch, setMismatch] = useState(false);

    const linkIsValid = Boolean(uid && token);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (newPassword !== confirmPassword) {
            setMismatch(true);
            return;
        }
        setMismatch(false);
        resetPassword(
            { uid: uid as string, token: token as string, new_password: newPassword },
            {
                onSuccess: () => {
                    setTimeout(() => router.push("/login"), 2500);
                },
            }
        );
    };

    return (
        <div className="flex min-h-screen items-center justify-center bg-slate-50 dark:bg-slate-950 p-6">
            <div className="w-full max-w-md space-y-8 animate-in fade-in zoom-in duration-500">
                <div className="flex flex-col items-center text-center">
                    <div className="p-3 bg-sky-600 rounded-2xl shadow-lg shadow-sky-500/20 mb-4">
                        <GraduationCap className="h-10 w-10 text-white" />
                    </div>
                    <h2 className="text-3xl font-bold text-slate-900 dark:text-white">Edu Sekai</h2>
                </div>

                <Card className="border-none shadow-2xl bg-white/80 dark:bg-slate-900/80 backdrop-blur-md outline-slate-200/50 dark:outline-slate-800/50">
                    {!linkIsValid ? (
                        <CardContent className="pt-6">
                            <div className="flex flex-col items-center text-center gap-3">
                                <div className="p-3 bg-red-100 dark:bg-red-900/30 rounded-full">
                                    <AlertCircle className="h-8 w-8 text-red-600 dark:text-red-400" />
                                </div>
                                <CardTitle className="text-xl font-bold text-slate-900 dark:text-white">Invalid reset link</CardTitle>
                                <CardDescription className="text-slate-600 dark:text-slate-400">
                                    This password reset link is missing or malformed. Please request a new one.
                                </CardDescription>
                                <Link href="/forgot-password" className="w-full">
                                    <Button className="w-full mt-2">Request a new link</Button>
                                </Link>
                            </div>
                        </CardContent>
                    ) : isSuccess ? (
                        <CardContent className="pt-6">
                            <div className="flex flex-col items-center text-center gap-3">
                                <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-full">
                                    <CheckCircle className="h-8 w-8 text-green-600 dark:text-green-400" />
                                </div>
                                <CardTitle className="text-xl font-bold text-slate-900 dark:text-white">Password reset</CardTitle>
                                <CardDescription className="text-slate-600 dark:text-slate-400">
                                    Redirecting you to login...
                                </CardDescription>
                            </div>
                        </CardContent>
                    ) : (
                        <>
                            <CardHeader className="space-y-2 pb-6">
                                <CardTitle className="text-2xl font-bold text-slate-900 dark:text-white">Set a new password</CardTitle>
                                <CardDescription className="text-slate-600 dark:text-slate-400">
                                    Choose a new password for your account.
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <form onSubmit={handleSubmit} className="space-y-6">
                                    <FloatingLabelInput
                                        id="new-password"
                                        type="password"
                                        autoComplete="new-password"
                                        label="New password"
                                        value={newPassword}
                                        onChange={(e) => setNewPassword(e.target.value)}
                                        required
                                        className="h-12"
                                    />
                                    <FloatingLabelInput
                                        id="confirm-password"
                                        type="password"
                                        autoComplete="new-password"
                                        label="Confirm new password"
                                        value={confirmPassword}
                                        onChange={(e) => setConfirmPassword(e.target.value)}
                                        required
                                        className="h-12"
                                        error={mismatch ? "Passwords do not match." : (error as any)?.response?.data?.error}
                                    />

                                    <Button type="submit" size="xl" className="w-full" disabled={isPending}>
                                        {isPending ? (
                                            <>
                                                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                                                Resetting...
                                            </>
                                        ) : (
                                            <>
                                                Reset password
                                                <ArrowRight className="ml-2 h-5 w-5" />
                                            </>
                                        )}
                                    </Button>
                                </form>
                            </CardContent>
                        </>
                    )}
                </Card>
            </div>
        </div>
    );
}
