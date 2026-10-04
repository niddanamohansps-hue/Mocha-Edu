"use client";

import { useParams, useRouter } from "next/navigation";
import { useInstructor, useDeleteInstructor } from "@/hooks/useStaff";
import { usePermissions } from "@/providers/PermissionProvider";
import Unauthorized from "@/components/Unauthorized";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { User, BookOpen, ChevronLeft, Trash2, Mail, Phone, MapPin, Calendar, Award } from "lucide-react";
import TeachingAssignmentsTab from "@/components/dashboard/instructors/TeachingAssignmentsTab";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function InstructorDetailPage() {
    const params = useParams();
    const router = useRouter();
    const id = params?.id as string;
    const { can } = usePermissions();
    const { data: instructor, isLoading, error } = useInstructor(id);
    const { mutate: deleteInstructor, isPending: isDeleting } = useDeleteInstructor();

    const [showDeleteDialog, setShowDeleteDialog] = useState(false);

    if (isLoading) {
        return <div className="p-8 text-center text-slate-500 text-premium">Loading profile...</div>;
    }

    if (error) {
        return (
            <div className="p-8 text-center text-red-500">
                <h3 className="text-lg font-bold">Error loading instructor</h3>
                <p className="text-sm">{(error as any)?.response?.data?.detail || error.message || "Unknown error"}</p>
            </div>
        );
    }

    if (!instructor) {
        return <div className="p-8 text-center text-red-500">Instructor not found (ID: {id})</div>;
    }

    const canView = can("view_staff");
    const canDelete = can("delete_staff");

    if (!canView) return <Unauthorized />;

    const details = instructor.staff_member.profile_details;
    const fullName = `${details.first_name} ${details.middle_name ? details.middle_name + " " : ""}${details.last_name}`;

    const handleDelete = () => {
        deleteInstructor(instructor.id, {
            onSuccess: () => {
                router.push("/dashboard/instructors");
            }
        });
    };

    return (
        <div className="space-y-6">
            {/* Header Area */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => router.back()}
                        className="rounded-full hover:bg-slate-100"
                    >
                        <ChevronLeft className="h-5 w-5" />
                    </Button>
                    <div>
                        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">
                            {fullName}
                        </h1>
                        <p className="text-muted-foreground flex items-center gap-2 font-medium">
                            <Award className="h-4 w-4 text-indigo-500" />
                            {instructor.staff_member.designation} • {instructor.specialization}
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {canDelete && (
                        <Button
                            variant="destructive"
                            className="gap-2 bg-red-500 hover:bg-red-600"
                            onClick={() => setShowDeleteDialog(true)}
                        >
                            <Trash2 className="h-4 w-4" />
                            Delete Instructor
                        </Button>
                    )}
                </div>
            </div>

            {/* Quick Stats/ID Bar */}
            <div className="flex flex-wrap gap-4 p-4 bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl">
                <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Employee ID:</span>
                    <span className="text-sm font-semibold">{instructor.staff_member.employee_id}</span>
                </div>
                <div className="h-4 w-px bg-slate-300 hidden md:block" />
                <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Status:</span>
                    <span className="text-xs px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full font-bold">Active</span>
                </div>
            </div>

            <Tabs defaultValue="assignments" className="space-y-6">
                <TabsList className="bg-slate-100 dark:bg-slate-800 p-1 rounded-xl">
                    <TabsTrigger value="assignments" className="gap-2 rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm">
                        <BookOpen className="h-4 w-4" />
                        Teaching Assignments
                    </TabsTrigger>
                    <TabsTrigger value="profile" className="gap-2 rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm">
                        <User className="h-4 w-4" />
                        Profile Details
                    </TabsTrigger>
                </TabsList>

                <TabsContent value="profile" className="space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Personal Card */}
                        <Card className="border-none shadow-sm bg-white dark:bg-slate-950">
                            <CardHeader>
                                <CardTitle className="text-lg flex items-center gap-2 text-indigo-600">
                                    <User className="h-5 w-5" />
                                    Personal Information
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-1">
                                        <Label className="text-slate-400 text-xs uppercase">Gender</Label>
                                        <p className="font-medium capitalize">{details.gender}</p>
                                    </div>
                                    <div className="space-y-1">
                                        <Label className="text-slate-400 text-xs uppercase">Date of Birth</Label>
                                        <p className="font-medium flex items-center gap-2">
                                            <Calendar className="h-4 w-4 text-slate-400" />
                                            {details.date_of_birth || "N/A"}
                                        </p>
                                    </div>
                                </div>
                                <div className="space-y-1">
                                    <Label className="text-slate-400 text-xs uppercase">Email Address</Label>
                                    <p className="font-medium flex items-center gap-2">
                                        <Mail className="h-4 w-4 text-slate-400" />
                                        {details.email || "No email provided"}
                                    </p>
                                </div>
                                <div className="space-y-1">
                                    <Label className="text-slate-400 text-xs uppercase">Contact Number</Label>
                                    <p className="font-medium flex items-center gap-2">
                                        <Phone className="h-4 w-4 text-slate-400" />
                                        {details.phone || "No phone provided"}
                                    </p>
                                </div>
                                <div className="space-y-1">
                                    <Label className="text-slate-400 text-xs uppercase">Address</Label>
                                    <p className="font-medium flex items-center gap-2">
                                        <MapPin className="h-4 w-4 text-slate-400" />
                                        {details.address || "No address provided"}
                                    </p>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Professional Card */}
                        <Card className="border-none shadow-sm bg-white dark:bg-slate-950">
                            <CardHeader>
                                <CardTitle className="text-lg flex items-center gap-2 text-sky-600">
                                    <Award className="h-5 w-5" />
                                    Professional Profile
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="space-y-1">
                                    <Label className="text-slate-400 text-xs uppercase">Specialization</Label>
                                    <p className="font-medium">{instructor.specialization}</p>
                                </div>
                                <div className="space-y-1">
                                    <Label className="text-slate-400 text-xs uppercase">Qualification</Label>
                                    <p className="font-medium">{instructor.staff_member.qualification || "N/A"}</p>
                                </div>
                                <div className="space-y-1">
                                    <Label className="text-slate-400 text-xs uppercase">Experience</Label>
                                    <p className="font-medium">{instructor.staff_member.experience_years} Years</p>
                                </div>
                                <div className="space-y-1 pt-2">
                                    <Label className="text-slate-400 text-xs uppercase">Bio</Label>
                                    <p className="text-slate-600 dark:text-slate-400 italic text-sm leading-relaxed">
                                        {instructor.bio || "No biography provided."}
                                    </p>
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    <div className="p-4 bg-amber-50 dark:bg-amber-950/20 text-amber-700 dark:text-amber-400 rounded-xl border border-amber-100 dark:border-amber-900/50 text-sm font-medium">
                        Looking to edit this profile? Personal details and employment data are managed in the Global Staff Directory.
                    </div>
                </TabsContent>

                <TabsContent value="assignments" className="space-y-4">
                    <TeachingAssignmentsTab instructorId={instructor.id} />
                </TabsContent>
            </Tabs>

            {/* Delete Confirmation Dialog */}
            <ConfirmationDialog
                open={showDeleteDialog}
                onOpenChange={setShowDeleteDialog}
                title={<span className="text-xl font-bold">Resign/Delete Instructor?</span>}
                description={
                    <span className="text-base text-slate-600">
                        Are you absolutely sure you want to remove <span className="font-bold text-slate-900">{fullName}</span> from the faculty list?
                        This will also remove all their active teaching assignments.
                    </span>
                }
                cancelLabel="Go Back"
                confirmLabel={isDeleting ? "Processing..." : "Confirm Deletion"}
                onConfirm={handleDelete}
                footerClassName="gap-2 sm:gap-0"
                cancelClassName="rounded-lg"
                confirmClassName="rounded-lg shadow-lg shadow-red-500/20"
            />
        </div>
    );
}
