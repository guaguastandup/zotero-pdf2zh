export type ServiceAction = "Start" | "Stop";
export interface ServiceHealth {
    status: string;
    version: string;
    message: string;
}
export interface LaunchPaths {
    helper: string;
    directory: string;
    executable: string;
}
export interface LocalServiceRuntime {
    URL: typeof URL;
    getPref(key: string): unknown;
    setPref(key: string, value: string | boolean): void;
    health(base: string): Promise<ServiceHealth | null>;
    launch(
        action: ServiceAction,
        port: number,
        directory: string,
    ): Promise<void>;
    now(): number;
    delay(ms: number): Promise<void>;
    alert(text: string): void;
}

function pdf2zhPowerShellQuote(value: string) {
    return "'" + String(value).replace(/'/g, "''") + "'";
}

export function pdf2zhLaunchCommand(
    paths: LaunchPaths,
    action: ServiceAction,
    port: number,
) {
    if (!["Start", "Stop"].includes(action)) throw new Error("无效的服务操作");
    if (!Number.isInteger(port) || port < 1 || port > 65535)
        throw new Error("无效端口");
    for (const value of [paths.helper, paths.directory, paths.executable]) {
        if (
            !value ||
            value.includes('"') ||
            [...value].some((c) => c.charCodeAt(0) < 32)
        )
            throw new Error("服务路径包含无效字符");
    }
    const args = `-NoLogo -NoProfile -ExecutionPolicy Bypass -File "${paths.helper}" -Action ${action} -Port ${port} -NoPause`;
    return `Start-Process -FilePath ${pdf2zhPowerShellQuote(paths.executable)} -ArgumentList ${pdf2zhPowerShellQuote(args)} -WorkingDirectory ${pdf2zhPowerShellQuote(paths.directory)} -WindowStyle Normal`;
}

export function createPDF2zhLocalService(runtime: LocalServiceRuntime) {
    const starting = new Map<string, Promise<ServiceHealth>>();
    const defaultDirectory = "";
    function address(value: unknown) {
        let url;
        try {
            url = new runtime.URL(String(value || "").trim());
        } catch (_) {
            throw new Error("PDF2zh 服务地址无效，请检查插件设置。");
        }
        if (
            !["http:", "https:"].includes(url.protocol) ||
            url.username ||
            url.password ||
            url.search ||
            url.hash
        ) {
            throw new Error(
                "PDF2zh 服务地址必须是不含账号、查询参数的 HTTP/HTTPS 地址。",
            );
        }
        const base = url.href.replace(/\/+$/, "");
        const local =
            url.protocol === "http:" &&
            ["localhost", "127.0.0.1"].includes(url.hostname.toLowerCase()) &&
            url.pathname === "/";
        return {
            base,
            local,
            port: Number(url.port || (url.protocol === "https:" ? 443 : 80)),
        };
    }
    function folder() {
        const directory = String(
            runtime.getPref("local_service_directory") || defaultDirectory,
        ).trim();
        if (!directory)
            throw new Error(
                "请先在 PDF2zh 设置中填写本机服务文件夹，并开启自动启动，或手动启动 Server。",
            );
        return directory;
    }
    async function health(base: string): Promise<ServiceHealth | null> {
        try {
            const data = await runtime.health(base);
            return data &&
                data.status === "ok" &&
                data.message === "PDF2zh Server is running" &&
                typeof data.version === "string"
                ? data
                : null;
        } catch (_) {
            return null;
        }
    }
    async function startAndWait(info: {
        base: string;
        port: number;
    }): Promise<ServiceHealth> {
        await runtime.launch("Start", info.port, folder());
        const deadline = runtime.now() + 90000;
        while (runtime.now() < deadline) {
            const data = await health(info.base);
            if (data) return data;
            await runtime.delay(750);
        }
        throw new Error(
            "已打开 PDF2zh 启动终端，但服务在 90 秒内未就绪。请查看终端中的错误，并核对服务目录和端口。",
        );
    }
    async function ensure(
        serverUrl?: string,
        options: { manual?: boolean } = {},
    ) {
        const info = address(serverUrl || runtime.getPref("new_serverip"));
        const ready = await health(info.base);
        if (ready) return ready;
        if (!info.local)
            throw new Error(
                "无法连接 PDF2zh 服务。远程地址或 HTTPS 地址需要先自行启动对应服务；仅本机 HTTP 地址支持自动启动。",
            );
        if (
            !options.manual &&
            runtime.getPref("local_service_auto_start") !== true
        ) {
            throw new Error(
                "PDF2zh 本机服务尚未启动。请在 PDF2zh 右键菜单中选择“启动本机服务”，或开启翻译前自动启动。",
            );
        }
        if (!starting.has(info.base)) {
            const operation = startAndWait(info);
            starting.set(info.base, operation);
            operation
                .finally(() => {
                    if (starting.get(info.base) === operation)
                        starting.delete(info.base);
                })
                .catch(() => {});
        }
        return starting.get(info.base)!;
    }
    async function menu(action: ServiceAction) {
        try {
            const info = address(runtime.getPref("new_serverip"));
            if (!info.local)
                throw new Error(
                    "启动和停止菜单仅用于本机 HTTP 服务，请检查服务地址。",
                );
            if (action === "Start") {
                const data = await ensure(info.base, { manual: true });
                runtime.alert(
                    `本机 PDF2zh ${data.version} 已就绪。\n${info.base}\n可继续选择翻译操作。`,
                );
            } else if (action === "Stop") {
                await runtime.launch("Stop", info.port, folder());
            } else {
                throw new Error("无效的服务操作");
            }
        } catch (error) {
            runtime.alert(
                error instanceof Error ? error.message : String(error),
            );
        }
    }
    function bindPreferences(window: Window) {
        const doc = window.document;
        const directory = doc.getElementById(
            "pdf2zh-local-service-directory",
        ) as (HTMLInputElement & { pdf2zhBound?: boolean }) | null;
        const auto = doc.getElementById("pdf2zh-local-service-auto") as
            | (HTMLInputElement & { pdf2zhBound?: boolean })
            | null;
        if (directory && !directory.pdf2zhBound) {
            directory.value = String(
                runtime.getPref("local_service_directory") || "",
            );
            directory.addEventListener("change", () =>
                runtime.setPref(
                    "local_service_directory",
                    directory.value.trim(),
                ),
            );
            directory.pdf2zhBound = true;
        }
        if (auto && !auto.pdf2zhBound) {
            auto.checked = runtime.getPref("local_service_auto_start") === true;
            auto.addEventListener("change", () =>
                runtime.setPref("local_service_auto_start", auto.checked),
            );
            auto.pdf2zhBound = true;
        }
    }
    return { ensure, menu, bindPreferences };
}

function createPDF2zhLocalRuntime(): LocalServiceRuntime {
    const prefix = "extensions.zotero.pdf2zh.";
    return {
        URL: ztoolkit.getGlobal("URL"),
        getPref: (key: string) => Zotero.Prefs.get(prefix + key, true),
        setPref: (key: string, value: string | boolean) =>
            Zotero.Prefs.set(prefix + key, value, true),
        now: () => Date.now(),
        delay: (ms: number) => Zotero.Promise.delay(ms),
        alert: (text: string) =>
            Zotero.alert(Zotero.getMainWindow(), "PDF2zh", text),
        async health(base: string) {
            const result = await Zotero.HTTP.request("GET", base + "/health", {
                responseType: "json",
                timeout: 1500,
            });
            return result.response;
        },
        async launch(action: ServiceAction, port: number, directory: string) {
            if (!Zotero.isWin)
                throw new Error("本机服务启动脚本目前仅支持 Windows。");
            const Ci = Components.interfaces;
            const root = Zotero.File.pathToFile(directory);
            if (!root.exists() || !root.isDirectory())
                throw new Error(
                    "本机服务目录不存在，请在 PDF2zh 设置中修改服务目录。\n" +
                        directory,
                );
            const helper = root.clone();
            helper.append("utils");
            helper.append("pdf2zh-service.ps1");
            if (!helper.exists() || !helper.isFile())
                throw new Error(
                    "服务目录中找不到 utils\\pdf2zh-service.ps1。\n" +
                        directory,
                );
            const executable = Services.dirsvc.get("WinD", Ci.nsIFile).clone();
            for (const part of [
                "System32",
                "WindowsPowerShell",
                "v1.0",
                "powershell.exe",
            ])
                executable.append(part);
            if (!executable.exists())
                throw new Error("找不到 Windows PowerShell。");
            const command = pdf2zhLaunchCommand(
                {
                    helper: helper.path,
                    directory: root.path,
                    executable: executable.path,
                },
                action,
                port,
            );
            const process = Components.classes[
                "@mozilla.org/process/util;1"
            ].createInstance(Ci.nsIProcess);
            process.init(executable);
            const args = [
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ];
            return new Promise<void>((resolve, reject) => {
                process.runwAsync(args, args.length, {
                    observe(_subject: unknown, topic: string) {
                        if (
                            topic === "process-finished" &&
                            process.exitValue === 0
                        )
                            resolve();
                        else
                            reject(
                                new Error(
                                    "无法打开服务终端，请检查本机服务目录和 PowerShell。",
                                ),
                            );
                    },
                });
            });
        },
    };
}

let service: ReturnType<typeof createPDF2zhLocalService> | undefined;
export function getLocalService() {
    return (service ??= createPDF2zhLocalService(createPDF2zhLocalRuntime()));
}
