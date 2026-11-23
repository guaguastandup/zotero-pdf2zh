// lifecycle hooks
import { PDF2zhBasicFactory, PDF2zhUIFactory } from "./modules/pdf2zh";
import { PDF2zhHelperFactory } from "./modules/pdf2zhHelper";
import { getString, initLocale } from "./utils/locale";
import { registerPrefsScripts } from "./modules/preferenceScript";

async function onStartup() {
    await Promise.all([
        Zotero.initializationPromise,
        Zotero.unlockPromise,
        Zotero.uiReadyPromise,
    ]);
    if (!addon.data.alive) return;
    initLocale(); // 初始化多语言
    await PDF2zhBasicFactory.registerPrefs(); // 注册偏好设置
    if (!addon.data.alive) return;
    await Promise.all(
        Zotero.getMainWindows().map((win) => onMainWindowLoad(win)),
    );
}

async function onMainWindowLoad(win: Window): Promise<void> {
    // 注册右键菜单, 显示加载弹窗
    PDF2zhUIFactory.registerRightClickMenuItem(win);
}

async function onPrefsEvent(type: string, data: { [key: string]: any }) {
    switch (type) {
        case "load":
            await registerPrefsScripts(data.window);
            break;
        default:
            return;
    }
}

async function onMainWindowUnload(win: Window): Promise<void> {
    // The toolkit is shared by all windows; only remove this window's menu.
    win.document.querySelector("#zotero-itemmenu-pdf2zh")?.remove();
    addon.data.dialog?.window?.close();
}

function onShutdown(): void {
    ztoolkit.unregisterAll();
    addon.data.dialog?.window?.close();
    // Remove addon object
    addon.data.alive = false;
    // @ts-ignore - Plugin instance is not typed
    delete Zotero[addon.data.config.addonInstance];
}

/**
 * This function is just an example of dispatcher for Notify events.
 * Any operations should be placed in a function to keep this funcion clear.
 */
async function onNotify(
    event: string,
    type: string,
    ids: Array<string | number>,
    extraData: { [key: string]: any },
) {
    return;
}

function onShortcuts(type: string) {
    switch (type) {
        default:
            break;
    }
}

function onDialogEvents(type: string) {
    switch (type) {
        case "translatePDF":
            PDF2zhHelperFactory.processWorker("translate");
            break;
        case "cropPDF":
            PDF2zhHelperFactory.processWorker("crop");
            break;
        case "crop-comparePDF":
            PDF2zhHelperFactory.processWorker("crop-compare");
            break;
        case "comparePDF":
            PDF2zhHelperFactory.processWorker("compare");
            break;
        default:
            break;
    }
}

export default {
    onStartup,
    onShutdown,
    onMainWindowLoad,
    onMainWindowUnload,
    onNotify,
    onPrefsEvent,
    onShortcuts,
    onDialogEvents,
};
