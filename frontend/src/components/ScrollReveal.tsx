"use client";

import { useEffect, useRef, useState } from "react";

export function ScrollReveal({
    children,
    delay = 0,
    className = "",
}: {
    children: React.ReactNode;
    delay?: number;
    className?: string;
}) {
    const ref = useRef<HTMLDivElement>(null);
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        const node = ref.current;
        if (!node) return;

        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting) {
                    setVisible(true);
                    observer.disconnect();
                }
            },
            { threshold: 0.15, rootMargin: "0px 0px -40px 0px" }
        );

        observer.observe(node);
        return () => observer.disconnect();
    }, []);

    return (
        <div
            ref={ref}
            style={{ transitionDelay: visible ? `${delay}ms` : "0ms" }}
            className={`transition-all duration-700 ease-out will-change-transform ${visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
                } ${className}`}
        >
            {children}
        </div>
    );
}
