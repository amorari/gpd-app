import {
  invoke
} from "./chunk-6G5MRFJP.js";
import "./chunk-G3PMV62Z.js";

// ../../node_modules/.bun/@tauri-apps+plugin-process@2.3.1/node_modules/@tauri-apps/plugin-process/dist-js/index.js
async function exit(code = 0) {
  await invoke("plugin:process|exit", { code });
}
async function relaunch() {
  await invoke("plugin:process|restart");
}
export {
  exit,
  relaunch
};
//# sourceMappingURL=@tauri-apps_plugin-process.js.map
