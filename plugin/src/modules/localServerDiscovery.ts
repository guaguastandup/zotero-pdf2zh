/** Read-only, bounded discovery. Candidates are suggestions, never executed here. */
export interface DiscoveryIO {
    join(...parts: string[]): string;
    isFile(path: string): Promise<boolean>;
    read(path: string): Promise<string>;
}
export async function discoverLocalServer(
    home: string,
    io: DiscoveryIO,
    configuredScript = "",
) {
    const folders = [
        home,
        ...["Downloads", "Desktop", "Documents"].map((name) =>
            io.join(home, name),
        ),
    ];
    const candidates = configuredScript
        ? [configuredScript]
        : folders.flatMap((folder) => [
              io.join(folder, "zotero-pdf2zh", "server", "server.py"),
              io.join(folder, "zotero-pdf2zh-main", "server", "server.py"),
              io.join(folder, "server", "server.py"),
          ]);
    const matches: string[] = [];
    for (const script of candidates) {
        try {
            const parent = script.slice(
                0,
                Math.max(script.lastIndexOf("/"), script.lastIndexOf("\\")),
            );
            if (
                !(await io.isFile(script)) ||
                !(await io.isFile(io.join(parent, "requirements.txt"))) ||
                !(await io.isFile(io.join(parent, "utils", "config.py")))
            )
                continue;
            const source = await io.read(script);
            if (
                source.includes("--non-interactive") &&
                source.includes("PDF2zh")
            )
                matches.push(script);
        } catch {
            /* Missing or unreadable directories do not block manual setup. */
        }
    }
    if (matches.length !== 1) return {};
    const scriptPath = matches[0];
    const parent = scriptPath.slice(
        0,
        Math.max(scriptPath.lastIndexOf("/"), scriptPath.lastIndexOf("\\")),
    );
    // Translation-engine environments do not necessarily contain Server dependencies.
    for (const env of [".venv", "venv"]) {
        for (const tail of [
            ["Scripts", "python.exe"],
            ["python.exe"],
            ["bin", "python"],
        ]) {
            const pythonPath = io.join(parent, env, ...tail);
            try {
                if (await io.isFile(pythonPath))
                    return { scriptPath, pythonPath };
            } catch {
                /* Try next candidate. */
            }
        }
    }
    return { scriptPath };
}
