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

export interface NotificationSettings {
    fee_reminders_enabled: boolean;
    absence_alerts_enabled: boolean;
    payment_receipts_enabled: boolean;
    low_stock_alerts_enabled: boolean;
    fee_reminder_days_before: number;
    overdue_reminder_interval_days: number;
    max_overdue_reminders: number;
}

export type AlertKind = "fee_due_soon" | "fee_overdue" | "absence" | "payment_receipt";

export type AlertDeliveryStatus = "pending" | "retrying" | "sent" | "failed" | "in_app_only";

export interface AlertLogItem {
    id: string;
    kind: AlertKind | string;
    created_at: string;
    delivery_status: AlertDeliveryStatus | string;
    enrollment_id: string;
    recipient: string;
}

export interface AlertLogFilters {
    kind?: string;
    created_after?: string;
    created_before?: string;
    enrollment_id?: string;
    page?: number;
    pageSize?: number;
}
