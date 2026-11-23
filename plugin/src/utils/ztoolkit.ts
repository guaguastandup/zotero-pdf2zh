import {
    BasicTool,
    UITool,
    MenuManager,
    FilePickerHelper,
    ProgressWindowHelper,
    VirtualizedTableHelper,
    unregister,
} from "zotero-plugin-toolkit";
import { config } from "../../package.json";

export { createZToolkit };

function createZToolkit() {
    const _ztoolkit = new MyToolkit();
    initZToolkit(_ztoolkit);
    return _ztoolkit;
}

function initZToolkit(_ztoolkit: ReturnType<typeof createZToolkit>) {
    const env = __env__;
    _ztoolkit.basicOptions.log.prefix = `[${config.addonName}]`;
    _ztoolkit.basicOptions.log.disableConsole = env === "production";
    _ztoolkit.UI.basicOptions.ui.enableElementJSONLog = env === "development";
    _ztoolkit.UI.basicOptions.ui.enableElementDOMLog = env === "development";
    _ztoolkit.ProgressWindow.setIconURI(
        "default",
        `chrome://${config.addonRef}/content/icons/favicon.png`,
    );
}

class MyToolkit extends BasicTool {
    UI: UITool;
    Menu: MenuManager;
    FilePicker: typeof FilePickerHelper;
    ProgressWindow: typeof ProgressWindowHelper;
    VirtualizedTable: typeof VirtualizedTableHelper;

    constructor() {
        super();
        this.UI = new UITool(this);
        this.Menu = new MenuManager(this);
        this.FilePicker = FilePickerHelper;
        this.ProgressWindow = ProgressWindowHelper;
        this.VirtualizedTable = VirtualizedTableHelper;
    }

    unregisterAll() {
        unregister(this);
    }
}
