"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ResponsiveList } from "@/components/common/ResponsiveList";
import { EmptyHint, FilterBar } from "@/components/common/PageLayout";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { SetSalaryDialog, StructureDialog } from "@/components/dashboard/payroll/SalaryDialogs";
import { PageHeader, Pager, formatDate, formatMoney } from "@/components/dashboard/payroll/shared";
import { useSalaries } from "@/hooks/usePayroll";
import { usePermissions } from "@/providers/PermissionProvider";

export default function SalariesPage() {
    const { can } = usePermissions();
    const [page, setPage] = useState(1);
    const [search, setSearch] = useState("");
    const [searchText, setSearchText] = useState("");
    const [setting, setSetting] = useState(false);
    const [viewing, setViewing] = useState<{ id: string; name: string } | null>(null);
    const { data, isLoading, isError, refetch } = useSalaries({ page, search });

    if (!can("view_payroll")) return <ErrorState message="You do not have permission to view salaries." />;
    const rows = data?.results ?? [];

    return (
        <div className="space-y-6">
            <PageHeader
                title="Salaries"
                description="Each person's basic monthly salary in force today. Open a person to see their pay structure, add allowances or deductions, or change their salary."
                actions={can("manage_salary_structures") && <Button onClick={() => setSetting(true)}>Set a salary</Button>}
            />
            <FilterBar onSubmit={() => { setPage(1); setSearch(searchText.trim()); }}>
                <Input type="text" placeholder="Search name or employee ID" aria-label="Search staff" value={searchText} onChange={(e) => setSearchText(e.target.value)} />
                <Button type="submit" variant="outline">Search</Button>
            </FilterBar>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load salaries. Please try again." onRetry={refetch} />
            ) : rows.length === 0 ? (
                <EmptyHint
                    title={search ? "No one matches your search." : "No salaries set yet."}
                    hint={search ? "Try a different word." : "Staff without a salary are left out of the payroll. Set a salary for each person first."}
                    action={!search && can("manage_salary_structures") ? <Button onClick={() => setSetting(true)}>Set the first salary</Button> : undefined}
                />
            ) : (
                <ResponsiveList
                    rows={rows}
                    rowKey={(r) => r.id}
                    columns={[
                        { key: "name", header: "Staff member", primary: true, cell: (r) => <>{r.staff_name} <span className="text-xs font-normal text-slate-500">({r.employee_id})</span></> },
                        { key: "basic", header: "Basic salary", className: "font-bold", cell: (r) => formatMoney(r.basic_amount) },
                        { key: "from", header: "Since", className: "text-slate-500", cell: (r) => formatDate(r.effective_from) },
                        { key: "note", header: "Note", hideOnMobile: true, className: "text-slate-500", cell: (r) => r.note || "-" },
                    ]}
                    actionsHeader="Details"
                    actions={(r) => <Button size="sm" variant="outline" onClick={() => setViewing({ id: r.staff, name: r.staff_name })}>Pay structure</Button>}
                />
            )}
            <Pager data={data} page={page} onPage={setPage} />

            <SetSalaryDialog open={setting} onClose={() => setSetting(false)} />
            <StructureDialog staffId={viewing?.id ?? null} staffName={viewing?.name ?? ""} onClose={() => setViewing(null)} />
        </div>
    );
}
