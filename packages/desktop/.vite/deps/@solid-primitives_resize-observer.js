import {
  createHydratableSingletonRoot,
  createHydratableStaticStore,
  createStaticStore
} from "./chunk-P4OVEZFE.js";
import {
  access,
  asArray,
  filterNonNullable,
  handleDiffArray,
  makeEventListener,
  noop
} from "./chunk-E4MUVEY4.js";
import {
  isServer
} from "./chunk-D7NEWJXD.js";
import {
  createEffect,
  onCleanup,
  sharedConfig
} from "./chunk-BWBVP47I.js";
import "./chunk-G3PMV62Z.js";

// ../../node_modules/.bun/@solid-primitives+resize-observer@2.1.3+95b571dd5236cc92/node_modules/@solid-primitives/resize-observer/dist/index.js
function makeResizeObserver(callback, options) {
  if (isServer) {
    return { observe: noop, unobserve: noop };
  }
  const observer = new ResizeObserver(callback);
  onCleanup(observer.disconnect.bind(observer));
  return {
    observe: (ref) => observer.observe(ref, options),
    unobserve: observer.unobserve.bind(observer)
  };
}
function createResizeObserver(targets, onResize, options) {
  if (isServer)
    return;
  const previousMap = /* @__PURE__ */ new WeakMap(), { observe, unobserve } = makeResizeObserver((entries) => {
    for (const entry of entries) {
      const { contentRect, target } = entry, width = Math.round(contentRect.width), height = Math.round(contentRect.height), previous = previousMap.get(target);
      if (!previous || previous.width !== width || previous.height !== height) {
        onResize(contentRect, target, entry);
        previousMap.set(target, { width, height });
      }
    }
  }, options);
  createEffect((prev) => {
    const refs = filterNonNullable(asArray(access(targets)));
    handleDiffArray(refs, prev, observe, unobserve);
    return refs;
  }, []);
}
var WINDOW_SIZE_FALLBACK = { width: 0, height: 0 };
function getWindowSize() {
  if (isServer)
    return { ...WINDOW_SIZE_FALLBACK };
  return {
    width: window.innerWidth,
    height: window.innerHeight
  };
}
function createWindowSize() {
  if (isServer) {
    return WINDOW_SIZE_FALLBACK;
  }
  const [size, setSize] = createHydratableStaticStore(WINDOW_SIZE_FALLBACK, getWindowSize);
  makeEventListener(window, "resize", () => setSize(getWindowSize()));
  return size;
}
var useWindowSize = createHydratableSingletonRoot(createWindowSize);
var ELEMENT_SIZE_FALLBACK = { width: null, height: null };
function getElementSize(target) {
  if (isServer || !target) {
    return { ...ELEMENT_SIZE_FALLBACK };
  }
  const { width, height } = target.getBoundingClientRect();
  return { width, height };
}
function createElementSize(target) {
  if (isServer) {
    return ELEMENT_SIZE_FALLBACK;
  }
  const isFn = typeof target === "function";
  const [size, setSize] = createStaticStore(sharedConfig.context || isFn ? ELEMENT_SIZE_FALLBACK : getElementSize(target));
  const ro = new ResizeObserver(([e]) => setSize(getElementSize(e.target)));
  onCleanup(() => ro.disconnect());
  if (isFn) {
    createEffect(() => {
      const el = target();
      if (el) {
        setSize(getElementSize(el));
        ro.observe(el);
        onCleanup(() => ro.unobserve(el));
      }
    });
  } else {
    ro.observe(target);
    onCleanup(() => ro.unobserve(target));
  }
  return size;
}
export {
  createElementSize,
  createResizeObserver,
  createWindowSize,
  getElementSize,
  getWindowSize,
  makeResizeObserver,
  useWindowSize
};
//# sourceMappingURL=@solid-primitives_resize-observer.js.map
