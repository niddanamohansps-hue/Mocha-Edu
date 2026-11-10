"use client";

import React, { useEffect } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
    Dialog,
    DialogBody,
    DialogContent,
    DialogFooter,
} from "@/components/ui/dialog";
import { ModalHeader } from "@/components/ui/modal-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    FormSection,
    FormGrid,
    FormGrid3,
    FormFieldWrapper,
} from "@/components/ui/form-layout";
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
    whatsapp_opt_in: z.boolean(),
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
            whatsapp_opt_in: false,
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
                    whatsapp_opt_in: parent.whatsapp_opt_in ?? false,
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
                    whatsapp_opt_in: false,
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
            whatsapp_opt_in: values.whatsapp_opt_in,
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
            <DialogContent className="max-w-2xl max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                <ModalHeader
                    title={isEdit ? "Edit Parent Details" : "Add New Parent / Guardian"}
                    subtitle={
                        isEdit
                            ? "Update contact information, profile data, and employment details."
                            : "Create a new parent profile. You can link students directly after saving."
                    }
                    onClose={() => onOpenChange(false)}
                />

                <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                    <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-6">
                        {/* Primary Name Details */}
                        <FormSection title="1. Personal Identification">
                            <FormGrid3>
                                <FormFieldWrapper
                                    label="First Name"
                                    htmlFor="first_name"
                                    required
                                    error={form.formState.errors.first_name?.message}
                                >
                                    <Input
                                        id="first_name"
                                        placeholder="e.g. Ramesh"
                                        {...form.register("first_name")}
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper
                                    label="Middle Name"
                                    htmlFor="middle_name"
                                    error={form.formState.errors.middle_name?.message}
                                >
                                    <Input
                                        id="middle_name"
                                        placeholder="e.g. Kumar"
                                        {...form.register("middle_name")}
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper
                                    label="Last Name"
                                    htmlFor="last_name"
                                    required
                                    error={form.formState.errors.last_name?.message}
                                >
                                    <Input
                                        id="last_name"
                                        placeholder="e.g. Sharma"
                                        {...form.register("last_name")}
                                    />
                                </FormFieldWrapper>
                            </FormGrid3>
                        </FormSection>

                        {/* Contact & Gender */}
                        <FormSection title="2. Contact Information">
                            <FormGrid3>
                                <FormFieldWrapper
                                    label="Phone Number"
                                    htmlFor="phone"
                                    error={form.formState.errors.phone?.message}
                                >
                                    <Input
                                        id="phone"
                                        placeholder="e.g. 9876543210"
                                        {...form.register("phone")}
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper
                                    label="Email Address"
                                    htmlFor="email"
                                    error={form.formState.errors.email?.message}
                                >
                                    <Input
                                        id="email"
                                        type="email"
                                        placeholder="e.g. ramesh@example.com"
                                        {...form.register("email")}
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper
                                    label="Gender"
                                    htmlFor="gender"
                                >
                                    <Controller
                                        control={form.control}
                                        name="gender"
                                        render={({ field }) => (
                                            <Select
                                                value={field.value || "male"}
                                                onValueChange={field.onChange}
                                            >
                                                <SelectTrigger id="gender">
                                                    <SelectValue placeholder="Select gender" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="male">Male</SelectItem>
                                                    <SelectItem value="female">Female</SelectItem>
                                                    <SelectItem value="other">Other</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        )}
                                    />
                                </FormFieldWrapper>
                            </FormGrid3>

                            <div className="mt-4">
                                <FormFieldWrapper
                                    label="Residential Address"
                                    htmlFor="address"
                                    colSpan="full"
                                    error={form.formState.errors.address?.message}
                                >
                                    <Input
                                        id="address"
                                        placeholder="House / Street / City / PIN"
                                        {...form.register("address")}
                                    />
                                </FormFieldWrapper>
                            </div>
                        </FormSection>

                        {/* Occupation & Employment */}
                        <FormSection title="3. Occupation & Communication Preferences">
                            <FormGrid3>
                                <FormFieldWrapper
                                    label="Occupation"
                                    htmlFor="occupation"
                                    error={form.formState.errors.occupation?.message}
                                >
                                    <Input
                                        id="occupation"
                                        placeholder="e.g. Software Engineer"
                                        {...form.register("occupation")}
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper
                                    label="Office Address"
                                    htmlFor="office_address"
                                    error={form.formState.errors.office_address?.message}
                                >
                                    <Input
                                        id="office_address"
                                        placeholder="e.g. Tech Park, Block B"
                                        {...form.register("office_address")}
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper
                                    label="Income Level"
                                    htmlFor="income_level"
                                    error={form.formState.errors.income_level?.message}
                                >
                                    <Input
                                        id="income_level"
                                        placeholder="e.g. Middle / Upper Middle"
                                        {...form.register("income_level")}
                                    />
                                </FormFieldWrapper>
                            </FormGrid3>

                            <div className="mt-4">
                                <label className="flex items-start gap-3 rounded-xl border border-slate-200 dark:border-slate-800 p-3.5 text-sm bg-slate-50/60 dark:bg-slate-900/60 hover:bg-slate-100/60 dark:hover:bg-slate-800/40 transition-colors cursor-pointer">
                                    <input
                                        type="checkbox"
                                        className="mt-1 h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500"
                                        {...form.register("whatsapp_opt_in")}
                                    />
                                    <div className="space-y-0.5">
                                        <span className="font-semibold text-slate-800 dark:text-slate-200">
                                            Send fee reminders and absence alerts on WhatsApp
                                        </span>
                                        <span className="block text-xs text-slate-400">
                                            Tick only if the parent has agreed. Messages will be dispatched to the verified phone number above.
                                        </span>
                                    </div>
                                </label>
                            </div>
                        </FormSection>
                    </DialogBody>

                    <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => onOpenChange(false)}
                            disabled={isSubmitting}
                        >
                            Cancel
                        </Button>
                        <Button
                            type="submit"
                            disabled={isSubmitting}
                            className="min-w-[120px]"
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
