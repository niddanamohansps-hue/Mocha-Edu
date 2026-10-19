import { Suspense } from "react";
import { Loader2 } from "lucide-react";
import { PaymentCallbackHandler } from "@/components/dashboard/fees/PaymentCallbackHandler";

export default function ParentFeesCallbackPage() {
    return (
        <Suspense
            fallback={
                <div className="flex h-96 items-center justify-center">
                    <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
                </div>
            }
        >
            <PaymentCallbackHandler
                returnPath="/dashboard/parent-portal/fees"
                portalTitle="Parent Portal"
            />
        </Suspense>
    );
}

