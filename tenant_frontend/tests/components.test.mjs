import { describe, it } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { getAvatarStyle, getInitials, AVATAR_PALETTES } from "../src/lib/avatar.ts";

const AVATAR_PATH = path.resolve(import.meta.dirname, "../src/components/ui/avatar.tsx");
const STATUS_BADGE_PATH = path.resolve(import.meta.dirname, "../src/components/ui/StatusBadge.tsx");
const COMMON_STATUS_BADGE_PATH = path.resolve(import.meta.dirname, "../src/components/common/StatusBadge.tsx");
const MODAL_HEADER_PATH = path.resolve(import.meta.dirname, "../src/components/ui/modal-header.tsx");
const FORM_LAYOUT_PATH = path.resolve(import.meta.dirname, "../src/components/ui/form-layout.tsx");
const EXPENSES_PAGE_PATH = path.resolve(import.meta.dirname, "../src/app/dashboard/expenses/page.tsx");
const FRONT_OFFICE_PAGE_PATH = path.resolve(import.meta.dirname, "../src/app/dashboard/front-office/page.tsx");
const PTM_PAGE_PATH = path.resolve(import.meta.dirname, "../src/app/dashboard/ptm/page.tsx");
const PARENT_PTM_PAGE_PATH = path.resolve(import.meta.dirname, "../src/app/dashboard/parent-portal/ptm/page.tsx");

describe("Phase 2: Avatar & Status Badge Component Standardization Tests", () => {
    describe("1. Avatar Utilities & Logic (lib/avatar.ts)", () => {
        it("returns deterministic palette index based on string hash", () => {
            const style1 = getAvatarStyle("Aarav Sharma");
            const style2 = getAvatarStyle("Aarav Sharma");
            assert.deepEqual(style1, style2, "Same name must yield identical avatar palette");
            assert.ok(style1.bg && style1.text && style1.border);
        });

        it("handles empty or null name gracefully with fallback palette", () => {
            const style = getAvatarStyle(null);
            assert.deepEqual(style, AVATAR_PALETTES[0]);
        });

        it("extracts initials correctly from multi-word names", () => {
            assert.equal(getInitials("Aarav Sharma"), "AS");
            assert.equal(getInitials("Mohammad Ali Khan"), "MK");
        });

        it("extracts initials correctly from single-word names", () => {
            assert.equal(getInitials("Rahul"), "RA");
            assert.equal(getInitials("A"), "A");
        });

        it("supports dual parameter signature (firstName, lastName)", () => {
            assert.equal(getInitials("Priya", "Patel"), "PP");
        });
    });

    describe("2. Shared Avatar Component (components/ui/avatar.tsx)", () => {
        const avatarContent = fs.readFileSync(AVATAR_PATH, "utf8");

        it("exports Avatar component and size/status definitions", () => {
            assert.match(avatarContent, /export function Avatar\(/);
            assert.match(avatarContent, /export type AvatarSize =/);
            assert.match(avatarContent, /export type AvatarStatus =/);
        });

        it("supports multiple standard sizes including card", () => {
            const sizes = ["xs", "sm", "md", "lg", "xl", "2xl", "3xl", "card"];
            for (const size of sizes) {
                assert.match(avatarContent, new RegExp(`\\b${size}\\b`), `Size ${size} must be supported`);
            }
        });

        it("supports status indicator dots", () => {
            assert.match(avatarContent, /status &&/);
            assert.match(avatarContent, /STATUS_STYLES/);
            assert.match(avatarContent, /bg-emerald-500/);
            assert.match(avatarContent, /bg-rose-500/);
        });

        it("supports composable AvatarImage and AvatarFallback", () => {
            assert.match(avatarContent, /export function AvatarImage\(/);
            assert.match(avatarContent, /export function AvatarFallback\(/);
        });
    });

    describe("3. Standardized StatusBadge (components/ui/StatusBadge.tsx)", () => {
        const badgeContent = fs.readFileSync(STATUS_BADGE_PATH, "utf8");
        const commonBadgeContent = fs.readFileSync(COMMON_STATUS_BADGE_PATH, "utf8");

        it("exports StatusBadge with comprehensive semantic variants", () => {
            assert.match(badgeContent, /export function StatusBadge\(/);
            assert.match(badgeContent, /export type StatusBadgeVariant =/);
            const variants = ["success", "warning", "danger", "info", "neutral", "active", "inactive", "pending"];
            for (const v of variants) {
                assert.match(badgeContent, new RegExp(`"${v}"`), `Variant ${v} must be supported`);
            }
        });

        it("auto-detects common enterprise status keywords", () => {
            const keywords = ["active", "paid", "present", "pending", "draft", "inactive", "unpaid", "cancelled"];
            for (const kw of keywords) {
                assert.match(badgeContent, new RegExp(`"${kw}"`), `Keyword ${kw} must be auto-detected`);
            }
        });

        it("preserves backward compatibility in common/StatusBadge.tsx", () => {
            assert.match(commonBadgeContent, /from "@\/components\/ui\/StatusBadge"/);
            assert.match(commonBadgeContent, /export function StatusBadge/);
        });
    });

    describe("4. Global Modal Header Standard (components/ui/modal-header.tsx)", () => {
        const modalHeaderContent = fs.readFileSync(MODAL_HEADER_PATH, "utf8");

        it("exports ModalHeader component with full prop types", () => {
            assert.match(modalHeaderContent, /export function ModalHeader\(/);
            assert.match(modalHeaderContent, /export interface ModalHeaderProps/);
        });

        it("enforces canonical 36x36px close button with Lucide X and accessible attributes", () => {
            assert.match(modalHeaderContent, /h-9 w-9/);
            assert.match(modalHeaderContent, /<X className="h-4\.5 w-4\.5" \/>/);
            assert.match(modalHeaderContent, /aria-label="Close"/);
        });

        it("enforces minimum header height and fixed sticky top boundary", () => {
            assert.match(modalHeaderContent, /min-h-\[72px\]/);
            assert.match(modalHeaderContent, /border-b/);
            assert.match(modalHeaderContent, /shrink-0/);
        });

        it("supports leading icon, title, badge, subtitle, and metadata", () => {
            assert.match(modalHeaderContent, /title:/);
            assert.match(modalHeaderContent, /badge\?:/);
            assert.match(modalHeaderContent, /subtitle\?:/);
            assert.match(modalHeaderContent, /metadata\?:/);
            assert.match(modalHeaderContent, /icon\?:/);
        });
    });

    describe("5. Global Form Layout Standards (components/ui/form-layout.tsx)", () => {
        const formLayoutContent = fs.readFileSync(FORM_LAYOUT_PATH, "utf8");

        it("exports FormSection, FormGrid, FormGrid3, and FormFieldWrapper", () => {
            assert.match(formLayoutContent, /export function FormSection\(/);
            assert.match(formLayoutContent, /export function FormGrid\(/);
            assert.match(formLayoutContent, /export function FormGrid3\(/);
            assert.match(formLayoutContent, /export function FormFieldWrapper\(/);
        });

        it("enforces 2-column responsive layout for FormGrid", () => {
            assert.match(formLayoutContent, /grid-cols-1 md:grid-cols-2/);
        });

        it("enforces 3-column responsive layout for FormGrid3", () => {
            assert.match(formLayoutContent, /grid-cols-1 sm:grid-cols-3/);
        });

        it("handles required field indicators and inline validation errors", () => {
            assert.match(formLayoutContent, /required = false/);
            assert.match(formLayoutContent, /text-rose-500/);
            assert.match(formLayoutContent, /helpText &&/);
        });
    });

    describe("6. Complete Migration of Legacy Hand-Rolled Modals", () => {
        it("expenses/page.tsx has zero hand-rolled overlays and uses standard Dialog components", () => {
            const content = fs.readFileSync(EXPENSES_PAGE_PATH, "utf8");
            assert.doesNotMatch(content, /fixed inset-0.*bg-black/, "Must not contain hand-rolled modal overlays");
            assert.match(content, /<Dialog open={isExpenseModalOpen}/);
            assert.match(content, /<Dialog open={isCashEntryModalOpen}/);
            assert.match(content, /<Dialog open={isCancelModalOpen/);
            assert.match(content, /<ModalHeader/);
            assert.match(content, /<FormFieldWrapper/);
        });

        it("front-office/page.tsx has zero hand-rolled overlays and uses standard Dialog components", () => {
            const content = fs.readFileSync(FRONT_OFFICE_PAGE_PATH, "utf8");
            assert.doesNotMatch(content, /fixed inset-0.*bg-black/, "Must not contain hand-rolled modal overlays");
            assert.match(content, /<Dialog open={isVisitorModalOpen}/);
            assert.match(content, /<Dialog open={!*visitorToCheckOut}/);
            assert.match(content, /<Dialog open={isGatePassModalOpen}/);
            assert.match(content, /<Dialog open={!*gatePassToExit}/);
            assert.match(content, /<Dialog open={isPostalModalOpen}/);
            assert.match(content, /<ModalHeader/);
        });

        it("ptm/page.tsx has zero hand-rolled overlays and uses standard Dialog components", () => {
            const content = fs.readFileSync(PTM_PAGE_PATH, "utf8");
            assert.doesNotMatch(content, /fixed inset-0.*bg-black/, "Must not contain hand-rolled modal overlays");
            assert.match(content, /<Dialog open={isCreateModalOpen}/);
            assert.match(content, /<Dialog open={!*feedbackModalSlot}/);
            assert.match(content, /<ModalHeader/);
        });

        it("parent-portal/ptm/page.tsx has zero hand-rolled overlays and uses standard Dialog components", () => {
            const content = fs.readFileSync(PARENT_PTM_PAGE_PATH, "utf8");
            assert.doesNotMatch(content, /fixed inset-0.*bg-black/, "Must not contain hand-rolled modal overlays");
            assert.match(content, /<Dialog open={!*bookingSlot}/);
            assert.match(content, /<ModalHeader/);
        });

        it("CallDialog.tsx uses Radix Dialog with canonical ModalHeader and FormFieldWrapper", () => {
            const content = fs.readFileSync(path.resolve(import.meta.dirname, "../src/components/fees/CallDialog.tsx"), "utf8");
            assert.match(content, /<Dialog/);
            assert.match(content, /<ModalHeader/);
            assert.match(content, /<FormFieldWrapper/);
        });
    });
});
