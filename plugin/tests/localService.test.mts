import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
    createPDF2zhLocalService,
    pdf2zhLaunchCommand,
} from "../src/modules/localService.ts";
const READY = {
    status: "ok",
    version: "4.1.8",
    message: "PDF2zh Server is running",
};
function fixture(options = {}) {
    const prefs = {
        new_serverip: "http://localhost:8890",
        local_service_auto_start: true,
        local_service_directory: "E:\\Test user's folder\\PDF2zh",
        ...options.prefs,
    };
    const launches = [],
        alerts = [];
    let ready = options.ready || false,
        time = 0;
    const runtime = {
        URL,
        now: () => time,
        delay: async (ms) => {
            time += ms;
        },
        getPref: (key) => prefs[key],
        setPref: (key, value) => {
            prefs[key] = value;
        },
        health: async () => (ready ? READY : null),
        launch: async (...args) => {
            launches.push(args);
            if (!options.neverReady) ready = true;
        },
        alert: (text) => alerts.push(text),
        ...options.runtime,
    };
    return {
        service: createPDF2zhLocalService(runtime),
        runtime,
        launches,
        alerts,
        prefs,
        setReady: (v) => {
            ready = v;
        },
    };
}

test("running server is reused with automatic start disabled", async () => {
    const f = fixture({
        ready: true,
        prefs: { local_service_auto_start: false },
    });
    assert.equal(await f.service.ensure(), READY);
    assert.equal(f.launches.length, 0);
});
test("local server starts at selected port and configured folder", async () => {
    const f = fixture();
    await f.service.ensure("http://127.0.0.1:8891/");
    assert.deepEqual(f.launches, [
        ["Start", 8891, f.prefs.local_service_directory],
    ]);
});
test("parallel PDF submissions share one startup", async () => {
    const f = fixture();
    await Promise.all([
        f.service.ensure(),
        f.service.ensure(),
        f.service.ensure(),
    ]);
    assert.equal(f.launches.length, 1);
});
test("remote and HTTPS addresses never launch local processes", async () => {
    for (const url of [
        "http://example.com:8890",
        "http://localhost.example.com:8890",
        "https://localhost:8890",
    ]) {
        const f = fixture();
        await assert.rejects(f.service.ensure(url), /远程地址或 HTTPS/);
        assert.equal(f.launches.length, 0);
    }
});
test("invalid schemes, userinfo and query strings are rejected", async () => {
    for (const url of [
        "file:///C:/x",
        "http://localhost@evil.example:8890",
        "http://localhost:8890/?command=x",
        "not a url",
    ]) {
        const f = fixture();
        await assert.rejects(f.service.ensure(url));
        assert.equal(f.launches.length, 0);
    }
});
test("manual start remains available with auto-start disabled", async () => {
    const f = fixture({ prefs: { local_service_auto_start: false } });
    await assert.rejects(f.service.ensure(), /尚未启动/);
    await f.service.menu("Start");
    assert.equal(f.launches.length, 1);
    assert.match(f.alerts[0], /已就绪/);
});
test("stop delegates to existing task-aware script", async () => {
    const f = fixture();
    await f.service.menu("Stop");
    assert.deepEqual(f.launches, [
        ["Stop", 8890, f.prefs.local_service_directory],
    ]);
});
test("startup timeout reports terminal error before PDF submission", async () => {
    const f = fixture({ neverReady: true });
    await assert.rejects(f.service.ensure(), /90 秒内未就绪/);
    assert.equal(f.launches.length, 1);
});
test("failed launch is cleared for retry after fixing path", async () => {
    const f = fixture({
        runtime: {
            launch: async () => {
                throw new Error("Missing script");
            },
        },
    });
    await assert.rejects(f.service.ensure(), /Missing script/);
    f.runtime.launch = async (...args) => {
        f.launches.push(args);
        f.setReady(true);
    };
    await f.service.ensure();
    assert.equal(f.launches.length, 1);
});
test("PowerShell quoting handles spaces, apostrophes and Chinese", () => {
    const paths = {
        directory: "E:\\Test user's folder\\翻译",
        helper: "E:\\Test user's folder\\翻译\\utils\\pdf2zh-service.ps1",
        executable:
            "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
    };
    const command = pdf2zhLaunchCommand(paths, "Start", 8890);
    assert.match(command, /Test user''s folder/);
    assert.match(command, /-WindowStyle Normal$/);
    assert.match(command, /-Action Start -Port 8890 -NoPause/);
    assert.throws(() =>
        pdf2zhLaunchCommand({ ...paths, helper: 'bad"path' }, "Start", 8890),
    );
    assert.throws(() => pdf2zhLaunchCommand(paths, "Delete", 8890));
    assert.throws(() => pdf2zhLaunchCommand(paths, "Start", 99999));
});
test("PDF preflight runs before preparation and menus are present", () => {
    const source = readFileSync(
        new URL("../src/modules/pdf2zhHelper.ts", import.meta.url),
        "utf8",
    );
    const method = source.slice(
        source.indexOf("static async processSingleFile"),
        source.indexOf("static async prepareFileData"),
    );
    assert.ok(
        method.indexOf("getLocalService().ensure") <
            method.indexOf("await this.prepareFileData"),
    );
    const menu = readFileSync(
        new URL("../src/modules/pdf2zh.ts", import.meta.url),
        "utf8",
    );
    assert.match(menu, /pdf2zh-start-service/);
    assert.match(menu, /pdf2zh-stop-service/);
});
