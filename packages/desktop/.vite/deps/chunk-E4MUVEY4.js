import {
  isServer
} from "./chunk-D7NEWJXD.js";
import {
  DEV,
  createEffect,
  createRenderEffect,
  createSignal,
  getOwner,
  onCleanup,
  onMount,
  sharedConfig
} from "./chunk-BWBVP47I.js";

// ../../node_modules/.bun/@solid-primitives+utils@6.4.0+95b571dd5236cc92/node_modules/@solid-primitives/utils/dist/index.js
var isClient = !isServer;
var isDev = isClient && !!DEV;
var noop = (() => void 0);
function isObject(value) {
  return value !== null && (typeof value === "object" || typeof value === "function");
}
var isNonNullable = (i) => i != null;
var filterNonNullable = (arr) => arr.filter(isNonNullable);
function chain(callbacks) {
  return (...args) => {
    for (const callback of callbacks)
      callback && callback(...args);
  };
}
var access = (v) => typeof v === "function" && !v.length ? v() : v;
var asArray = (value) => Array.isArray(value) ? value : value ? [value] : [];
function accessWith(valueOrFn, ...args) {
  return typeof valueOrFn === "function" ? valueOrFn(...args) : valueOrFn;
}
var entries = Object.entries;
var keys = Object.keys;
var tryOnCleanup = isDev ? (fn) => getOwner() ? onCleanup(fn) : fn : onCleanup;
var createCallbackStack = () => {
  let stack = [];
  const clear = () => stack = [];
  return {
    push: (...callbacks) => stack.push(...callbacks),
    execute(arg0, arg1, arg2, arg3) {
      stack.forEach((cb) => cb(arg0, arg1, arg2, arg3));
      clear();
    },
    clear
  };
};
function createHydratableSignal(serverValue, update, options) {
  if (isServer) {
    return createSignal(serverValue, options);
  }
  if (sharedConfig.context) {
    const [state, setState] = createSignal(serverValue, options);
    onMount(() => setState(() => update()));
    return [state, setState];
  }
  return createSignal(update(), options);
}
function handleDiffArray(current, prev, handleAdded, handleRemoved) {
  const currLength = current.length;
  const prevLength = prev.length;
  let i = 0;
  if (!prevLength) {
    for (; i < currLength; i++)
      handleAdded(current[i]);
    return;
  }
  if (!currLength) {
    for (; i < prevLength; i++)
      handleRemoved(prev[i]);
    return;
  }
  for (; i < prevLength; i++) {
    if (prev[i] !== current[i])
      break;
  }
  let prevEl;
  let currEl;
  prev = prev.slice(i);
  current = current.slice(i);
  for (prevEl of prev) {
    if (!current.includes(prevEl))
      handleRemoved(prevEl);
  }
  for (currEl of current) {
    if (!prev.includes(currEl))
      handleAdded(currEl);
  }
}

// ../../node_modules/.bun/@solid-primitives+event-listener@2.4.5+95b571dd5236cc92/node_modules/@solid-primitives/event-listener/dist/eventListener.js
function makeEventListener(target, type, handler, options) {
  target.addEventListener(type, handler, options);
  return tryOnCleanup(target.removeEventListener.bind(target, type, handler, options));
}
function createEventListener(targets, type, handler, options) {
  if (isServer)
    return;
  const attachListeners = () => {
    asArray(access(targets)).forEach((el) => {
      if (el)
        asArray(access(type)).forEach((type2) => makeEventListener(el, type2, handler, options));
    });
  };
  if (typeof targets === "function")
    createEffect(attachListeners);
  else
    createRenderEffect(attachListeners);
}
function createEventSignal(target, type, options) {
  if (isServer) {
    return () => void 0;
  }
  const [lastEvent, setLastEvent] = createSignal();
  createEventListener(target, type, setLastEvent, options);
  return lastEvent;
}
var eventListener = (target, props) => {
  createEffect(() => {
    const [type, handler, options] = props();
    makeEventListener(target, type, handler, options);
  });
};

// ../../node_modules/.bun/@solid-primitives+event-listener@2.4.5+95b571dd5236cc92/node_modules/@solid-primitives/event-listener/dist/eventListenerMap.js
function createEventListenerMap(targets, handlersMap, options) {
  if (isServer) {
    return;
  }
  for (const [eventName, handler] of entries(handlersMap)) {
    if (handler)
      createEventListener(targets, eventName, handler, options);
  }
}

// ../../node_modules/.bun/@solid-primitives+event-listener@2.4.5+95b571dd5236cc92/node_modules/@solid-primitives/event-listener/dist/components.js
var attachPropListeners = (target, props) => {
  keys(props).forEach((attr) => {
    if (attr.startsWith("on") && typeof props[attr] === "function")
      makeEventListener(target, attr.substring(2).toLowerCase(), props[attr]);
  });
};
var WindowEventListener = (props) => {
  if (isServer)
    return null;
  attachPropListeners(window, props);
};
var DocumentEventListener = (props) => {
  if (isServer)
    return null;
  attachPropListeners(document, props);
};

// ../../node_modules/.bun/@solid-primitives+event-listener@2.4.5+95b571dd5236cc92/node_modules/@solid-primitives/event-listener/dist/eventListenerStack.js
function makeEventListenerStack(target, options) {
  if (isServer) {
    return [() => () => void 0, () => void 0];
  }
  const { push, execute } = createCallbackStack();
  return [
    (type, handler, overwriteOptions) => {
      const clear = makeEventListener(target, type, handler, overwriteOptions ?? options);
      push(clear);
      return clear;
    },
    onCleanup(execute)
  ];
}

// ../../node_modules/.bun/@solid-primitives+event-listener@2.4.5+95b571dd5236cc92/node_modules/@solid-primitives/event-listener/dist/callbackWrappers.js
var preventDefault = (callback) => (e) => {
  e.preventDefault();
  callback(e);
};
var stopPropagation = (callback) => (e) => {
  e.stopPropagation();
  callback(e);
};
var stopImmediatePropagation = (callback) => (e) => {
  e.stopImmediatePropagation();
  callback(e);
};

export {
  noop,
  isObject,
  filterNonNullable,
  chain,
  access,
  asArray,
  accessWith,
  entries,
  createHydratableSignal,
  handleDiffArray,
  makeEventListener,
  createEventListener,
  createEventSignal,
  eventListener,
  createEventListenerMap,
  WindowEventListener,
  DocumentEventListener,
  makeEventListenerStack,
  preventDefault,
  stopPropagation,
  stopImmediatePropagation
};
//# sourceMappingURL=chunk-E4MUVEY4.js.map
