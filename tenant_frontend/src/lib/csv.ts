/** Download rows as a CSV file the school can open in Excel. Values containing commas, quotes or line breaks are quoted. */
export function downloadCsv(filename: string, rows: (string | number | null | undefined)[][]) {
    const escape = (value: string | number | null | undefined) => {
        const text = value === null || value === undefined ? "" : String(value);
        return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
    };
    // The leading byte-order mark makes Excel read accented and Indian-language names correctly.
    const blob = new Blob(["\ufeff" + rows.map((row) => row.map(escape).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
}
