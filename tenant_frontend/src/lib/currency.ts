/** The currency symbol shown beside every amount of money. Change it here to change it everywhere. */
export const CURRENCY = "₹";

export interface FormatCurrencyOptions {
    compact?: boolean;
    showSymbol?: boolean;
    decimals?: number;
}

/**
 * Formats a numeric or string value according to Indian numbering system (Lakhs & Crores).
 * Example:
 *  formatIndianCurrency("11199871.37", { compact: true }) => "₹1.12 Cr"
 *  formatIndianCurrency("11199871.37") => "₹1,11,99,871.37"
 *  formatIndianCurrency(450000, { compact: true }) => "₹4.50 L"
 */
export function formatIndianCurrency(
    amount: number | string | null | undefined,
    options: FormatCurrencyOptions = {}
): string {
    const { compact = false, showSymbol = true, decimals } = options;

    if (amount === null || amount === undefined || amount === "") {
        return showSymbol ? `${CURRENCY}0` : "0";
    }

    const num = typeof amount === "string" ? parseFloat(amount) : amount;
    if (isNaN(num)) {
        return showSymbol ? `${CURRENCY}0` : "0";
    }

    const symbolPrefix = showSymbol ? `${CURRENCY}` : "";
    const isNegative = num < 0;
    const absVal = Math.abs(num);

    if (compact) {
        if (absVal >= 10000000) {
            // Crores (1 Cr = 1,00,00,000)
            const cr = absVal / 10000000;
            return `${isNegative ? "-" : ""}${symbolPrefix}${cr.toFixed(decimals ?? 2)} Cr`;
        }
        if (absVal >= 100000) {
            // Lakhs (1 L = 1,00,000)
            const lakh = absVal / 100000;
            return `${isNegative ? "-" : ""}${symbolPrefix}${lakh.toFixed(decimals ?? 2)} L`;
        }
        if (absVal >= 1000) {
            // Thousands (1 K = 1,000)
            const k = absVal / 1000;
            return `${isNegative ? "-" : ""}${symbolPrefix}${k.toFixed(decimals ?? 1)} K`;
        }
    }

    // Standard en-IN formatting
    const formatted = new Intl.NumberFormat("en-IN", {
        minimumFractionDigits: decimals !== undefined ? decimals : (absVal % 1 === 0 ? 0 : 2),
        maximumFractionDigits: decimals !== undefined ? decimals : 2,
    }).format(absVal);

    return `${isNegative ? "-" : ""}${symbolPrefix}${formatted}`;
}

/**
 * Formats a number with Indian comma grouping (e.g. 1,00,000)
 */
export function formatIndianNumber(num: number | string | null | undefined): string {
    if (num === null || num === undefined || num === "") return "0";
    const parsed = typeof num === "string" ? parseFloat(num) : num;
    if (isNaN(parsed)) return "0";
    return new Intl.NumberFormat("en-IN").format(parsed);
}
