"use client";

import { useState } from "react";
import Link from "next/link";
import { GraduationCap, Loader2, ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useLogin } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { FloatingLabelInput } from "@/components/ui/floating-label-input";


export default function LoginPage() {
    const router = useRouter();
    const { mutate: login, isPending: isLoading } = useLogin();
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        login({ username, password }, {
            onSuccess: () => {
                router.push("/dashboard/profile");
            }
        });
    };

    return (
        <div className="flex min-h-screen bg-slate-50 dark:bg-slate-950">
            {/* Left Side - Information (Hidden on mobile) */}
            <div className="hidden lg:flex lg:w-5/12 bg-sky-600 p-12 flex-col justify-between text-white relative overflow-hidden">
                <div className="relative z-10">
                    <div className="flex items-center gap-3 mb-12 animate-in slide-in-from-left duration-700">
                        <GraduationCap className="h-10 w-10" />
                        <span className="text-3xl font-bold">Edu Sekai</span>
                    </div>

                    <div className="space-y-10">
                        <div className="animate-in slide-in-from-left duration-700 delay-100">
                            <h1 className="text-5xl font-extrabold mb-6 leading-tight">
                                Manage Your Education Institution <br />
                                <span className="text-sky-200">With Confidence.</span>
                            </h1>
                            <p className="text-xl text-sky-50/80 max-w-lg leading-relaxed">
                                Access your personalized dashboard to manage students, staff, and institutional operations with ease.
                            </p>
                        </div>
                    </div>
                </div>

                <div className="relative z-10 pt-12 border-t border-white/20 flex flex-wrap justify-between gap-2 items-center text-white text-sm">
                    <p>© 2025 Edu Sekai Ltd.</p>
                    <div className="flex gap-4">
                        <a href="#">Privacy</a>
                        <a href="#">Terms</a>
                    </div>
                </div>
            </div>

            {/* Right Side - Login Form */}
            <div className="flex-1 flex items-center justify-center p-6 lg:p-12 animate-in fade-in zoom-in duration-500">
                <div className="w-full max-w-md space-y-8">
                    <div className="lg:hidden flex flex-col items-center text-center mb-8">
                        <div className="p-3 bg-sky-600 rounded-2xl shadow-lg shadow-sky-500/20 mb-4">
                            <GraduationCap className="h-10 w-10 text-white" />
                        </div>
                        <h2 className="text-3xl font-bold text-slate-900 dark:text-white">Edu Sekai</h2>
                        <p className="text-slate-500 dark:text-slate-400">Institutional Login</p>
                    </div>

                    <Card className="border-none shadow-2xl bg-white/80 dark:bg-slate-900/80 backdrop-blur-md outline-slate-200/50 dark:outline-slate-800/50">
                        <CardHeader className="space-y-2 pb-6">
                            <CardTitle className="text-2xl font-bold text-slate-900 dark:text-white">Welcome Back</CardTitle>
                            <CardDescription className="text-slate-600 dark:text-slate-400">
                                Please enter your credentials to access your dashboard
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <form onSubmit={handleLogin} className="space-y-6">
                                <FloatingLabelInput
                                    id="username"
                                    autoComplete="username"
                                    type="text"
                                    label="Username"
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    required
                                    className="h-12"
                                />

                                <div className="space-y-1">
                                    <FloatingLabelInput
                                        id="password"
                                        autoComplete="current-password"
                                        type="password"
                                        label="Password"
                                        value={password}
                                        onChange={(e) => setPassword(e.target.value)}
                                        required
                                        className="h-12"
                                    />
                                    <div className="flex justify-end pt-1">
                                        <Link href="/forgot-password" className="text-xs font-semibold text-sky-600 hover:text-sky-500 dark:text-sky-400">
                                            Forgot password?
                                        </Link>
                                    </div>
                                </div>

                                <Button
                                    type="submit"
                                    size="xl"
                                    className="w-full "
                                    disabled={isLoading}
                                >
                                    {isLoading ? (
                                        <>
                                            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                                            Authenticating...
                                        </>
                                    ) : (
                                        <>
                                            Login to Dashboard
                                            <ArrowRight className="ml-2 h-5 w-5" />
                                        </>
                                    )}
                                </Button>
                            </form>
                        </CardContent>
                    </Card>

                    <p className="text-center text-sm text-slate-500 dark:text-slate-500">
                        Having trouble? <a href="#" className="font-bold text-sky-600 dark:text-sky-400">Contact Support</a>
                    </p>
                </div>
            </div>
        </div>
    );
}
