import { Suspense } from "react";
import { Loader2 } from "lucide-react";
import { PaymentCallbackHandler } from "@/components/dashboard/fees/PaymentCallbackHandler";

export default function FeesCallbackPage() {
    return (
        <Suspense
            fallback={
                <div className="flex h-96 items-center justify-center">
                    <Loader2 className="h-8 w-8 animate-spin text-indigo-600" />
                </div>
            }
        >
            <PaymentCallbackHandler
                returnPath="/dashboard/fees/my-fees"
                portalTitle="My Fees"
            />
        </Suspense>
    );
}

