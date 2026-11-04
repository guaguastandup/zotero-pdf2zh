import assert from "node:assert/strict";
import test from "node:test";
import { supportsReferenceSkip } from "../src/modules/pdf2zhReferenceSkip.ts";

test("old and malformed Servers cannot activate Reference Skip", () => {
    for (const value of [
        null,
        undefined,
        1,
        "",
        [],
        {},
        { referenceSkip: "true" },
        { referenceSkip: false },
    ]) {
        assert.equal(supportsReferenceSkip(value), false);
    }
    assert.equal(
        supportsReferenceSkip({ status: "ok", referenceSkip: true }),
        true,
    );
});
