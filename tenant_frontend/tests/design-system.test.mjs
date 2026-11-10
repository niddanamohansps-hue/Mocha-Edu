import { describe, it } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const GLOBALS_CSS_PATH = path.resolve(process.cwd(), "src/app/globals.css");
const BUTTON_PATH = path.resolve(process.cwd(), "src/components/ui/button.tsx");
const CARD_PATH = path.resolve(process.cwd(), "src/components/ui/card.tsx");
const BADGE_PATH = path.resolve(process.cwd(), "src/components/ui/badge.tsx");
const INPUT_PATH = path.resolve(process.cwd(), "src/components/ui/input.tsx");
const SELECT_PATH = path.resolve(process.cwd(), "src/components/ui/select.tsx");

describe("Phase 1: Global UI Design System & Token Standardization Tests", () => {
    describe("1. Global Design Tokens (globals.css)", () => {
        const cssContent = fs.readFileSync(GLOBALS_CSS_PATH, "utf8");

        it("defines consolidated light mode semantic tokens with accessible contrast", () => {
            assert.match(cssContent, /--primary:\s*#0284c7/, "Primary brand color should be accessible Sky-600");
            assert.match(cssContent, /--foreground:\s*#0f172a/, "Foreground text should be Slate-900");
            assert.match(cssContent, /--accent:\s*#f1f5f9/, "Subtle surface hover accent should be Slate-100");
            assert.match(cssContent, /--accent-foreground:\s*#0f172a/, "Accent foreground should be Slate-900");
            assert.match(cssContent, /--destructive:\s*#dc2626/, "Destructive should be Red-600");
            assert.match(cssContent, /--destructive-foreground:\s*#ffffff/, "Destructive foreground should be White");
        });

        it("defines consolidated dark mode semantic tokens", () => {
            assert.match(cssContent, /--primary:\s*#0ea5e9/, "Dark mode primary should be vibrant Sky-500");
            assert.match(cssContent, /--foreground:\s*#f8fafc/, "Dark mode foreground text should be Slate-50");
            assert.match(cssContent, /--accent:\s*#1e293b/, "Dark mode subtle surface hover should be Slate-800");
            assert.match(cssContent, /--accent-foreground:\s*#f8fafc/, "Dark mode accent foreground should be Slate-50");
            assert.match(cssContent, /--destructive:\s*#ef4444/, "Dark mode destructive should be Red-500");
            assert.match(cssContent, /--destructive-foreground:\s*#ffffff/, "Dark mode destructive foreground should be White");
        });

        it("binds theme tokens into Tailwind CSS @theme inline", () => {
            assert.match(cssContent, /--color-primary:\s*var\(--primary\)/);
            assert.match(cssContent, /--color-accent:\s*var\(--accent\)/);
            assert.match(cssContent, /--color-destructive-foreground:\s*var\(--destructive-foreground\)/);
            assert.match(cssContent, /--radius-md:\s*calc\(var\(--radius\) - 2px\)/);
        });

        it("preserves touch-device (pointer: coarse) accessibility rules", () => {
            assert.match(cssContent, /@media \(pointer: coarse\)/);
            assert.match(cssContent, /min-height:\s*44px/);
            assert.match(cssContent, /font-size:\s*16px/);
        });

        it("preserves universal print engine stylesheets for ID cards & receipts", () => {
            assert.match(cssContent, /@media print/);
            assert.match(cssContent, /\[data-slot="dialog-overlay"\]/);
            assert.match(cssContent, /print-color-adjust:\s*exact/);
        });
    });

    describe("2. Standardized Button Component (button.tsx)", () => {
        const buttonContent = fs.readFileSync(BUTTON_PATH, "utf8");

        it("removes intrusive hover scaling and jitter", () => {
            assert.doesNotMatch(buttonContent, /hover:scale-\[1\.03\]/, "Should not contain hover:scale-[1.03]");
            assert.doesNotMatch(buttonContent, /active:scale-100/, "Should not contain conflicting active:scale-100");
        });

        it("removes exaggerated glowing cyan drop shadows", () => {
            assert.doesNotMatch(buttonContent, /shadow-sky-500\/25/, "Should not contain neon cyan drop shadows");
            assert.doesNotMatch(buttonContent, /shadow-teal-500\/30/, "Should not contain neon teal drop shadows");
        });

        it("removes hardcoded hex values in outline variant", () => {
            assert.doesNotMatch(buttonContent, /#1A82C4/, "Outline button should not hardcode #1A82C4");
        });

        it("provides standard enterprise button variants", () => {
            assert.match(buttonContent, /default:/);
            assert.match(buttonContent, /destructive:/);
            assert.match(buttonContent, /outline:/);
            assert.match(buttonContent, /secondary:/);
            assert.match(buttonContent, /ghost:/);
            assert.match(buttonContent, /link:/);
        });

        it("preserves all required size variants without breaking callers", () => {
            const sizes = ["default:", "sm:", "lg:", "xl:", "xxl:", "icon:", /"?icon-sm"?:/, /"?icon-lg"?:/];
            for (const size of sizes) {
                if (typeof size === "string") {
                    assert.match(buttonContent, new RegExp(size), `Size variant ${size} must be preserved`);
                } else {
                    assert.match(buttonContent, size, `Size variant ${size} must be preserved`);
                }
            }
        });
    });

    describe("3. Standardized Card Component (card.tsx)", () => {
        const cardContent = fs.readFileSync(CARD_PATH, "utf8");

        it("removes hover shadow jitter from static cards", () => {
            assert.doesNotMatch(cardContent, /hover:shadow-lg/, "Static cards should not jitter with hover:shadow-lg");
            assert.doesNotMatch(cardContent, /hover:border-sky-200/, "Static cards should not shift border on hover");
        });

        it("standardizes card border and shadow to subtle enterprise tokens", () => {
            assert.match(cardContent, /border-slate-200\/80/);
            assert.match(cardContent, /shadow-2xs/);
        });
    });

    describe("4. Semantic Badge Primitives (badge.tsx)", () => {
        const badgeContent = fs.readFileSync(BADGE_PATH, "utf8");

        it("supports semantic status variants alongside base variants", () => {
            assert.match(badgeContent, /default:/);
            assert.match(badgeContent, /secondary:/);
            assert.match(badgeContent, /destructive:/);
            assert.match(badgeContent, /outline:/);
            assert.match(badgeContent, /success:/);
            assert.match(badgeContent, /warning:/);
            assert.match(badgeContent, /info:/);
            assert.match(badgeContent, /neutral:/);
        });
    });

    describe("5. Input & Select Density Normalization", () => {
        const inputContent = fs.readFileSync(INPUT_PATH, "utf8");
        const selectContent = fs.readFileSync(SELECT_PATH, "utf8");

        it("standardizes input height to desktop h-9 and mobile touch safety", () => {
            assert.doesNotMatch(inputContent, /h-\[42px\]/, "Should eliminate non-standard h-[42px] input height");
            assert.match(inputContent, /h-9/, "Input should default to standard h-9");
        });

        it("standardizes select trigger height to match input height", () => {
            assert.doesNotMatch(selectContent, /data-\[size=default\]:h-\[42px\]/);
            assert.match(selectContent, /data-\[size=default\]:h-9/);
        });
    });
});
