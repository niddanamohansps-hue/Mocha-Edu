import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    FileText,
    Download,
    ExternalLink,
    Pin,
    Calendar,
    User,
    Loader2
} from "lucide-react";
import { contentTypeIcons, contentTypeColors } from "./constants";
import { downloadCourseContentFile } from "@/hooks/useCourseContent";

interface MaterialItem {
    id: string;
    title: string;
    description: string;
    content_type: "note" | "document" | "video" | "link" | "assignment";
    content_type_display: string;
    created_by_name: string;
    created_at: string;
    file?: string | null;
    external_url?: string;
    file_size?: number | null;
    is_pinned: boolean;
}

interface MaterialCardProps {
    material: MaterialItem;
}

function formatFileSize(bytes: number | null) {
    if (!bytes) return null;
    const mb = bytes / (1024 * 1024);
    return mb < 1 ? `${(bytes / 1024).toFixed(0)}KB` : `${mb.toFixed(2)}MB`;
}

export function MaterialCard({ material }: MaterialCardProps) {
    const [isDownloading, setIsDownloading] = useState(false);
    const Icon = contentTypeIcons[material.content_type] || FileText;
    const colorClass = contentTypeColors[material.content_type] || contentTypeColors.note;

    return (
        <Card className="p-5 hover:shadow-md transition-shadow relative">
            {material.is_pinned && (
                <div className="absolute top-4 right-4">
                    <Pin className="h-4 w-4 text-amber-500 fill-amber-500" />
                </div>
            )}

            <div className="flex items-start gap-3 mb-3">
                <div className={`h-10 w-10 rounded-lg ${colorClass} flex items-center justify-center flex-shrink-0`}>
                    <Icon className="h-5 w-5" />
                </div>
                <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-slate-900 dark:text-white truncate">
                        {material.title}
                    </h3>
                    <p className="text-xs text-slate-500 flex items-center gap-1 mt-1">
                        <User className="h-3 w-3" />
                        {material.created_by_name}
                    </p>
                </div>
            </div>

            <p className="text-sm text-slate-600 dark:text-slate-400 line-clamp-2 mb-4">
                {material.description}
            </p>

            <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-xs">
                        {material.content_type_display}
                    </Badge>
                    {material.file_size && (
                        <span className="text-xs text-slate-500">
                            {formatFileSize(material.file_size)}
                        </span>
                    )}
                </div>

                {material.file ? (
                    <Button
                        size="sm"
                        variant="outline"
                        className="h-8 gap-2"
                        disabled={isDownloading}
                        onClick={async () => {
                            setIsDownloading(true);
                            try {
                                await downloadCourseContentFile(material.id, material.title);
                            } finally {
                                setIsDownloading(false);
                            }
                        }}
                    >
                        {isDownloading ? (
                            <>
                                <Loader2 className="h-3 w-3 animate-spin" />
                                Downloading...
                            </>
                        ) : (
                            <>
                                <Download className="h-3 w-3" />
                                Download
                            </>
                        )}
                    </Button>
                ) : material.external_url ? (
                    <Button
                        size="sm"
                        variant="outline"
                        className="h-8 gap-2"
                        onClick={() => window.open(material.external_url, '_blank')}
                    >
                        <ExternalLink className="h-3 w-3" />
                        Open
                    </Button>
                ) : null}
            </div>

            <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800">
                <div className="flex items-center gap-1 text-xs text-slate-400">
                    <Calendar className="h-3 w-3" />
                    {new Date(material.created_at).toLocaleDateString()}
                </div>
            </div>
        </Card>
    );
}
