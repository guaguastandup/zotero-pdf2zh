import { MenuitemOptions } from "zotero-plugin-toolkit";
import { getString } from "../utils/locale";

export class PDF2zhBasicFactory {
    static registerPrefs() {
        Zotero.PreferencePanes.register({
            pluginID: addon.data.config.addonID,
            src: rootURI + "content/preferences.xhtml",
            label: getString("prefs-title"),
            image: `chrome://${addon.data.config.addonRef}/content/icons/favicon.svg`,
        });
    }
}

export class PDF2zhUIFactory {
    static registerRightClickMenuItem(win: Window) {
        // A string target resolves against the active window in the toolkit,
        // which may not be the window delivered by the lifecycle callback.
        const popup =
            win.document.querySelector<XUL.MenuPopup>("#zotero-itemmenu");
        if (!popup) {
            Zotero.logError(
                new Error(
                    "[PDF2zh] Cannot register menu: #zotero-itemmenu is missing",
                ),
            );
            return;
        }
        if (win.document.querySelector("#zotero-itemmenu-pdf2zh")) return;
        const menuIcon = `chrome://${addon.data.config.addonRef}/content/icons/favicon@0.5x.svg`;
        const MENU_ITEMS = [
            {
                id: "translate-pdf",
                label: getString("prefs-menu-translate"),
                command: "translatePDF",
            },
            {
                id: "crop-pdf",
                label: getString("prefs-menu-cut"),
                command: "cropPDF",
            },
            {
                id: "compare-pdf",
                label: getString("prefs-menu-compare"),
                command: "comparePDF",
            },
            {
                id: "crop-compare-pdf",
                label: getString("prefs-menu-crop-compare"),
                command: "crop-comparePDF",
            },
        ];
        const pdf2zhMenu: MenuitemOptions = {
            tag: "menu",
            id: "zotero-itemmenu-pdf2zh",
            icon: menuIcon,
            label: `PDF2zh`,
            children: MENU_ITEMS.map(({ id, label, command }) => ({
                tag: "menuitem",
                id: `zotero-itemmenu-${id}`,
                label: `PDF2zh: ${label}`,
                commandListener: () => addon.hooks.onDialogEvents(command),
                icon: menuIcon,
            })),
        };
        ztoolkit.Menu.register(popup, pdf2zhMenu);
    }
}
