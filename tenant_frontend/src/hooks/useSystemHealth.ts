import { useQuery } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { SystemHealth } from "@/types/SystemHealth";

/** Refreshes every 30 seconds while the page is open (paused when the tab is hidden). */
export const useSystemHealth = () =>
    useQuery({
        queryKey: ["system-health"],
        queryFn: async () => (await axiosInstance.get("/system-health/")).data as SystemHealth,
        refetchInterval: 30_000,
        refetchIntervalInBackground: false,
    });
