/** Diagonal light sweep that plays across a button on hover. Parent needs `group relative overflow-hidden`. */
export function ShineOverlay() {
    return (
        <span className="pointer-events-none absolute inset-0 -translate-x-full skew-x-12 bg-gradient-to-r from-transparent via-white/30 to-transparent transition-transform duration-700 ease-out group-hover:translate-x-full" />
    );
}
