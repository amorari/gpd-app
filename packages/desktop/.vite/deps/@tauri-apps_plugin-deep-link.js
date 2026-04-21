import {
  listen
} from "./chunk-GBHCCZWB.js";
import {
  invoke
} from "./chunk-6G5MRFJP.js";
import "./chunk-G3PMV62Z.js";

// ../../node_modules/.bun/@tauri-apps+plugin-deep-link@2.4.8/node_modules/@tauri-apps/plugin-deep-link/dist-js/index.js
async function getCurrent() {
  return await invoke("plugin:deep-link|get_current");
}
async function register(protocol) {
  return await invoke("plugin:deep-link|register", { protocol });
}
async function unregister(protocol) {
  return await invoke("plugin:deep-link|unregister", { protocol });
}
async function isRegistered(protocol) {
  return await invoke("plugin:deep-link|is_registered", { protocol });
}
async function onOpenUrl(handler) {
  return await listen("deep-link://new-url", (event) => {
    handler(event.payload);
  });
}
export {
  getCurrent,
  isRegistered,
  onOpenUrl,
  register,
  unregister
};
//# sourceMappingURL=@tauri-apps_plugin-deep-link.js.map
