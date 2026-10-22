"use client";

import { useProfile, useUpdateProfile } from "@/hooks/useProfile";
import { useMe, useLogout } from "@/hooks/useAuth";
import { isAxiosError } from "axios";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FloatingLabelInput } from "@/components/ui/floating-label-input";
import { useState, useEffect, useRef } from "react";
import {
    Loader2,
    User,
    Save,
    Mail,
    Phone,
    Calendar,
    MapPin,
    Briefcase,
    BookOpen,
    ShieldCheck,
    BadgeCheck,
    ImageIcon,
    AlertCircle,
    LogOut
} from "lucide-react";
import { toast } from "sonner";
import { AnyProfile, StaffProfile, StudentProfile } from "@/types/Profile";
import { getMediaUrl } from "@/lib/utils";

export default function ProfilePage() {
    const { data: user } = useMe();
    const { data: profile, isLoading, isError, error } = useProfile();
    const { mutate: updateProfile, isPending: isUpdating } = useUpdateProfile();
    const { mutate: logout, isPending: isLoggingOut } = useLogout();

    const [formData, setFormData] = useState<Partial<AnyProfile>>({});
    const [selectedImage, setSelectedImage] = useState<File | null>(null);
    const [imagePreview, setImagePreview] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (profile) {
            setFormData(profile);
        }
    }, [profile]);

    if (isLoading) {
        return (
            <div className="flex h-[60vh] items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                    <Loader2 className="h-12 w-12 animate-spin text-sky-600" />
                    <p className="text-slate-500 font-medium animate-pulse">Loading your profile...</p>
                </div>
            </div>
        );
    }

    if (isError || !profile) {
        const isNotFound = isAxiosError(error) ? error.response?.status === 404 : !profile;
        const errorData = isAxiosError(error) ? (error.response?.data as Record<string, unknown> | undefined) : undefined;
        const errorMessage = typeof errorData?.error === "string" ? errorData.error : typeof errorData?.detail === "string" ? errorData.detail : undefined;

        return (
            <div className="max-w-2xl mx-auto mt-12 space-y-6">
                <Card className="border-slate-200 dark:border-slate-800 shadow-xl overflow-hidden">
                    <div className="h-3 bg-amber-500" />
                    <CardHeader className="text-center pt-8 pb-4">
                        <div className="mx-auto w-16 h-16 rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center text-amber-600 mb-4">
                            <AlertCircle className="h-8 w-8" />
                        </div>
                        <CardTitle className="text-2xl font-bold text-slate-900 dark:text-white">
                            {isNotFound ? "No Profile Found" : "Unable to Load Profile"}
                        </CardTitle>
                        <CardDescription className="text-base mt-2 text-slate-600 dark:text-slate-400 max-w-md mx-auto">
                            {isNotFound
                                ? "Your account is authenticated, but no institutional profile has been established for you in this organization."
                                : errorMessage || "An unexpected error occurred while retrieving your institutional profile."}
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-6 text-center pb-8">
                        <div className="bg-slate-50 dark:bg-slate-900 rounded-xl p-4 text-sm text-slate-600 dark:text-slate-400 text-left border border-slate-200/60 dark:border-slate-800">
                            <h4 className="font-semibold text-slate-900 dark:text-slate-200 mb-1">Provisioning Guidance</h4>
                            <p className="mb-2">
                                Institutional profiles are created and managed by school administration:
                            </p>
                            <ul className="list-disc list-inside space-y-1 text-slate-500 text-xs">
                                <li>Contact your institution administrator or admissions office to complete profile provisioning.</li>
                                <li>Verify that you are accessing the correct institution subdomain.</li>
                                <li>Profiles cannot be self-created directly from this client.</li>
                            </ul>
                        </div>

                        <div className="flex flex-col sm:flex-row gap-3 justify-center pt-2">
                            <Button
                                variant="outline"
                                onClick={() => logout()}
                                disabled={isLoggingOut}
                                className="gap-2"
                            >
                                <LogOut className="h-4 w-4" />
                                {isLoggingOut ? "Signing Out..." : "Sign Out / Switch Account"}
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            </div>
        );
    }

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setFormData({ ...formData, [e.target.id]: e.target.value });
    };

    const handleImageClick = () => {
        fileInputRef.current?.click();
    };

    const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            setSelectedImage(file);
            const previewUrl = URL.createObjectURL(file);
            setImagePreview(previewUrl);
        }
    };

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();

        const payload = new FormData();

        // Append all text fields
        Object.keys(formData).forEach(key => {
            const value = (formData as any)[key];
            if (value !== null && value !== undefined && key !== 'profile_image') {
                payload.append(key, value as string);
            }
        });

        // Append image if selected
        if (selectedImage) {
            payload.append("profile_image", selectedImage);
        }

        updateProfile(payload, {
            onSuccess: (data) => {
                toast.success("Profile updated successfully!");
                // Update local state with returned data (especially the new image URL)
                setFormData(data);
                setSelectedImage(null);
                setImagePreview(null);
            },
            onError: (err) => {
                toast.error("Failed to update profile.");
            }
        });
    };

    const role = user?.roles?.[0] || "member";
    const initials = `${formData.first_name?.[0] || user?.email?.[0] || 'U'}${formData.last_name?.[0] || ''}`.toUpperCase();

    return (
        <div className="space-y-8">
            {/* Header Section */}
            <div className="relative h-24 bg-gradient-to-r from-sky-600 via-sky-600 to-teal-600 rounded-xl overflow-hidden shadow-xl shadow-sky-500/10 animate-in fade-in slide-in-from-top-4 duration-700 mb-5 flex items-center gap-5 pl-5">
                <div className="absolute -top-10 -right-10 w-40 h-40 bg-white/10 rounded-full blur-2xl" />
                <div className="p-2 bg-white rounded-4xl shadow-2xl relative z-10 transition-transform duration-300 ease-out hover:scale-105 hover:-rotate-3">
                    <div className="relative group">
                        <User className="h-12 w-12 text-sky-600" />
                    </div>
                </div>

                <div className="hidden md:block text-white">
                    <div className="flex items-center gap-2 mb-1">
                        <h1 className="text-2xl font-bold">
                            {formData.first_name || formData.last_name
                                ? `${formData.first_name || ''} ${formData.last_name || ''}`.trim()
                                : 'New Member'}
                        </h1>
                        <BadgeCheck className="h-5 w-5 text-sky-200" />
                    </div>
                    <div className="flex items-center gap-4 text-sky-50/80 text-sm font-medium">
                        <span className="flex items-center gap-1.5 capitalize"><ShieldCheck className="h-3.5 w-3.5" /> {role}</span>
                        <div className="h-1 w-1 rounded-full bg-white/40" />
                        <span className="flex items-center gap-1.5"><Mail className="h-3.5 w-3.5" /> {profile?.email || 'No email provided'}</span>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 pt-4">
                {/* Left Column - Stats/Quick Info */}
                <div className="space-y-6">
                    <Card className="border-none shadow-xl shadow-slate-200/50 dark:shadow-none dark:bg-slate-900 overflow-hidden group pt-0">
                        <CardHeader className="pt-2">
                            <CardTitle className="text-lg">Personal Rank</CardTitle>
                            <CardDescription>Role and Designation</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-100 dark:border-slate-800 flex items-center gap-4 transition-all duration-300 ease-out hover:border-sky-200 dark:hover:border-sky-900 hover:bg-white dark:hover:bg-slate-800 hover:shadow-md hover:-translate-y-0.5">
                                <div className="p-3 bg-sky-100 dark:bg-sky-500/10 text-sky-600 rounded-xl">
                                    <Briefcase className="h-6 w-6" />
                                </div>
                                <div>
                                    <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">Designation</p>
                                    <p className="font-bold text-slate-700 dark:text-slate-200">
                                        {(formData as StaffProfile)?.designation || (role === 'student' ? 'Student' : 'Staff Member')}
                                    </p>
                                </div>
                            </div>

                            {((profile as StaffProfile)?.employee_id || (profile as StudentProfile)?.enrollment_id) && (
                                <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-100 dark:border-slate-800 flex items-center gap-4 transition-all duration-300 ease-out hover:border-sky-200 dark:hover:border-sky-900 hover:bg-white dark:hover:bg-slate-800 hover:shadow-md hover:-translate-y-0.5">
                                    <div className="p-3 bg-teal-100 dark:bg-teal-500/10 text-teal-600 rounded-xl">
                                        <BadgeCheck className="h-6 w-6" />
                                    </div>
                                    <div>
                                        <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">ID Reference</p>
                                        <p className="font-bold text-slate-700 dark:text-slate-200">
                                            {(profile as StaffProfile)?.employee_id || (profile as StudentProfile)?.enrollment_id}
                                        </p>
                                    </div>
                                </div>
                            )}

                            {role === 'student' && (
                                <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-100 dark:border-slate-800 flex items-center gap-4 transition-all duration-300 ease-out hover:border-sky-200 dark:hover:border-sky-900 hover:bg-white dark:hover:bg-slate-800 hover:shadow-md hover:-translate-y-0.5">
                                    <div className="p-3 bg-indigo-100 dark:bg-indigo-500/10 text-indigo-600 rounded-xl">
                                        <BookOpen className="h-6 w-6" />
                                    </div>
                                    <div>
                                        <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">Level</p>
                                        <p className="font-bold text-slate-700 dark:text-slate-200">{(formData as StudentProfile)?.current_level || 'Not Set'}</p>
                                    </div>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    <Card className="border-none shadow-xl shadow-slate-200/50 dark:shadow-none dark:bg-slate-900 overflow-hidden pt-0">
                        <CardHeader className="pt-2">
                            <CardTitle className="text-lg">Profile Picture</CardTitle>
                            <CardDescription>Visual identity of yourself</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            <div className="space-y-4">
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    className="hidden"
                                    accept="image/*"
                                    onChange={handleImageChange}
                                />
                                <div
                                    className="aspect-square bg-slate-50 dark:bg-slate-800 rounded-3xl border-2 border-dashed border-slate-200 dark:border-slate-700 flex flex-col items-center justify-center group relative cursor-pointer overflow-hidden transition-all duration-300 ease-out hover:border-sky-400 hover:bg-sky-50/50 dark:hover:bg-sky-500/5 hover:shadow-lg hover:shadow-sky-500/10"
                                    onClick={handleImageClick}
                                >
                                    {imagePreview || formData.profile_image ? (
                                        <img
                                            src={imagePreview || getMediaUrl(formData.profile_image) || ''}
                                            alt="Profile"
                                            className="w-full h-full object-cover"
                                        />
                                    ) : (
                                        <>
                                            <ImageIcon className="h-10 w-10 text-slate-300 mb-2 group-hover:scale-110 transition-transform" />
                                            <span className="text-xs font-bold text-slate-400">Click to upload</span>
                                        </>
                                    )}
                                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center backdrop-blur-[2px]">
                                        <Button variant="default" size="lg" className="font-bold pointer-events-none">Choose Image</Button>
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Right Column - Main Form */}
                <div className="lg:col-span-2 space-y-5">
                    <Card className="border-none shadow-xl shadow-slate-200/50 dark:shadow-none dark:bg-slate-900">
                        <CardHeader className="border-b border-slate-50 dark:border-slate-800 pb-0">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                                <div>
                                    <CardTitle className="text-2xl font-bold">Profile Details</CardTitle>
                                    <CardDescription>Manage your personal information and contact details</CardDescription>
                                </div>
                            </div>
                        </CardHeader>
                        <CardContent className="">
                            <form onSubmit={handleSubmit} className="space-y-5">
                                {/* Name Section */}
                                <div className="space-y-6">
                                    <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest">Full Identity</h3>
                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                        <FloatingLabelInput
                                            id="first_name"
                                            label="First Name"
                                            value={formData.first_name || ""}
                                            onChange={handleChange}
                                            required
                                        />
                                        <FloatingLabelInput
                                            id="middle_name"
                                            label="Middle Name (Optional)"
                                            value={formData.middle_name || ""}
                                            onChange={handleChange}
                                        />
                                        <FloatingLabelInput
                                            id="last_name"
                                            label="Last Name"
                                            value={formData.last_name || ""}
                                            onChange={handleChange}
                                            required
                                        />
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <div className="relative">
                                            <div className="relative">
                                                <Mail className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                                                <FloatingLabelInput
                                                    id="email"
                                                    label="Personal Email"
                                                    className="pl-12"
                                                    value={formData.email || ""}
                                                    onChange={handleChange}
                                                />
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Contact Section */}
                                <div className="space-y-6 pt-4 border-t border-slate-50 dark:border-slate-800">
                                    <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest">Communication</h3>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <div className="relative">
                                            <Phone className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                                            <FloatingLabelInput
                                                id="phone"
                                                label="Phone Number"
                                                className="pl-12"
                                                value={formData.phone || ""}
                                                onChange={handleChange}
                                            />
                                        </div>
                                        <div className="relative">
                                            <Calendar className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                                            <FloatingLabelInput
                                                id="date_of_birth"
                                                label="Date of Birth"
                                                type="date"
                                                className="pl-12"
                                                value={formData.date_of_birth || ""}
                                                onChange={handleChange}
                                            />
                                        </div>
                                    </div>
                                    <div className="relative">
                                        <MapPin className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                                        <FloatingLabelInput
                                            id="address"
                                            label="Current Address"
                                            className="pl-12"
                                            value={formData.address || ""}
                                            onChange={handleChange}
                                        />
                                    </div>
                                </div>

                                {/* Role-specific Section */}
                                {role === 'student' && (
                                    <div className="space-y-6 pt-4 border-t border-slate-50 dark:border-slate-800">
                                        <h3 className="text-sm font-bold text-slate-400 uppercase tracking-widest">Guardian details</h3>
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                            <FloatingLabelInput
                                                id="guardian_name"
                                                label="Guardian's Name"
                                                value={(formData as StudentProfile)?.guardian_name || ""}
                                                onChange={handleChange}
                                            />
                                            <FloatingLabelInput
                                                id="guardian_phone"
                                                label="Guardian's Phone"
                                                value={(formData as StudentProfile)?.guardian_phone || ""}
                                                onChange={handleChange}
                                            />
                                        </div>
                                    </div>
                                )}

                                <div className="flex justify-end pt-4">
                                    <Button
                                        type="submit"
                                        size="xxl"
                                        disabled={isUpdating}
                                    >
                                        {isUpdating ? (
                                            <>
                                                <Loader2 className="h-5 w-5 animate-spin mr-2" />
                                                Saving Changes...
                                            </>
                                        ) : (
                                            <>
                                                <Save className="h-5 w-5 mr-2" />
                                                Update Profile
                                            </>
                                        )}
                                    </Button>
                                </div>
                            </form>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
}
