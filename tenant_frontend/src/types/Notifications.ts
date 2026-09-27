export interface Notification {
    id: string;
    title: string;
    body: string;
    category: string;
    link: string;
    is_read: boolean;
    read_at: string | null;
    created_at: string;
}

export interface NotificationListResponse {
    count: number;
    next: string | null;
    previous: string | null;
    results: Notification[];
}

export interface UnreadCountResponse {
    unread_count: number;
}

export type MarkReadResponse = Notification;

export interface MarkAllReadResponse {
    updated_count: number;
}
