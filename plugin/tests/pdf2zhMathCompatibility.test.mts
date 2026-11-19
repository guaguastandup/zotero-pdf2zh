import assert from "node:assert/strict";
import test from "node:test";
import { supportsMathCompatibility } from "../src/modules/pdf2zhMathCompatibility.ts";

test("old and malformed Servers cannot activate math compatibility", () => {
    for (const value of [
        null,
        undefined,
        1,
        "",
        [],
        {},
        { mathCompatibility: "true" },
        { mathCompatibility: false },
    ]) {
        assert.equal(supportsMathCompatibility(value), false);
    }
    assert.equal(
        supportsMathCompatibility({ status: "ok", mathCompatibility: true }),
        true,
    );
});
