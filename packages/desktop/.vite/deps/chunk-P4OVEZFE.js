import {
  accessWith,
  isObject
} from "./chunk-E4MUVEY4.js";
import {
  isServer
} from "./chunk-D7NEWJXD.js";
import {
  batch,
  createRoot,
  createSignal,
  getListener,
  getOwner,
  onCleanup,
  onMount,
  sharedConfig,
  untrack
} from "./chunk-BWBVP47I.js";

// ../../node_modules/.bun/@solid-primitives+static-store@0.1.3+95b571dd5236cc92/node_modules/@solid-primitives/static-store/dist/index.js
function createStaticStore(init) {
  const copy = { ...init }, store = { ...init }, cache = {};
  const getValue = (key) => {
    let signal = cache[key];
    if (!signal) {
      if (!getListener())
        return copy[key];
      cache[key] = signal = createSignal(copy[key], { internal: true });
      delete copy[key];
    }
    return signal[0]();
  };
  for (const key in init) {
    Object.defineProperty(store, key, { get: () => getValue(key), enumerable: true });
  }
  const setValue = (key, value) => {
    const signal = cache[key];
    if (signal)
      return signal[1](value);
    if (key in copy)
      copy[key] = accessWith(value, copy[key]);
  };
  return [
    store,
    (a, b) => {
      if (isObject(a)) {
        const entries = untrack(() => Object.entries(accessWith(a, store)));
        batch(() => {
          for (const [key, value] of entries)
            setValue(key, () => value);
        });
      } else
        setValue(a, b);
      return store;
    }
  ];
}
function createHydratableStaticStore(serverValue, update) {
  if (isServer)
    return createStaticStore(serverValue);
  if (sharedConfig.context) {
    const [state, setState] = createStaticStore(serverValue);
    onMount(() => setState(update()));
    return [state, setState];
  }
  return createStaticStore(update());
}

// ../../node_modules/.bun/@solid-primitives+rootless@1.5.3+95b571dd5236cc92/node_modules/@solid-primitives/rootless/dist/index.js
function createSingletonRoot(factory, detachedOwner = getOwner()) {
  let listeners = 0, value, disposeRoot;
  return () => {
    listeners++;
    onCleanup(() => {
      listeners--;
      queueMicrotask(() => {
        if (!listeners && disposeRoot) {
          disposeRoot();
          disposeRoot = value = void 0;
        }
      });
    });
    if (!disposeRoot) {
      createRoot((dispose) => value = factory(disposeRoot = dispose), detachedOwner);
    }
    return value;
  };
}
function createHydratableSingletonRoot(factory) {
  const owner = getOwner();
  const singleton = createSingletonRoot(factory, owner);
  return () => isServer || sharedConfig.context ? createRoot(factory, owner) : singleton();
}

export {
  createStaticStore,
  createHydratableStaticStore,
  createHydratableSingletonRoot
};
//# sourceMappingURL=chunk-P4OVEZFE.js.map
