"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Loader2, GraduationCap, CheckCircle, Shield, Zap, Users } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";

import { useInitPayment, useVerifyAccount, useCheckDomain } from "@/hooks/payments";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
    Form,
    FormControl,
    FormDescription,
    FormField,
    FormItem,
    FormLabel,
    FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { FloatingLabelInput } from "@/components/ui/floating-label-input";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";

const formSchema = z.object({
    organizationName: z.string().min(2, "School name must be at least 2 characters."),
    subdomain: z.string()
        .min(3, "Subdomain must be at least 3 characters.")
        .regex(/^[a-z0-9]+$/, "Subdomain must be lowercase letters and numbers only."),
    username: z.string().min(3, "Username must be at least 3 characters.").regex(/^[a-z0-9_]+$/, "Username can only contain lowercase letters, numbers, and underscores."),
    email: z.string().email("Invalid email address."),
    password: z.string().min(8, "Password must be at least 8 characters."),
    phone: z.string().min(10, "Phone number must be at least 10 digits."),
});

type FormValues = z.infer<typeof formSchema>;

import { Suspense } from "react";

function GetStartedContent() {
    const router = useRouter();
    const [step, setStep] = useState<"form" | "payment">("form");
    const [formData, setFormData] = useState<FormValues | null>(null);
    const [paymentData, setPaymentData] = useState<any>(null);
    const [isChecking, setIsChecking] = useState(false);
    const searchParams = useSearchParams();

    useEffect(() => {
        if (searchParams.get("status") === "failed" || searchParams.get("payment") === "failed") {
            toast.error("Payment was cancelled or failed. Please try again.");
            // Reset to form step if it was on payment
            setStep("form");
        }
    }, [searchParams]);

    const { mutateAsync: initPayment } = useInitPayment();
    const { mutateAsync: verifyAccount } = useVerifyAccount();
    const { mutateAsync: checkDomain } = useCheckDomain();

    const form = useForm<FormValues>({
        resolver: zodResolver(formSchema),
        defaultValues: {
            organizationName: "",
            subdomain: "",
            username: "",
            email: "",
            password: "",
            phone: "",
        },
    });

    async function onFormSubmit(values: FormValues) {
        setIsChecking(true);
        try {
            // 1. Check Subdomain
            const domainResult = await checkDomain(values.subdomain);
            if (domainResult.exists) {
                form.setError("subdomain", { message: "This subdomain is already taken." });
                setIsChecking(false);
                return;
            }

            // 2. Check Username and Email
            const accountResult = await verifyAccount({
                email: values.email,
                username: values.username,
                password: values.password
            });

            if (accountResult.username_exists && !accountResult.email_exists) {
                form.setError("username", { message: "This username is already taken by another account." });
                setIsChecking(false);
                return;
            }

            if (accountResult.email_exists && !accountResult.valid_password) {
                form.setError("password", { message: "Account exists with this email but password is incorrect." });
                setIsChecking(false);
                return;
            }

            // 3. Proceed to Payment Init
            const payload = {
                organization_name: values.organizationName,
                subdomain: values.subdomain,
                username: values.username,
                email: values.email,
                password: values.password,
                phone: values.phone,
            };

            const response = await initPayment(payload);
            setFormData(values);
            setPaymentData(response);
            setStep("payment");
        } catch (error: any) {
            console.error("Validation or Payment error", error);
            toast.error(error.response?.data?.error || "Something went wrong. Please try again.");
        } finally {
            setIsChecking(false);
        }
    }

    function handleEsewaPayment() {
        if (!paymentData || !formData) return;

        const form = document.createElement('form');
        form.method = 'POST';
        form.action = paymentData.url;

        const fields = {
            amount: paymentData.amount,
            tax_amount: '0',
            total_amount: paymentData.amount,
            transaction_uuid: paymentData.transaction_uuid,
            product_code: paymentData.product_code,
            product_service_charge: '0',
            product_delivery_charge: '0',
            success_url: `${window.location.origin}/payment-success`,
            failure_url: `${window.location.origin}/get-started?payment=failed`,
            signed_field_names: 'total_amount,transaction_uuid,product_code',
            signature: paymentData.signature,
        };

        Object.entries(fields).forEach(([key, value]) => {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = key;
            input.value = value;
            form.appendChild(input);
        });

        document.body.appendChild(form);
        form.submit();
    }

    return (
        <div className="flex min-h-screen from-blue-50 via-teal-50 to-green-50">
            {/* Left Side - Information */}
            <div className="hidden lg:flex lg:w-5/12 bg-primary p-12 flex-col justify-between text-white">
                <div>
                    <div className="flex items-center gap-3 mb-12">
                        <GraduationCap className="h-10 w-10" />
                        <span className="text-3xl font-bold">Edu Sekai</span>
                    </div>

                    <div className="space-y-8">
                        <div>
                            <h1 className="text-4xl font-bold mb-4 leading-tight">
                                Start Your Educational Journey Today
                            </h1>
                            <p className="text-lg text-blue-100">
                                Join thousands of institutions transforming education with our comprehensive management platform.
                            </p>
                        </div>

                        <div className="space-y-6 mt-12">
                            <div className="flex items-start gap-4">
                                <div className="p-3 bg-white/10 rounded-lg backdrop-blur-sm">
                                    <CheckCircle className="h-6 w-6" />
                                </div>
                                <div>
                                    <h3 className="font-semibold text-lg mb-1">Complete Management Solution</h3>
                                    <p className="text-blue-100">Manage students, teachers, fees, and more in one place</p>
                                </div>
                            </div>

                            <div className="flex items-start gap-4">
                                <div className="p-3 bg-white/10 rounded-lg backdrop-blur-sm">
                                    <Shield className="h-6 w-6" />
                                </div>
                                <div>
                                    <h3 className="font-semibold text-lg mb-1">Secure & Reliable</h3>
                                    <p className="text-blue-100">Bank-grade security with 99.9% uptime guarantee</p>
                                </div>
                            </div>

                            <div className="flex items-start gap-4">
                                <div className="p-3 bg-white/10 rounded-lg backdrop-blur-sm">
                                    <Zap className="h-6 w-6" />
                                </div>
                                <div>
                                    <h3 className="font-semibold text-lg mb-1">Quick Setup</h3>
                                    <p className="text-blue-100">Get started in minutes with our intuitive setup process</p>
                                </div>
                            </div>

                            <div className="flex items-start gap-4">
                                <div className="p-3 bg-white/10 rounded-lg backdrop-blur-sm">
                                    <Users className="h-6 w-6" />
                                </div>
                                <div>
                                    <h3 className="font-semibold text-lg mb-1">24/7 Support</h3>
                                    <p className="text-blue-100">Dedicated support team ready to help anytime</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                Please enter your credentials to access your dashboard
            </div>

            {/* Right Side - Form */}
            <div className="flex-1 flex items-center justify-center p-6 lg:p-12">
                <Card className="w-full max-w-xl border-slate-200 shadow-2xl">
                    <CardHeader className="space-y-3 pb-6">
                        <div className="lg:hidden flex items-center gap-2 mb-4">
                            <GraduationCap className="h-8 w-8 text-blue-600" />
                            <span className="text-2xl font-bold bg-linear-to-r from-blue-600 to-teal-600 bg-clip-text text-transparent">Edu Sekai</span>
                        </div>
                        <CardTitle className="text-2xl font-bold text-slate-900">
                            {step === "form" ? "Create Your Institution Account" : "Complete Your Payment"}
                        </CardTitle>
                        <CardDescription className="text-slate-600">
                            {step === "form"
                                ? "Fill in your details to get started with a 30-day free trial"
                                : "Secure your lifetime access with a one-time payment"}
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        {step === "form" ? (
                            <Form {...form}>
                                <form onSubmit={form.handleSubmit(onFormSubmit)} className="space-y-5">
                                    <FormField
                                        control={form.control}
                                        name="organizationName"
                                        render={({ field }) => (
                                            <FormItem>
                                                <FormControl>
                                                    <FloatingLabelInput label="Institution Name" {...field} />
                                                </FormControl>
                                                <FormMessage />
                                            </FormItem>
                                        )}
                                    />

                                    <FormField
                                        control={form.control}
                                        name="subdomain"
                                        render={({ field }) => (
                                            <FormItem>
                                                <FormLabel className="text-slate-700">Your Subdomain</FormLabel>
                                                <FormControl>
                                                    <div className="flex">
                                                        <Input aria-label="myschool"
                                                            placeholder="myschool"
                                                            {...field}
                                                            className="rounded-r-none border-slate-300 focus:border-blue-500"
                                                        />
                                                        <div className="flex items-center px-4 border border-l-0 rounded-r-lg bg-slate-50 text-sm text-slate-600 font-medium">
                                                            .localhost
                                                        </div>
                                                    </div>
                                                </FormControl>
                                                <FormDescription className="text-xs text-slate-500">
                                                    Your unique URL for accessing the platform
                                                </FormDescription>
                                                <FormMessage />
                                            </FormItem>
                                        )}
                                    />

                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        <FormField
                                            control={form.control}
                                            name="username"
                                            render={({ field }) => (
                                                <FormItem>
                                                    <FormControl>
                                                        <FloatingLabelInput label="Owner Username" {...field} />
                                                    </FormControl>
                                                    <FormMessage />
                                                </FormItem>
                                            )}
                                        />
                                        <FormField
                                            control={form.control}
                                            name="email"
                                            render={({ field }) => (
                                                <FormItem>
                                                    <FormControl>
                                                        <FloatingLabelInput label="Admin Email" type="email" {...field} />
                                                    </FormControl>
                                                    <FormMessage />
                                                </FormItem>
                                            )}
                                        />
                                    </div>

                                    <FormField
                                        control={form.control}
                                        name="phone"
                                        render={({ field }) => (
                                            <FormItem>
                                                <FormControl>
                                                    <FloatingLabelInput label="Phone Number" {...field} />
                                                </FormControl>
                                                <FormMessage />
                                            </FormItem>
                                        )}
                                    />

                                    <FormField
                                        control={form.control}
                                        name="password"
                                        render={({ field }) => (
                                            <FormItem>
                                                <FormControl>
                                                    <FloatingLabelInput label="Password (min 8 characters)" type="password" {...field} />
                                                </FormControl>
                                                <FormMessage />
                                            </FormItem>
                                        )}
                                    />

                                    <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
                                        <div className="flex items-start gap-3">
                                            <CheckCircle className="h-5 w-5 text-blue-600 mt-0.5 shrink-0" />
                                            <div className="text-sm text-blue-900">
                                                <p className="font-semibold mb-1">30-Day Free Trial Included</p>
                                                <p className="text-blue-700">No credit card required. Full access to all features.</p>
                                            </div>
                                        </div>
                                    </div>

                                    <Button
                                        type="submit"
                                        className="inline-flex items-center justify-center gap-2 whitespace-nowrap disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive cursor-pointer bg-sky-600 hover:bg-teal-600 shadow-lg shadow-sky-500/25 transition-all text-base font-bold text-white duration-300 ease-in-out h-12 rounded-md px-8 has-[>svg]:px-4 w-full"
                                        disabled={isChecking}
                                    >
                                        {isChecking ? (
                                            <>
                                                <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                                                Processing...
                                            </>
                                        ) : (
                                            "Continue to Payment"
                                        )}
                                    </Button>

                                    <p className="text-xs text-center text-slate-500 pt-2">
                                        By continuing, you agree to our Terms of Service and Privacy Policy
                                    </p>
                                </form>
                            </Form>
                        ) : (
                            <div className="space-y-6">
                                <div className="bg-linear-to-br from-green-50 to-emerald-50 p-6 rounded-xl border-2 border-green-200">
                                    <div className="flex items-center justify-between mb-4">
                                        <div>
                                            <p className="text-sm font-medium text-green-700 mb-1">One-Time Payment</p>
                                            <p className="text-4xl font-bold text-green-900">Rs. {paymentData?.amount}</p>
                                        </div>
                                        <div className="text-right">
                                            <div className="inline-block bg-green-600 text-white px-4 py-2 rounded-full text-sm font-bold">
                                                Lifetime Access
                                            </div>
                                        </div>
                                    </div>
                                    <div className="border-t border-green-200 pt-4 mt-4">
                                        <p className="text-sm text-green-700">
                                            <CheckCircle className="inline h-4 w-4 mr-2" />
                                            All features included
                                        </p>
                                        <p className="text-sm text-green-700 mt-2">
                                            <CheckCircle className="inline h-4 w-4 mr-2" />
                                            No recurring fees
                                        </p>
                                    </div>
                                </div>

                                <div className="bg-slate-50 p-5 rounded-lg border border-slate-200">
                                    <p className="text-sm text-slate-700 mb-2">
                                        <span className="font-semibold text-slate-900">Institution:</span> {formData?.organizationName}
                                    </p>
                                    <p className="text-sm text-slate-700 mb-2">
                                        <span className="font-semibold text-slate-900">Subdomain:</span> {formData?.subdomain}.localhost
                                    </p>
                                    <p className="text-sm text-slate-700">
                                        <span className="font-semibold text-slate-900">Admin Account:</span> {formData?.username} ({formData?.email})
                                    </p>
                                </div>

                                <Button
                                    className="w-full h-12 text-base font-semibold bg-linear-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700"
                                    onClick={handleEsewaPayment}
                                    disabled={isChecking}
                                >
                                    {isChecking ? (
                                        <>
                                            <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                                            Processing...
                                        </>
                                    ) : (
                                        <>
                                            <Shield className="mr-2 h-5 w-5" />
                                            Pay Securely with eSewa
                                        </>
                                    )}
                                </Button>

                                <Button
                                    variant="outline"
                                    className="w-full h-12 border-slate-300"
                                    onClick={() => setStep("form")}
                                    disabled={isChecking}
                                >
                                    Back to Details
                                </Button>

                                <p className="text-xs text-center text-slate-500">
                                    <Shield className="inline h-3 w-3 mr-1" />
                                    Secure payment powered by eSewa
                                </p>
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}

export default function GetStartedPage() {
    return (
        <Suspense fallback={
            <div className="flex min-h-screen items-center justify-center bg-slate-50">
                <Loader2 className="h-10 w-10 animate-spin text-blue-600" />
            </div>
        }>
            <GetStartedContent />
        </Suspense>
    );
}