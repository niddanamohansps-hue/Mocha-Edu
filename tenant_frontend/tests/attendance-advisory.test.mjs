import { describe, it } from "node:test";
import assert from "node:assert/strict";

describe("Frontend Attendance Holiday Advisory Logic & State Machine Tests", () => {
    // 1. Date Range Formatting Logic
    describe("Date Range Formatter (formatDateRange)", () => {
        function formatDateRange(startStr, endStr) {
            if (!startStr || !endStr) return "";
            if (startStr === endStr) {
                // Single day format
                const [year, month, day] = startStr.split("-").map(Number);
                const dateObj = new Date(year, month - 1, day);
                const monthName = dateObj.toLocaleString("en-US", { month: "long" });
                return `${day} ${monthName} ${year}`;
            }
            // Multi day format
            const [y1, m1, d1] = startStr.split("-").map(Number);
            const [y2, m2, d2] = endStr.split("-").map(Number);
            const date1 = new Date(y1, m1 - 1, d1);
            const date2 = new Date(y2, m2 - 1, d2);
            const month1 = date1.toLocaleString("en-US", { month: "short" });
            const month2 = date2.toLocaleString("en-US", { month: "short" });
            const diffTime = Math.abs(date2.getTime() - date1.getTime());
            const days = Math.round(diffTime / (1000 * 60 * 60 * 24)) + 1;

            if (y1 === y2 && m1 === m2) {
                return `${d1} – ${d2} ${month1} ${y1} (${days} days)`;
            }
            return `${d1} ${month1} ${y1} – ${d2} ${month2} ${y2} (${days} days)`;
        }

        it("formats single-day event into clean day month year format", () => {
            const formatted = formatDateRange("2026-10-02", "2026-10-02");
            assert.equal(formatted, "2 October 2026");
        });

        it("formats multi-day event spanning same month with days count", () => {
            const formatted = formatDateRange("2026-10-15", "2026-10-22");
            assert.equal(formatted, "15 – 22 Oct 2026 (8 days)");
        });

        it("formats multi-day event spanning different months", () => {
            const formatted = formatDateRange("2026-10-28", "2026-11-04");
            assert.equal(formatted, "28 Oct 2026 – 4 Nov 2026 (8 days)");
        });
    });

    // 2. Event Matching & Date Interval Coverage
    describe("Event Date Overlap & Filter Defense (filterRelevantEvents)", () => {
        function filterRelevantEvents(events, selectedDate) {
            if (!events || !Array.isArray(events) || !selectedDate) return [];
            return events.filter((evt) => {
                const status = (evt.status || "").toUpperCase();
                if (status !== "PUBLISHED") return false;
                const type = (evt.event_type || "").toUpperCase();
                const isHolidayOrClosure = evt.is_holiday || type === "HOLIDAY" || type === "CLOSURE";
                if (!isHolidayOrClosure) return false;
                return evt.start_date <= selectedDate && selectedDate <= evt.end_date;
            });
        }

        const eventsMock = [
            {
                id: "1",
                title: "Gandhi Jayanti",
                event_type: "HOLIDAY",
                is_holiday: true,
                status: "PUBLISHED",
                start_date: "2026-10-02",
                end_date: "2026-10-02",
            },
            {
                id: "2",
                title: "Dashain Vacation",
                event_type: "HOLIDAY",
                is_holiday: true,
                status: "PUBLISHED",
                start_date: "2026-10-15",
                end_date: "2026-10-22",
            },
            {
                id: "3",
                title: "Emergency Campus Closure",
                event_type: "CLOSURE",
                is_holiday: true,
                status: "PUBLISHED",
                start_date: "2026-10-18",
                end_date: "2026-10-18",
            },
            {
                id: "4",
                title: "Draft Holiday",
                event_type: "HOLIDAY",
                is_holiday: true,
                status: "DRAFT",
                start_date: "2026-10-02",
                end_date: "2026-10-02",
            },
            {
                id: "5",
                title: "Cancelled Event",
                event_type: "HOLIDAY",
                is_holiday: true,
                status: "CANCELLED",
                start_date: "2026-10-02",
                end_date: "2026-10-02",
            },
            {
                id: "6",
                title: "Normal Academic Class",
                event_type: "ACADEMIC",
                is_holiday: false,
                status: "PUBLISHED",
                start_date: "2026-10-02",
                end_date: "2026-10-02",
            },
        ];

        it("matches single-day holiday on exact date", () => {
            const result = filterRelevantEvents(eventsMock, "2026-10-02");
            assert.equal(result.length, 1);
            assert.equal(result[0].title, "Gandhi Jayanti");
        });

        it("strictly excludes draft and cancelled events on the same date", () => {
            const result = filterRelevantEvents(eventsMock, "2026-10-02");
            const ids = result.map((r) => r.id);
            assert.equal(ids.includes("4"), false); // draft
            assert.equal(ids.includes("5"), false); // cancelled
        });

        it("strictly excludes non-holiday academic events", () => {
            const result = filterRelevantEvents(eventsMock, "2026-10-02");
            const ids = result.map((r) => r.id);
            assert.equal(ids.includes("6"), false);
        });

        it("matches multi-day event on boundary start date, middle date, and end date", () => {
            const startDay = filterRelevantEvents(eventsMock, "2026-10-15");
            assert.equal(startDay.some((e) => e.title === "Dashain Vacation"), true);

            const middleDay = filterRelevantEvents(eventsMock, "2026-10-18");
            assert.equal(middleDay.some((e) => e.title === "Dashain Vacation"), true);

            const endDay = filterRelevantEvents(eventsMock, "2026-10-22");
            assert.equal(endDay.some((e) => e.title === "Dashain Vacation"), true);

            const outsideBefore = filterRelevantEvents(eventsMock, "2026-10-14");
            assert.equal(outsideBefore.some((e) => e.title === "Dashain Vacation"), false);

            const outsideAfter = filterRelevantEvents(eventsMock, "2026-10-23");
            assert.equal(outsideAfter.some((e) => e.title === "Dashain Vacation"), false);
        });

        it("returns multiple applicable events when both a holiday and closure occur on the same date", () => {
            const result = filterRelevantEvents(eventsMock, "2026-10-18");
            assert.equal(result.length, 2);
            const titles = result.map((e) => e.title);
            assert.equal(titles.includes("Dashain Vacation"), true);
            assert.equal(titles.includes("Emergency Campus Closure"), true);
        });

        it("returns empty array when date has no applicable events", () => {
            const result = filterRelevantEvents(eventsMock, "2026-11-01");
            assert.equal(result.length, 0);
        });
    });

    // 3. Advisory Classification & Text Generator
    describe("Advisory Classification & Text Generation", () => {
        function getAdvisoryContent(event, selectedDate) {
            const isClosure = (event.event_type || "").toUpperCase() === "CLOSURE";
            const dateDisplay = event.start_date === event.end_date ? event.start_date : `${event.start_date} to ${event.end_date}`;

            if (isClosure) {
                return {
                    variant: "closure",
                    badgeText: "School Closure Advisory",
                    headline: `School Closure Advisory: "${event.title}" covers the selected attendance date (${dateDisplay}).`,
                    actionNote: "Please verify school closure instructions before proceeding with attendance recording.",
                    themeColor: "amber",
                };
            }
            return {
                variant: "holiday",
                badgeText: "Holiday Advisory",
                headline: `Holiday Advisory: "${event.title}" is scheduled for ${dateDisplay}.`,
                actionNote: "Please verify the school academic calendar before marking attendance for this date.",
                themeColor: "rose",
            };
        }

        it("correctly classifies school closure event with amber warning", () => {
            const event = {
                title: "Maintenance Shutdown",
                event_type: "CLOSURE",
                is_holiday: true,
                start_date: "2026-10-05",
                end_date: "2026-10-05",
            };
            const content = getAdvisoryContent(event, "2026-10-05");
            assert.equal(content.variant, "closure");
            assert.equal(content.badgeText, "School Closure Advisory");
            assert.equal(content.themeColor, "amber");
            assert.equal(
                content.headline,
                'School Closure Advisory: "Maintenance Shutdown" covers the selected attendance date (2026-10-05).'
            );
        });

        it("correctly classifies standard holiday event with rose warning", () => {
            const event = {
                title: "Diwali Break",
                event_type: "HOLIDAY",
                is_holiday: true,
                start_date: "2026-11-01",
                end_date: "2026-11-03",
            };
            const content = getAdvisoryContent(event, "2026-11-02");
            assert.equal(content.variant, "holiday");
            assert.equal(content.badgeText, "Holiday Advisory");
            assert.equal(content.themeColor, "rose");
            assert.equal(
                content.headline,
                'Holiday Advisory: "Diwali Break" is scheduled for 2026-11-01 to 2026-11-03.'
            );
        });
    });

    // 4. Stale Date Prevention & Dynamic Date Switching
    describe("Stale Date & Query Key Consistency", () => {
        function buildQueryKey(userId, date, academicYearId) {
            return ["calendar-events", "advisory", userId, date, academicYearId];
        }

        it("generates distinct query keys for different dates to avoid stale overwrites", () => {
            const key1 = buildQueryKey("user-1", "2026-10-02", "ay-1");
            const key2 = buildQueryKey("user-1", "2026-10-03", "ay-1");
            assert.notDeepEqual(key1, key2);
            assert.equal(key1[3], "2026-10-02");
            assert.equal(key2[3], "2026-10-03");
        });

        it("scopes query key by academic year and user", () => {
            const keyA = buildQueryKey("user-1", "2026-10-02", "ay-1");
            const keyB = buildQueryKey("user-1", "2026-10-02", "ay-2");
            assert.notDeepEqual(keyA, keyB);
        });
    });

    // 5. API Error State Handling
    describe("API Error & Recovery Behavior", () => {
        function evaluateBannerState({ isLoading, isError, events }) {
            if (isLoading) return "loading";
            if (isError) return "service_unavailable_notice";
            if (!events || events.length === 0) return "hidden";
            return "visible_advisory";
        }

        it("transitions from loading to visible when events are found", () => {
            assert.equal(evaluateBannerState({ isLoading: true, isError: false, events: [] }), "loading");
            assert.equal(evaluateBannerState({ isLoading: false, isError: false, events: [{ id: "1" }] }), "visible_advisory");
        });

        it("renders service unavailable notice without falsely asserting date is clear when API fails", () => {
            const state = evaluateBannerState({ isLoading: false, isError: true, events: [] });
            assert.equal(state, "service_unavailable_notice");
            assert.notEqual(state, "hidden");
        });

        it("hides completely when there are no events and no errors", () => {
            const state = evaluateBannerState({ isLoading: false, isError: false, events: [] });
            assert.equal(state, "hidden");
        });
    });
});

