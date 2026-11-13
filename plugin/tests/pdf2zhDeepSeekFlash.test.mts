import assert from "node:assert/strict";
import test from "node:test";
import {
    needsDeepSeekFlashPatch,
    supportsDeepSeekFlashPatch,
} from "../src/modules/pdf2zhDeepSeekFlash.ts";

test("only DeepSeek Flash uses the hook; other providers stay unchanged", () => {
    assert.equal(
        needsDeepSeekFlashPatch({
            service: "deepseek",
            model: "deepseek-flash",
        }),
        true,
    );
    assert.equal(
        needsDeepSeekFlashPatch({
            service: "deepseek",
            model: " deepseek-flash ",
        }),
        true,
    );
    for (const value of [
        null,
        {},
        { service: "deepseek", model: "deepseek-v4-flash" },
        { service: "deepseek", model: "DeepSeek-Flash" },
        { service: "deepseek", model: "deepseek-v4-pro" },
        { service: "openailiked", model: "deepseek-flash" },
    ]) {
        assert.equal(needsDeepSeekFlashPatch(value), false);
    }
});

test("old Server cannot silently send a costly Flash request", () => {
    for (const value of [
        null,
        {},
        [],
        1,
        { deepseekFlashThinkingPatch: false },
        { deepseekFlashThinkingPatch: "true" },
    ]) {
        assert.equal(supportsDeepSeekFlashPatch(value), false);
    }
    assert.equal(
        supportsDeepSeekFlashPatch({ deepseekFlashThinkingPatch: true }),
        true,
    );
});
