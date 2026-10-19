export interface AuditLogItem {
    id: string;
    actor_id: string | null;
    actor_username: string | null;
    action: string;
    model_name: string;
    object_id: string | null;
    changes: Record<string, any> | null;
    ip_address: string | null;
    user_agent: string | null;
    created_at: string;
}

export interface AuditLogFilters {
    page: number;
    page_size?: number;
    search?: string;
    actor_username?: string;
    action?: string;
    model_name?: string;
    object_id?: string;
    date_from?: string;
    date_to?: string;
    ordering?: string;
}

export interface AuditLogMetadata {
    actions: string[];
    model_names: string[];
}

