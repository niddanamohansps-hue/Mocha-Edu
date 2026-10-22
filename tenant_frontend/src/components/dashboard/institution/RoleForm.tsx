"use client";

import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { FloatingLabelInput } from "@/components/ui/floating-label-input";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Loader2, Save, ArrowLeft, ShieldCheck, ChevronDown } from "lucide-react";
import { useRouter } from "next/navigation";
import { RoleFormData, PermissionGroup } from "@/types/roles";
import { Role } from "@/types/auth";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const roleSchema = z.object({
    name: z.string().min(1, "Role name is required"),
    description: z.string(),
    permission_ids: z.array(z.string()).min(1, "Select at least one permission"),
});

export type RoleFormValues = z.infer<typeof roleSchema>;

interface RoleFormProps {
    initialData?: Role;
    permissionGroups: PermissionGroup[];
    onSubmit: (data: RoleFormData) => void;
    isSubmitting: boolean;
}

export default function RoleForm({ initialData, permissionGroups, onSubmit, isSubmitting }: RoleFormProps) {
    const router = useRouter();
    const isEditing = !!initialData;

    const form = useForm<RoleFormValues>({
        resolver: zodResolver(roleSchema),
        defaultValues: {
            name: initialData?.name || "",
            description: initialData?.description || "",
            permission_ids: initialData?.permissions.map(p => p.id) || [],
        },
    });

    const togglePermission = (permissionId: string) => {
        const currentIds = form.getValues("permission_ids");
        const exists = currentIds.includes(permissionId);
        const newIds = exists
            ? currentIds.filter(id => id !== permissionId)
            : [...currentIds, permissionId];

        form.setValue("permission_ids", newIds, { shouldValidate: true });
    };

    // Modules with at least one pre-checked permission start expanded (edit mode);
    // everything else starts collapsed so the 13-module list isn't one giant scroll.
    const [openModules, setOpenModules] = useState<Set<string>>(() => {
        const initiallySelected = new Set(initialData?.permissions.map(p => p.id) || []);
        const expanded = new Set<string>();
        for (const group of permissionGroups) {
            if (group.permissions.some(p => initiallySelected.has(p.id))) {
                expanded.add(group.module);
            }
        }
        return expanded;
    });

    const toggleModule = (module: string) => {
        setOpenModules(prev => {
            const next = new Set(prev);
            if (next.has(module)) next.delete(module);
            else next.add(module);
            return next;
        });
    };

    const allExpanded = openModules.size === permissionGroups.length;
    const toggleAll = () => {
        setOpenModules(allExpanded ? new Set() : new Set(permissionGroups.map(g => g.module)));
    };

    const selectedIds = form.watch("permission_ids");
    const selectedCountByModule = useMemo(() => {
        const counts: Record<string, number> = {};
        for (const group of permissionGroups) {
            counts[group.module] = group.permissions.filter(p => selectedIds.includes(p.id)).length;
        }
        return counts;
    }, [permissionGroups, selectedIds]);

    return (
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-4 min-w-0">
                    <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => router.back()}
                        className="rounded-full shrink-0"
                    >
                        <ArrowLeft className="h-5 w-5" />
                    </Button>
                    <div className="min-w-0">
                        <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-white truncate">
                            {isEditing ? `Edit Role: ${initialData.name}` : "Create New Role"}
                        </h1>
                        <p className="text-slate-500 dark:text-slate-400 text-sm sm:text-base">
                            {isEditing ? "Modify role details and permissions" : "Define a new role and assign permissions"}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                    <Button type="button" variant="outline" size="xl" onClick={() => router.back()} className="flex-1 sm:flex-none">
                        Cancel
                    </Button>
                    <Button type="submit" disabled={isSubmitting} size="xl" className="flex-1 sm:flex-none">
                        {isSubmitting ? (
                            <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        ) : (
                            <Save className="h-4 w-4 mr-2" />
                        )}
                        {isEditing ? "Update Role" : "Create Role"}
                    </Button>
                </div>
            </div>

            <div>
                {/* Basic Info */}
                <div>
                    <Card className="border-none shadow-xl shadow-slate-200/50 dark:shadow-none dark:bg-slate-900">
                        <CardHeader>
                            <CardTitle className="text-xl">General Information</CardTitle>
                            <CardDescription>Basic details about this role</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <FloatingLabelInput
                                {...form.register("name")}
                                id="name"
                                label="Role Name"
                                required
                                disabled={initialData?.is_system_role}
                                error={form.formState.errors.name?.message}
                            />
                            {initialData?.is_system_role && (
                                <p className="text-xs text-amber-600 bg-amber-50 dark:bg-amber-900/20 p-3 rounded-xl flex items-start gap-2 border border-amber-100 dark:border-amber-900/30">
                                    <ShieldCheck className="h-4 w-4 mt-0.5" />
                                    <span>System Role names cannot be changed, but you can modify their permissions.</span>
                                </p>
                            )}

                            <FloatingLabelInput
                                {...form.register("description")}
                                id="description"
                                label="Description"
                                error={form.formState.errors.description?.message}
                            />
                        </CardContent>
                    </Card>
                </div>

                {/* Permissions */}
                <div className="mt-6">
                    <Card className="border-none shadow-xl shadow-slate-200/50 dark:shadow-none dark:bg-slate-900">
                        <CardHeader className="flex flex-wrap flex-row items-center justify-between gap-2 space-y-0 pb-6">
                            <div>
                                <CardTitle className="text-xl">Access Permissions</CardTitle>
                                <CardDescription>Select what this role is allowed to do</CardDescription>
                            </div>
                            <div className="flex items-center gap-3">
                                <button
                                    type="button"
                                    onClick={toggleAll}
                                    className="text-xs font-bold text-sky-600 hover:text-sky-700 dark:text-sky-400 transition-colors"
                                >
                                    {allExpanded ? "Collapse all" : "Expand all"}
                                </button>
                                <div className="bg-sky-50 dark:bg-sky-900/30 text-sky-600 dark:text-sky-300 px-3 py-1 rounded-full text-xs font-bold">
                                    {selectedIds.length} selected
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent>
                            {form.formState.errors.permission_ids && (
                                <p className="text-sm text-red-500 font-semibold mb-6 p-3 bg-red-50 dark:bg-red-900/20 rounded-xl border border-red-100 dark:border-red-900/30">
                                    {form.formState.errors.permission_ids.message}
                                </p>
                            )}

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {permissionGroups.map((group) => {
                                    const isOpen = openModules.has(group.module);
                                    const count = selectedCountByModule[group.module];
                                    return (
                                        <div
                                            key={group.module}
                                            className="rounded-2xl border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 overflow-hidden transition-colors duration-200 hover:border-sky-200 dark:hover:border-sky-900"
                                        >
                                            <button
                                                type="button"
                                                onClick={() => toggleModule(group.module)}
                                                className="w-full flex flex-wrap items-center justify-between gap-3 px-4 py-3 cursor-pointer group"
                                            >
                                                <span className="flex items-center gap-2">
                                                    <h4 className="font-bold text-sm text-slate-500 dark:text-slate-400 uppercase tracking-widest group-hover:text-sky-600 dark:group-hover:text-sky-400 transition-colors">
                                                        {group.module}
                                                    </h4>
                                                    {count > 0 && (
                                                        <span className="bg-sky-100 dark:bg-sky-500/10 text-sky-600 dark:text-sky-400 text-[10px] font-bold px-2 py-0.5 rounded-full">
                                                            {count}
                                                        </span>
                                                    )}
                                                </span>
                                                <ChevronDown
                                                    className={cn(
                                                        "h-4 w-4 text-slate-400 transition-transform duration-200 ease-out",
                                                        isOpen && "rotate-180"
                                                    )}
                                                />
                                            </button>

                                            {isOpen && (
                                                <div className="space-y-3 px-4 pb-4 animate-in fade-in slide-in-from-top-2 duration-200">
                                                    {group.permissions.map((perm) => (
                                                        <div key={perm.id} className="flex items-start gap-3 group">
                                                            <Checkbox
                                                                id={perm.id}
                                                                checked={selectedIds.includes(perm.id)}
                                                                onCheckedChange={() => togglePermission(perm.id)}
                                                                className="mt-1"
                                                            />
                                                            <div className="grid gap-1.5 leading-none">
                                                                <Label
                                                                    htmlFor={perm.id}
                                                                    className="text-sm font-semibold leading-none cursor-pointer group-hover:text-sky-600 transition-colors"
                                                                >
                                                                    {perm.name}
                                                                </Label>
                                                                <p className="text-xs text-slate-500 dark:text-slate-400 leading-normal">
                                                                    {perm.description}
                                                                </p>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>

            {/* Sticky action bar so Cancel/Save stay reachable through the long permission list */}
            <div className="sticky bottom-0 -mx-3 sm:-mx-6 px-3 sm:px-6 py-4 mt-8 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md border-t border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-t-xl shadow-[0_-4px_12px_rgba(0,0,0,0.04)]">
                <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">
                    {selectedIds.length} permission{selectedIds.length === 1 ? "" : "s"} selected
                </p>
                <div className="flex items-center gap-3">
                    <Button type="button" variant="outline" size="xl" onClick={() => router.back()} className="flex-1 sm:flex-none">
                        Cancel
                    </Button>
                    <Button type="submit" disabled={isSubmitting} size="xl" className="flex-1 sm:flex-none">
                        {isSubmitting ? (
                            <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        ) : (
                            <Save className="h-4 w-4 mr-2" />
                        )}
                        {isEditing ? "Update Role" : "Create Role"}
                    </Button>
                </div>
            </div>
        </form>
    );
}
