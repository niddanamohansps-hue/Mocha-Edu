"use client";

import Link from "next/link";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { UserPlus, ArrowRight } from "lucide-react";
import { useInstructors } from "@/hooks/useStaff";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/ui/pagination";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

const PAGE_SIZE = 20;

export default function FacultyDirectoryPage() {
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const pageParam = Number(searchParams.get("page"));
    const page = Number.isInteger(pageParam) && pageParam >= 1 ? pageParam : 1;
    const { data, isLoading, isError, refetch } = useInstructors({ page, pageSize: PAGE_SIZE });
    const instructors = data?.results;

    const handlePageChange = (nextPage: number) => {
        const params = new URLSearchParams(searchParams.toString());
        if (nextPage <= 1) {
            params.delete("page");
        } else {
            params.set("page", String(nextPage));
        }
        const query = params.toString();
        router.replace(query ? `${pathname}?${query}` : pathname);
    };

    if (isError) {
        return <ErrorState onRetry={refetch} className="m-6" />;
    }

    return (
        <div className="space-y-6">
            <div className="flex flex-wrap justify-between gap-2 items-center">
                <div>
                    <h1 className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
                        Faculty Directory
                    </h1>
                    <p className="text-lg text-slate-600 dark:text-slate-400 mt-2">
                        Manage your teaching staff and instructors
                    </p>
                </div>
            </div>

            <div className="bg-white dark:bg-slate-950 rounded-lg border border-slate-200 dark:border-slate-800 overflow-hidden">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Name</TableHead>
                            <TableHead>Designation</TableHead>
                            <TableHead>Employee ID</TableHead>
                            <TableHead>Specialization</TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {isLoading && (
                            <TableRow>
                                <TableCell colSpan={5} className="text-center py-8">
                                    <LoadingState size="sm" message="Loading faculty..." />
                                </TableCell>
                            </TableRow>
                        )}
                        {!isLoading && instructors?.map((instructor) => (
                            <TableRow key={instructor.id}>
                                <TableCell className="font-medium">
                                    {instructor.staff_member.profile_details.first_name} {instructor.staff_member.profile_details.last_name}
                                </TableCell>
                                <TableCell>{instructor.staff_member.designation}</TableCell>
                                <TableCell>{instructor.staff_member.employee_id}</TableCell>
                                <TableCell>{instructor.specialization}</TableCell>
                                <TableCell className="text-right">
                                    <Link href={`/dashboard/instructors/${instructor.id}`}>
                                        <Button variant="ghost" size="sm" className="gap-2">
                                            View Profile
                                            <ArrowRight className="h-4 w-4" />
                                        </Button>
                                    </Link>
                                </TableCell>
                            </TableRow>
                        ))}
                        {!isLoading && (!instructors || instructors.length === 0) && (
                            <TableRow>
                                <TableCell colSpan={5} className="text-center py-8">
                                    <EmptyState
                                        title="No instructors found. Recruit some!"
                                        className="text-muted-foreground py-0"
                                    />
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
                {data && (
                    <Pagination
                        page={page}
                        pageSize={PAGE_SIZE}
                        count={data.count}
                        onPageChange={handlePageChange}
                        className="border-t border-slate-200 dark:border-slate-800"
                    />
                )}
            </div>
        </div>
    );
}
