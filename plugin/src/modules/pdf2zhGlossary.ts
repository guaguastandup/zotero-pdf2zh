import { getString } from "../utils/locale";

const MAX_GLOSSARY_BYTES = 1024 * 1024;

export async function readGlossaryFile(path: string): Promise<string> {
    if (!path.toLowerCase().endsWith(".csv")) {
        throw new Error(getString("glossary-error-format"));
    }
    let size: number;
    let content: string;
    try {
        const info = await IOUtils.stat(path);
        if (info.type !== "regular" || typeof info.size !== "number") {
            throw new Error("Expected a regular glossary file");
        }
        size = info.size;
        content = size > MAX_GLOSSARY_BYTES ? "" : await IOUtils.readUTF8(path);
    } catch {
        throw new Error(getString("glossary-error-read"));
    }
    if (size > MAX_GLOSSARY_BYTES) {
        throw new Error(getString("glossary-error-size"));
    }
    if (!content.trim()) {
        throw new Error(getString("glossary-error-format"));
    }
    return content;
}
