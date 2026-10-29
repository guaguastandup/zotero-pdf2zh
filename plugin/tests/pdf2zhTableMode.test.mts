import assert from "node:assert/strict";
import test from "node:test";
import {
    tableModeFromPref,
    requireTableModeSupport,
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

test("old servers cannot silently ignore a selected mode", () => {
    assert.throws(() => requireTableModeSupport("fixed", {}));
    assert.throws(() =>
        requireTableModeSupport("adaptive", {
            tableModes: ["preserve", "fixed"],
        }),
    );
    assert.doesNotThrow(() =>
        requireTableModeSupport("fixed", { tableModes: ["preserve", "fixed"] }),
    );
});
