"use client";

import { useState } from "react";
import Link from "next/link";
import { GraduationCap, Loader2, ArrowRight, ArrowLeft, MailCheck } from "lucide-react";
import { useForgotPassword } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { FloatingLabelInput } from "@/components/ui/floating-label-input";

export default function ForgotPasswordPage() {
    const { mutate: forgotPassword, isPending, isSuccess } = useForgotPassword();
    const [email, setEmail] = useState("");

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        forgotPassword(email);
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
                    {isSuccess ? (
                        <>
                            <CardHeader className="space-y-2 pb-6 items-center text-center">
                                <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-full mb-2">
                                    <MailCheck className="h-8 w-8 text-green-600 dark:text-green-400" />
                                </div>
                                <CardTitle className="text-2xl font-bold text-slate-900 dark:text-white">Check your email</CardTitle>
                                <CardDescription className="text-slate-600 dark:text-slate-400">
                                    If an account with that email exists, we&apos;ve sent a link to reset your password.
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <Link href="/login">
                                    <Button variant="outline" className="w-full">
                                        <ArrowLeft className="mr-2 h-4 w-4" />
                                        Back to login
                                    </Button>
                                </Link>
                            </CardContent>
                        </>
                    ) : (
                        <>
                            <CardHeader className="space-y-2 pb-6">
                                <CardTitle className="text-2xl font-bold text-slate-900 dark:text-white">Forgot password?</CardTitle>
                                <CardDescription className="text-slate-600 dark:text-slate-400">
                                    Enter the email on your account and we&apos;ll send you a link to reset it.
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <form onSubmit={handleSubmit} className="space-y-6">
                                    <FloatingLabelInput
                                        id="email"
                                        type="email"
                                        label="Email"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        required
                                        className="h-12"
                                    />

                                    <Button type="submit" size="xl" className="w-full" disabled={isPending}>
                                        {isPending ? (
                                            <>
                                                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                                                Sending...
                                            </>
                                        ) : (
                                            <>
                                                Send reset link
                                                <ArrowRight className="ml-2 h-5 w-5" />
                                            </>
                                        )}
                                    </Button>
                                </form>
                            </CardContent>
                        </>
                    )}
                </Card>

                <p className="text-center text-sm text-slate-500 dark:text-slate-500">
                    Remembered your password?{" "}
                    <Link href="/login" className="font-bold text-sky-600 dark:text-sky-400">
                        Back to login
                    </Link>
                </p>
            </div>
        </div>
    );
}
