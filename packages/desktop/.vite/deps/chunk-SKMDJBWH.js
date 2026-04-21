import {
  isString
} from "./chunk-LGAWTJKT.js";
import {
  createEffect,
  createSignal
} from "./chunk-BWBVP47I.js";

// ../../node_modules/.bun/@kobalte+core@0.13.11+95b571dd5236cc92/node_modules/@kobalte/core/dist/chunk/ET5T45DO.js
function createTagName(ref, fallback) {
  const [tagName, setTagName] = createSignal(stringOrUndefined(fallback?.()));
  createEffect(() => {
    setTagName(ref()?.tagName.toLowerCase() || stringOrUndefined(fallback?.()));
  });
  return tagName;
}
function stringOrUndefined(value) {
  return isString(value) ? value : void 0;
}

export {
  createTagName
};
//# sourceMappingURL=chunk-SKMDJBWH.js.map
