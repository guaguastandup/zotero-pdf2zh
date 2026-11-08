import { createHash } from "node:crypto";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
const plugin = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const server = path.resolve(plugin, "../server");
// Explicit runtime roots; never recursively include a user's installation.
const roots = [
    "server.py",
    "manage_packages.py",
    "update_packages.py",
    "requirements.txt",
    "index.html",
    "favicon.svg",
    "notice.json",
    "bo.mp3",
    "config/config.json.example",
    "config/config.toml.example",
    "config/venv.json.example",
];
for (const name of [
    "auto_update.py",
    "config.py",
    "config_map.py",
    "config_migration.py",
    "cropper.py",
    "deepseek_thinking.py",
    "environment_lifecycle.py",
    "error_catalog.py",
    "execute.py",
    "log_stream.py",
    "package_network.py",
    "record.py",
    "reference_skip.py",
    "startup.py",
    "table_batching.py",
    "table_code.py",
    "table_columns.py",
    "table_geometry.py",
    "table_images.py",
    "table_labels.py",
    "table_layout.py",
    "table_mode.py",
    "table_process.py",
    "table_runner.py",
    "table_runtime.py",
    "table_semantics.py",
    "table_structure.py",
    "task_manager.py",
    "venv.py",
])
    roots.push(`utils/${name}`);
for (const name of [
    "install-with-conda.bat",
    "install-with-conda.sh",
    "install-with-uv.bat",
    "install-with-uv.sh",
])
    roots.push(`warmup/${name}`);
const files = [];
for (const name of roots.sort()) {
    const bytes = await readFile(path.join(server, name));
    files.push({
        path: name,
        base64: bytes.toString("base64"),
        sha256: createHash("sha256").update(bytes).digest("hex"),
    });
}
const { version } = JSON.parse(
    await readFile(path.join(plugin, "package.json"), "utf8"),
);
const output = path.join(plugin, "addon/content/bundled-server.json");
await mkdir(path.dirname(output), { recursive: true });
await writeFile(output, JSON.stringify({ version, files }));
console.log(`Bundled Server ${version}: ${files.length} files`);
