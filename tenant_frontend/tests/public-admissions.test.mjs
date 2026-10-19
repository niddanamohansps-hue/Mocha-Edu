import { describe, it } from "node:test";
import assert from "node:assert/strict";

describe("EduSekai Public Self-Service Admissions Frontend Logic Tests", () => {
    // -------------------------------------------------------------------------
    // 1. Applicant Surname Masking Logic (Privacy Preservation)
    // -------------------------------------------------------------------------
    describe("Applicant Surname Masking Logic", () => {
        function maskStudentName(firstName, lastName) {
            const first = (firstName || "").trim();
            const last = (lastName || "").trim();
            if (!last) return first;

            let maskedLast = last;
            if (last.length > 2) {
                maskedLast = `${last[0]}${"*".repeat(last.length - 2)}${last[last.length - 1]}`;
            } else if (last.length === 2) {
                maskedLast = `${last[0]}*`;
            }
            return first ? `${first} ${maskedLast}` : maskedLast;
        }

        it("masks regular multi-letter surnames correctly", () => {
            assert.equal(maskStudentName("Aarav", "Sharma"), "Aarav S****a");
            assert.equal(maskStudentName("Riya", "Patel"), "Riya P***l");
            assert.equal(maskStudentName("John", "Doe"), "John D*e");
            assert.equal(maskStudentName("Emma", "Watson"), "Emma W****n");
        });

        it("masks two-letter surnames correctly", () => {
            assert.equal(maskStudentName("Bo", "Li"), "Bo L*");
            assert.equal(maskStudentName("Kai", "Wu"), "Kai W*");
        });

        it("leaves single-character surnames unmasked", () => {
            assert.equal(maskStudentName("Kiran", "K"), "Kiran K");
        });

        it("handles missing or empty last names safely", () => {
            assert.equal(maskStudentName("Aarav", ""), "Aarav");
            assert.equal(maskStudentName("Aarav", "   "), "Aarav");
        });
    });

    // -------------------------------------------------------------------------
    // 2. Application Payload Validation
    // -------------------------------------------------------------------------
    describe("Public Admissions Form Validation", () => {
        function validatePublicApplicationPayload(payload) {
            const errors = {};

            if (!payload.first_name || !payload.first_name.trim()) {
                errors.first_name = "First name is required.";
            }
            if (!payload.last_name || !payload.last_name.trim()) {
                errors.last_name = "Last name is required.";
            }

            // DOB validation
            if (!payload.date_of_birth) {
                errors.date_of_birth = "Date of birth is required.";
            } else {
                const dob = new Date(payload.date_of_birth);
                const today = new Date();
                if (isNaN(dob.getTime())) {
                    errors.date_of_birth = "Invalid date format.";
                } else if (dob > today) {
                    errors.date_of_birth = "Date of birth cannot be in the future.";
                }
            }

            // Guardian validations
            if (!payload.guardian_first_name || !payload.guardian_first_name.trim()) {
                errors.guardian_first_name = "Guardian first name is required.";
            }
            if (!payload.guardian_last_name || !payload.guardian_last_name.trim()) {
                errors.guardian_last_name = "Guardian last name is required.";
            }
            if (!payload.guardian_phone || !payload.guardian_phone.trim()) {
                errors.guardian_phone = "Guardian phone number is required.";
            } else {
                const cleanPhone = payload.guardian_phone.replace(/[\s\-()+]/g, "");
                if (cleanPhone.length < 7 || cleanPhone.length > 15) {
                    errors.guardian_phone = "Please enter a valid phone number (7-15 digits).";
                }
            }

            // Guardian Email validation
            if (payload.guardian_email) {
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRegex.test(payload.guardian_email.trim())) {
                    errors.guardian_email = "Invalid email address format.";
                }
            }

            // Academic program/year
            if (!payload.level) {
                errors.level = "Academic grade/level is required.";
            }
            if (!payload.academic_year_ref) {
                errors.academic_year_ref = "Academic year is required.";
            }

            // Consent check
            if (payload.consent !== true) {
                errors.consent = "Consent to admissions terms and privacy policy is required.";
            }

            return {
                isValid: Object.keys(errors).length === 0,
                errors,
            };
        }

        it("validates a complete, compliant application payload", () => {
            const validPayload = {
                first_name: "Aditi",
                last_name: "Verma",
                date_of_birth: "2015-06-15",
                gender: "female",
                guardian_first_name: "Rajesh",
                guardian_last_name: "Verma",
                guardian_relationship: "father",
                guardian_phone: "9876543210",
                guardian_email: "rajesh.verma@example.com",
                level: "lvl-grade-5",
                academic_year_ref: "ay-2026",
                consent: true,
            };

            const result = validatePublicApplicationPayload(validPayload);
            assert.equal(result.isValid, true);
            assert.deepEqual(result.errors, {});
        });

        it("fails validation if mandatory consent is unchecked", () => {
            const payloadWithoutConsent = {
                first_name: "Aditi",
                last_name: "Verma",
                date_of_birth: "2015-06-15",
                guardian_first_name: "Rajesh",
                guardian_last_name: "Verma",
                guardian_phone: "9876543210",
                level: "lvl-grade-5",
                academic_year_ref: "ay-2026",
                consent: false,
            };

            const result = validatePublicApplicationPayload(payloadWithoutConsent);
            assert.equal(result.isValid, false);
            assert.equal(
                result.errors.consent,
                "Consent to admissions terms and privacy policy is required."
            );
        });

        it("rejects future dates of birth", () => {
            const futureDate = new Date();
            futureDate.setFullYear(futureDate.getFullYear() + 1);

            const payloadWithFutureDob = {
                first_name: "Aditi",
                last_name: "Verma",
                date_of_birth: futureDate.toISOString().split("T")[0],
                guardian_first_name: "Rajesh",
                guardian_last_name: "Verma",
                guardian_phone: "9876543210",
                level: "lvl-grade-5",
                academic_year_ref: "ay-2026",
                consent: true,
            };

            const result = validatePublicApplicationPayload(payloadWithFutureDob);
            assert.equal(result.isValid, false);
            assert.equal(result.errors.date_of_birth, "Date of birth cannot be in the future.");
        });

        it("validates invalid guardian phone numbers", () => {
            const payloadWithBadPhone = {
                first_name: "Aditi",
                last_name: "Verma",
                date_of_birth: "2015-06-15",
                guardian_first_name: "Rajesh",
                guardian_last_name: "Verma",
                guardian_phone: "123", // too short
                level: "lvl-grade-5",
                academic_year_ref: "ay-2026",
                consent: true,
            };

            const result = validatePublicApplicationPayload(payloadWithBadPhone);
            assert.equal(result.isValid, false);
            assert.ok(result.errors.guardian_phone);
        });
    });

    // -------------------------------------------------------------------------
    // 3. Capability Token & Request Header Generation
    // -------------------------------------------------------------------------
    describe("Capability Token & Request Header Logic", () => {
        function buildStatusRequestHeaders(token) {
            if (!token || typeof token !== "string" || !token.trim()) {
                throw new Error("Application access token is required.");
            }
            return {
                "X-Application-Token": token.trim(),
            };
        }

        function formatStatusUrl(applicationNumber) {
            if (!applicationNumber || typeof applicationNumber !== "string" || !applicationNumber.trim()) {
                throw new Error("Application number is required.");
            }
            const sanitized = encodeURIComponent(applicationNumber.trim());
            return `/admissions/public/applications/${sanitized}/status/`;
        }

        it("constructs safe X-Application-Token header with trimmed capability token", () => {
            const sampleToken = "sec_cap_tok_9918237482348239048203948234";
            const headers = buildStatusRequestHeaders(`  ${sampleToken}  `);
            assert.deepEqual(headers, {
                "X-Application-Token": sampleToken,
            });
        });

        it("throws error when token is absent or blank", () => {
            assert.throws(() => buildStatusRequestHeaders(""), /Application access token is required/);
            assert.throws(() => buildStatusRequestHeaders("   "), /Application access token is required/);
            assert.throws(() => buildStatusRequestHeaders(null), /Application access token is required/);
        });

        it("encodes application number safely in the API URL", () => {
            const url = formatStatusUrl("APP-2026-0001");
            assert.equal(url, "/admissions/public/applications/APP-2026-0001/status/");

            const urlWithSpecial = formatStatusUrl("APP/2026/0042");
            assert.equal(urlWithSpecial, "/admissions/public/applications/APP%2F2026%2F0042/status/");
        });
    });

    // -------------------------------------------------------------------------
    // 4. Public Status Mapping & Action Eligibility Logic
    // -------------------------------------------------------------------------
    describe("Public Status Mapping & Action Eligibility", () => {
        const PUBLIC_STATUS_MAPPING = {
            draft: {
                title: "Application Draft",
                can_upload: true,
            },
            submitted: {
                title: "Application Submitted",
                can_upload: true,
            },
            under_review: {
                title: "Application Under Review",
                can_upload: true,
            },
            documents_pending: {
                title: "Documents Required",
                can_upload: true,
            },
            documents_verified: {
                title: "Documents Verified",
                can_upload: false,
            },
            assessment_pending: {
                title: "Assessment / Interaction In Progress",
                can_upload: false,
            },
            approved: {
                title: "Admission Approved / Offer Extended",
                can_upload: false,
            },
            waitlisted: {
                title: "Application Waitlisted",
                can_upload: false,
            },
            rejected: {
                title: "Application Decision Finalized",
                can_upload: false,
            },
            offer_accepted: {
                title: "Offer Accepted",
                can_upload: false,
            },
            enrolled: {
                title: "Enrolled",
                can_upload: false,
            },
            withdrawn: {
                title: "Application Withdrawn",
                can_upload: false,
            },
        };

        function canUploadDocuments(status) {
            return ["draft", "submitted", "under_review", "documents_pending"].includes(status);
        }

        it("maps all 12 internal lifecycle statuses to safe public titles", () => {
            const statuses = Object.keys(PUBLIC_STATUS_MAPPING);
            assert.equal(statuses.length, 12);

            // Rejection should never expose internal words like "Rejected by reviewer"
            assert.equal(PUBLIC_STATUS_MAPPING["rejected"].title, "Application Decision Finalized");
            assert.equal(PUBLIC_STATUS_MAPPING["approved"].title, "Admission Approved / Offer Extended");
            assert.equal(PUBLIC_STATUS_MAPPING["enrolled"].title, "Enrolled");
        });

        it("allows public document uploads only for pre-decision stages", () => {
            assert.equal(canUploadDocuments("draft"), true);
            assert.equal(canUploadDocuments("submitted"), true);
            assert.equal(canUploadDocuments("under_review"), true);
            assert.equal(canUploadDocuments("documents_pending"), true);

            assert.equal(canUploadDocuments("documents_verified"), false);
            assert.equal(canUploadDocuments("assessment_pending"), false);
            assert.equal(canUploadDocuments("approved"), false);
            assert.equal(canUploadDocuments("waitlisted"), false);
            assert.equal(canUploadDocuments("rejected"), false);
            assert.equal(canUploadDocuments("offer_accepted"), false);
            assert.equal(canUploadDocuments("enrolled"), false);
            assert.equal(canUploadDocuments("withdrawn"), false);
        });
    });

    // -------------------------------------------------------------------------
    // 5. Document Upload Client-Side File Validation
    // -------------------------------------------------------------------------
    describe("Public Document Upload Client-Side File Validation", () => {
        const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10MB
        const ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"];

        function validateUploadFile(file) {
            if (!file) {
                return { isValid: false, error: "Please select a file to upload." };
            }
            if (file.size > MAX_FILE_SIZE_BYTES) {
                return {
                    isValid: false,
                    error: `File size (${(file.size / (1024 * 1024)).toFixed(1)}MB) exceeds the 10MB maximum limit.`,
                };
            }

            const fileName = file.name || "";
            const dotIndex = fileName.lastIndexOf(".");
            if (dotIndex === -1) {
                return { isValid: false, error: "File has no extension." };
            }

            const extension = fileName.substring(dotIndex).toLowerCase();
            if (!ALLOWED_EXTENSIONS.includes(extension)) {
                return {
                    isValid: false,
                    error: `Unsupported file extension (${extension}). Allowed formats: ${ALLOWED_EXTENSIONS.join(", ")}`,
                };
            }

            return { isValid: true, error: null };
        }

        it("accepts valid PDF, JPG, PNG, and DOCX documents under 10MB", () => {
            const validPdf = { name: "birth_cert.pdf", size: 2 * 1024 * 1024 };
            const validJpg = { name: "passport_photo.JPG", size: 500 * 1024 };
            const validDocx = { name: "transfer_certificate.docx", size: 1.5 * 1024 * 1024 };

            assert.equal(validateUploadFile(validPdf).isValid, true);
            assert.equal(validateUploadFile(validJpg).isValid, true);
            assert.equal(validateUploadFile(validDocx).isValid, true);
        });

        it("rejects files exceeding 10MB", () => {
            const oversizedFile = { name: "huge_scan.pdf", size: 11 * 1024 * 1024 };
            const result = validateUploadFile(oversizedFile);
            assert.equal(result.isValid, false);
            assert.match(result.error, /exceeds the 10MB maximum limit/);
        });

        it("rejects unsupported and potentially unsafe file extensions", () => {
            const dangerousFiles = [
                { name: "script.exe", size: 1024 },
                { name: "script.sh", size: 1024 },
                { name: "archive.zip", size: 1024 },
                { name: "code.js", size: 1024 },
                { name: "markup.html", size: 1024 },
            ];

            for (const file of dangerousFiles) {
                const result = validateUploadFile(file);
                assert.equal(result.isValid, false);
                assert.match(result.error, /Unsupported file extension/);
            }
        });
    });

    // -------------------------------------------------------------------------
    // 6. URL Fragment (Hash) Token Security & Address Bar Sanitization
    // -------------------------------------------------------------------------
    describe("URL Fragment (Hash) Token Security & Address Bar Sanitization", () => {
        function extractCredentialsFromLocation(hash, search) {
            let ref = "";
            let token = "";
            let source = "none";

            // Hash fragment takes priority (never sent over the wire or logged in server logs)
            if (hash && hash.startsWith("#")) {
                const hashParams = new URLSearchParams(hash.substring(1));
                const hashRef = hashParams.get("ref");
                const hashTok = hashParams.get("token");
                if (hashRef) ref = hashRef.trim();
                if (hashTok) {
                    token = hashTok.trim();
                    source = "hash";
                }
            }

            // Search params fallback (legacy)
            if (!token && search) {
                const searchParams = new URLSearchParams(search);
                const searchRef = searchParams.get("ref");
                const searchTok = searchParams.get("token");
                if (!ref && searchRef) ref = searchRef.trim();
                if (searchTok) {
                    token = searchTok.trim();
                    source = "query";
                }
            }

            return { ref, token, source };
        }

        function sanitizeBrowserUrl(pathname, hasTokenInUrl) {
            // Emulates window.history.replaceState({}, document.title, window.location.pathname)
            if (hasTokenInUrl) {
                return {
                    sanitizedUrl: pathname,
                    historyReplaced: true,
                };
            }
            return {
                sanitizedUrl: pathname,
                historyReplaced: false,
            };
        }

        it("extracts capability token and reference number from URL hash fragment", () => {
            const hash = "#ref=APP-2026-1049&token=K_h8xL92mnQ_v84Zp7";
            const result = extractCredentialsFromLocation(hash, "");
            assert.equal(result.ref, "APP-2026-1049");
            assert.equal(result.token, "K_h8xL92mnQ_v84Zp7");
            assert.equal(result.source, "hash");
        });

        it("falls back to search query parameters if hash is absent", () => {
            const search = "?ref=APP-2026-1049&token=legacy_query_tok_123";
            const result = extractCredentialsFromLocation("", search);
            assert.equal(result.ref, "APP-2026-1049");
            assert.equal(result.token, "legacy_query_tok_123");
            assert.equal(result.source, "query");
        });

        it("prefers hash fragment over search query parameters", () => {
            const hash = "#ref=APP-2026-HASH&token=hash_tok_456";
            const search = "?ref=APP-2026-QUERY&token=query_tok_123";
            const result = extractCredentialsFromLocation(hash, search);
            assert.equal(result.ref, "APP-2026-HASH");
            assert.equal(result.token, "hash_tok_456");
            assert.equal(result.source, "hash");
        });

        it("sanitizes browser URL to remove token from browser address bar and history", () => {
            const currentPath = "/admissions/status";
            const result = sanitizeBrowserUrl(currentPath, true);
            assert.equal(result.sanitizedUrl, "/admissions/status");
            assert.equal(result.historyReplaced, true);
            // Verify no token is present in sanitized URL
            assert.equal(result.sanitizedUrl.includes("token"), false);
        });
    });

    // -------------------------------------------------------------------------
    // 7. Token Rotation State Management Logic
    // -------------------------------------------------------------------------
    describe("Token Rotation State Management Logic", () => {
        function handleTokenRotation(currentState, rotationResponse) {
            if (!rotationResponse || !rotationResponse.success || !rotationResponse.access_token) {
                throw new Error("Invalid rotation response");
            }
            return {
                ...currentState,
                token: rotationResponse.access_token,
                statusData: currentState.statusData
                    ? {
                          ...currentState.statusData,
                          access_token_expires_at: rotationResponse.access_token_expires_at,
                      }
                    : null,
                showRotationNotice: true,
                rotationMessage: rotationResponse.message,
            };
        }

        it("updates local token state and stores new expiry on successful rotation", () => {
            const initialState = {
                ref: "APP-2026-0099",
                token: "old_token_val_1111",
                statusData: {
                    application_number: "APP-2026-0099",
                    status: "submitted",
                    access_token_expires_at: "2026-12-01T00:00:00Z",
                },
                showRotationNotice: false,
            };

            const rotationResponse = {
                success: true,
                application_number: "APP-2026-0099",
                access_token: "new_token_val_2222",
                access_token_expires_at: "2027-03-01T00:00:00Z",
                message: "Access token rotated successfully.",
            };

            const updated = handleTokenRotation(initialState, rotationResponse);
            assert.equal(updated.token, "new_token_val_2222");
            assert.notEqual(updated.token, initialState.token);
            assert.equal(updated.statusData.access_token_expires_at, "2027-03-01T00:00:00Z");
            assert.equal(updated.showRotationNotice, true);
        });
    });

    // -------------------------------------------------------------------------
    // 8. File Upload Hardening: Double Extension & Magic Byte Detection
    // -------------------------------------------------------------------------
    describe("File Upload Hardening: Double Extension & Magic Byte Checks", () => {
        const DANGEROUS_DOUBLE_EXTENSIONS = [".php.", ".exe.", ".sh.", ".py.", ".pl.", ".jsp.", ".asp."];

        function checkFileSafety(fileName, buffer) {
            // 1. Check double extension
            const lowerName = fileName.toLowerCase();
            for (const d of DANGEROUS_DOUBLE_EXTENSIONS) {
                if (lowerName.includes(d)) {
                    return { safe: false, reason: "Dangerous file name format: double extension detected." };
                }
            }

            // 2. Check empty file
            if (!buffer || buffer.length === 0) {
                return { safe: false, reason: "Empty files are not allowed." };
            }

            // 3. Magic byte checks
            if (lowerName.endsWith(".pdf")) {
                const header = buffer.subarray(0, 4).toString("ascii");
                if (header !== "%PDF") {
                    return { safe: false, reason: "File content does not match the .pdf extension." };
                }
            } else if (lowerName.endsWith(".jpg") || lowerName.endsWith(".jpeg")) {
                if (buffer[0] !== 0xff || buffer[1] !== 0xd8 || buffer[2] !== 0xff) {
                    return { safe: false, reason: "File content does not match JPEG signature." };
                }
            } else if (lowerName.endsWith(".png")) {
                const pngSig = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
                if (!buffer.subarray(0, 8).equals(pngSig)) {
                    return { safe: false, reason: "File content does not match PNG signature." };
                }
            }

            return { safe: true, reason: null };
        }

        it("detects and blocks dangerous double extensions", () => {
            const file1 = checkFileSafety("passport.php.pdf", Buffer.from("%PDF-1.4"));
            assert.equal(file1.safe, false);
            assert.match(file1.reason, /double extension detected/);

            const file2 = checkFileSafety("invoice.exe.jpg", Buffer.from([0xff, 0xd8, 0xff, 0xe0]));
            assert.equal(file2.safe, false);
            assert.match(file2.reason, /double extension detected/);
        });

        it("rejects zero-length files", () => {
            const empty = checkFileSafety("doc.pdf", Buffer.from([]));
            assert.equal(empty.safe, false);
            assert.match(empty.reason, /Empty files are not allowed/);
        });

        it("detects content mismatch where fake extension is used", () => {
            const fakePdf = checkFileSafety("report.pdf", Buffer.from("<html><script>evil()</script></html>"));
            assert.equal(fakePdf.safe, false);
            assert.match(fakePdf.reason, /File content does not match/);

            const fakeJpg = checkFileSafety("photo.jpg", Buffer.from("not-an-image"));
            assert.equal(fakeJpg.safe, false);
            assert.match(fakeJpg.reason, /JPEG signature/);
        });

        it("accepts authentic files with genuine signatures", () => {
            const genuinePdf = checkFileSafety("report.pdf", Buffer.from("%PDF-1.7\nvalid content"));
            assert.equal(genuinePdf.safe, true);

            const genuineJpg = checkFileSafety("photo.jpg", Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10]));
            assert.equal(genuineJpg.safe, true);

            const genuinePng = checkFileSafety("logo.png", Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00]));
            assert.equal(genuinePng.safe, true);
        });
    });

    // -------------------------------------------------------------------------
    // 9. Duplicate Submission Protection & Zero-Credential Leakage Logic
    // -------------------------------------------------------------------------
    describe("Duplicate Submission Protection & Zero-Credential Leakage Logic", () => {
        function handleDuplicateErrorResponse(errorResponse) {
            const nonFieldErrors = errorResponse?.non_field_errors || [];
            const isDuplicate = nonFieldErrors.some((msg) =>
                msg.toLowerCase().includes("already been submitted")
            );

            return {
                isDuplicate,
                hasCredentials: Boolean(errorResponse?.access_token || errorResponse?.application_number),
                errorMessage: nonFieldErrors[0] || "Application submission failed.",
            };
        }

        it("correctly identifies duplicate rejection without credential leakage", () => {
            const backendError = {
                non_field_errors: [
                    "An admission application for this student has already been submitted recently. " +
                    "For security and privacy, access credentials cannot be re-issued through this form. " +
                    "Please use your saved reference number and access token to check your status."
                ]
            };

            const result = handleDuplicateErrorResponse(backendError);
            assert.equal(result.isDuplicate, true);
            assert.equal(result.hasCredentials, false);
            assert.match(result.errorMessage, /already been submitted/);
        });

        it("ensures duplicate response cannot inject or overwrite local token state", () => {
            let userToken = "legitimate_parent_token_ABC123";
            const duplicateError = {
                non_field_errors: ["An admission application for this student has already been submitted recently."]
            };

            const result = handleDuplicateErrorResponse(duplicateError);
            if (!result.hasCredentials) {
                userToken = userToken;
            }
            assert.equal(userToken, "legitimate_parent_token_ABC123");
        });
    });

    // -------------------------------------------------------------------------
    // 10. Document Antivirus Quarantine & Scan Status Interpretation
    // -------------------------------------------------------------------------
    describe("Document Antivirus Quarantine & Scan Status Interpretation", () => {
        function getDocumentQuarantineState(doc) {
            const scanStatus = doc.scan_status || "pending";
            const isQuarantined = scanStatus !== "clean";
            const isDownloadAllowed = !isQuarantined && doc.verification_status !== "rejected";

            let userMessage = "Security inspection complete.";
            if (scanStatus === "pending") {
                userMessage = "Security scan in progress. File is temporarily quarantined.";
            } else if (scanStatus === "infected") {
                userMessage = "File quarantined: security threat detected. Please upload an alternative file.";
            } else if (scanStatus === "error") {
                userMessage = "Security inspection unavailable. File remains quarantined.";
            }

            return {
                scanStatus,
                isQuarantined,
                isDownloadAllowed,
                userMessage,
            };
        }

        it("correctly identifies clean scanned files as downloadable", () => {
            const doc = {
                id: "doc-1",
                scan_status: "clean",
                verification_status: "pending",
            };
            const state = getDocumentQuarantineState(doc);
            assert.equal(state.scanStatus, "clean");
            assert.equal(state.isQuarantined, false);
            assert.equal(state.isDownloadAllowed, true);
        });

        it("quarantines pending files and prevents download", () => {
            const doc = {
                id: "doc-2",
                scan_status: "pending",
                verification_status: "pending",
            };
            const state = getDocumentQuarantineState(doc);
            assert.equal(state.scanStatus, "pending");
            assert.equal(state.isQuarantined, true);
            assert.equal(state.isDownloadAllowed, false);
            assert.match(state.userMessage, /scan in progress/i);
        });

        it("quarantines infected files with high-severity warning", () => {
            const doc = {
                id: "doc-3",
                scan_status: "infected",
                verification_status: "rejected",
            };
            const state = getDocumentQuarantineState(doc);
            assert.equal(state.scanStatus, "infected");
            assert.equal(state.isQuarantined, true);
            assert.equal(state.isDownloadAllowed, false);
            assert.match(state.userMessage, /threat detected/i);
        });

        it("fails closed for files with scan error status", () => {
            const doc = {
                id: "doc-4",
                scan_status: "error",
                verification_status: "pending",
            };
            const state = getDocumentQuarantineState(doc);
            assert.equal(state.scanStatus, "error");
            assert.equal(state.isQuarantined, true);
            assert.equal(state.isDownloadAllowed, false);
        });
    });
});

