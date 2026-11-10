"use client";

import { useState } from "react";
import { usePendingStaffCredentials } from "@/hooks/useStaff";
import { Button } from "@/components/ui/button";
import {
    Copy,
    Eye,
    EyeOff,
    LoaderCircle,
    CircleCheck
} from "lucide-react";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle
} from "@/components/ui/card";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow
} from "@/components/ui/table";
import { toast } from "sonner";
import { downloadCsv } from "@/lib/csv";
import { ErrorState } from "@/components/feedback/ErrorState";

export default function StaffDistributionTab() {
    // using the generic staff credentials hook
    const { data: pendingCreds, isLoading: loadingCreds, isError: credsError, refetch: refetchCreds } = usePendingStaffCredentials();
    const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({});

    const copyToClipboard = (text: string, label: string) => {
        navigator.clipboard.writeText(text);
        toast.success(`${label} copied!`);
    };

    // The login details still to hand out, as a sheet the office can print or share class by class.
    const exportList = () => {
        if (!pendingCreds || pendingCreds.length === 0) return;
        downloadCsv(`staff_credentials_${new Date().toISOString().slice(0, 10)}.csv`, [
            ["Full Name", "Employee ID", "Designation", "Username", "Initial Password"],
            ...pendingCreds.map((c) => [c.full_name, c.employee_id, c.designation, c.username, c.initial_password]),
        ]);
        toast.success("Login details downloaded");
    };

    const togglePasswordVisibility = (id: string) => {
        setShowPasswords(prev => ({ ...prev, [id]: !prev[id] }));
    };

    return (
        <div className="animate-in fade-in duration-500 space-y-6">
            <Card className="border-none ring-1 ring-slate-200 gap-0 dark:ring-slate-800 overflow-hidden bg-white dark:bg-slate-900 py-0">
                <CardHeader className="bg-slate-50 dark:bg-slate-900/30 border-b border-slate-100 dark:border-slate-800 p-8">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                        <div className="space-y-1">
                            <CardTitle className="text-2xl">
                                Staff login details not yet handed out
                            </CardTitle>
                            <CardDescription className="text-base">
                                List of staff members who haven't performed their first security reset yet.
                            </CardDescription>
                        </div>
                        <div className="flex gap-2">
                            <Button variant="outline" size="lg" onClick={exportList} disabled={!pendingCreds || pendingCreds.length === 0}>
                                Export List
                            </Button>
                        </div>
                    </div>
                </CardHeader>
            </Card>

            <Card className="border-none shadow-2xl ring-1 ring-slate-200 gap-0 dark:ring-slate-800 overflow-hidden bg-white dark:bg-slate-900 py-0">
                <CardContent className="p-0">
                    <div className="overflow-x-auto min-h-[400px]">
                        {loadingCreds ? (
                            <div className="p-12 flex justify-center">
                                <LoaderCircle className="h-10 w-10 text-indigo-400 animate-spin" />
                            </div>
                        ) : credsError ? (
                            <ErrorState onRetry={refetchCreds} className="p-12" />
                        ) : !pendingCreds || pendingCreds.length === 0 ? (
                            <div className="h-[400px] flex flex-col items-center justify-center text-slate-400 space-y-4">
                                <div className="p-6 bg-emerald-50 dark:bg-emerald-900/10 rounded-full">
                                    <CircleCheck className="h-12 w-12 text-emerald-500" />
                                </div>
                                <p className="font-medium">All pending staff have successfully activated their accounts!</p>
                            </div>
                        ) : (
                            <Table>
                                <TableHeader className="bg-slate-50 dark:bg-slate-800/50">
                                    <TableRow>
                                        <TableHead className="pl-10 py-5 uppercase text-xs font-bold tracking-wider">Staff Member</TableHead>
                                        <TableHead className="uppercase text-xs font-bold tracking-wider">Designation</TableHead>
                                        <TableHead className="uppercase text-xs font-bold tracking-wider">Portal Username</TableHead>
                                        <TableHead className="uppercase text-xs font-bold tracking-wider">Initial Password</TableHead>
                                        <TableHead className="text-right pr-10 uppercase text-xs font-bold tracking-wider">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {pendingCreds.map((cred: any) => (
                                        <TableRow key={cred.id} className="group hover:bg-slate-50 transition-colors">
                                            <TableCell className="pl-10 py-3">
                                                <p className="font-bold text-slate-900 dark:text-white text-base">{cred.full_name}</p>
                                                <p className="text-xs text-slate-400 font-mono mt-0.5">{cred.employee_id}</p>
                                            </TableCell>
                                            <TableCell>
                                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800">
                                                    {cred.designation}
                                                </span>
                                            </TableCell>
                                            <TableCell>
                                                <div className="flex items-center gap-2">
                                                    <code className="text-sm px-3 py-1 font-bold bg-slate-100 rounded text-slate-700">
                                                        {cred.username}
                                                    </code>
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-7 w-7"
                                                        onClick={() => copyToClipboard(cred.username, "Username")}
                                                    >
                                                        <Copy className="h-3 w-3" />
                                                    </Button>
                                                </div>
                                            </TableCell>
                                            <TableCell>
                                                <div className="flex items-center gap-2">
                                                    <code className="text-sm px-3 py-1 font-bold bg-slate-100 rounded text-slate-700">
                                                        {showPasswords[cred.id] ? cred.initial_password : "•".repeat(10)}
                                                    </code>
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-7 w-7"
                                                        onClick={() => togglePasswordVisibility(cred.id)}
                                                    >
                                                        {showPasswords[cred.id] ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                                                    </Button>
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-7 w-7"
                                                        onClick={() => copyToClipboard(cred.initial_password, "Password")}
                                                    >
                                                        <Copy className="h-3 w-3" />
                                                    </Button>
                                                </div>
                                            </TableCell>
                                            <TableCell className="text-right pr-10">
                                                <Button variant="outline" size="sm">
                                                    Send Mail
                                                </Button>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        )}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
