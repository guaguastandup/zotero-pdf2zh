import assert from "node:assert/strict";
import test from "node:test";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
test("build generator includes runtime resources and excludes private state", () => {
    const plugin = new URL("../", import.meta.url);
    execFileSync(process.execPath, [
        fileURLToPath(new URL("scripts/bundle-server.mjs", plugin)),
    ]);
    const bundle = JSON.parse(
        readFileSync(
            new URL("addon/content/bundled-server.json", plugin),
            "utf8",
        ),
    );
    const names = bundle.files.map((f: { path: string }) => f.path);
    for (const p of [
        "server.py",
        "utils/config.py",
        "utils/venv.py",
        "index.html",
        "bo.mp3",
        "requirements.txt",
        "config/config.json.example",
        "config/config.toml.example",
        "config/venv.json.example",
    ])
        assert(names.includes(p), p);
    for (const p of names)
        assert(
            !/^(tests|doc|logs|translated|\.venv)\/|\.pdf$|^config\/(?:config\.(?:json|toml)|venv\.json)$/.test(
                p,
            ),
            p,
        );
    for (const f of bundle.files)
        assert.equal(
            createHash("sha256")
                .update(Buffer.from(f.base64, "base64"))
                .digest("hex"),
            f.sha256,
        );
});
