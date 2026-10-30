import { ParentPortalNav } from "@/components/parent-portal/ParentPortalNav";

export const metadata = {
    title: "Parent Portal | School Sansar ERP",
    description: "Parent portal command center for attendance, online fees, report cards, timetable, and parent-teacher meetings.",
};

export default function ParentPortalLayout({ children }: { children: React.ReactNode }) {
    return (
        <div className="max-w-7xl mx-auto space-y-6 pb-12 animate-in fade-in duration-500">
            <ParentPortalNav />
            {children}
        </div>
    );
}
