"use client";

import React, { createContext, useContext, useEffect, useState, useMemo, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAcademicYears } from "@/hooks/useAcademics";
import { usePermissions } from "@/providers/PermissionProvider";
import { AcademicYear } from "@/types/Academics";

interface AcademicYearContextType {
    selectedYear: AcademicYear | null;
    currentYear: AcademicYear | null;
    academicYears: AcademicYear[];
    setSelectedYear: (year: AcademicYear | null) => void;
    selectYearById: (id: string) => void;
    isLoading: boolean;
    isError: boolean;
    hasAccess: boolean;
}

const AcademicYearContext = createContext<AcademicYearContextType | undefined>(undefined);

function getStorageKey(): string {
    if (typeof window === "undefined") return "edusekai_academic_year";
    return `edusekai_academic_year_${window.location.hostname}`;
}

export function AcademicYearProvider({ children }: { children: React.ReactNode }) {
    const queryClient = useQueryClient();
    // Parents and students cannot list academic years; don't ask (the server would answer 403).
    const { can } = usePermissions();
    const canListYears = can("view_academic_level");
    const { data: years = [], isLoading: loadingYears, isError, error } = useAcademicYears(canListYears);
    const isLoading = canListYears && loadingYears;
    const [selectedYear, setSelectedYearState] = useState<AcademicYear | null>(null);
    const [isInitialized, setIsInitialized] = useState(false);

    // Identify current active year from API records
    const currentYear = useMemo(() => {
        return years.find((y) => y.is_current) || null;
    }, [years]);

    // Handle selection and persistence
    const setSelectedYear = useCallback((year: AcademicYear | null) => {
        setSelectedYearState(year);
        try {
            const key = getStorageKey();
            if (year) {
                localStorage.setItem(key, year.id);
            } else {
                localStorage.removeItem(key);
            }
        } catch {
            // Ignore localStorage errors (private mode, quota, etc.)
        }

        // Invalidate dependent query caches so records from different years are never mixed
        queryClient.invalidateQueries({ queryKey: ["examinations"] });
        queryClient.invalidateQueries({ queryKey: ["fees"] });
        queryClient.invalidateQueries({ queryKey: ["timetable"] });
        queryClient.invalidateQueries({ queryKey: ["attendance"] });
        queryClient.invalidateQueries({ queryKey: ["promotion"] });
        queryClient.invalidateQueries({ queryKey: ["students"] });
        queryClient.invalidateQueries({ queryKey: ["parent-portal"] });
        queryClient.invalidateQueries({ queryKey: ["dashboard"] });
        queryClient.invalidateQueries({ queryKey: ["course-content"] });
        queryClient.invalidateQueries({ queryKey: ["calendar-events"] });
        queryClient.invalidateQueries({ queryKey: ["calendar-holidays"] });
        queryClient.invalidateQueries({ queryKey: ["upcoming-events"] });
    }, [queryClient]);

    const selectYearById = useCallback((id: string) => {
        const found = years.find((y) => y.id === id);
        if (found) {
            setSelectedYear(found);
        }
    }, [years, setSelectedYear]);

    // Sync on initial load or when years change
    useEffect(() => {
        if (isLoading) return;

        if (isError || !years || years.length === 0) {
            setSelectedYearState(null);
            setIsInitialized(true);
            return;
        }

        let savedId: string | null = null;
        try {
            savedId = localStorage.getItem(getStorageKey());
        } catch {
            savedId = null;
        }

        // If savedId exists and is valid in current list
        const matched = savedId ? years.find((y) => y.id === savedId || y.name === savedId) : null;

        if (matched) {
            setSelectedYearState(matched);
        } else if (currentYear) {
            setSelectedYearState(currentYear);
            try {
                localStorage.setItem(getStorageKey(), currentYear.id);
            } catch {}
        } else {
            // Fallback to first available year
            setSelectedYearState(years[0]);
            try {
                localStorage.setItem(getStorageKey(), years[0].id);
            } catch {}
        }

        setIsInitialized(true);
    }, [years, isLoading, isError, currentYear]);

    const hasAccess = canListYears && (!isError || (error as any)?.response?.status !== 403);

    return (
        <AcademicYearContext.Provider
            value={{
                selectedYear,
                currentYear,
                academicYears: years,
                setSelectedYear,
                selectYearById,
                isLoading: isLoading || !isInitialized,
                isError,
                hasAccess,
            }}
        >
            {children}
        </AcademicYearContext.Provider>
    );
}

export function useAcademicYear() {
    const context = useContext(AcademicYearContext);
    if (context === undefined) {
        throw new Error("useAcademicYear must be used within an AcademicYearProvider");
    }
    return context;
}

