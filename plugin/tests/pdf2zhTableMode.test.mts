import assert from "node:assert/strict";
import test from "node:test";
import {
    tableModeFromPref,
    supportsTableMode,
} from "../src/modules/pdf2zhTableMode.ts";

test("unchecked or old mode preferences keep legacy behavior", () => {
    for (const value of [
        undefined,
        null,
        "",
        "unknown",
        false,
        "fixed",
        "preserve",
        "adaptive",
        "true",
    ]) {
        assert.equal(tableModeFromPref(value, true), "");
    }
    assert.equal(tableModeFromPref(true, true), "fixed");
});

test("the master table switch gates a saved prettier-table choice", () => {
    for (const master of [false, undefined, null, "true"]) {
        assert.equal(tableModeFromPref(true, master), "");
    }
    assert.equal(tableModeFromPref(false, true), "");
    assert.equal(tableModeFromPref(true, true), "fixed");
});

test("capabilities distinguish legacy servers from malformed responses", () => {
    assert.equal(supportsTableMode("fixed", {}), false);
    assert.equal(supportsTableMode("fixed", { tableModes: [] }), false);
    assert.equal(
        supportsTableMode("fixed", { tableModes: ["preserve", "fixed"] }),
        true,
    );
    for (const payload of [
        null,
        [],
        "invalid",
        { tableModes: null },
        { tableModes: [1] },
    ]) {
        assert.throws(() => supportsTableMode("fixed", payload));
    }
});
