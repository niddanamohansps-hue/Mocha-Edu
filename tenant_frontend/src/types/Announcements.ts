export type AnnouncementStatus = "draft" | "scheduled" | "published" | "archived";

export type AudienceType = "all" | "all_staff" | "all_parents" | "all_students" | "section" | "level";

export interface Announcement {
    id: string;
    title: string;
    body: string;
    audience_type: AudienceType;
    audience_section: string | null;
    audience_level: string | null;
    send_email: boolean;
    status: AnnouncementStatus;
    scheduled_at: string | null;
    published_at: string | null;
    created_by_user_id: string;
    recipient_count: number;
    created_at: string;
    updated_at: string;
}

export interface AnnouncementInput {
    title: string;
    body: string;
    audience_type: AudienceType;
    audience_section: string | null;
    audience_level: string | null;
    send_email: boolean;
}

// What a recipient sees from /announcements/mine/ - no audience or admin data.
export interface MyAnnouncement {
    id: string;
    title: string;
    body: string;
    published_at: string;
}

export interface AnnouncementRecipient {
    user_id: string;
    email_sent: boolean;
    created_at: string;
}

export interface AnnouncementFilters {
    page: number;
    status: AnnouncementStatus | "";
    audience_type: AudienceType | "";
    search: string;
}

export const AUDIENCE_LABELS: Record<AudienceType, string> = {
    all: "Everyone",
    all_staff: "All staff",
    all_parents: "All parents",
    all_students: "All students",
    section: "A section",
    level: "A level",
};

export const STATUS_LABELS: Record<AnnouncementStatus, string> = {
    draft: "Draft",
    scheduled: "Scheduled",
    published: "Published",
    archived: "Archived",
};
