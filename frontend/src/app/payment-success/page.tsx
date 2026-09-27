"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, CheckCircle, XCircle, AlertCircle, ArrowRight, GraduationCap } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useVerifyPayment } from "@/hooks/payments";
import { Button } from "@/components/ui/button";

export default function PaymentSuccessPage() {
    return (
        <Suspense
            fallback={
                <div className="flex min-h-screen items-center justify-center bg-linear-to-br from-blue-50 via-teal-50 to-green-50 p-4">
                    <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
                </div>
            }
        >
            <PaymentSuccessContent />
        </Suspense>
    );
}

function PaymentSuccessContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const dataParam = searchParams.get("data");
    const { mutate: verifyPayment, isPending, isSuccess, error, data } = useVerifyPayment();

    useEffect(() => {
        if (dataParam) {
            verifyPayment(dataParam, {
                onSuccess: (response) => {
                    if (response.domain_url) {
                        setTimeout(() => {
                            window.location.href = response.domain_url;
                        }, 3000);
                    }
                }
            });
        }
    }, [dataParam, verifyPayment]);

    const handleManualRedirect = () => {
        if (data?.domain_url) {
            window.location.href = data.domain_url;
        }
    };

    return (
        <div className="flex min-h-screen items-center justify-center bg-linear-to-br from-blue-50 via-teal-50 to-green-50 p-4">
            <Card className="w-full max-w-lg border-slate-200 shadow-2xl">
                <CardHeader className="text-center space-y-4 pb-6">
                    <div className="flex justify-center">
                        {isPending && (
                            <div className="p-4 bg-blue-100 rounded-full">
                                <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
                            </div>
                        )}
                        {isSuccess && (
                            <div className="p-4 bg-green-100 rounded-full animate-bounce-once">
                                <CheckCircle className="h-12 w-12 text-green-600" />
                            </div>
                        )}
                        {error && (
                            <div className="p-4 bg-red-100 rounded-full">
                                <XCircle className="h-12 w-12 text-red-600" />
                            </div>
                        )}
                        {!isPending && !isSuccess && !error && (
                            <div className="p-4 bg-slate-100 rounded-full">
                                <AlertCircle className="h-12 w-12 text-slate-600 animate-pulse" />
                            </div>
                        )}
                    </div>

                    <CardTitle className="text-2xl font-bold">
                        {isPending && <span className="text-blue-600">Verifying Payment...</span>}
                        {isSuccess && <span className="text-green-600">Payment Successful!</span>}
                        {error && <span className="text-red-600">Payment Verification Failed</span>}
                        {!isPending && !isSuccess && !error && <span className="text-slate-600">Processing Payment...</span>}
                    </CardTitle>

                    <CardDescription className="text-base text-slate-600">
                        {isPending && "Please wait while we verify your payment and set up your institution."}
                        {isSuccess && "Your organization has been created successfully!"}
                        {error && "There was an issue verifying your payment."}
                        {!isPending && !isSuccess && !error && "Waiting for payment data..."}
                    </CardDescription>
                </CardHeader>

                <CardContent className="space-y-6">
                    {isPending && (
                        <div className="space-y-4">
                            <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                                <div className="flex items-start gap-3">
                                    <Loader2 className="h-5 w-5 text-blue-600 mt-0.5 animate-spin shrink-0" />
                                    <div className="text-sm text-blue-900 space-y-2">
                                        <p className="font-semibold">Setting up your institution...</p>
                                        <ul className="space-y-1 text-blue-700">
                                            <li className="flex items-center gap-2">
                                                <div className="h-1.5 w-1.5 rounded-full bg-blue-600"></div>
                                                Verifying payment details
                                            </li>
                                            <li className="flex items-center gap-2">
                                                <div className="h-1.5 w-1.5 rounded-full bg-blue-600"></div>
                                                Creating your database
                                            </li>
                                            <li className="flex items-center gap-2">
                                                <div className="h-1.5 w-1.5 rounded-full bg-blue-600"></div>
                                                Configuring admin account
                                            </li>
                                        </ul>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {isSuccess && (
                        <div className="space-y-4">
                            <div className="bg-linear-to-br from-green-50 to-emerald-50 p-6 rounded-xl border-2 border-green-200">
                                <div className="space-y-3">
                                    <div className="flex items-center gap-2 text-green-800">
                                        <CheckCircle className="h-5 w-5" />
                                        <p className="font-semibold">Payment Confirmed</p>
                                    </div>
                                    <div className="flex items-center gap-2 text-green-800">
                                        <CheckCircle className="h-5 w-5" />
                                        <p className="font-semibold">Institution Created</p>
                                    </div>
                                    <div className="flex items-center gap-2 text-green-800">
                                        <CheckCircle className="h-5 w-5" />
                                        <p className="font-semibold">Admin Account Ready</p>
                                    </div>
                                </div>
                            </div>

                            <div className="bg-slate-50 p-5 rounded-lg border border-slate-200 text-center">
                                <GraduationCap className="h-8 w-8 text-blue-600 mx-auto mb-2" />
                                <p className="text-sm font-medium text-slate-900 mb-1">
                                    Redirecting to your login page in 3 seconds...
                                </p>
                                <p className="text-xs text-slate-600">
                                    You can now access your institution dashboard
                                </p>
                            </div>

                            <Button
                                onClick={handleManualRedirect}
                                className="w-full h-12 bg-linear-to-r from-blue-600 to-teal-600 hover:from-blue-700 hover:to-teal-700"
                            >
                                Go to Login Now
                                <ArrowRight className="ml-2 h-5 w-5" />
                            </Button>
                        </div>
                    )}

                    {error && (
                        <div className="space-y-4">
                            <div className="bg-red-50 p-5 rounded-lg border-2 border-red-200">
                                <div className="flex items-start gap-3">
                                    <XCircle className="h-5 w-5 text-red-600 mt-0.5 shrink-0" />
                                    <div className="text-sm text-red-900">
                                        <p className="font-semibold mb-2">Verification Failed</p>
                                        <p className="text-red-700">
                                            {(error as any)?.response?.data?.error || (error as any)?.response?.data?.message || error.message || "An unexpected error occurred during payment verification."}
                                        </p>
                                    </div>
                                </div>
                            </div>

                            <div className="bg-slate-50 p-5 rounded-lg border border-slate-200">
                                <p className="text-sm text-slate-700 mb-3 font-medium">What to do next:</p>
                                <ul className="space-y-2 text-sm text-slate-600">
                                    <li className="flex items-start gap-2">
                                        <div className="h-1.5 w-1.5 rounded-full bg-slate-400 mt-1.5 shrink-0"></div>
                                        <span>Check your email for transaction details</span>
                                    </li>
                                    <li className="flex items-start gap-2">
                                        <div className="h-1.5 w-1.5 rounded-full bg-slate-400 mt-1.5 shrink-0"></div>
                                        <span>Contact our support team with your transaction ID</span>
                                    </li>
                                    <li className="flex items-start gap-2">
                                        <div className="h-1.5 w-1.5 rounded-full bg-slate-400 mt-1.5 shrink-0"></div>
                                        <span>Email: support@edusekai.com</span>
                                    </li>
                                </ul>
                            </div>

                            <div className="flex gap-3">
                                <Button
                                    onClick={() => router.push('/get-started')}
                                    variant="outline"
                                    className="flex-1 border-slate-300"
                                >
                                    Try Again
                                </Button>
                                <Button
                                    onClick={() => router.push('/contact-support')}
                                    className="flex-1 bg-slate-900 hover:bg-slate-800"
                                >
                                    Contact Support
                                </Button>
                            </div>
                        </div>
                    )}

                    {!isPending && !isSuccess && !error && (
                        <div className="bg-slate-50 p-5 rounded-lg border border-slate-200 text-center">
                            <AlertCircle className="h-8 w-8 text-slate-600 mx-auto mb-3 animate-pulse" />
                            <p className="text-sm text-slate-700">
                                Waiting for payment confirmation...
                            </p>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}