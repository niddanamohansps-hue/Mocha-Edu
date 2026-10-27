"use client";

import React, { useEffect } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Loader2 } from "lucide-react";
import { useCreateParent, useUpdateParent } from "@/hooks/useFamilies";
import type { Parent, ParentFormData } from "@/types/Families";

const parentSchema = z.object({
    first_name: z.string().trim().min(2, "First name must be at least 2 characters"),
    middle_name: z.string().trim().optional(),
    last_name: z.string().trim().min(2, "Last name must be at least 2 characters"),
    phone: z.string().trim().optional(),
    email: z
        .string()
        .trim()
        .email("Please enter a valid email address")
        .optional()
        .or(z.literal("")),
    gender: z.string().optional(),
    address: z.string().trim().optional(),
    occupation: z.string().trim().optional(),
    office_address: z.string().trim().optional(),
    income_level: z.string().trim().optional(),
});

type ParentFormValues = z.infer<typeof parentSchema>;

interface ParentFormDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    parent?: Parent | null;
    onSuccess?: (parent: Parent) => void;
}

export function ParentFormDialog({
    open,
    onOpenChange,
    parent,
    onSuccess,
}: ParentFormDialogProps) {
    const isEdit = Boolean(parent);
    const { mutate: createParent, isPending: isCreating } = useCreateParent();
    const { mutate: updateParent, isPending: isUpdating } = useUpdateParent();
    const isSubmitting = isCreating || isUpdating;

    const form = useForm<ParentFormValues>({
        resolver: zodResolver(parentSchema),
        defaultValues: {
            first_name: "",
            middle_name: "",
            last_name: "",
            phone: "",
            email: "",
            gender: "male",
            address: "",
            occupation: "",
            office_address: "",
            income_level: "",
        },
    });

    useEffect(() => {
        if (open) {
            if (parent) {
                form.reset({
                    first_name: parent.profile_details?.first_name || "",
                    middle_name: parent.profile_details?.middle_name || "",
                    last_name: parent.profile_details?.last_name || "",
                    phone: parent.profile_details?.phone || "",
                    email: parent.profile_details?.email || "",
                    gender: parent.profile_details?.gender || "male",
                    address: parent.profile_details?.address || "",
                    occupation: parent.occupation || "",
                    office_address: parent.office_address || "",
                    income_level: parent.income_level || "",
                });
            } else {
                form.reset({
                    first_name: "",
                    middle_name: "",
                    last_name: "",
                    phone: "",
                    email: "",
                    gender: "male",
                    address: "",
                    occupation: "",
                    office_address: "",
                    income_level: "",
                });
            }
        }
    }, [open, parent, form]);

    const onSubmit = (values: ParentFormValues) => {
        const payload: ParentFormData = {
            first_name: values.first_name,
            middle_name: values.middle_name || undefined,
            last_name: values.last_name,
            phone: values.phone || undefined,
            email: values.email || undefined,
            gender: values.gender || undefined,
            address: values.address || undefined,
            occupation: values.occupation || undefined,
            office_address: values.office_address || undefined,
            income_level: values.income_level || undefined,
        };

        if (isEdit && parent) {
            updateParent(
                { id: parent.id, data: payload },
                {
                    onSuccess: (saved) => {
                        onOpenChange(false);
                        onSuccess?.(saved);
                    },
                }
            );
        } else {
            createParent(payload, {
                onSuccess: (saved) => {
                    onOpenChange(false);
                    onSuccess?.(saved);
                },
            });
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto rounded-3xl">
                <DialogHeader>
                    <DialogTitle className="text-xl font-bold">
                        {isEdit ? "Edit Parent Details" : "Add New Parent / Guardian"}
                    </DialogTitle>
                    <DialogDescription>
                        {isEdit
                            ? "Update contact information, profile data, and employment details."
                            : "Create a new parent profile. You can link students directly after saving."}
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6 pt-2">
                    {/* Primary Name Details */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="space-y-1.5">
                            <Label htmlFor="first_name" className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                                First Name <span className="text-red-500">*</span>
                            </Label>
                            <Input
                                id="first_name"
                                placeholder="e.g. Ramesh"
                                {...form.register("first_name")}
                                className="rounded-xl"
                            />
                            {form.formState.errors.first_name && (
                                <p className="text-xs text-red-500">{form.formState.errors.first_name.message}</p>
                            )}
                        </div>

                        <div className="space-y-1.5">
                            <Label htmlFor="middle_name" className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                                Middle Name
                            </Label>
                            <Input
                                id="middle_name"
                                placeholder="e.g. Kumar"
                                {...form.register("middle_name")}
                                className="rounded-xl"
                            />
                        </div>

                        <div className="space-y-1.5">
                            <Label htmlFor="last_name" className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                                Last Name <span className="text-red-500">*</span>
                            </Label>
                            <Input
                                id="last_name"
                                placeholder="e.g. Sharma"
                                {...form.register("last_name")}
                                className="rounded-xl"
                            />
                            {form.formState.errors.last_name && (
                                <p className="text-xs text-red-500">{form.formState.errors.last_name.message}</p>
                            )}
                        </div>
                    </div>

                    {/* Contact & Gender */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="space-y-1.5">
                            <Label htmlFor="phone" className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                                Phone Number
                            </Label>
                            <Input
                                id="phone"
                                placeholder="e.g. 9876543210"
                                {...form.register("phone")}
                                className="rounded-xl"
                            />
                            {form.formState.errors.phone && (
                                <p className="text-xs text-red-500">{form.formState.errors.phone.message}</p>
                            )}
                        </div>

                        <div className="space-y-1.5">
                            <Label htmlFor="email" className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                                Email Address
                            </Label>
                            <Input
                                id="email"
                                type="email"
                                placeholder="e.g. ramesh@example.com"
                                {...form.register("email")}
                                className="rounded-xl"
                            />
                            {form.formState.errors.email && (
                                <p className="text-xs text-red-500">{form.formState.errors.email.message}</p>
                            )}
                        </div>

                        <div className="space-y-1.5">
                            <Label htmlFor="gender" className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                                Gender
                            </Label>
                            <Controller
                                control={form.control}
                                name="gender"
                                render={({ field }) => (
                                    <Select
                                        value={field.value || "male"}
                                        onValueChange={field.onChange}
                                    >
                                        <SelectTrigger id="gender" className="rounded-xl">
                                            <SelectValue placeholder="Select gender" />
                                        </SelectTrigger>
                                        <SelectContent className="rounded-xl">
                                            <SelectItem value="male">Male</SelectItem>
                                            <SelectItem value="female">Female</SelectItem>
                                            <SelectItem value="other">Other</SelectItem>
                                        </SelectContent>
                                    </Select>
                                )}
                            />
                        </div>
                    </div>

                    {/* Residential Address */}
                    <div className="space-y-1.5">
                        <Label htmlFor="address" className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                            Residential Address
                        </Label>
                        <Input
                            id="address"
                            placeholder="House / Street / City / PIN"
                            {...form.register("address")}
                            className="rounded-xl"
                        />
                    </div>

                    {/* Occupation & Employment */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="space-y-1.5">
                            <Label htmlFor="occupation" className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                                Occupation
                            </Label>
                            <Input
                                id="occupation"
                                placeholder="e.g. Software Engineer"
                                {...form.register("occupation")}
                                className="rounded-xl"
                            />
                        </div>

                        <div className="space-y-1.5">
                            <Label htmlFor="office_address" className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                                Office Address
                            </Label>
                            <Input
                                id="office_address"
                                placeholder="e.g. Tech Park, Block B"
                                {...form.register("office_address")}
                                className="rounded-xl"
                            />
                        </div>

                        <div className="space-y-1.5">
                            <Label htmlFor="income_level" className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                                Income Level
                            </Label>
                            <Input
                                id="income_level"
                                placeholder="e.g. Middle / Upper Middle"
                                {...form.register("income_level")}
                                className="rounded-xl"
                            />
                        </div>
                    </div>

                    <DialogFooter className="gap-2 pt-4">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => onOpenChange(false)}
                            disabled={isSubmitting}
                            className="rounded-xl"
                        >
                            Cancel
                        </Button>
                        <Button
                            type="submit"
                            disabled={isSubmitting}
                            className="rounded-xl min-w-[120px]"
                        >
                            {isSubmitting ? (
                                <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    Saving...
                                </>
                            ) : isEdit ? (
                                "Update Parent"
                            ) : (
                                "Create Parent"
                            )}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

