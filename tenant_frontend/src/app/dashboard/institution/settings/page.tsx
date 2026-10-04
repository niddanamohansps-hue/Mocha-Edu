"use client";

import { useInstitutionProfile, useUpdateInstitutionProfile } from "@/hooks/useProfile";
import { usePermissions } from "@/providers/PermissionProvider";
import { getMediaUrl } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FloatingLabelInput } from "@/components/ui/floating-label-input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
    Loader2,
    Globe,
    Save,
    Compass,
    Image as ImageIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";

const institutionSchema = z.object({
    name: z.string().min(1, "Institutional name is required"),
    tagline: z.string().optional().or(z.literal("")),
    email: z.string().email("Invalid email address").optional().or(z.literal("")),
    phone: z.string().optional().or(z.literal("")),
    about: z.string().optional().or(z.literal("")),
    website: z.string().url("Invalid website URL").optional().or(z.literal("")),
    established_date: z.string().optional().or(z.literal("")),
    mission: z.string().optional().or(z.literal("")),
    vision: z.string().optional().or(z.literal("")),
    facebook_url: z.string().url("Invalid URL").optional().or(z.literal("")),
    instagram_url: z.string().url("Invalid URL").optional().or(z.literal("")),
    twitter_url: z.string().url("Invalid URL").optional().or(z.literal("")),
    linkedin_url: z.string().url("Invalid URL").optional().or(z.literal("")),
});

type InstitutionFormValues = z.infer<typeof institutionSchema>;

export default function InstitutionSettingsPage() {
    const { can, isOwner } = usePermissions();
    const { data: profile, isLoading, isError, refetch } = useInstitutionProfile();
    const { mutate: updateProfile, isPending: isUpdating } = useUpdateInstitutionProfile();
    const router = useRouter();

    const canView = isOwner || can("view_institution_profile");
    const canEdit = isOwner || can("change_institution_profile");

    const form = useForm<InstitutionFormValues>({
        resolver: zodResolver(institutionSchema),
        defaultValues: {
            name: "",
            tagline: "",
            email: "",
            phone: "",
            about: "",
            website: "",
            established_date: "",
            mission: "",
            vision: "",
            facebook_url: "",
            instagram_url: "",
            twitter_url: "",
            linkedin_url: "",
        },
    });

    const [selectedLogo, setSelectedLogo] = useState<File | null>(null);
    const [logoPreview, setLogoPreview] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleLogoClick = () => {
        fileInputRef.current?.click();
    };

    const handleLogoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            setSelectedLogo(file);
            const previewUrl = URL.createObjectURL(file);
            setLogoPreview(previewUrl);
        }
    };

    useEffect(() => {
        if (profile) {
            form.reset({
                name: profile.name || "",
                tagline: profile.tagline || "",
                email: profile.email || "",
                phone: profile.phone || "",
                about: profile.about || "",
                website: profile.website || "",
                established_date: profile.established_date || "",
                mission: profile.mission || "",
                vision: profile.vision || "",
                facebook_url: profile.facebook_url || "",
                instagram_url: profile.instagram_url || "",
                twitter_url: profile.twitter_url || "",
                linkedin_url: profile.linkedin_url || "",
            });
        }
    }, [profile, form]);

    if (isLoading) {
        return <LoadingState className="h-[60vh]" />;
    }

    if (isError) {
        return <ErrorState onRetry={refetch} className="m-6" />;
    }

    if (!canView) {
        return (
            <Unauthorized />
        );
    }

    const onSubmit = (data: InstitutionFormValues) => {
        if (!canEdit) {
            toast.error("You do not have permission to edit institutional settings.");
            return;
        }

        const payload = new FormData();

        // Append all text fields from the form
        Object.keys(data).forEach(key => {
            const value = (data as any)[key];
            if (value !== null && value !== undefined) {
                payload.append(key, value);
            }
        });

        // Append logo if selected
        if (selectedLogo) {
            payload.append("logo", selectedLogo);
        }

        updateProfile(payload, {
            onSuccess: () => {
                toast.success("Institution details updated successfully!");
                setSelectedLogo(null);
                setLogoPreview(null);
            },
            onError: () => {
                toast.error("Failed to update details.");
            }
        });
    };

    return (
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-5">
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-10">
                {/* Header info */}
                <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                    <div>
                        <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Institution Profile</h1>
                        <p className="text-slate-500 dark:text-slate-400 mt-2 text-lg">Manage your school's brand and public identity</p>
                    </div>
                    {canEdit && (
                        <Button
                            type="submit"
                            size="xxl"
                            disabled={isUpdating}
                        >
                            {isUpdating ? <Loader2 className="h-5 w-5 animate-spin mr-2" /> : <Save className="h-5 w-5 mr-2" />}
                            Save All Changes
                        </Button>
                    )}
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
                    {/* Left Side: Secondary Content */}
                    <div className="lg:col-span-4 space-y-8">
                        <Card className="border-none shadow-xl shadow-slate-200/50 dark:shadow-none dark:bg-slate-900 overflow-hidden pt-0">
                            <CardHeader className="pt-2">
                                <CardTitle className="text-lg">Logo & Banner</CardTitle>
                                <CardDescription>Visual identity of your school</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="space-y-4">
                                    <Label className="text-xs uppercase font-extrabold text-slate-400 tracking-widest">School Logo</Label>
                                    <div className="aspect-square bg-slate-50 dark:bg-slate-800 rounded-3xl border-2 border-dashed border-slate-200 dark:border-slate-700 flex flex-col items-center justify-center group relative cursor-pointer overflow-hidden"
                                        onClick={handleLogoClick}>
                                        <input
                                            type="file"
                                            ref={fileInputRef}
                                            className="hidden"
                                            accept="image/*"
                                            onChange={handleLogoChange}
                                        />
                                        {logoPreview || profile?.logo ? (
                                            <img src={logoPreview || getMediaUrl(profile?.logo) || ''} alt="Logo" className="w-full h-full object-contain p-4" />
                                        ) : (
                                            <>
                                                <ImageIcon className="h-10 w-10 text-slate-300 mb-2 group-hover:scale-110 transition-transform" />
                                                <span className="text-xs font-bold text-slate-400">Click to upload</span>
                                            </>
                                        )}
                                        {canEdit && (
                                            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-[2px]">
                                                <Button variant="default" size="lg" className="font-bold pointer-events-none">Choose Image</Button>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Right Side: Main Forms */}
                    <div className="lg:col-span-8 space-y-10">
                        {/* Basic Info */}
                        <Card className="border-none shadow-xl shadow-slate-200/50 dark:shadow-none dark:bg-slate-900">
                            <CardHeader className="border-b border-slate-50 dark:border-slate-800 pb-0">
                                <CardTitle className="text-xl">Basic Information</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-5 pt-6">
                                <FloatingLabelInput
                                    {...form.register("name")}
                                    id="name"
                                    label="Institutional Name"
                                    error={form.formState.errors.name?.message}
                                    disabled={!canEdit}
                                />

                                <FloatingLabelInput
                                    {...form.register("tagline")}
                                    id="tagline"
                                    label="Institutional Tagline"
                                    error={form.formState.errors.tagline?.message}
                                    disabled={!canEdit}
                                />

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                    <FloatingLabelInput
                                        {...form.register("email")}
                                        id="email"
                                        label="Official School Email"
                                        type="email"
                                        error={form.formState.errors.email?.message}
                                        disabled={!canEdit}
                                    />
                                    <FloatingLabelInput
                                        {...form.register("phone")}
                                        id="phone"
                                        label="Official School Phone"
                                        error={form.formState.errors.phone?.message}
                                        disabled={!canEdit}
                                    />
                                </div>

                                <div className="space-y-3">
                                    <Label htmlFor="about" className="text-xs uppercase font-extrabold text-slate-400 tracking-widest pl-1">About the school</Label>
                                    <Textarea
                                        {...form.register("about")}
                                        id="about"
                                        className="min-h-[140px] bg-slate-50 dark:bg-slate-800/50 border-transparent focus:border-sky-500 dark:focus:border-sky-500 transition-all rounded-3xl p-6 text-base"
                                        disabled={!canEdit}
                                    />
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                    <FloatingLabelInput
                                        {...form.register("website")}
                                        id="website"
                                        label="Official Website"
                                        error={form.formState.errors.website?.message}
                                        disabled={!canEdit}
                                    />
                                    <FloatingLabelInput
                                        {...form.register("established_date")}
                                        id="established_date"
                                        label="Established Date"
                                        type="date"
                                        error={form.formState.errors.established_date?.message}
                                        disabled={!canEdit}
                                    />
                                </div>
                            </CardContent>
                        </Card>

                        {/* Mission & Vision */}
                        <Card className="border-none shadow-xl shadow-slate-200/50 dark:shadow-none dark:bg-slate-900">
                            <CardHeader className="border-b border-slate-50 dark:border-slate-800">
                                <CardTitle className="text-xl">Core Values</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-5 pt-6">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                    <div className="space-y-3">
                                        <div className="flex items-center gap-2 mb-1 pl-1">
                                            <Compass className="h-4 w-4 text-sky-500" />
                                            <Label htmlFor="mission" className="text-xs uppercase font-extrabold text-slate-400 tracking-widest">Mission</Label>
                                        </div>
                                        <Textarea
                                            {...form.register("mission")}
                                            id="mission"
                                            className="min-h-[120px] bg-slate-50 dark:bg-slate-800/50 border-transparent focus:border-teal-500 transition-all rounded-xl p-6"
                                            disabled={!canEdit}
                                        />
                                    </div>
                                    <div className="space-y-3">
                                        <div className="flex items-center gap-2 mb-1 pl-1">
                                            <Globe className="h-4 w-4 text-teal-500" />
                                            <Label htmlFor="vision" className="text-xs uppercase font-extrabold text-slate-400 tracking-widest">Vision</Label>
                                        </div>
                                        <Textarea
                                            {...form.register("vision")}
                                            id="vision"
                                            className="min-h-[120px] bg-slate-50 dark:bg-slate-800/50 border-transparent focus:border-teal-500 transition-all rounded-xl p-6"
                                            disabled={!canEdit}
                                        />
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Social links */}
                        <Card className="border-none shadow-xl shadow-slate-200/50 dark:shadow-none dark:bg-slate-900 overflow-hidden">
                            <CardHeader className="border-b border-slate-50 dark:border-slate-800">
                                <CardTitle className="text-xl">Social Presence</CardTitle>
                            </CardHeader>
                            <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-8 pt-6">
                                <div className="relative">
                                    <FloatingLabelInput
                                        {...form.register("facebook_url")}
                                        id="facebook_url"
                                        label="Facebook URL"
                                        error={form.formState.errors.facebook_url?.message}
                                        disabled={!canEdit}
                                    />
                                </div>
                                <div className="relative">
                                    <FloatingLabelInput
                                        {...form.register("instagram_url")}
                                        id="instagram_url"
                                        label="Instagram URL"
                                        error={form.formState.errors.instagram_url?.message}
                                        disabled={!canEdit}
                                    />
                                </div>
                                <div className="relative">
                                    <FloatingLabelInput
                                        {...form.register("twitter_url")}
                                        id="twitter_url"
                                        label="Twitter URL"
                                        error={form.formState.errors.twitter_url?.message}
                                        disabled={!canEdit}
                                    />
                                </div>
                                <div className="relative">
                                    <FloatingLabelInput
                                        {...form.register("linkedin_url")}
                                        id="linkedin_url"
                                        label="LinkedIn URL"
                                        error={form.formState.errors.linkedin_url?.message}
                                        disabled={!canEdit}
                                    />
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </form>
        </div>
    );
}
