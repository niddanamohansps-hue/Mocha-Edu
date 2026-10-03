"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { GraduationCap, Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ShineOverlay } from "@/components/ShineOverlay";

const NAV_LINKS = [
    { href: "#features", label: "Features" },
    { href: "#how-it-works", label: "How it Works" },
    { href: "#testimonials", label: "Testimonials" },
    { href: "#pricing", label: "Pricing" },
];

export function Header() {
    const [scrolled, setScrolled] = useState(false);
    const [mobileOpen, setMobileOpen] = useState(false);

    useEffect(() => {
        const onScroll = () => setScrolled(window.scrollY > 8);
        onScroll();
        window.addEventListener("scroll", onScroll, { passive: true });
        return () => window.removeEventListener("scroll", onScroll);
    }, []);

    return (
        <header
            className={`px-4 lg:px-6 h-16 flex items-center sticky top-0 z-50 bg-white/85 backdrop-blur-md transition-all duration-300 border-b ${scrolled ? "shadow-md border-slate-200/70" : "border-blue-100/60"
                }`}
        >
            <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-blue-500/40 via-teal-500/40 to-green-500/40" />

            <Link className="flex items-center justify-center gap-2 group" href="#">
                <span className="p-1.5 rounded-lg bg-gradient-to-br from-blue-500 to-teal-500 shadow-sm shadow-blue-500/30 transition-transform duration-300 group-hover:-rotate-12 group-hover:scale-110">
                    <GraduationCap className="h-5 w-5 text-white" />
                </span>
                <span className="font-bold text-2xl bg-gradient-to-r from-blue-600 to-teal-600 bg-clip-text text-transparent">
                    Edu Sekai
                </span>
            </Link>

            <nav className="ml-auto hidden md:flex items-center gap-6">
                {NAV_LINKS.map((link) => (
                    <Link
                        key={link.href}
                        className="relative text-sm font-medium text-slate-700 hover:text-blue-600 transition-colors after:absolute after:left-0 after:-bottom-1 after:h-0.5 after:w-0 after:bg-gradient-to-r after:from-blue-600 after:to-teal-600 after:transition-all after:duration-300 hover:after:w-full"
                        href={link.href}
                    >
                        {link.label}
                    </Link>
                ))}
                <Link href="/get-started">
                    <Button className="group relative overflow-hidden bg-gradient-to-r from-blue-600 to-teal-600 hover:from-blue-700 hover:to-teal-700 shadow-md shadow-blue-600/20 hover:shadow-lg hover:shadow-blue-600/40 hover:scale-105 active:scale-100 transition-all duration-300 ease-out">
                        <ShineOverlay />
                        <span className="relative">Get Started</span>
                    </Button>
                </Link>
            </nav>

            <button
                className="ml-auto md:hidden p-2 text-slate-700 hover:text-blue-600 transition-colors"
                onClick={() => setMobileOpen((open) => !open)}
                aria-label="Toggle menu"
            >
                {mobileOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </button>

            {mobileOpen && (
                <nav className="absolute top-16 left-0 right-0 bg-white border-b border-slate-200 shadow-lg flex flex-col p-4 gap-4 md:hidden animate-in fade-in slide-in-from-top-4 duration-200">
                    {NAV_LINKS.map((link) => (
                        <Link
                            key={link.href}
                            className="text-sm font-medium text-slate-700 hover:text-blue-600 transition-colors"
                            href={link.href}
                            onClick={() => setMobileOpen(false)}
                        >
                            {link.label}
                        </Link>
                    ))}
                    <Link href="/get-started" onClick={() => setMobileOpen(false)}>
                        <Button className="w-full bg-gradient-to-r from-blue-600 to-teal-600 hover:from-blue-700 hover:to-teal-700">
                            Get Started
                        </Button>
                    </Link>
                </nav>
            )}
        </header>
    );
}
