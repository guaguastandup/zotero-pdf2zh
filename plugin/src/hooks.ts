// lifecycle hooks
import { PDF2zhBasicFactory, PDF2zhUIFactory } from "./modules/pdf2zh";
import { PDF2zhHelperFactory } from "./modules/pdf2zhHelper";
import { getString, initLocale } from "./utils/locale";
import { createZToolkit } from "./utils/ztoolkit";
import { registerPrefsScripts, initTableUI } from "./modules/preferenceScript";

async function onStartup() {
    await Promise.all([
        Zotero.initializationPromise,
        Zotero.unlockPromise,
        Zotero.uiReadyPromise,
    ]);
    initLocale(); // 初始化多语言
    PDF2zhBasicFactory.registerPrefs(); // 注册偏好设置
    await Promise.all(
        Zotero.getMainWindows().map((win) => onMainWindowLoad(win)),
    );
}

async function onMainWindowLoad(win: Window): Promise<void> {
    addon.data.ztoolkit = createZToolkit(); // Create ztoolkit for every window
    // 注册右键菜单, 显示加载弹窗
    PDF2zhUIFactory.registerRightClickMenuItem();
    await Zotero.Promise.delay(200);
    // 渲染偏好设置的LLM API表格, 避免第一次打开Preference页面时LLM Config条目未完全加载
    // TOCHECK: 目前可以有效解决问题, 但是关闭Preference后这个初始化的内容不会被删除吗??
    initTableUI();
    // 给老用户的通知
    // const progressWindow = new ztoolkit.ProgressWindow(
    //     "zotero-pdf2zh插件 给老用户的通知",
    //     { closeOnClick: true, closeTime: -1 },
    // ).createLine({
    //     text: "重要:【老用户必读】 本插件在近期进行了重大更新, 并在此3.0.32版本推送到更新主分支。需要使用2.4.3版本的老用户根据插件主页更新的教程内容, 重新进行环境配置, 如果您不想重新配置, 请卸载此版本插件并在项目Github主页的Release页面重新下载并安装2.4.3版本插件, 并且关闭插件自动更新选项。为您造成的不便, 深感抱歉!",
    //     type: "default",
    //     progress: 100,
    // });
    // progressWindow.show();
    // progressWindow.startCloseTimer(15000); // 15秒后自动关闭
}

async function onPrefsEvent(type: string, data: { [key: string]: any }) {
    switch (type) {
        case "load":
            registerPrefsScripts(data.window);
            break;
        default:
            return;
    }
}

async function onMainWindowUnload(win: Window): Promise<void> {
    ztoolkit.unregisterAll();
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
        case "skimPDF":
            PDF2zhHelperFactory.processWorker("skim");
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
