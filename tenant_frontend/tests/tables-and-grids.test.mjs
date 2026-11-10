import { describe, it } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const TABLE_PATH = path.resolve(import.meta.dirname, "../src/components/ui/table.tsx");
const TABLE_SHELL_PATH = path.resolve(import.meta.dirname, "../src/components/common/table/TableShell.tsx");
const PAGINATION_PATH = path.resolve(import.meta.dirname, "../src/components/ui/pagination.tsx");
const FILTER_BAR_PATH = path.resolve(import.meta.dirname, "../src/components/common/table/FilterBar.tsx");

const AUDIT_LOGS_PAGE_PATH = path.resolve(import.meta.dirname, "../src/app/dashboard/audit-logs/page.tsx");
const CERTIFICATES_PAGE_PATH = path.resolve(import.meta.dirname, "../src/app/dashboard/certificates/page.tsx");
const EXPENSES_PAGE_PATH = path.resolve(import.meta.dirname, "../src/app/dashboard/expenses/page.tsx");
const FEES_COLLECTION_PAGE_PATH = path.resolve(import.meta.dirname, "../src/app/dashboard/fees/collection/page.tsx");
const FEES_DUES_PAGE_PATH = path.resolve(import.meta.dirname, "../src/app/dashboard/fees/dues/page.tsx");
const INVENTORY_PAGE_PATH = path.resolve(import.meta.dirname, "../src/app/dashboard/inventory/page.tsx");
const LIBRARY_PAGE_PATH = path.resolve(import.meta.dirname, "../src/app/dashboard/library/page.tsx");
const PAYROLL_PAGE_PATH = path.resolve(import.meta.dirname, "../src/app/dashboard/payroll/page.tsx");
const TRANSPORT_FLEET_PAGE_PATH = path.resolve(import.meta.dirname, "../src/app/dashboard/transport/fleet/page.tsx");

describe("Phase 4: Tables, Data Grids & Responsive Refinement Tests", () => {
    describe("1. Shared Table Primitives (components/ui/table.tsx)", () => {
        const tableContent = fs.readFileSync(TABLE_PATH, "utf8");

        it("exports core table components and specialized cell variants", () => {
            const exports = [
                "Table",
                "TableHeader",
                "TableBody",
                "TableFooter",
                "TableHead",
                "TableRow",
                "TableCell",
                "TableCaption",
                "TableHeadNumeric",
                "TableCellNumeric",
                "TableCellDate",
                "TableCellAction",
            ];
            for (const exp of exports) {
                assert.match(tableContent, new RegExp(`\\b${exp}\\b`), `Must define and export ${exp}`);
            }
            assert.match(tableContent, /export\s*\{[^}]*Table[^}]*\}/s);
        });

        it("enforces canonical 40px (h-10) header height and standard uppercase tracking", () => {
            assert.match(tableContent, /h-10/, "TableHead must use standardized h-10 height");
            assert.match(tableContent, /text-\[11\.5px\]/, "TableHead must use standardized 11.5px font size");
            assert.match(tableContent, /uppercase tracking-wider/, "TableHead must use uppercase tracking-wider");
            assert.match(tableContent, /text-slate-500/, "TableHead must use semantic slate-500 text token");
        });

        it("supports opt-in zebra striping on TableBody via striped prop", () => {
            assert.match(tableContent, /striped\?: boolean/, "TableBody must accept optional striped boolean");
            assert.match(tableContent, /\[&>tr:nth-child\(even\)\]:bg-slate-50\/50/, "Striped body must color even rows in light mode");
            assert.match(tableContent, /dark:\[&>tr:nth-child\(even\)\]:bg-slate-800\/25/, "Striped body must color even rows in dark mode");
        });

        it("enforces right-alignment and tabular-nums for numeric headers and cells", () => {
            assert.match(tableContent, /TableHeadNumeric.*text-right/s);
            assert.match(tableContent, /TableCellNumeric.*text-right/s);
            assert.match(tableContent, /TableCellNumeric.*tabular-nums/s);
            assert.match(tableContent, /TableCellNumeric.*font-mono/s);
        });

        it("enforces right-alignment and compact spacing for action cells", () => {
            assert.match(tableContent, /TableCellAction.*text-right/s);
            assert.match(tableContent, /TableCellAction.*whitespace-nowrap/s);
        });
    });

    describe("2. Shared TableShell Container (components/common/table/TableShell.tsx)", () => {
        const shellContent = fs.readFileSync(TABLE_SHELL_PATH, "utf8");

        it("exports TableShell with optional header, footer, and styling props", () => {
            assert.match(shellContent, /export interface TableShellProps/);
            assert.match(shellContent, /header\?: React\.ReactNode/);
            assert.match(shellContent, /footer\?: React\.ReactNode/);
            assert.match(shellContent, /export function TableShell\(/);
        });

        it("enforces rounded-2xl border and subtle elevation (shadow-2xs)", () => {
            assert.match(shellContent, /rounded-2xl/);
            assert.match(shellContent, /border border-slate-200 dark:border-slate-800/);
            assert.match(shellContent, /shadow-2xs/);
        });

        it("renders header slot with bottom divider when provided", () => {
            assert.match(shellContent, /header && \(/);
            assert.match(shellContent, /border-b border-slate-100 dark:border-slate-800/);
        });

        it("renders footer slot inside shell container when provided", () => {
            assert.match(shellContent, /\{footer\}/);
        });

        it("maintains horizontal overflow wrapper for mobile responsiveness", () => {
            assert.match(shellContent, /overflow-x-auto/);
        });
    });

    describe("3. Shared Pagination (components/ui/pagination.tsx)", () => {
        const paginationContent = fs.readFileSync(PAGINATION_PATH, "utf8");

        it("supports backward-compatible core pagination contract", () => {
            assert.match(paginationContent, /page: number/);
            assert.match(paginationContent, /pageSize: number/);
            assert.match(paginationContent, /count: number/);
            assert.match(paginationContent, /onPageChange: \(page: number\) => void/);
        });

        it("supports optional rows-per-page selector with configurable options", () => {
            assert.match(paginationContent, /pageSizeOptions\?: number\[\]/);
            assert.match(paginationContent, /onPageSizeChange\?: \(pageSize: number\) => void/);
            assert.match(paginationContent, /aria-label="Rows per page"/);
        });

        it("renders accurate record range and disabled navigation boundaries", () => {
            assert.match(paginationContent, /totalPages = Math\.max\(1, Math\.ceil\(count \/ pageSize\)\)/);
            assert.match(paginationContent, /startRow = \(page - 1\) \* pageSize \+ 1/);
            assert.match(paginationContent, /endRow = Math\.min\(page \* pageSize, count\)/);
            assert.match(paginationContent, /disabled=\{page <= 1\}/);
            assert.match(paginationContent, /disabled=\{page >= totalPages\}/);
        });
    });

    describe("4. Enterprise FilterBar Component (components/common/table/FilterBar.tsx)", () => {
        const filterBarContent = fs.readFileSync(FILTER_BAR_PATH, "utf8");

        it("exports FilterBar component with comprehensive configuration options", () => {
            assert.match(filterBarContent, /export interface FilterBarProps/);
            assert.match(filterBarContent, /export function FilterBar\(/);
            assert.match(filterBarContent, /searchValue\?: string/);
            assert.match(filterBarContent, /onSearchChange\?: \(value: string\) => void/);
            assert.match(filterBarContent, /onSearchDebounced\?: \(value: string\) => void/);
            assert.match(filterBarContent, /debounceMs\?: number/);
            assert.match(filterBarContent, /onReset\?: \(\) => void/);
            assert.match(filterBarContent, /actions\?: React\.ReactNode/);
        });

        it("supports search input with debouncing and one-click clear button", () => {
            assert.match(filterBarContent, /Search\s+className="absolute left-3/);
            assert.match(filterBarContent, /setTimeout\(\(\) => \{\s+onSearchDebounced\(localQuery\);\s+\}, debounceMs\)/);
            assert.match(filterBarContent, /aria-label="Clear search"/);
        });

        it("supports optional reset filters button with RotateCcw icon", () => {
            assert.match(filterBarContent, /onReset && \(/);
            assert.match(filterBarContent, /<RotateCcw className="h-3 w-3" \/>/);
            assert.match(filterBarContent, /resetLabel/);
        });

        it("supports flexible wrapping for responsive desktop, tablet, and mobile views", () => {
            assert.match(filterBarContent, /flex flex-col md:flex-row/);
            assert.match(filterBarContent, /flex-wrap/);
        });
    });

    describe("5. Module Table Migrations & Standards Verification", () => {
        it("audit-logs/page.tsx embeds Pagination inside TableShell footer with pageSizeOptions", () => {
            const content = fs.readFileSync(AUDIT_LOGS_PAGE_PATH, "utf8");
            assert.match(content, /<TableShell\s+footer=\{/);
            assert.match(content, /<Pagination/);
            assert.match(content, /pageSizeOptions=\{\[10, 20, 50\]\}/);
            assert.match(content, /<TableBody striped>/);
            assert.doesNotMatch(content, /Showing <strong.*events.*<Select/s, "Must not contain redundant detached pagination bar");
        });

        it("certificates/page.tsx embeds Pagination inside TableShell footer", () => {
            const content = fs.readFileSync(CERTIFICATES_PAGE_PATH, "utf8");
            assert.match(content, /<TableShell\s+footer=\{/);
            assert.match(content, /<Pagination/);
            assert.match(content, /<TableBody striped>/);
        });

        it("expenses/page.tsx uses TableShell and TableCellNumeric for amounts", () => {
            const content = fs.readFileSync(EXPENSES_PAGE_PATH, "utf8");
            assert.match(content, /<TableShell>/);
            assert.match(content, /<TableCellNumeric/);
            assert.match(content, /<TableCellAction/);
        });

        it("fees/collection/page.tsx uses TableShell and right-aligned numeric cells", () => {
            const content = fs.readFileSync(FEES_COLLECTION_PAGE_PATH, "utf8");
            assert.match(content, /<TableShell>/);
            assert.match(content, /<TableHeadNumeric>/);
            assert.match(content, /<TableCellNumeric>/);
            assert.doesNotMatch(content, /<table className=/);
        });

        it("fees/dues/page.tsx embeds shared Pagination inside TableShell", () => {
            const content = fs.readFileSync(FEES_DUES_PAGE_PATH, "utf8");
            assert.match(content, /<TableShell\s+footer=\{/);
            assert.match(content, /<Pagination/);
            assert.match(content, /<TableHeadNumeric>/);
            assert.match(content, /<TableCellNumeric>/);
        });

        it("inventory/page.tsx embeds Pagination inside TableShell and uses TableCellNumeric", () => {
            const content = fs.readFileSync(INVENTORY_PAGE_PATH, "utf8");
            assert.match(content, /<TableShell\s+footer=\{/);
            assert.match(content, /<Pagination/);
            assert.match(content, /<TableHeadNumeric>/);
            assert.match(content, /<TableCellNumeric>/);
            assert.match(content, /<TableBody striped>/);
        });

        it("library/page.tsx embeds Pagination inside TableShell and uses standard TableHead", () => {
            const content = fs.readFileSync(LIBRARY_PAGE_PATH, "utf8");
            assert.match(content, /<TableShell\s+footer=\{/);
            assert.match(content, /<Pagination/);
            assert.match(content, /<TableBody striped>/);
            assert.doesNotMatch(content, /<div className="space-y-3">\s*<TableShell>\s*<Table>\s*.*\s*<\/TableShell>\s*\{\/\* Pagination \*\/\}/s);
        });

        it("payroll/page.tsx right-aligns Gross Pay, Deductions, and Net Payable", () => {
            const content = fs.readFileSync(PAYROLL_PAGE_PATH, "utf8");
            assert.match(content, /<TableShell\s+footer=\{/);
            assert.match(content, /<Pagination/);
            assert.match(content, /<TableHeadNumeric>\s*Gross Pay/s);
            assert.match(content, /<TableHeadNumeric>\s*Deductions/s);
            assert.match(content, /<TableHeadNumeric>\s*Net Payable/s);
            assert.match(content, /<TableBody striped>/);
        });

        it("transport/fleet/page.tsx uses TableShell and striped TableBody", () => {
            const content = fs.readFileSync(TRANSPORT_FLEET_PAGE_PATH, "utf8");
            assert.match(content, /<TableShell>/);
            assert.match(content, /<TableBody striped>/);
        });
    });
});
