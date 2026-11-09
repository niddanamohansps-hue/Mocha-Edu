"use client";

import { useState, useEffect, useCallback } from "react";

export interface FavoriteItem {
    label: string;
    href: string;
    parent?: string;
}

export function useFavorites(userId?: string | number | null) {
    const storageKey = `school_sansar_favs_${userId || "global"}`;

    const [favorites, setFavorites] = useState<FavoriteItem[]>([]);
    const [isInitialized, setIsInitialized] = useState(false);

    useEffect(() => {
        if (typeof window === "undefined") return;
        try {
            const raw = localStorage.getItem(storageKey);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (Array.isArray(parsed)) {
                    setFavorites(parsed);
                    setIsInitialized(true);
                    return;
                }
            }
            // Initial sensible defaults
            const defaults: FavoriteItem[] = [
                { label: "Dashboard", href: "/dashboard" },
                { label: "Student Directory", href: "/dashboard/students", parent: "Student Management" },
                { label: "Fee Collection", href: "/dashboard/fees/collect", parent: "Fees" },
                { label: "Mark Attendance", href: "/dashboard/attendance/mark", parent: "Attendance" },
            ];
            setFavorites(defaults);
            localStorage.setItem(storageKey, JSON.stringify(defaults));
        } catch {
            setFavorites([]);
        } finally {
            setIsInitialized(true);
        }
    }, [storageKey]);

    const isFavorite = useCallback((href: string) => {
        return favorites.some((f) => f.href === href);
    }, [favorites]);

    const toggleFavorite = useCallback((item: FavoriteItem) => {
        setFavorites((prev) => {
            const exists = prev.some((f) => f.href === item.href);
            const next = exists
                ? prev.filter((f) => f.href !== item.href)
                : [...prev, item];
            if (typeof window !== "undefined") {
                try {
                    localStorage.setItem(storageKey, JSON.stringify(next));
                } catch (e) {
                    console.error("Failed to persist favorites", e);
                }
            }
            return next;
        });
    }, [storageKey]);

    return {
        favorites,
        isFavorite,
        toggleFavorite,
        isInitialized,
    };
}
