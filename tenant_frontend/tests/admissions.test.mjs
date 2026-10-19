import { describe, it } from "node:test";
import assert from "node:assert/strict";

describe("Frontend Admissions Management Logic & State Machine Tests", () => {
    // 1. Application State Machine Transitions
    describe("Application State Machine Validation", () => {
        const ALLOWED_TRANSITIONS = {
            draft: ["submitted", "withdrawn"],
            submitted: ["under_review", "documents_pending", "withdrawn", "rejected"],
            under_review: [
                "documents_pending",
                "documents_verified",
                "assessment_pending",
                "approved",
                "waitlisted",
                "rejected",
                "withdrawn",
            ],
            documents_pending: ["under_review", "documents_verified", "withdrawn", "rejected"],
            documents_verified: [
                "under_review",
                "assessment_pending",
                "approved",
                "waitlisted",
                "rejected",
                "withdrawn",
            ],
            assessment_pending: ["under_review", "approved", "waitlisted", "rejected", "withdrawn"],
            approved: ["offer_accepted", "withdrawn", "rejected"],
            waitlisted: ["under_review", "approved", "rejected", "withdrawn"],
            offer_accepted: ["withdrawn", "rejected"],
            enrolled: [],
            rejected: ["under_review"],
            withdrawn: ["draft", "under_review"],
        };

        function canTransition(currentStatus, targetStatus) {
            const allowed = ALLOWED_TRANSITIONS[currentStatus] || [];
            return allowed.includes(targetStatus);
        }

        it("allows valid forward transitions from draft to submitted", () => {
            assert.equal(canTransition("draft", "submitted"), true);
            assert.equal(canTransition("draft", "withdrawn"), true);
            assert.equal(canTransition("draft", "approved"), false);
            assert.equal(canTransition("draft", "enrolled"), false);
        });

        it("allows under_review to transition to documentation and evaluation stages", () => {
            assert.equal(canTransition("under_review", "documents_pending"), true);
            assert.equal(canTransition("under_review", "documents_verified"), true);
            assert.equal(canTransition("under_review", "assessment_pending"), true);
            assert.equal(canTransition("under_review", "approved"), true);
            assert.equal(canTransition("under_review", "waitlisted"), true);
            assert.equal(canTransition("under_review", "rejected"), true);
        });

        it("enforces enrolled as a terminal state with no outbound transitions", () => {
            const enrolledTransitions = ALLOWED_TRANSITIONS["enrolled"];
            assert.deepEqual(enrolledTransitions, []);
            assert.equal(canTransition("enrolled", "draft"), false);
            assert.equal(canTransition("enrolled", "withdrawn"), false);
            assert.equal(canTransition("enrolled", "approved"), false);
        });

        it("allows reopened review from rejected status", () => {
            assert.equal(canTransition("rejected", "under_review"), true);
            assert.equal(canTransition("rejected", "approved"), false);
            assert.equal(canTransition("rejected", "enrolled"), false);
        });
    });

    // 2. Enrollment Action Guard & Idempotency Logic
    describe("Enrollment Action Guard", () => {
        function canEnrollApplication(status) {
            return status === "approved" || status === "offer_accepted";
        }

        function isAlreadyEnrolled(status, studentEnrollmentId) {
            return status === "enrolled" || Boolean(studentEnrollmentId);
        }

        it("permits enrollment only for approved or offer_accepted status", () => {
            assert.equal(canEnrollApplication("approved"), true);
            assert.equal(canEnrollApplication("offer_accepted"), true);
            assert.equal(canEnrollApplication("draft"), false);
            assert.equal(canEnrollApplication("submitted"), false);
            assert.equal(canEnrollApplication("under_review"), false);
            assert.equal(canEnrollApplication("waitlisted"), false);
            assert.equal(canEnrollApplication("rejected"), false);
            assert.equal(canEnrollApplication("enrolled"), false);
        });

        it("detects already enrolled application correctly to prevent double enrollment", () => {
            assert.equal(isAlreadyEnrolled("enrolled", "STU-2026-001"), true);
            assert.equal(isAlreadyEnrolled("enrolled", null), true);
            assert.equal(isAlreadyEnrolled("approved", "STU-2026-001"), true);
            assert.equal(isAlreadyEnrolled("approved", null), false);
            assert.equal(isAlreadyEnrolled("offer_accepted", null), false);
        });
    });

    // 3. Document Verification & Rejection Guard
    describe("Document Verification & Rejection Rules", () => {
        const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
        const ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"];

        function validateDocumentFile(filename, size) {
            if (size > MAX_FILE_SIZE) {
                return { valid: false, error: "File exceeds 10MB limit" };
            }
            const extMatch = filename.match(/\.[0-9a-z]+$/i);
            if (!extMatch) {
                return { valid: false, error: "Missing file extension" };
            }
            const ext = extMatch[0].toLowerCase();
            if (!ALLOWED_EXTENSIONS.includes(ext)) {
                return { valid: false, error: `Unsupported extension: ${ext}` };
            }
            return { valid: true };
        }

        function validateDocumentRejection(reason) {
            if (!reason || reason.trim().length === 0) {
                return { valid: false, error: "Rejection reason is required" };
            }
            return { valid: true };
        }

        it("accepts valid document file under 10MB with allowed extension", () => {
            const res = validateDocumentFile("birth_cert.pdf", 2 * 1024 * 1024);
            assert.equal(res.valid, true);
        });

        it("rejects document file exceeding 10MB limit", () => {
            const res = validateDocumentFile("scanned_record.pdf", 11 * 1024 * 1024);
            assert.equal(res.valid, false);
            assert.equal(res.error, "File exceeds 10MB limit");
        });

        it("rejects document with executable or unauthorized extension", () => {
            const res = validateDocumentFile("script.sh", 1024);
            assert.equal(res.valid, false);
            assert.match(res.error, /Unsupported extension/);
        });

        it("enforces mandatory reason when rejecting a document", () => {
            const emptyRes = validateDocumentRejection("   ");
            assert.equal(emptyRes.valid, false);
            assert.equal(emptyRes.error, "Rejection reason is required");

            const validRes = validateDocumentRejection("Illegible scan of birth certificate");
            assert.equal(validRes.valid, true);
        });
    });

    // 4. API Error Message Extraction
    describe("API Error Message Extraction (admissionsErrorMessage)", () => {
        function admissionsErrorMessage(error, fallback) {
            const data = error?.response?.data;
            if (!data || typeof data !== "object") return fallback;
            if (typeof data.error === "string") return data.error;
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

        it("extracts error message from data.error", () => {
            const err = { response: { data: { error: "Application is not in approved state" } } };
            assert.equal(admissionsErrorMessage(err, "Fallback"), "Application is not in approved state");
        });

        it("extracts error message from data.detail", () => {
            const err = { response: { data: { detail: "Authentication credentials were not provided." } } };
            assert.equal(admissionsErrorMessage(err, "Fallback"), "Authentication credentials were not provided.");
        });

        it("extracts field errors cleanly formatted", () => {
            const err = { response: { data: { guardian_phone: ["Enter a valid phone number."] } } };
            assert.equal(admissionsErrorMessage(err, "Fallback"), "guardian phone: Enter a valid phone number.");
        });

        it("extracts non_field_errors without field prefix", () => {
            const err = { response: { data: { non_field_errors: ["Application already enrolled."] } } };
            assert.equal(admissionsErrorMessage(err, "Fallback"), "Application already enrolled.");
        });

        it("returns fallback when error payload is empty or not an object", () => {
            assert.equal(admissionsErrorMessage(null, "Network error"), "Network error");
            assert.equal(admissionsErrorMessage({ response: { data: "Server Error" } }, "Failed"), "Failed");
        });
    });

    // 5. Enquiry to Application Conversion Logic
    describe("Enquiry Data Mapping", () => {
        function mapEnquiryToApplicationDefaults(enquiry) {
            const nameParts = (enquiry.student_name || "").trim().split(/\s+/);
            const firstName = nameParts[0] || "";
            const lastName = nameParts.length > 1 ? nameParts.slice(1).join(" ") : "Student";

            const guardianParts = (enquiry.guardian_name || "").trim().split(/\s+/);
            const guardianFirstName = guardianParts[0] || "";
            const guardianLastName = guardianParts.length > 1 ? guardianParts.slice(1).join(" ") : "Guardian";

            return {
                enquiry: enquiry.id,
                first_name: firstName,
                last_name: lastName,
                date_of_birth: enquiry.date_of_birth || "",
                gender: enquiry.gender || "male",
                guardian_first_name: guardianFirstName,
                guardian_last_name: guardianLastName,
                guardian_relationship: enquiry.guardian_relationship || "guardian",
                guardian_phone: enquiry.guardian_phone,
                guardian_email: enquiry.guardian_email || "",
                address: enquiry.address || "",
                academic_year: enquiry.academic_year,
                level: enquiry.preferred_level,
                previous_school: enquiry.previous_school || "",
            };
        }

        it("splits compound student name into first and last name", () => {
            const enq = {
                id: "enq-123",
                student_name: "Aarav Sharma",
                guardian_name: "Rajesh Sharma",
                guardian_relationship: "father",
                guardian_phone: "9876543210",
                academic_year: "2026-2027",
                preferred_level: "lvl-5",
            };
            const mapped = mapEnquiryToApplicationDefaults(enq);
            assert.equal(mapped.first_name, "Aarav");
            assert.equal(mapped.last_name, "Sharma");
            assert.equal(mapped.guardian_first_name, "Rajesh");
            assert.equal(mapped.guardian_last_name, "Sharma");
            assert.equal(mapped.guardian_phone, "9876543210");
            assert.equal(mapped.academic_year, "2026-2027");
            assert.equal(mapped.level, "lvl-5");
        });

        it("handles single-word student name gracefully with fallback last name", () => {
            const enq = {
                id: "enq-456",
                student_name: "Pooja",
                guardian_name: "Anita",
                guardian_relationship: "mother",
                guardian_phone: "9123456789",
                academic_year: "2026-2027",
            };
            const mapped = mapEnquiryToApplicationDefaults(enq);
            assert.equal(mapped.first_name, "Pooja");
            assert.equal(mapped.last_name, "Student");
            assert.equal(mapped.guardian_first_name, "Anita");
            assert.equal(mapped.guardian_last_name, "Guardian");
        });
    });

    // 6. Conversion Rate & Metrics Calculator
    describe("Admissions Metrics Calculation", () => {
        function calculateConversionRate(enquiriesCount, convertedCount) {
            if (!enquiriesCount || enquiriesCount <= 0) return 0;
            return Math.round((convertedCount / enquiriesCount) * 1000) / 10;
        }

        it("computes accurate conversion percentage", () => {
            assert.equal(calculateConversionRate(10, 3), 30.0);
            assert.equal(calculateConversionRate(3, 1), 33.3);
            assert.equal(calculateConversionRate(0, 0), 0);
            assert.equal(calculateConversionRate(100, 75), 75.0);
        });
    });
});

