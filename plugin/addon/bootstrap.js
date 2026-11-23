/* eslint-disable no-undef */

/**
 * Most of this code is from Zotero team's official Make It Red example[1]
 * or the Zotero 7 documentation[2].
 * [1] https://github.com/zotero/make-it-red
 * [2] https://www.zotero.org/support/dev/zotero_7_for_developers
 */

var chromeHandle;
var startupPromise;
var startupGeneration = 0;

function install(data, reason) {}

async function startup({ id, version, resourceURI, rootURI }, reason) {
    const generation = ++startupGeneration;
    startupPromise = (async () => {
        await Zotero.initializationPromise;
        if (generation !== startupGeneration) return;

        // String 'rootURI' introduced in Zotero 7
        if (!rootURI) {
            rootURI = resourceURI.spec;
        }

        var aomStartup = Components.classes[
            "@mozilla.org/addons/addon-manager-startup;1"
        ].getService(Components.interfaces.amIAddonManagerStartup);
        var manifestURI = Services.io.newURI(rootURI + "manifest.json");
        chromeHandle = aomStartup.registerChrome(manifestURI, [
            ["content", "__addonRef__", rootURI + "content/"],
        ]);

        /**
         * Global variables for plugin code.
         * The `_globalThis` is the global root variable of the plugin sandbox environment
         * and all child variables assigned to it is globally accessible.
         * See `src/index.ts` for details.
         */
        const ctx = {
            rootURI,
        };
        // Gecko 128+ removed JSM imports. Zotero can still expose a legacy
        // `import` shim, which misleads the toolkit's feature detection.
        // Override only our script scope; leave the host and other plugins alone.
        if (parseInt(Services.appinfo.platformVersion, 10) >= 128) {
            ctx.ChromeUtils = Object.create(ChromeUtils, {
                import: { value: undefined },
                importESModule: {
                    value: ChromeUtils.importESModule.bind(ChromeUtils),
                },
            });
        }
        ctx._globalThis = ctx;

        Services.scriptloader.loadSubScript(
            `${rootURI}/content/scripts/__addonRef__.js`,
            ctx,
        );
        await Zotero.__addonInstance__.hooks.onStartup();
    })();
    try {
        await startupPromise;
    } catch (error) {
        Zotero.logError(error);
        if (generation === startupGeneration) {
            shutdown({ id, version, resourceURI, rootURI }, reason);
        }
        throw error;
    }
}

async function onMainWindowLoad({ window }, reason) {
    await startupPromise;
    await Zotero.__addonInstance__?.hooks.onMainWindowLoad(window);
}

async function onMainWindowUnload({ window }, reason) {
    await Zotero.__addonInstance__?.hooks.onMainWindowUnload(window);
}

function shutdown({ id, version, resourceURI, rootURI }, reason) {
    ++startupGeneration;
    if (reason === APP_SHUTDOWN) {
        return;
    }

    if (typeof Zotero === "undefined") {
        Zotero = Components.classes["@zotero.org/Zotero;1"].getService(
            Components.interfaces.nsISupports,
        ).wrappedJSObject;
    }
    Zotero.__addonInstance__?.hooks.onShutdown();

    Cc["@mozilla.org/intl/stringbundle;1"]
        .getService(Components.interfaces.nsIStringBundleService)
        .flushBundles();

    if (chromeHandle) {
        chromeHandle.destruct();
        chromeHandle = null;
    }
}

function uninstall(data, reason) {}
