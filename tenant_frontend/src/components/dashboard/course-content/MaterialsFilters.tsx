import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

interface MaterialsFiltersProps {
    searchQuery: string;
    onSearchChange: (query: string) => void;
    contentTypeFilter: string;
    onContentTypeChange: (type: string) => void;
}

export function MaterialsFilters({
    searchQuery,
    onSearchChange,
    contentTypeFilter,
    onContentTypeChange
}: MaterialsFiltersProps) {
    return (
        <div className="flex flex-col md:flex-row gap-4 items-center justify-between p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm">
            <div className="relative flex-1 w-full max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <Input aria-label="Search materials..."
                    placeholder="Search materials..."
                    value={searchQuery}
                    onChange={(e) => onSearchChange(e.target.value)}
                    className="pl-10 h-10 rounded-xl border-slate-100 dark:border-slate-800"
                />
            </div>
            <Select value={contentTypeFilter} onValueChange={onContentTypeChange}>
                <SelectTrigger className="w-full md:w-[200px] h-10 rounded-xl">
                    <SelectValue placeholder="All Types" />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="note">Notes</SelectItem>
                    <SelectItem value="document">Documents</SelectItem>
                    <SelectItem value="video">Videos</SelectItem>
                    <SelectItem value="link">Links</SelectItem>
                </SelectContent>
            </Select>
        </div>
    );
}
