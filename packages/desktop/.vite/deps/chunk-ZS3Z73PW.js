import {
  accessWith
} from "./chunk-E4MUVEY4.js";
import {
  createMemo,
  createSignal,
  untrack
} from "./chunk-BWBVP47I.js";

// ../../node_modules/.bun/@kobalte+core@0.13.11+95b571dd5236cc92/node_modules/@kobalte/core/dist/chunk/BLN63FDC.js
function createControllableSignal(props) {
  const [_value, _setValue] = createSignal(props.defaultValue?.());
  const isControlled = createMemo(() => props.value?.() !== void 0);
  const value = createMemo(() => isControlled() ? props.value?.() : _value());
  const setValue = (next) => {
    untrack(() => {
      const nextValue = accessWith(next, value());
      if (!Object.is(nextValue, value())) {
        if (!isControlled()) {
          _setValue(nextValue);
        }
        props.onChange?.(nextValue);
      }
      return nextValue;
    });
  };
  return [value, setValue];
}
function createControllableBooleanSignal(props) {
  const [_value, setValue] = createControllableSignal(props);
  const value = () => _value() ?? false;
  return [value, setValue];
}

// ../../node_modules/.bun/@kobalte+core@0.13.11+95b571dd5236cc92/node_modules/@kobalte/core/dist/chunk/E4R2EMM4.js
function createRegisterId(setter) {
  return (id) => {
    setter(id);
    return () => setter(void 0);
  };
}

export {
  createControllableSignal,
  createControllableBooleanSignal,
  createRegisterId
};
//# sourceMappingURL=chunk-ZS3Z73PW.js.map
