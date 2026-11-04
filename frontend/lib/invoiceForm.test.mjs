// Self-check for buildPatch: `node --experimental-strip-types lib/invoiceForm.test.mjs`
import assert from "node:assert/strict";
import { buildPatch, toForm, toRows } from "./invoiceForm.ts";

const inv = {
  invoice_number: "A-1", invoice_date: null, supplier_name: "Acme", customer_name: null,
  subtotal: "365.20", tax: "18.26", total: "383.46", currency: "EUR",
  line_items: [{ description: "Chair", quantity: "2.00", unit_price: "182.60", amount: "365.20" }],
};

const form = toForm(inv);
assert.equal(form.invoice_date, "", "null renders as empty, not 0");
assert.deepEqual(buildPatch(inv, form, toRows(inv.line_items)), {}, "no edits, empty patch");
assert.deepEqual(buildPatch(inv, { ...form, subtotal: "365.2" }, toRows(inv.line_items)), {}, "same number is not a change");
assert.deepEqual(buildPatch(inv, { ...form, supplier_name: " " }, toRows(inv.line_items)), { supplier_name: null }, "blank clears");
assert.deepEqual(buildPatch(inv, { ...form, currency: "usd" }, toRows(inv.line_items)), { currency: "USD" });
assert.deepEqual(buildPatch(inv, form, []), { line_items: [] }, "removing all rows sends empty list");
const rows = [...toRows(inv.line_items), { description: "Desk", quantity: "", unit_price: "", amount: "10" }];
assert.deepEqual(buildPatch(inv, form, rows).line_items[1], { description: "Desk", quantity: null, unit_price: null, amount: "10" });
console.log("invoiceForm: all checks passed");
