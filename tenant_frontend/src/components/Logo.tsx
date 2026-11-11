import Image from "next/image";

/** EduSekai logo: the mark plus a live wordmark, so the text stays readable in dark mode. */
export default function Logo({ width, height }: { width: number; height: number }) {
    return (
        <span className="inline-flex items-center gap-2 select-none" style={{ height }} aria-label="EduSekai">
            <Image src="/assets/images/edusekai-mark.svg" alt="" width={height} height={height} unoptimized priority />
            <span
                className="font-extrabold tracking-tight leading-none"
                style={{ fontSize: Math.round(height * 0.62), maxWidth: width }}
                aria-hidden="true"
            >
                <span className="text-slate-900 dark:text-white">Edu</span>
                <span className="text-sky-600 dark:text-sky-400">Sekai</span>
            </span>
        </span>
    );
}
