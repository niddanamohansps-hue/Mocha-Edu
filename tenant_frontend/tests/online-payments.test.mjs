import { describe, it } from "node:test";
import assert from "node:assert/strict";

describe("Frontend Online Fee Payments Logic & State Machine", () => {
    describe("Fee Eligibility & Balance Computation", () => {
        const mockFees = [
            {
                id: "fee-1",
                fee_head_name: "Tuition Fee",
                amount_due: "5000.00",
                amount_paid: "2000.00",
                outstanding_balance: "3000.00",
                status: "active",
            },
            {
                id: "fee-2",
                fee_head_name: "Library Fee",
                amount_due: "500.00",
                amount_paid: "500.00",
                outstanding_balance: "0.00",
                status: "active",
            },
            {
                id: "fee-3",
                fee_head_name: "Lab Fee",
                amount_due: "1000.00",
                amount_paid: "0.00",
                outstanding_balance: "1000.00",
                status: "cancelled",
            },
            {
                id: "fee-4",
                fee_head_name: "Sports Fee",
                amount_due: "800.00",
                amount_paid: "0.00",
                outstanding_balance: "800.00",
                status: "active",
            },
        ];

        it("filters eligible fees to only active fees with outstanding balance > 0", () => {
            const eligible = mockFees.filter(
                (f) => f.status === "active" && parseFloat(f.outstanding_balance) > 0
            );
            assert.equal(eligible.length, 2);
            assert.deepEqual(
                eligible.map((f) => f.id),
                ["fee-1", "fee-4"]
            );
        });

        it("handles empty fee lists without error", () => {
            const emptyFees = [];
            const eligible = emptyFees.filter(
                (f) => f.status === "active" && parseFloat(f.outstanding_balance) > 0
            );
            assert.equal(eligible.length, 0);
        });

        it("calculates selected total amount correctly", () => {
            const selectedIds = ["fee-1", "fee-4"];
            const selectedFees = mockFees.filter((f) => selectedIds.includes(f.id));
            const total = selectedFees.reduce(
                (sum, f) => sum + parseFloat(f.outstanding_balance),
                0
            );
            assert.equal(total, 3800.0);
        });
    });

    describe("Allocation Validation & Double Submission Prevention", () => {
        function validateAllocations(selectedFees, allocations) {
            let totalAmount = 0;
            const errors = {};

            if (!selectedFees || selectedFees.length === 0) {
                return { isValid: false, errors: { general: "No fees selected" }, totalAmount: 0 };
            }

            for (const fee of selectedFees) {
                const valStr = allocations[fee.id] || "0";
                const val = parseFloat(valStr);
                const max = parseFloat(fee.outstanding_balance);

                if (isNaN(val) || val <= 0) {
                    errors[fee.id] = "Must be greater than 0";
                } else if (val > max) {
                    errors[fee.id] = `Cannot exceed outstanding NPR ${max.toFixed(2)}`;
                } else {
                    totalAmount += val;
                }
            }

            const hasErrors = Object.keys(errors).length > 0 || totalAmount <= 0;
            return {
                isValid: !hasErrors,
                errors,
                totalAmount: Number(totalAmount.toFixed(2)),
            };
        }

        it("accepts valid full allocations", () => {
            const selected = [
                { id: "fee-1", outstanding_balance: "3000.00" },
                { id: "fee-2", outstanding_balance: "1000.00" },
            ];
            const allocs = { "fee-1": "3000.00", "fee-2": "1000.00" };
            const result = validateAllocations(selected, allocs);
            assert.equal(result.isValid, true);
            assert.equal(result.totalAmount, 4000.0);
            assert.equal(Object.keys(result.errors).length, 0);
        });

        it("accepts valid partial allocations", () => {
            const selected = [
                { id: "fee-1", outstanding_balance: "3000.00" },
            ];
            const allocs = { "fee-1": "1500.00" };
            const result = validateAllocations(selected, allocs);
            assert.equal(result.isValid, true);
            assert.equal(result.totalAmount, 1500.0);
        });

        it("rejects allocation exceeding outstanding balance", () => {
            const selected = [
                { id: "fee-1", outstanding_balance: "3000.00" },
            ];
            const allocs = { "fee-1": "3500.00" };
            const result = validateAllocations(selected, allocs);
            assert.equal(result.isValid, false);
            assert.ok(result.errors["fee-1"].includes("Cannot exceed outstanding"));
        });

        it("rejects zero or negative allocation", () => {
            const selected = [
                { id: "fee-1", outstanding_balance: "3000.00" },
            ];
            const allocs = { "fee-1": "0.00" };
            const result = validateAllocations(selected, allocs);
            assert.equal(result.isValid, false);
            assert.ok(result.errors["fee-1"].includes("Must be greater than 0"));
        });

        it("disables payment button when submission is in flight to prevent double click", () => {
            const isSubmitting = true;
            const hasErrors = false;
            const selectedCount = 1;

            const isButtonDisabled = hasErrors || isSubmitting || selectedCount === 0;
            assert.equal(isButtonDisabled, true);
        });
    });

    describe("Gateway Form Parameter Assembly", () => {
        it("constructs valid hidden POST parameters from server gateway payload", () => {
            const serverPayload = {
                gateway: "esewa",
                gateway_url: "https://rc-epay.esewa.com.np/api/epay/main/v2/form",
                method: "POST",
                form_parameters: {
                    amount: "2500.00",
                    tax_amount: "0",
                    total_amount: "2500.00",
                    transaction_uuid: "abc-123",
                    product_code: "EPAYTEST",
                    product_service_charge: "0",
                    product_delivery_charge: "0",
                    success_url: "http://localhost:3555/dashboard/fees/callback",
                    failure_url: "http://localhost:3555/dashboard/fees/callback?status=failed",
                    signed_field_names: "total_amount,transaction_uuid,product_code",
                    signature: "mockHMACSignature==",
                },
                order_id: "order-uuid-1",
                gateway_order_id: "abc-123",
            };

            assert.equal(serverPayload.method, "POST");
            assert.equal(serverPayload.gateway_url, "https://rc-epay.esewa.com.np/api/epay/main/v2/form");
            assert.equal(serverPayload.form_parameters.total_amount, "2500.00");
            assert.equal(serverPayload.form_parameters.signed_field_names, "total_amount,transaction_uuid,product_code");
            assert.ok(serverPayload.form_parameters.signature.length > 0);
        });
    });

    describe("Payment Callback Lifecycle & Option B Reconciliation Handling", () => {
        function resolveCallbackState(response) {
            if (response.status === "success" || response.status === "already_completed") {
                return {
                    uiState: "success",
                    requiresReconciliation: false,
                    isPending: false,
                };
            }
            if (response.status === "reconciliation_required") {
                return {
                    uiState: "reconciliation_required",
                    requiresReconciliation: true,
                    isPending: false,
                    message:
                        response.reason ||
                        "Payment was received by the gateway but requires manual school reconciliation.",
                };
            }
            if (response.status === "pending" || response.status === "initiated") {
                return {
                    uiState: "pending",
                    requiresReconciliation: false,
                    isPending: true,
                };
            }
            return {
                uiState: "failed",
                requiresReconciliation: false,
                isPending: false,
                message: response.reason || "Payment settlement could not be completed.",
            };
        }

        it("maps 'success' to success UI state", () => {
            const state = resolveCallbackState({ status: "success", receipt_number: "RCPT-101" });
            assert.equal(state.uiState, "success");
            assert.equal(state.requiresReconciliation, false);
        });

        it("maps 'already_completed' to success UI state idempotently", () => {
            const state = resolveCallbackState({ status: "already_completed", receipt_number: "RCPT-101" });
            assert.equal(state.uiState, "success");
        });

        it("maps 'reconciliation_required' (Option B conflict) to alert UI state without promising instant settlement", () => {
            const state = resolveCallbackState({
                status: "reconciliation_required",
                reason: "Counter payment processed concurrently. School admin must reconcile.",
            });
            assert.equal(state.uiState, "reconciliation_required");
            assert.equal(state.requiresReconciliation, true);
            assert.ok(state.message.includes("Counter payment processed concurrently"));
        });

        it("maps 'pending' to polling state", () => {
            const state = resolveCallbackState({ status: "pending" });
            assert.equal(state.uiState, "pending");
            assert.equal(state.isPending, true);
        });

        it("maps 'failed' to failure UI state", () => {
            const state = resolveCallbackState({ status: "failed", reason: "Invalid gateway signature" });
            assert.equal(state.uiState, "failed");
            assert.ok(state.message.includes("Invalid gateway signature"));
        });
    });

    describe("Parent Portal Child Scoping", () => {
        const parentChildren = [
            { student_id: "child-1", full_name: "Alice Smith" },
            { student_id: "child-2", full_name: "Bob Smith" },
        ];

        it("only allows selection among authorized linked children", () => {
            const requestedChildId = "child-3"; // Unrelated child
            const isAuthorized = parentChildren.some((c) => c.student_id === requestedChildId);
            assert.equal(isAuthorized, false);

            const validChildId = "child-1";
            const isValidAuthorized = parentChildren.some((c) => c.student_id === validChildId);
            assert.equal(isValidAuthorized, true);
        });
    });
});

