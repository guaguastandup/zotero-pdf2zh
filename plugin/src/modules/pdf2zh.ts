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
    static registerRightClickMenuItem() {
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

        const doc = Zotero.getMainWindow().document;
        const popup = doc.querySelector("#zotero-itemmenu");
        if (!popup) return;

        const menu = doc.createElementNS(
            "http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul",
            "menu",
        );
        menu.id = "zotero-itemmenu-pdf2zh";
        menu.setAttribute("label", "PDF2zh");
        menu.setAttribute("image", menuIcon);
        menu.classList.add("menu-iconic");

        const subPopup = doc.createElementNS(
            "http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul",
            "menupopup",
        );

        for (const item of MENU_ITEMS) {
            const menuitem = doc.createElementNS(
                "http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul",
                "menuitem",
            );
            menuitem.id = `zotero-itemmenu-${item.id}`;
            menuitem.setAttribute("label", `PDF2zh: ${item.label}`);
            menuitem.setAttribute("image", menuIcon);
            menuitem.classList.add("menuitem-iconic");
            menuitem.addEventListener("command", () =>
                addon.hooks.onDialogEvents(item.command),
            );
            subPopup.appendChild(menuitem);
        }

        menu.appendChild(subPopup);
        popup.appendChild(menu);
    }
}
