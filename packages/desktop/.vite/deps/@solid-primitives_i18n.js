import "./chunk-G3PMV62Z.js";

// ../../node_modules/.bun/@solid-primitives+i18n@2.2.1+95b571dd5236cc92/node_modules/@solid-primitives/i18n/dist/index.js
var isDict = (value) => value != null && (value = Object.getPrototypeOf(value), value === Array.prototype || value === Object.prototype);
var isRecordDict = (value) => value != null && Object.getPrototypeOf(value) === Object.prototype;
function visitDict(flat_dict, dict, path) {
  for (const [key, value] of Object.entries(dict)) {
    const key_path = `${path}.${key}`;
    flat_dict[key_path] = value;
    isDict(value) && visitDict(flat_dict, value, key_path);
  }
}
function flatten(dict) {
  const flat_dict = { ...dict };
  for (const [key, value] of Object.entries(dict)) {
    isDict(value) && visitDict(flat_dict, value, key);
  }
  return flat_dict;
}
var prefix = (dict, prefix2) => {
  prefix2 += ".";
  const result = {};
  for (const [key, value] of Object.entries(dict)) {
    result[prefix2 + key] = value;
  }
  return result;
};
var template = (source) => source;
var resolveTemplate = (string, args) => {
  if (args)
    for (const [key, value] of Object.entries(args))
      string = string.replace(new RegExp(`{{\\s*${key}\\s*}}`, "g"), value);
  return string;
};
var identityResolveTemplate = ((v) => v);
function translator(dict, resolveTemplate2 = identityResolveTemplate) {
  return (path, ...args) => {
    if (path[0] === ".")
      path = path.slice(1);
    const value = dict()?.[path];
    switch (typeof value) {
      case "function":
        return value(...args);
      case "string":
        return resolveTemplate2(value, args[0]);
      default:
        return value;
    }
  };
}
function scopedTranslator(translator2, scope) {
  return (path, ...args) => translator2(`${scope}.${path}`, ...args);
}
function chainedTranslator(init_dict, translate, path = "") {
  const result = { ...init_dict };
  for (const [key, value] of Object.entries(init_dict)) {
    const key_path = `${path}.${key}`;
    result[key] = isRecordDict(value) ? chainedTranslator(value, translate, key_path) : (...args) => translate(
      key_path,
      ...args
    );
  }
  return result;
}
function proxyTranslator(translate, path = "") {
  return new Proxy(translate.bind(void 0, path), new Traps(translate, path));
}
var Traps = class {
  translate;
  path;
  constructor(translate, path) {
    this.translate = translate;
    this.path = path;
  }
  get(target, prop) {
    if (typeof prop !== "string")
      return Reflect.get(target, prop);
    return proxyTranslator(this.translate, `${this.path}.${prop}`);
  }
  has(target, prop) {
    if (typeof prop !== "string")
      return Reflect.has(target, prop);
    return proxyTranslator(this.translate, `${this.path}.${prop}`) !== void 0;
  }
  getOwnPropertyDescriptor(target, prop) {
    if (typeof prop !== "string")
      return Reflect.getOwnPropertyDescriptor(target, prop);
    return {
      enumerable: true,
      get: () => proxyTranslator(this.translate, `${this.path}.${prop}`)
    };
  }
};
export {
  chainedTranslator,
  flatten,
  identityResolveTemplate,
  prefix,
  proxyTranslator,
  resolveTemplate,
  scopedTranslator,
  template,
  translator
};
//# sourceMappingURL=@solid-primitives_i18n.js.map
