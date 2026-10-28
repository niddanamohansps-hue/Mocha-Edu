import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import axiosInstance from "@/lib/axios";

type PushState = "unsupported" | "off-server" | "denied" | "off" | "on" | "loading";

function urlBase64ToUint8Array(base64: string) {
    const padding = "=".repeat((4 - (base64.length % 4)) % 4);
    const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
    return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

function supported() {
    return typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

/** Turns phone / browser notifications on or off for this device (free Web Push). */
export function usePushNotifications() {
    const [state, setState] = useState<PushState>("loading");
    const [busy, setBusy] = useState(false);

    const refresh = useCallback(async () => {
        if (!supported()) return setState("unsupported");
        try {
            const { data } = await axiosInstance.get<{ enabled: boolean; public_key: string }>("/notifications/push/key/");
            if (!data.enabled) return setState("off-server");
            if (Notification.permission === "denied") return setState("denied");
            const registration = await navigator.serviceWorker.getRegistration("/");
            const subscription = registration ? await registration.pushManager.getSubscription() : null;
            setState(subscription ? "on" : "off");
        } catch {
            setState("off");
        }
    }, []);

    useEffect(() => {
        void refresh();
    }, [refresh]);

    const turnOn = async () => {
        setBusy(true);
        try {
            const { data } = await axiosInstance.get<{ enabled: boolean; public_key: string }>("/notifications/push/key/");
            if (!data.enabled) throw new Error("Phone notifications are not set up on the server yet.");
            const permission = await Notification.requestPermission();
            if (permission !== "granted") {
                setState(permission === "denied" ? "denied" : "off");
                return;
            }
            const registration = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
            await navigator.serviceWorker.ready;
            const subscription = (await registration.pushManager.getSubscription())
                ?? (await registration.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: urlBase64ToUint8Array(data.public_key),
                }));
            await axiosInstance.post("/notifications/push/", subscription.toJSON());
            setState("on");
            toast.success("Notifications are on for this device.");
            await axiosInstance.post("/notifications/push/test/").catch(() => undefined);
        } catch (error) {
            toast.error(error instanceof Error ? error.message : "Could not turn on notifications.");
        } finally {
            setBusy(false);
        }
    };

    const turnOff = async () => {
        setBusy(true);
        try {
            const registration = await navigator.serviceWorker.getRegistration("/");
            const subscription = registration ? await registration.pushManager.getSubscription() : null;
            if (subscription) {
                await axiosInstance.delete("/notifications/push/", { data: { endpoint: subscription.endpoint } }).catch(() => undefined);
                await subscription.unsubscribe();
            }
            setState("off");
            toast.success("Notifications are off for this device.");
        } finally {
            setBusy(false);
        }
    };

    return { state, busy, turnOn, turnOff };
}
