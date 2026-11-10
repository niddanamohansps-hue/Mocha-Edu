"use client";

import { useState } from "react";
import { useParentCredentials } from "@/hooks/useFamilies";
import { Button } from "@/components/ui/button";
import {
    Copy,
    Eye,
    EyeOff,
    LoaderCircle,
    CircleCheck,
    Printer,
    Download,
} from "lucide-react";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { toast } from "sonner";
import { downloadCsv } from "@/lib/csv";
import { ErrorState } from "@/components/feedback/ErrorState";

export default function ParentDistributionTab() {
    const { data: pendingCreds, isLoading: loadingCreds, isError: credsError, refetch: refetchCreds } = useParentCredentials();
    const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({});

    const copyToClipboard = (text: string, label: string) => {
        navigator.clipboard.writeText(text);
        toast.success(`${label} copied!`);
    };

    const togglePasswordVisibility = (id: string) => {
        setShowPasswords((prev) => ({ ...prev, [id]: !prev[id] }));
    };

    const handlePrint = () => {
        window.print();
    };

    const handleExportCSV = () => {
        if (!pendingCreds || pendingCreds.length === 0) return;
        downloadCsv(`parent_credentials_${new Date().toISOString().slice(0, 10)}.csv`, [
            ["Full Name", "Username", "Initial Password"],
            ...pendingCreds.map((c) => [c.full_name, c.username, c.initial_password]),
        ]);
        toast.success("Credentials CSV downloaded!");
    };

    return (
        <div className="space-y-6">
            <Card className="border border-slate-200 dark:border-slate-800 rounded-3xl bg-white dark:bg-slate-900 shadow-xs">
                <CardHeader className="bg-slate-50/50 dark:bg-slate-900/30 border-b border-slate-100 dark:border-slate-800 p-8">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                        <div className="space-y-1">
                            <CardTitle className="text-2xl font-bold">
                                Parent Credentials Distribution List
                            </CardTitle>
                            <CardDescription className="text-base">
                                List of parents who have been provisioned but have not yet completed their first password reset.
                            </CardDescription>
                        </div>
                        {pendingCreds && pendingCreds.length > 0 && (
                            <div className="flex gap-2.5">
                                <Button
                                    variant="outline"
                                    size="lg"
                                    onClick={handleExportCSV}
                                    className="rounded-xl h-11"
                                >
                                    <Download className="h-4 w-4 mr-2" />
                                    Export CSV
                                </Button>
                                <Button
                                    variant="outline"
                                    size="lg"
                                    onClick={handlePrint}
                                    className="rounded-xl h-11"
                                >
                                    <Printer className="h-4 w-4 mr-2" />
                                    Print Slips
                                </Button>
                            </div>
                        )}
                    </div>
                </CardHeader>

                <CardContent className="p-0">
                    <div className="overflow-x-auto min-h-[350px]">
                        {loadingCreds ? (
                            <div className="p-16 flex justify-center items-center text-slate-400 gap-2">
                                <LoaderCircle className="h-8 w-8 text-sky-500 animate-spin" />
                                <span>Loading distribution roster...</span>
                            </div>
                        ) : credsError ? (
                            <ErrorState onRetry={refetchCreds} className="p-12" />
                        ) : !pendingCreds || pendingCreds.length === 0 ? (
                            <div className="h-[350px] flex flex-col items-center justify-center text-slate-400 space-y-3">
                                <div className="p-4 bg-emerald-50 dark:bg-emerald-950/20 rounded-full">
                                    <CircleCheck className="h-10 w-10 text-emerald-500" />
                                </div>
                                <h3 className="font-semibold text-slate-700 dark:text-slate-200">
                                    All Parent Credentials Handed Out
                                </h3>
                                <p className="text-xs text-slate-400 max-w-sm text-center">
                                    There are currently no parents with uncollected temporary login credentials.
                                </p>
                            </div>
                        ) : (
                            <Table>
                                <TableHeader className="bg-slate-50 dark:bg-slate-800/50">
                                    <TableRow>
                                        <TableHead className="py-4 pl-8">Parent Name</TableHead>
                                        <TableHead>Portal Username</TableHead>
                                        <TableHead>Temporary Password</TableHead>
                                        <TableHead className="text-right pr-8">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {pendingCreds.map((cred) => {
                                        const isVisible = Boolean(showPasswords[cred.id]);
                                        return (
                                            <TableRow key={cred.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/50">
                                                <TableCell className="py-4 pl-8 font-semibold text-slate-900 dark:text-white">
                                                    {cred.full_name}
                                                </TableCell>

                                                <TableCell>
                                                    <div className="flex items-center gap-2">
                                                        <code className="text-xs bg-slate-100 dark:bg-slate-800 px-2.5 py-1 rounded-lg font-mono">
                                                            {cred.username}
                                                        </code>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => copyToClipboard(cred.username, "Username")}
                                                            className="h-7 w-7 text-slate-400 hover:text-sky-500 rounded-lg"
                                                            title="Copy Username"
                                                        >
                                                            <Copy className="h-3.5 w-3.5" />
                                                        </Button>
                                                    </div>
                                                </TableCell>

                                                <TableCell>
                                                    <div className="flex items-center gap-2">
                                                        <code className="text-xs bg-slate-100 dark:bg-slate-800 px-2.5 py-1 rounded-lg font-mono tracking-wider">
                                                            {isVisible ? cred.initial_password : "••••••••••"}
                                                        </code>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => togglePasswordVisibility(cred.id)}
                                                            className="h-7 w-7 text-slate-400 hover:text-sky-500 rounded-lg"
                                                            title={isVisible ? "Hide Password" : "Show Password"}
                                                        >
                                                            {isVisible ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                                                        </Button>
                                                        <Button
                                                            variant="ghost"
                                                            size="icon"
                                                            onClick={() => copyToClipboard(cred.initial_password, "Password")}
                                                            className="h-7 w-7 text-slate-400 hover:text-sky-500 rounded-lg"
                                                            title="Copy Password"
                                                        >
                                                            <Copy className="h-3.5 w-3.5" />
                                                        </Button>
                                                    </div>
                                                </TableCell>

                                                <TableCell className="text-right pr-8">
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        onClick={() => {
                                                            copyToClipboard(
                                                                `Login details for ${cred.full_name}:\nUsername: ${cred.username}\nTemporary Password: ${cred.initial_password}`,
                                                                "Full credentials"
                                                            );
                                                        }}
                                                        className="rounded-xl text-xs h-8"
                                                    >
                                                        Copy Details
                                                    </Button>
                                                </TableCell>
                                            </TableRow>
                                        );
                                    })}
                                </TableBody>
                            </Table>
                        )}
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}

