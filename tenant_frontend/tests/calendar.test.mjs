import { describe, it } from "node:test";
import assert from "node:assert/strict";

describe("Frontend Academic Calendar & Holiday Logic Tests", () => {
    describe("Error Message Extraction (calendarErrorMessage)", () => {
        function calendarErrorMessage(error, fallback) {
            const data = error?.response?.data;
            if (!data || typeof data !== "object") return fallback;
            if (typeof data.detail === "string") return data.detail;
            for (const key of Object.keys(data)) {
                const value = data[key];
                const text = Array.isArray(value) ? value[0] : value;
                if (typeof text === "string") {
                    return key === "non_field_errors" ? text : `${key.replace(/_/g, " ")}: ${text}`;
                }
            }
            return fallback;
        }

        it("extracts detail message if provided", () => {
            const err = { response: { data: { detail: "Authentication credentials were not provided." } } };
            assert.equal(calendarErrorMessage(err, "Fallback"), "Authentication credentials were not provided.");
        });

        it("formats field-specific errors nicely", () => {
            const err = { response: { data: { end_date: ["End date cannot be earlier than start date."] } } };
            assert.equal(calendarErrorMessage(err, "Fallback"), "end date: End date cannot be earlier than start date.");
        });

        it("returns non_field_errors without field prefix", () => {
            const err = { response: { data: { non_field_errors: ["End time must be after start time."] } } };
            assert.equal(calendarErrorMessage(err, "Fallback"), "End time must be after start time.");
        });

        it("falls back gracefully when response data is missing or empty", () => {
            assert.equal(calendarErrorMessage(null, "Default error"), "Default error");
            assert.equal(calendarErrorMessage({}, "Default error"), "Default error");
        });
    });

    describe("Query Parameter Building & Filter Normalization", () => {
        function buildQueryParams(filters) {
            const params = {};
            if (filters.date_from) params.date_from = filters.date_from;
            if (filters.date_to) params.date_to = filters.date_to;
            if (filters.start_date) params.start_date = filters.start_date;
            if (filters.end_date) params.end_date = filters.end_date;
            if (filters.month) params.month = filters.month;
            if (filters.event_type) params.event_type = filters.event_type;
            if (filters.is_holiday !== undefined && filters.is_holiday !== "") {
                params.is_holiday = Boolean(filters.is_holiday);
            }
            if (filters.status) params.status = filters.status;
            if (filters.academic_year) params.academic_year = filters.academic_year;
            if (filters.audience) params.audience = filters.audience;
            if (filters.search && filters.search.trim()) params.search = filters.search.trim();
            return params;
        }

        it("builds empty params when no filters provided", () => {
            const params = buildQueryParams({});
            assert.deepEqual(params, {});
        });

        it("properly serializes date range and holiday filter", () => {
            const params = buildQueryParams({
                date_from: "2026-10-01",
                date_to: "2026-10-31",
                is_holiday: true,
                event_type: "holiday",
                search: "  Dashain  ",
            });
            assert.deepEqual(params, {
                date_from: "2026-10-01",
                date_to: "2026-10-31",
                is_holiday: true,
                event_type: "holiday",
                search: "Dashain",
            });
        });

        it("omits empty string holiday filter", () => {
            const params = buildQueryParams({ is_holiday: "" });
            assert.deepEqual(params, {});
        });
    });

    describe("Form Validation Logic", () => {
        function validateEventForm({
            title,
            startDate,
            endDate,
            isAllDay,
            startTime,
            endTime,
        }) {
            const errors = {};
            if (!title || !title.trim()) {
                errors.title = "Title is required.";
            }
            if (!startDate) {
                errors.start_date = "Start date is required.";
            }
            if (!endDate) {
                errors.end_date = "End date is required.";
            }
            if (startDate && endDate && endDate < startDate) {
                errors.end_date = "End date cannot be earlier than start date.";
            }
            if (!isAllDay) {
                if (startDate === endDate && startTime && endTime && endTime <= startTime) {
                    errors.end_time = "End time must be after start time on the same day.";
                }
            }
            return {
                isValid: Object.keys(errors).length === 0,
                errors,
            };
        }

        it("validates valid single-day all-day event", () => {
            const res = validateEventForm({
                title: "School Assembly",
                startDate: "2026-10-20",
                endDate: "2026-10-20",
                isAllDay: true,
            });
            assert.equal(res.isValid, true);
            assert.deepEqual(res.errors, {});
        });

        it("rejects missing title or dates", () => {
            const res = validateEventForm({
                title: "",
                startDate: "",
                endDate: "",
                isAllDay: true,
            });
            assert.equal(res.isValid, false);
            assert.equal(res.errors.title, "Title is required.");
            assert.equal(res.errors.start_date, "Start date is required.");
            assert.equal(res.errors.end_date, "End date is required.");
        });

        it("rejects end date earlier than start date", () => {
            const res = validateEventForm({
                title: "Tihar Break",
                startDate: "2026-11-10",
                endDate: "2026-11-05",
                isAllDay: true,
            });
            assert.equal(res.isValid, false);
            assert.equal(res.errors.end_date, "End date cannot be earlier than start date.");
        });

        it("rejects end time earlier or equal to start time on same day", () => {
            const res = validateEventForm({
                title: "PTA Meeting",
                startDate: "2026-10-20",
                endDate: "2026-10-20",
                isAllDay: false,
                startTime: "14:00",
                endTime: "13:00",
            });
            assert.equal(res.isValid, false);
            assert.equal(res.errors.end_time, "End time must be after start time on the same day.");
        });

        it("allows same start/end time across different dates", () => {
            const res = validateEventForm({
                title: "Overnight Camp",
                startDate: "2026-10-20",
                endDate: "2026-10-21",
                isAllDay: false,
                startTime: "18:00",
                endTime: "08:00",
            });
            assert.equal(res.isValid, true);
        });
    });

    describe("Multi-Day Event Spanning & Day Matching", () => {
        function eventOccursOnDay(event, dayStr) {
            return dayStr >= event.start_date && dayStr <= event.end_date;
        }

        it("accurately detects multi-day event inclusion across days", () => {
            const festival = {
                id: "1",
                title: "Dashain Break",
                start_date: "2026-10-15",
                end_date: "2026-10-22",
                is_holiday: true,
            };

            assert.equal(eventOccursOnDay(festival, "2026-10-14"), false);
            assert.equal(eventOccursOnDay(festival, "2026-10-15"), true);
            assert.equal(eventOccursOnDay(festival, "2026-10-18"), true);
            assert.equal(eventOccursOnDay(festival, "2026-10-22"), true);
            assert.equal(eventOccursOnDay(festival, "2026-10-23"), false);
        });
    });

    describe("School Status Evaluation", () => {
        function getSchoolStatus(events, checkDateStr) {
            const activeClosures = events.filter(
                (e) =>
                    checkDateStr >= e.start_date &&
                    checkDateStr <= e.end_date &&
                    (e.is_holiday || e.event_type === "closure") &&
                    e.status === "published"
            );

            if (activeClosures.length > 0) {
                return {
                    isOpen: false,
                    reason: activeClosures[0].title,
                };
            }
            return {
                isOpen: true,
                reason: "Regular academic operations",
            };
        }

        it("reports closed when published holiday is active", () => {
            const events = [
                {
                    title: "Public Holiday",
                    start_date: "2026-10-25",
                    end_date: "2026-10-25",
                    is_holiday: true,
                    event_type: "holiday",
                    status: "published",
                },
            ];

            const status = getSchoolStatus(events, "2026-10-25");
            assert.equal(status.isOpen, false);
            assert.equal(status.reason, "Public Holiday");
        });

        it("ignores draft holidays for school status", () => {
            const events = [
                {
                    title: "Draft Holiday",
                    start_date: "2026-10-25",
                    end_date: "2026-10-25",
                    is_holiday: true,
                    event_type: "holiday",
                    status: "draft",
                },
            ];

            const status = getSchoolStatus(events, "2026-10-25");
            assert.equal(status.isOpen, true);
        });

        it("reports open when only non-closure events exist", () => {
            const events = [
                {
                    title: "Science Fair",
                    start_date: "2026-10-25",
                    end_date: "2026-10-25",
                    is_holiday: false,
                    event_type: "activity",
                    status: "published",
                },
            ];

            const status = getSchoolStatus(events, "2026-10-25");
            assert.equal(status.isOpen, true);
        });
    });
});

