"use client";

import { useState } from "react";
import {
    useStaffMembers,
    useActivateStaff,
    useRoles,
    StaffActivationData,
    StaffMember
} from "@/hooks/useStaff";
import { Button } from "@/components/ui/button";
import {
    Users,
    Key,
    ShieldCheck,
    TriangleAlert,
    LoaderCircle,
    Plus,
    CircleCheck,
    Trash2,
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
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface ActivationTabProps {
    onSuccess: () => void;
}

export default function StaffActivationTab({ onSuccess }: ActivationTabProps) {
    // Queries
    // Bulk-activation screen needs the full staff roster to filter for
    // unactivated accounts, not one page of it - see the equivalent
    // pageSize=100 choice in students/ActivationTab.tsx.
    const { data: staffData, isLoading: loadingStaff } = useStaffMembers({ pageSize: 100 });
    const allStaff = staffData?.results;
    const { data: roles, isLoading: loadingRoles } = useRoles();
    const { mutateAsync: activatePortal, isPending } = useActivateStaff();

    // Filter for staff who do NOT have a user_id
    const unactivatedStaff = allStaff?.filter(s => !s.profile_details.user_id) || [];

    const [selections, setSelections] = useState<StaffActivationData[]>([]);
    const [errors, setErrors] = useState<any[]>([]);

    // Passwords Generation helper
    const generateUniquePassword = () => {
        const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%^&*";
        let password = "";
        for (let i = 0; i < 10; i++) {
            password += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        return password;
    };

    const generateCredentials = (staff: StaffMember): StaffActivationData => {
        // Generate username: firstname + surname
        const parts = [
            staff.profile_details.first_name.toLowerCase(),
            staff.profile_details.middle_name?.toLowerCase(),
            staff.profile_details.last_name.toLowerCase()
        ].filter(Boolean);

        const username = parts.join('').replace(/\s+/g, '');

        // Auto-match role based on designation
        let preSelectedRole = "";
        if (roles?.results || Array.isArray(roles)) {
            const list = roles.results || roles;
            const match = list.find((r: any) => r.name.toLowerCase() === staff.designation.toLowerCase());
            if (match) preSelectedRole = match.slug;
        }

        return {
            staff_id: staff.id,
            username: username,
            password: generateUniquePassword(),
            role_slug: preSelectedRole,
        };
    };

    const addStaffToSelection = (staff: StaffMember) => {
        if (selections.find(s => s.staff_id === staff.id)) return;
        setSelections([...selections, generateCredentials(staff)]);
    };

    const addAllStaff = () => {
        if (!unactivatedStaff) return;
        // Don't auto-add everyone to selection because role selection is mandatory and unique per person mostly
        // But we can add them, they will just show invalid state if we had validation.
        // For now, let's allow it but they must pick roles.
        const newSelections = unactivatedStaff.map(s => generateCredentials(s));
        setSelections(newSelections);
        toast.info("Added all staff. Please select a role for each member.");
    };

    const updateSelection = (id: string, field: keyof StaffActivationData, value: string) => {
        setSelections(selections.map(s => s.staff_id === id ? { ...s, [field]: value } : s));
    };

    const removeSelection = (id: string) => {
        setSelections(selections.filter(s => s.staff_id !== id));
    };

    const handleActivation = async () => {
        if (selections.length === 0) {
            toast.error("Please add at least one staff member to activate.");
            return;
        }

        // Validate Roles
        const missingRoles = selections.filter(s => !s.role_slug);
        if (missingRoles.length > 0) {
            toast.error(`Please select a role for all ${missingRoles.length} staff members.`);
            return;
        }

        const newErrors: any[] = [];
        for (let i = 0; i < selections.length; i++) {
            const item = selections[i];
            try {
                await activatePortal(item);
            } catch (error: any) {
                newErrors.push({ index: i, error: error.response?.data || "Activation failed" });
            }
        }

        if (newErrors.length > 0) {
            setErrors(newErrors);
            toast.error("Some accounts failed to activate.");
        } else {
            setSelections([]);
            onSuccess();
            toast.success("All selected accounts activated successfully!");
        }
    };

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Available Staff List */}
                <Card className="border-none shadow-xl ring-1 ring-slate-200 dark:ring-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm h-fit pb-0 gap-2">
                    <CardHeader className="border-b border-slate-100 dark:border-slate-800">
                        <CardTitle className="text-xl flex items-center gap-2">
                            <Users className="h-5 w-5 text-slate-400" />
                            Onboarded Staff
                        </CardTitle>
                        <CardDescription>
                            Unactivated staff profiles.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="px-2">
                        {loadingStaff ? (
                            <div className="p-8 flex justify-center">
                                <LoaderCircle className="h-8 w-8 text-slate-300 animate-spin" />
                            </div>
                        ) : !unactivatedStaff || unactivatedStaff.length === 0 ? (
                            <div className="p-12 text-center space-y-4">
                                <div className="p-4 bg-emerald-50 dark:bg-emerald-900/20 rounded-full w-fit mx-auto">
                                    <CircleCheck className="h-8 w-8 text-emerald-500" />
                                </div>
                                <p className="text-slate-500 font-medium">All staff members have portal access!</p>
                            </div>
                        ) : (
                            <div className="divide-y divide-slate-100 dark:divide-slate-800 max-h-[600px] overflow-y-auto">
                                {unactivatedStaff.map((staff) => {
                                    const isAdded = selections.find(s => s.staff_id === staff.id);
                                    const fullName = `${staff.profile_details.first_name} ${staff.profile_details.last_name}`;
                                    return (
                                        <div key={staff.id} className="p-4 flex items-center justify-between group hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                                            <div>
                                                <p className="font-bold text-slate-900 dark:text-white capitalize">{fullName}</p>
                                                <p className="text-xs text-slate-500 font-mono tracking-tighter uppercase">{staff.employee_id} • {staff.designation}</p>
                                            </div>
                                            <Button
                                                size="sm"
                                                variant={isAdded ? "ghost" : "outline"}
                                                onClick={() => addStaffToSelection(staff)}
                                                disabled={!!isAdded}
                                                className={cn(
                                                    "rounded-lg h-9 w-9 p-0",
                                                    isAdded && "text-emerald-600 bg-emerald-100 dark:bg-emerald-900/20"
                                                )}
                                            >
                                                {isAdded ? <CircleCheck className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                                            </Button>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Account Preparation Grid */}
                <Card className="lg:col-span-2 border-none shadow-2xl ring-1 ring-slate-200 dark:ring-slate-800 overflow-hidden bg-white/80 dark:bg-slate-900/80 backdrop-blur-md py-0">
                    <CardHeader className="bg-slate-50/50 dark:bg-slate-800/20 border-b border-slate-100 dark:border-slate-800 px-8 py-6">
                        <div className="flex items-center justify-between">
                            <div className="space-y-1">
                                <CardTitle className="text-2xl font-bold">Account Setup</CardTitle>
                                <CardDescription>Assign system roles and generate credentials.</CardDescription>
                            </div>
                            <div className="flex items-center gap-3">
                                <Button
                                    onClick={addAllStaff}
                                    variant="outline"
                                    size="lg"
                                    disabled={!unactivatedStaff || unactivatedStaff.length === 0}
                                >
                                    Batch Add
                                </Button>

                                <div className="bg-blue-50 dark:bg-blue-900/20 px-4 py-2 shadow-sm rounded-sm border border-blue-100 dark:border-blue-800">
                                    <span className="text-primary dark:text-blue-400 font-bold">{selections.length}</span>
                                    <span className="text-primary text-xs ml-2 font-medium">Ready</span>
                                </div>
                            </div>
                        </div>
                    </CardHeader>
                    <CardContent className="p-0">
                        <div className="overflow-x-auto min-h-[400px]">
                            {selections.length === 0 ? (
                                <div className="h-[400px] flex flex-col items-center justify-center text-slate-400 space-y-4">
                                    <div className="p-6 bg-slate-50 dark:bg-slate-800/50 rounded-3xl border-2 border-dashed border-slate-200 dark:border-slate-700">
                                        <Users className="h-12 w-12 opacity-20" />
                                    </div>
                                    <p className="font-medium">Selected staff will appear here.</p>
                                </div>
                            ) : (
                                <Table>
                                    <TableHeader className="bg-slate-50/80 dark:bg-slate-800/50">
                                        <TableRow className="border-b border-slate-200 dark:border-slate-800">
                                            <TableHead className="pl-6 text-xs font-bold py-4 uppercase w-[180px]">Staff Details</TableHead>
                                            <TableHead className="text-xs font-bold uppercase w-[200px]">System Role</TableHead>
                                            <TableHead className="text-xs font-bold uppercase">Username</TableHead>
                                            <TableHead className="text-xs font-bold uppercase w-[150px]">Password</TableHead>
                                            <TableHead className="w-12 pr-6"></TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {selections.map((item, index) => {
                                            const staff = unactivatedStaff.find(s => s.id === item.staff_id);
                                            const error = errors.find(e => e.index === index);
                                            const fullName = staff ? `${staff.profile_details.first_name} ${staff.profile_details.last_name}` : "Unknown";

                                            return (
                                                <TableRow key={item.staff_id} className={cn(
                                                    "group transition-all duration-200 hover:bg-indigo-50/10",
                                                    error && "bg-red-50/40"
                                                )}>
                                                    <TableCell className="pl-6 py-5 align-top">
                                                        <p className="font-bold text-slate-900 dark:text-white truncate max-w-[150px]">{fullName}</p>
                                                        <p className="text-[10px] text-slate-400 font-mono italic truncate">{staff?.employee_id}</p>
                                                        <p className="text-[10px] text-slate-500 truncate">{staff?.designation}</p>
                                                    </TableCell>
                                                    <TableCell className="align-top">
                                                        <Select
                                                            value={item.role_slug}
                                                            onValueChange={(value) => updateSelection(item.staff_id, "role_slug", value)}
                                                        >
                                                            <SelectTrigger className="h-9 w-full border-slate-200">
                                                                <SelectValue placeholder="Select Role" />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {(roles?.results || (Array.isArray(roles) ? roles : []))?.map((role: any) => (
                                                                    <SelectItem key={role.id} value={role.slug}>
                                                                        {role.name}
                                                                    </SelectItem>
                                                                ))}

                                                            </SelectContent>
                                                        </Select>
                                                    </TableCell>
                                                    <TableCell className="align-top">
                                                        <Input
                                                            value={item.username}
                                                            onChange={(e) => updateSelection(item.staff_id, "username", e.target.value)}
                                                            className="h-9 text-xs border-slate-200 dark:border-slate-800 bg-white/50"
                                                        />
                                                    </TableCell>
                                                    <TableCell className="align-top">
                                                        <div className="relative group/pass">
                                                            <Input
                                                                value={item.password}
                                                                type="text"
                                                                onChange={(e) => updateSelection(item.staff_id, "password", e.target.value)}
                                                                className="h-9 text-xs pr-8 border-indigo-200 bg-white/50 font-mono"
                                                            />
                                                            <Key className="absolute right-2 top-1/2 -translate-y-1/2 h-3 w-3 text-indigo-300" />
                                                        </div>
                                                    </TableCell>
                                                    <TableCell className="pr-6 align-top">
                                                        <Button
                                                            variant="destructive"
                                                            size="icon"
                                                            className="h-8 w-8"
                                                            onClick={() => removeSelection(item.staff_id)}
                                                        >
                                                            <Trash2 className="h-3 w-3" />
                                                        </Button>
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        })}
                                    </TableBody>
                                </Table>
                            )}
                        </div>
                        <div className="p-8 border-t border-slate-100 dark:border-slate-800 bg-slate-50/30 dark:bg-slate-900/30">
                            <Button
                                onClick={handleActivation}
                                disabled={isPending || selections.length === 0}
                                size="lg"
                                className="w-full text-lg h-14"
                            >
                                {isPending ? (
                                    <>
                                        <LoaderCircle className="h-6 w-6 mr-3 animate-spin" />
                                        Activating Portal Access...
                                    </>
                                ) : (
                                    <>
                                        <ShieldCheck className="h-6 w-6 mr-3" />
                                        Activate & Assign Roles
                                    </>
                                )}
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Error Reporting */}
            {
                errors.length > 0 && (
                    <div className="bg-red-50/50 dark:bg-red-900/10 border-2 border-red-100 dark:border-red-900/30 rounded-3xl p-8 space-y-4">
                        <div className="flex items-center gap-3 text-red-600 dark:text-red-400">
                            <TriangleAlert className="h-6 w-6" />
                            <h3 className="text-xl font-bold">Process Conflicts</h3>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {errors.map((err, i) => (
                                <div key={i} className="bg-white dark:bg-slate-950 p-4 rounded-2xl border border-red-100 dark:border-red-900/20">
                                    <p className="text-sm text-red-600 font-bold">Row {err.index + 1}: {JSON.stringify(err.error)}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                )
            }
        </div >
    );
}
