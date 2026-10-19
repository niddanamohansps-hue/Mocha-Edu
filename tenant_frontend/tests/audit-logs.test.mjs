import { describe, it } from "node:test";
import assert from "node:assert/strict";

describe("Frontend Audit Logs Logic & State Machine Tests", () => {
    describe("Error Message Extraction (auditLogErrorMessage)", () => {
        function auditLogErrorMessage(error, fallback) {
            const data = error?.response?.data;
            if (!data || typeof data !== "object") return fallback;
            if (typeof data.detail === "string") return data.detail;
            for (const key of Object.keys(data)) {
                const value = data[key];
                const text = Array.isArray(value) ? value[0] : value;
                if (typeof text === "string") return key === "non_field_errors" ? text : `${key.replace(/_/g, " ")}: ${text}`;
            }
            return fallback;
        }

        it("returns detail field if present", () => {
            const err = { response: { data: { detail: "Authentication credentials were not provided." } } };
            assert.equal(auditLogErrorMessage(err, "Fallback"), "Authentication credentials were not provided.");
        });

        it("formats field-specific errors nicely", () => {
            const err = { response: { data: { date_from: ["date_from cannot be after date_to."] } } };
            assert.equal(auditLogErrorMessage(err, "Fallback"), "date from: date_from cannot be after date_to.");
        });

        it("returns non_field_errors directly without field prefix", () => {
            const err = { response: { data: { non_field_errors: ["Invalid filter combination."] } } };
            assert.equal(auditLogErrorMessage(err, "Fallback"), "Invalid filter combination.");
        });

        it("falls back gracefully when response data is null or empty", () => {
            assert.equal(auditLogErrorMessage(null, "An unexpected error occurred."), "An unexpected error occurred.");
            assert.equal(auditLogErrorMessage({}, "An unexpected error occurred."), "An unexpected error occurred.");
        });
    });

    describe("Query Parameter Building & Filter Normalization", () => {
        function buildQueryParams(filters) {
            const params = { page: filters.page };
            if (filters.page_size) params.page_size = filters.page_size;
            if (filters.search && filters.search.trim()) params.search = filters.search.trim();
            if (filters.actor_username && filters.actor_username.trim()) params.actor_username = filters.actor_username.trim();
            if (filters.action && filters.action !== "ALL") params.action = filters.action;
            if (filters.model_name && filters.model_name !== "ALL") params.model_name = filters.model_name;
            if (filters.object_id && filters.object_id.trim()) params.object_id = filters.object_id.trim();
            if (filters.date_from) params.date_from = filters.date_from;
            if (filters.date_to) params.date_to = filters.date_to;
            if (filters.ordering) params.ordering = filters.ordering;
            return params;
        }

        it("includes page and omits undefined/empty filters", () => {
            const params = buildQueryParams({ page: 1 });
            assert.deepEqual(params, { page: 1 });
        });

        it("trims whitespace from text inputs", () => {
            const params = buildQueryParams({
                page: 2,
                search: "  alice  ",
                actor_username: "  admin_user  ",
                object_id: "  STU-1001  "
            });
            assert.equal(params.search, "alice");
            assert.equal(params.actor_username, "admin_user");
            assert.equal(params.object_id, "STU-1001");
        });

        it("ignores 'ALL' selection for dropdown filters", () => {
            const params = buildQueryParams({
                page: 1,
                action: "ALL",
                model_name: "ALL"
            });
            assert.equal("action" in params, false);
            assert.equal("model_name" in params, false);
        });

        it("passes specific action and model filters", () => {
            const params = buildQueryParams({
                page: 1,
                action: "role_created",
                model_name: "Role"
            });
            assert.equal(params.action, "role_created");
            assert.equal(params.model_name, "Role");
        });
    });

    describe("Date Range Boundary Logic", () => {
        function validateDateRange(dateFrom, dateTo) {
            if (dateFrom && dateTo && dateFrom > dateTo) {
                return "Start date cannot be after end date.";
            }
            return null;
        }

        it("accepts valid chronological date ranges", () => {
            assert.equal(validateDateRange("2026-10-01", "2026-10-17"), null);
            assert.equal(validateDateRange("2026-10-17", "2026-10-17"), null);
        });

        it("rejects inverted date ranges", () => {
            assert.equal(
                validateDateRange("2026-10-18", "2026-10-17"),
                "Start date cannot be after end date."
            );
        });

        it("allows single boundary dates", () => {
            assert.equal(validateDateRange("2026-10-01", ""), null);
            assert.equal(validateDateRange("", "2026-10-17"), null);
            assert.equal(validateDateRange("", ""), null);
        });
    });

    describe("Action Badge Variant Classification", () => {
        function getActionBadgeVariant(action) {
            const act = action.toLowerCase();
            if (act.includes("delete") || act.includes("remove") || act.includes("cancel") || act.includes("revers")) {
                return "destructive";
            }
            if (act.includes("create") || act.includes("add") || act.includes("enroll") || act.includes("publish")) {
                return "default";
            }
            if (act.includes("update") || act.includes("change") || act.includes("edit")) {
                return "secondary";
            }
            return "outline";
        }

        it("maps deletion and destructive actions to 'destructive'", () => {
            assert.equal(getActionBadgeVariant("role_deleted"), "destructive");
            assert.equal(getActionBadgeVariant("student_removed"), "destructive");
            assert.equal(getActionBadgeVariant("payment_cancelled"), "destructive");
            assert.equal(getActionBadgeVariant("promotion_reversed"), "destructive");
        });

        it("maps creation and publishing actions to 'default'", () => {
            assert.equal(getActionBadgeVariant("role_created"), "default");
            assert.equal(getActionBadgeVariant("student_enrolled"), "default");
            assert.equal(getActionBadgeVariant("exam_published"), "default");
            assert.equal(getActionBadgeVariant("user_add"), "default");
        });

        it("maps update and modification actions to 'secondary'", () => {
            assert.equal(getActionBadgeVariant("role_updated"), "secondary");
            assert.equal(getActionBadgeVariant("password_changed"), "secondary");
            assert.equal(getActionBadgeVariant("marks_edited"), "secondary");
        });

        it("maps other actions to 'outline'", () => {
            assert.equal(getActionBadgeVariant("session_locked"), "outline");
            assert.equal(getActionBadgeVariant("credentials_viewed"), "outline");
        });
    });

    describe("Audit Log Changes & Diff Interpretation", () => {
        function isDiffEntry(val) {
            return (
                typeof val === "object" &&
                val !== null &&
                ("old" in val || "new" in val)
            );
        }

        function formatValue(value) {
            if (value === null || value === undefined) return "(empty)";
            if (typeof value === "boolean") return value ? "true" : "false";
            if (typeof value === "object") {
                try {
                    return JSON.stringify(value, null, 2);
                } catch {
                    return String(value);
                }
            }
            return String(value);
        }

        it("detects old/new diff structure correctly", () => {
            assert.equal(isDiffEntry({ old: "Admin", new: "SuperAdmin" }), true);
            assert.equal(isDiffEntry({ old: null, new: "Active" }), true);
            assert.equal(isDiffEntry("plain string"), false);
            assert.equal(isDiffEntry({ status: "active" }), false);
            assert.equal(isDiffEntry(null), false);
        });

        it("formats primitives and empty values safely", () => {
            assert.equal(formatValue(null), "(empty)");
            assert.equal(formatValue(undefined), "(empty)");
            assert.equal(formatValue(true), "true");
            assert.equal(formatValue(false), "false");
            assert.equal(formatValue(12345), "12345");
            assert.equal(formatValue("text"), "text");
        });

        it("formats nested JSON objects safely", () => {
            const nested = { id: 1, role: "teacher" };
            assert.equal(formatValue(nested), JSON.stringify(nested, null, 2));
        });
    });
});

