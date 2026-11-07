import assert from "node:assert/strict";
import test from "node:test";
import {
    LocalServerManager,
    normalizeLocalServerUrl,
} from "../src/modules/localServer.ts";

const options = {
    serverUrl: "http://localhost:8890",
    pythonPath: "C:\\Python\\python.exe",
    scriptPath: "C:\\Server Folder\\server.py",
    timeoutMs: 30,
};
function fixture(health: (count: number) => boolean | "other" = (n) => n > 1) {
    let checks = 0,
        calls = 0,
        killed = 0,
        clock = 0;
    let launch: any;
    const manager = new LocalServerManager({
        probe: async () => health(++checks),
        spawn: async (spec) => {
            calls++;
            launch = spec;
            return {
                kill: async () => {
                    killed++;
                },
                wait: () => new Promise(() => {}),
            };
        },
        now: () => clock,
        sleep: async (ms) => {
            clock += ms;
        },
    });
    return { manager, counts: () => ({ calls, killed }), launch: () => launch };
}
test("only plain loopback HTTP addresses are launch targets", () => {
    for (const url of [
        "https://localhost:8890",
        "http://example.org:8890",
        "http://localhost.evil:8890",
        "http://user:secret@localhost:8890",
        "http://localhost:8890/path",
        "http://localhost:8890/?token=x",
    ])
        assert.throws(() => normalizeLocalServerUrl(url));
    assert.throws(
        () => normalizeLocalServerUrl("http://[::1]:8890/"),
        /localhost or 127\.0\.0\.1/,
    );
    assert.equal(normalizeLocalServerUrl("http://127.0.0.1:8890/").port, 8890);
});
test("existing server is never owned or stopped", async () => {
    const f = fixture(() => true);
    assert.deepEqual(await f.manager.start(options), {
        status: "already-running",
        owned: false,
    });
    await f.manager.stop();
    assert.deepEqual(f.counts(), { calls: 0, killed: 0 });
});
test("an existing server works without configured local paths", async () => {
    const f = fixture(() => true);
    assert.deepEqual(
        await f.manager.start({ ...options, pythonPath: "", scriptPath: "" }),
        {
            status: "already-running",
            owned: false,
        },
    );
    await f.manager.stop();
    assert.deepEqual(f.counts(), { calls: 0, killed: 0 });
});
test("concurrent starts spawn once and pass literal non-interactive arguments", async () => {
    const f = fixture();
    await Promise.all([f.manager.start(options), f.manager.start(options)]);
    assert.equal(f.counts().calls, 1);
    assert.deepEqual(f.launch().arguments, [
        options.scriptPath,
        "--host",
        "localhost",
        "--port",
        "8890",
        "--non-interactive",
        "--check_update",
        "false",
    ]);
    await f.manager.stop();
    assert.equal(f.counts().killed, 1);
});
test("occupied unrelated service blocks launch", async () => {
    const f = fixture(() => "other");
    await assert.rejects(f.manager.start(options), /another service/);
    assert.equal(f.counts().calls, 0);
});
test("timeout stops only launched process and resets state", async () => {
    const f = fixture(() => false);
    await assert.rejects(f.manager.start(options), /timed out/);
    assert.deepEqual(f.counts(), { calls: 1, killed: 1 });
    assert.equal(f.manager.getState(), "stopped");
});
test("a failed recheck does not terminate an already managed server", async () => {
    let healthy = false;
    const f = fixture((count) => (healthy ? false : count > 1));
    await f.manager.start(options);
    healthy = true;
    await assert.rejects(f.manager.start(options), /not healthy/);
    assert.deepEqual(f.counts(), { calls: 1, killed: 0 });
    assert.equal(f.manager.getState(), "running");
    await f.manager.stop();
    assert.equal(f.counts().killed, 1);
});
test("changing the address does not claim another running server", async () => {
    const f = fixture((count) => count > 1);
    await f.manager.start(options);
    await assert.rejects(
        f.manager.start({ ...options, serverUrl: "http://localhost:8891" }),
        /address/,
    );
    assert.deepEqual(f.counts(), { calls: 1, killed: 0 });
    await f.manager.stop();
});
test("stop cancels a launch whose process creation is still pending", async () => {
    let release: (value: any) => void = () => {};
    let killed = 0;
    const manager = new LocalServerManager({
        probe: async () => false,
        spawn: () =>
            new Promise((resolve) => {
                release = resolve;
            }),
        now: () => 0,
        sleep: async () => {},
    });
    const starting = manager.start(options);
    await Promise.resolve();
    const stopping = manager.stop();
    release({
        kill: async () => {
            killed++;
        },
        wait: () => new Promise(() => {}),
    });
    await assert.rejects(starting, /cancelled/);
    await stopping;
    assert.equal(killed, 1);
    assert.equal(manager.getState(), "stopped");
});
test("an early process exit is surfaced and clears ownership", async () => {
    const manager = new LocalServerManager({
        probe: async () => false,
        spawn: async () => ({
            kill: async () => {},
            wait: async () => ({ exitCode: 2 }),
        }),
        now: () => 0,
        sleep: async () => {},
    });
    await assert.rejects(manager.start(options), /exited/);
    assert.equal(manager.getState(), "stopped");
});
