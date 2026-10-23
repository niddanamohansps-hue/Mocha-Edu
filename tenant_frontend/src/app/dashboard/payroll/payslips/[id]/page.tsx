"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { PayslipView } from "@/components/dashboard/payroll/PayslipView";
import { PageHeader } from "@/components/dashboard/payroll/shared";
import { openProtectedFile, usePayslip } from "@/hooks/usePayroll";
import { usePermissions } from "@/providers/PermissionProvider";

export default function PayslipPage() {
    const params = useParams<{ id: string }>();
    const id = Array.isArray(params.id) ? params.id[0] : params.id;
    const { can } = usePermissions();
    const { data, isLoading, isError, refetch } = usePayslip(id);

    if (!can("view_payroll")) return <ErrorState message="You do not have permission to view payroll." />;
    if (isLoading) return <LoadingState className="py-20" />;
    if (isError || !data) return <ErrorState message="Could not load this payslip." onRetry={refetch} />;

    return (
        <div className="space-y-6 max-w-3xl">
            <PageHeader
                title="Payslip"
                actions={<Button asChild variant="outline"><Link href={`/dashboard/payroll/runs/${data.run}`}>Back to the payroll</Link></Button>}
            />
            <PayslipView payslip={data} onPdf={() => openProtectedFile(`/payroll/payslips/${data.id}/pdf/`, "payslip.pdf", "open")} />
        </div>
    );
}
