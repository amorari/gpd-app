import {
  bundledLanguages,
  bundledThemes,
  createHighlighter,
  createJavaScriptRegexEngine,
  createOnigurumaEngine,
  normalizeTheme
} from "./chunk-Z2JJGLSS.js";

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/constants.js
var DIFFS_TAG_NAME = "diffs-container";
var COMMIT_METADATA_SPLIT = /(?=^From [a-f0-9]+ .+$)/m;
var GIT_DIFF_FILE_BREAK_REGEX = /(?=^diff --git)/gm;
var UNIFIED_DIFF_FILE_BREAK_REGEX = /(?=^---\s+\S)/gm;
var FILE_CONTEXT_BLOB = /(?=^@@ )/gm;
var HUNK_HEADER = /^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?: (.*))?/m;
var SPLIT_WITH_NEWLINES = new RegExp("(?<=\\n)");
var FILENAME_HEADER_REGEX = /^(---|\+\+\+)\s+([^\t\r\n]+)/;
var FILENAME_HEADER_REGEX_GIT = /^(---|\+\+\+)\s+[ab]\/([^\t\r\n]+)/;
var ALTERNATE_FILE_NAMES_GIT = /^diff --git (?:"a\/(.+?)"|a\/(.+?)) (?:"b\/(.+?)"|b\/(.+?))$/;
var INDEX_LINE_METADATA = /^index ([0-9a-f]+)\.\.([0-9a-f]+)(?: (\d+))?$/i;
var HEADER_PREFIX_SLOT_ID = "header-prefix";
var HEADER_METADATA_SLOT_ID = "header-metadata";
var DEFAULT_THEMES = {
  dark: "pierre-dark",
  light: "pierre-light"
};
var UNSAFE_CSS_ATTRIBUTE = "data-unsafe-css";
var CORE_CSS_ATTRIBUTE = "data-core-css";
var DEFAULT_COLLAPSED_CONTEXT_THRESHOLD = 1;
var DEFAULT_VIRTUAL_FILE_METRICS = {
  hunkLineCount: 50,
  lineHeight: 20,
  diffHeaderHeight: 44,
  hunkSeparatorHeight: 32,
  fileGap: 8
};
var DEFAULT_EXPANDED_REGION = Object.freeze({
  fromStart: 0,
  fromEnd: 0
});
var DEFAULT_RENDER_RANGE = {
  startingLine: 0,
  totalLines: Infinity,
  bufferBefore: 0,
  bufferAfter: 0
};
var EMPTY_RENDER_RANGE = {
  startingLine: 0,
  totalLines: 0,
  bufferBefore: 0,
  bufferAfter: 0
};

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/hast_utils.js
function createTextNodeElement(value) {
  return {
    type: "text",
    value
  };
}
function createHastElement({ tagName, children = [], properties = {} }) {
  return {
    type: "element",
    tagName,
    properties,
    children
  };
}
function createIconElement({ name, width = 16, height = 16, properties }) {
  return createHastElement({
    tagName: "svg",
    properties: {
      width,
      height,
      viewBox: "0 0 16 16",
      ...properties
    },
    children: [createHastElement({
      tagName: "use",
      properties: { href: `#${name.replace(/^#/, "")}` }
    })]
  });
}
function findCodeElement(nodes) {
  let firstChild = nodes.children[0];
  while (firstChild != null) {
    if (firstChild.type === "element" && firstChild.tagName === "code") return firstChild;
    if ("children" in firstChild) firstChild = firstChild.children[0];
    else firstChild = null;
  }
}
function createGutterWrapper(children) {
  return createHastElement({
    tagName: "div",
    properties: { "data-gutter": "" },
    children
  });
}
function createGutterItem(lineType, lineNumber, lineIndex) {
  return createHastElement({
    tagName: "div",
    properties: {
      "data-line-type": lineType,
      "data-column-number": lineNumber,
      "data-line-index": lineIndex
    },
    children: lineNumber != null ? [createHastElement({
      tagName: "span",
      properties: { "data-line-number-content": "" },
      children: [createTextNodeElement(`${lineNumber}`)]
    })] : void 0
  });
}
function createGutterGap(type, bufferType, size) {
  return createHastElement({
    tagName: "div",
    properties: {
      "data-gutter-buffer": bufferType,
      "data-buffer-size": size,
      "data-line-type": bufferType === "annotation" ? void 0 : type,
      style: bufferType === "annotation" ? `grid-row: span ${size};` : `grid-row: span ${size};min-height:calc(${size} * 1lh);`
    }
  });
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/languages/constants.js
var ResolvedLanguages = /* @__PURE__ */ new Map();
var ResolvingLanguages = /* @__PURE__ */ new Map();
var RegisteredCustomLanguages = /* @__PURE__ */ new Map();
var AttachedLanguages = /* @__PURE__ */ new Set();

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/languages/attachResolvedLanguages.js
function attachResolvedLanguages(resolvedLanguages, highlighter2) {
  resolvedLanguages = Array.isArray(resolvedLanguages) ? resolvedLanguages : [resolvedLanguages];
  for (const resolvedLang of resolvedLanguages) {
    if (AttachedLanguages.has(resolvedLang.name)) continue;
    let lang = ResolvedLanguages.get(resolvedLang.name);
    if (lang == null) {
      lang = resolvedLang;
      ResolvedLanguages.set(resolvedLang.name, lang);
    }
    AttachedLanguages.add(lang.name);
    highlighter2.loadLanguageSync(lang.data);
  }
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/languages/cleanUpResolvedLanguages.js
function cleanUpResolvedLanguages() {
  ResolvedLanguages.clear();
  AttachedLanguages.clear();
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/isWorkerContext.js
function isWorkerContext() {
  return typeof WorkerGlobalScope !== "undefined" && typeof self !== "undefined" && self instanceof WorkerGlobalScope;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/languages/resolveLanguage.js
async function resolveLanguage(lang) {
  if (isWorkerContext()) throw new Error(`resolveLanguage("${lang}") cannot be called from a worker context. Languages must be pre-resolved on the main thread and passed to the worker via the resolvedLanguages parameter.`);
  const resolver = ResolvingLanguages.get(lang);
  if (resolver != null) return resolver;
  try {
    let loader = RegisteredCustomLanguages.get(lang);
    if (loader == null && Object.prototype.hasOwnProperty.call(bundledLanguages, lang)) loader = bundledLanguages[lang];
    if (loader == null) throw new Error(`resolveLanguage: "${lang}" not found in bundled or custom languages`);
    const resolver$1 = loader().then(({ default: data }) => {
      const resolvedLang = {
        name: lang,
        data
      };
      if (!ResolvedLanguages.has(lang)) ResolvedLanguages.set(lang, resolvedLang);
      return resolvedLang;
    });
    ResolvingLanguages.set(lang, resolver$1);
    return await resolver$1;
  } finally {
    ResolvingLanguages.delete(lang);
  }
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/languages/getResolvedOrResolveLanguage.js
function getResolvedOrResolveLanguage(language) {
  return ResolvedLanguages.get(language) ?? resolveLanguage(language);
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/themes/constants.js
var ResolvedThemes = /* @__PURE__ */ new Map();
var ResolvingThemes = /* @__PURE__ */ new Map();
var RegisteredCustomThemes = /* @__PURE__ */ new Map();
var AttachedThemes = /* @__PURE__ */ new Set();

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/themes/attachResolvedThemes.js
function attachResolvedThemes(themes, highlighter2) {
  themes = Array.isArray(themes) ? themes : [themes];
  for (let themeRef of themes) {
    let resolvedTheme;
    if (typeof themeRef === "string") {
      resolvedTheme = ResolvedThemes.get(themeRef);
      if (resolvedTheme == null) throw new Error(`loadResolvedThemes: ${themeRef} is not resolved, you must resolve it before calling loadResolvedThemes`);
    } else {
      resolvedTheme = themeRef;
      themeRef = themeRef.name;
      if (!ResolvedThemes.has(themeRef)) ResolvedThemes.set(themeRef, resolvedTheme);
    }
    if (AttachedThemes.has(themeRef)) continue;
    AttachedThemes.add(themeRef);
    highlighter2.loadThemeSync(resolvedTheme);
  }
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/themes/cleanUpResolvedThemes.js
function cleanUpResolvedThemes() {
  ResolvedThemes.clear();
  AttachedThemes.clear();
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/themes/resolveTheme.js
async function resolveTheme(themeName) {
  if (isWorkerContext()) throw new Error(`resolveTheme("${themeName}") cannot be called from a worker context. Themes must be pre-resolved on the main thread and passed to the worker via the resolvedLanguages parameter.`);
  const resolver = ResolvingThemes.get(themeName);
  if (resolver != null) return resolver;
  try {
    const loader = RegisteredCustomThemes.get(themeName) ?? bundledThemes[themeName];
    if (loader == null) throw new Error(`resolveTheme: No valid loader for ${themeName}`);
    const resolver$1 = loader().then((result) => {
      return normalizeAndCacheResolvedTheme(themeName, "default" in result ? result.default : result);
    });
    ResolvingThemes.set(themeName, resolver$1);
    const theme = await resolver$1;
    if (theme.name !== themeName) throw new Error(`resolvedTheme: themeName: ${themeName} does not match theme.name: ${theme.name}`);
    ResolvedThemes.set(theme.name, theme);
    return theme;
  } finally {
    ResolvingThemes.delete(themeName);
  }
}
function normalizeAndCacheResolvedTheme(themeName, themeData) {
  const resolvedTheme = ResolvedThemes.get(themeName);
  if (resolvedTheme != null) return resolvedTheme;
  themeData = normalizeTheme(themeData);
  ResolvedThemes.set(themeName, themeData);
  return themeData;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/themes/getResolvedOrResolveTheme.js
function getResolvedOrResolveTheme(themeName) {
  return ResolvedThemes.get(themeName) ?? resolveTheme(themeName);
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/themes/registerCustomTheme.js
function registerCustomTheme(themeName, loader) {
  if (RegisteredCustomThemes.has(themeName)) {
    console.error("SharedHighlight.registerCustomTheme: theme name already registered", themeName);
    return;
  }
  RegisteredCustomThemes.set(themeName, loader);
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/shared_highlighter.js
var highlighter;
async function getSharedHighlighter({ themes, langs, preferredHighlighter = "shiki-js" }) {
  highlighter ??= createHighlighter({
    themes: [],
    langs: ["text"],
    engine: preferredHighlighter === "shiki-wasm" ? createOnigurumaEngine(import("./wasm-HD4ILBYE.js")) : createJavaScriptRegexEngine()
  });
  const instance = isHighlighterLoading(highlighter) ? await highlighter : highlighter;
  highlighter = instance;
  const languageLoaders = [];
  for (const language of langs) {
    if (language === "text" || language === "ansi") continue;
    const maybeResolvedLanguage = getResolvedOrResolveLanguage(language);
    if ("then" in maybeResolvedLanguage) languageLoaders.push(maybeResolvedLanguage);
    else attachResolvedLanguages(maybeResolvedLanguage, instance);
  }
  const themeLoaders = [];
  for (const themeName of themes) {
    const maybeResolvedTheme = getResolvedOrResolveTheme(themeName);
    if ("then" in maybeResolvedTheme) themeLoaders.push(maybeResolvedTheme);
    else attachResolvedThemes(maybeResolvedTheme, highlighter);
  }
  if (languageLoaders.length > 0 || themeLoaders.length > 0) await Promise.all([Promise.all(languageLoaders).then((languages) => {
    attachResolvedLanguages(languages, instance);
  }), Promise.all(themeLoaders).then((themes$1) => {
    attachResolvedThemes(themes$1, instance);
  })]);
  return instance;
}
function isHighlighterLoaded(h = highlighter) {
  return h != null && !("then" in h);
}
function getHighlighterIfLoaded() {
  if (highlighter != null && !("then" in highlighter)) return highlighter;
}
function isHighlighterLoading(h = highlighter) {
  return h != null && "then" in h;
}
function isHighlighterNull(h = highlighter) {
  return h == null;
}
async function preloadHighlighter(options) {
  await getSharedHighlighter(options);
}
async function disposeHighlighter() {
  if (highlighter == null) return;
  (await highlighter).dispose();
  cleanUpResolvedLanguages();
  cleanUpResolvedThemes();
  highlighter = void 0;
}
registerCustomTheme("pierre-dark", async () => {
  const m = await import("./pierre-dark-AWY3BJYE.js");
  return {
    ...m.default ?? m,
    name: "pierre-dark"
  };
});
registerCustomTheme("pierre-light", async () => {
  const m = await import("./pierre-light-RMOHIEQ7.js");
  return {
    ...m.default ?? m,
    name: "pierre-light"
  };
});

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/getThemes.js
function getThemes(theme = DEFAULT_THEMES) {
  const themesArr = [];
  if (typeof theme === "string") themesArr.push(theme);
  else {
    themesArr.push(theme.dark);
    themesArr.push(theme.light);
  }
  return themesArr;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/themes/hasResolvedThemes.js
function hasResolvedThemes(themeNames) {
  for (const themeName of themeNames) if (!ResolvedThemes.has(themeName)) return false;
  return true;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/areThemesEqual.js
function areThemesEqual(themeA, themeB) {
  if (themeA == null || themeB == null || typeof themeA === "string" || typeof themeB === "string") return themeA === themeB;
  return themeA.dark === themeB.dark && themeA.light === themeB.light;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/getFiletypeFromFileName.js
var CUSTOM_EXTENSION_TO_FILE_FORMAT = /* @__PURE__ */ new Map();
var EXTENSION_TO_FILE_FORMAT = {
  "1c": "1c",
  abap: "abap",
  as: "actionscript-3",
  ada: "ada",
  adb: "ada",
  ads: "ada",
  adoc: "asciidoc",
  asciidoc: "asciidoc",
  "component.html": "angular-html",
  "component.ts": "angular-ts",
  conf: "nginx",
  htaccess: "apache",
  cls: "tex",
  trigger: "apex",
  apl: "apl",
  applescript: "applescript",
  scpt: "applescript",
  ara: "ara",
  asm: "asm",
  s: "riscv",
  astro: "astro",
  awk: "awk",
  bal: "ballerina",
  sh: "zsh",
  bash: "zsh",
  bat: "cmd",
  cmd: "cmd",
  be: "berry",
  beancount: "beancount",
  bib: "bibtex",
  bicep: "bicep",
  "blade.php": "blade",
  bsl: "bsl",
  c: "c",
  h: "objective-cpp",
  cs: "csharp",
  cpp: "cpp",
  hpp: "cpp",
  cc: "cpp",
  cxx: "cpp",
  hh: "cpp",
  cdc: "cdc",
  cairo: "cairo",
  clar: "clarity",
  clj: "clojure",
  cljs: "clojure",
  cljc: "clojure",
  soy: "soy",
  cmake: "cmake",
  "CMakeLists.txt": "cmake",
  cob: "cobol",
  cbl: "cobol",
  cobol: "cobol",
  CODEOWNERS: "codeowners",
  ql: "ql",
  coffee: "coffeescript",
  lisp: "lisp",
  cl: "lisp",
  lsp: "lisp",
  log: "log",
  v: "verilog",
  cql: "cql",
  cr: "crystal",
  css: "css",
  csv: "csv",
  cue: "cue",
  cypher: "cypher",
  cyp: "cypher",
  d: "d",
  dart: "dart",
  dax: "dax",
  desktop: "desktop",
  diff: "diff",
  patch: "diff",
  Dockerfile: "dockerfile",
  dockerfile: "dockerfile",
  env: "dotenv",
  dm: "dream-maker",
  edge: "edge",
  el: "emacs-lisp",
  ex: "elixir",
  exs: "elixir",
  elm: "elm",
  erb: "erb",
  erl: "erlang",
  hrl: "erlang",
  f: "fortran-fixed-form",
  for: "fortran-fixed-form",
  fs: "fsharp",
  fsi: "fsharp",
  fsx: "fsharp",
  f03: "f03",
  f08: "f08",
  f18: "f18",
  f77: "f77",
  f90: "fortran-free-form",
  f95: "fortran-free-form",
  fnl: "fennel",
  fish: "fish",
  ftl: "ftl",
  tres: "gdresource",
  res: "gdresource",
  gd: "gdscript",
  gdshader: "gdshader",
  gs: "genie",
  feature: "gherkin",
  COMMIT_EDITMSG: "git-commit",
  "git-rebase-todo": "git-rebase",
  gjs: "glimmer-js",
  gleam: "gleam",
  gts: "glimmer-ts",
  glsl: "glsl",
  vert: "glsl",
  frag: "glsl",
  shader: "shaderlab",
  gp: "gnuplot",
  plt: "gnuplot",
  gnuplot: "gnuplot",
  go: "go",
  graphql: "graphql",
  gql: "graphql",
  groovy: "groovy",
  gvy: "groovy",
  hack: "hack",
  haml: "haml",
  hbs: "handlebars",
  handlebars: "handlebars",
  hs: "haskell",
  lhs: "haskell",
  hx: "haxe",
  hcl: "hcl",
  hjson: "hjson",
  hlsl: "hlsl",
  fx: "hlsl",
  html: "html",
  htm: "html",
  http: "http",
  rest: "http",
  hxml: "hxml",
  hy: "hy",
  imba: "imba",
  ini: "ini",
  cfg: "ini",
  jade: "pug",
  pug: "pug",
  java: "java",
  js: "javascript",
  mjs: "javascript",
  cjs: "javascript",
  jinja: "jinja",
  jinja2: "jinja",
  j2: "jinja",
  jison: "jison",
  jl: "julia",
  json: "json",
  json5: "json5",
  jsonc: "jsonc",
  jsonl: "jsonl",
  jsonnet: "jsonnet",
  libsonnet: "jsonnet",
  jssm: "jssm",
  jsx: "jsx",
  kt: "kotlin",
  kts: "kts",
  kql: "kusto",
  tex: "tex",
  ltx: "tex",
  lean: "lean4",
  less: "less",
  liquid: "liquid",
  lit: "lit",
  ll: "llvm",
  logo: "logo",
  lua: "lua",
  luau: "luau",
  Makefile: "makefile",
  mk: "makefile",
  makefile: "makefile",
  md: "markdown",
  markdown: "markdown",
  marko: "marko",
  m: "wolfram",
  mat: "matlab",
  mdc: "mdc",
  mdx: "mdx",
  wiki: "wikitext",
  mediawiki: "wikitext",
  mmd: "mermaid",
  mermaid: "mermaid",
  mips: "mipsasm",
  mojo: "mojo",
  "🔥": "mojo",
  move: "move",
  nar: "narrat",
  nf: "nextflow",
  nim: "nim",
  nims: "nim",
  nimble: "nim",
  nix: "nix",
  nu: "nushell",
  mm: "objective-cpp",
  ml: "ocaml",
  mli: "ocaml",
  mll: "ocaml",
  mly: "ocaml",
  pas: "pascal",
  p: "pascal",
  pl: "prolog",
  pm: "perl",
  t: "perl",
  raku: "raku",
  p6: "raku",
  pl6: "raku",
  php: "php",
  phtml: "php",
  pls: "plsql",
  sql: "sql",
  po: "po",
  polar: "polar",
  pcss: "postcss",
  pot: "pot",
  potx: "potx",
  pq: "powerquery",
  pqm: "powerquery",
  ps1: "powershell",
  psm1: "powershell",
  psd1: "powershell",
  prisma: "prisma",
  pro: "prolog",
  P: "prolog",
  properties: "properties",
  proto: "protobuf",
  pp: "puppet",
  purs: "purescript",
  py: "python",
  pyw: "python",
  pyi: "python",
  qml: "qml",
  qmldir: "qmldir",
  qss: "qss",
  r: "r",
  R: "r",
  rkt: "racket",
  rktl: "racket",
  razor: "razor",
  cshtml: "razor",
  rb: "ruby",
  rbw: "ruby",
  reg: "reg",
  regex: "regexp",
  rel: "rel",
  rs: "rust",
  rst: "rst",
  rake: "ruby",
  gemspec: "ruby",
  sas: "sas",
  sass: "sass",
  scala: "scala",
  sc: "scala",
  scm: "scheme",
  ss: "scheme",
  sld: "scheme",
  scss: "scss",
  sdbl: "sdbl",
  shadergraph: "shader",
  st: "smalltalk",
  sol: "solidity",
  sparql: "sparql",
  rq: "sparql",
  spl: "splunk",
  config: "ssh-config",
  do: "stata",
  ado: "stata",
  dta: "stata",
  styl: "stylus",
  stylus: "stylus",
  svelte: "svelte",
  swift: "swift",
  sv: "system-verilog",
  svh: "system-verilog",
  service: "systemd",
  socket: "systemd",
  device: "systemd",
  timer: "systemd",
  talon: "talonscript",
  tasl: "tasl",
  tcl: "tcl",
  templ: "templ",
  tf: "tf",
  tfvars: "tfvars",
  toml: "toml",
  ts: "typescript",
  tsp: "typespec",
  tsv: "tsv",
  tsx: "tsx",
  ttl: "turtle",
  twig: "twig",
  typ: "typst",
  vv: "v",
  vala: "vala",
  vapi: "vala",
  vb: "vb",
  vbs: "vb",
  bas: "vb",
  vh: "verilog",
  vhd: "vhdl",
  vhdl: "vhdl",
  vim: "vimscript",
  vue: "vue",
  "vine.ts": "vue-vine",
  vy: "vyper",
  wasm: "wasm",
  wat: "wasm",
  wy: "文言",
  wgsl: "wgsl",
  wit: "wit",
  wl: "wolfram",
  nb: "wolfram",
  xml: "xml",
  xsl: "xsl",
  xslt: "xsl",
  yaml: "yaml",
  yml: "yml",
  zs: "zenscript",
  zig: "zig",
  zsh: "zsh",
  sty: "tex"
};
function getFiletypeFromFileName(fileName) {
  if (CUSTOM_EXTENSION_TO_FILE_FORMAT.has(fileName)) return CUSTOM_EXTENSION_TO_FILE_FORMAT.get(fileName) ?? "text";
  if (EXTENSION_TO_FILE_FORMAT[fileName] != null) return EXTENSION_TO_FILE_FORMAT[fileName];
  const compoundMatch = fileName.match(/\.([^/\\]+\.[^/\\]+)$/);
  if (compoundMatch != null) {
    if (CUSTOM_EXTENSION_TO_FILE_FORMAT.has(compoundMatch[1])) return CUSTOM_EXTENSION_TO_FILE_FORMAT.get(compoundMatch[1]) ?? "text";
    if (EXTENSION_TO_FILE_FORMAT[compoundMatch[1]] != null) return EXTENSION_TO_FILE_FORMAT[compoundMatch[1]] ?? "text";
  }
  const simpleMatch = fileName.match(/\.([^.]+)$/)?.[1] ?? "";
  if (CUSTOM_EXTENSION_TO_FILE_FORMAT.has(simpleMatch)) return CUSTOM_EXTENSION_TO_FILE_FORMAT.get(simpleMatch) ?? "text";
  return EXTENSION_TO_FILE_FORMAT[simpleMatch] ?? "text";
}
function extendFileFormatMap(map) {
  for (const key in map) {
    const lang = map[key];
    if (lang != null) CUSTOM_EXTENSION_TO_FILE_FORMAT.set(key, lang);
  }
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/cleanLastNewline.js
function cleanLastNewline(contents) {
  return contents.replace(/\n$|\r\n$/, "");
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/processLine.js
function processLine(node, line, state) {
  const lineInfo = typeof state.lineInfo === "function" ? state.lineInfo(line) : state.lineInfo[line - 1];
  if (lineInfo == null) {
    const errorMessage = `processLine: line ${line}, contains no state.lineInfo`;
    console.error(errorMessage, {
      node,
      line,
      state
    });
    throw new Error(errorMessage);
  }
  node.tagName = "div";
  node.properties["data-line"] = lineInfo.lineNumber;
  node.properties["data-alt-line"] = lineInfo.altLineNumber;
  node.properties["data-line-type"] = lineInfo.type;
  node.properties["data-line-index"] = lineInfo.lineIndex;
  if (node.children.length === 0) node.children.push(createTextNodeElement("\n"));
  return node;
}

// ../../node_modules/.bun/@shikijs+transformers@3.20.0/node_modules/@shikijs/transformers/dist/index.mjs
var symbol = Symbol("highlighted-lines");
function transformerStyleToClass(options = {}) {
  const {
    classPrefix = "__shiki_",
    classSuffix = "",
    classReplacer = (className) => className
  } = options;
  const classToStyle = /* @__PURE__ */ new Map();
  function stringifyStyle(style) {
    return Object.entries(style).map(([key, value]) => `${key}:${value}`).join(";");
  }
  function registerStyle(style) {
    const str = typeof style === "string" ? style : stringifyStyle(style);
    let className = classPrefix + cyrb53(str) + classSuffix;
    className = classReplacer(className);
    if (!classToStyle.has(className)) {
      classToStyle.set(
        className,
        typeof style === "string" ? style : { ...style }
      );
    }
    return className;
  }
  return {
    name: "@shikijs/transformers:style-to-class",
    pre(t) {
      if (!t.properties.style)
        return;
      const className = registerStyle(t.properties.style);
      delete t.properties.style;
      this.addClassToHast(t, className);
    },
    tokens(lines) {
      for (const line of lines) {
        for (const token of line) {
          if (!token.htmlStyle)
            continue;
          const className = registerStyle(token.htmlStyle);
          token.htmlStyle = {};
          token.htmlAttrs ||= {};
          if (!token.htmlAttrs.class)
            token.htmlAttrs.class = className;
          else
            token.htmlAttrs.class += ` ${className}`;
        }
      }
    },
    getClassRegistry() {
      return classToStyle;
    },
    getCSS() {
      let css = "";
      for (const [className, style] of classToStyle.entries()) {
        css += `.${className}{${typeof style === "string" ? style : stringifyStyle(style)}}`;
      }
      return css;
    },
    clearRegistry() {
      classToStyle.clear();
    }
  };
}
function cyrb53(str, seed = 0) {
  let h1 = 3735928559 ^ seed;
  let h2 = 1103547991 ^ seed;
  for (let i = 0, ch; i < str.length; i++) {
    ch = str.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ h1 >>> 16, 2246822507);
  h1 ^= Math.imul(h2 ^ h2 >>> 13, 3266489909);
  h2 = Math.imul(h2 ^ h2 >>> 16, 2246822507);
  h2 ^= Math.imul(h1 ^ h1 >>> 13, 3266489909);
  return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(36).slice(0, 6);
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/createTransformerWithState.js
function createTransformerWithState(useCSSClasses = false) {
  const state = { lineInfo: [] };
  const transformers = [{
    line(node) {
      delete node.properties.class;
      return node;
    },
    pre(pre) {
      const code = findCodeElement(pre);
      const children = [];
      if (code != null) {
        let index = 1;
        for (const node of code.children) {
          if (node.type !== "element") continue;
          children.push(processLine(node, index, state));
          index++;
        }
        code.children = children;
      }
      return pre;
    }
  }];
  if (useCSSClasses) transformers.push(tokenStyleNormalizer, toClass);
  return {
    state,
    transformers,
    toClass
  };
}
var toClass = transformerStyleToClass({ classPrefix: "hl-" });
var tokenStyleNormalizer = {
  name: "token-style-normalizer",
  tokens(lines) {
    for (const line of lines) for (const token of line) {
      if (token.htmlStyle != null) continue;
      const style = {};
      if (token.color != null) style.color = token.color;
      if (token.bgColor != null) style["background-color"] = token.bgColor;
      if (token.fontStyle != null && token.fontStyle !== 0) {
        if ((token.fontStyle & 1) !== 0) style["font-style"] = "italic";
        if ((token.fontStyle & 2) !== 0) style["font-weight"] = "bold";
        if ((token.fontStyle & 4) !== 0) style["text-decoration"] = "underline";
      }
      if (Object.keys(style).length > 0) token.htmlStyle = style;
    }
  }
};

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/formatCSSVariablePrefix.js
function formatCSSVariablePrefix(type) {
  return `--${type === "token" ? "diffs-token" : "diffs"}-`;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/getHighlighterThemeStyles.js
function getHighlighterThemeStyles({ theme = DEFAULT_THEMES, highlighter: highlighter2, prefix }) {
  let styles = "";
  if (typeof theme === "string") {
    const themeData = highlighter2.getTheme(theme);
    styles += `color:${themeData.fg};`;
    styles += `background-color:${themeData.bg};`;
    styles += `${formatCSSVariablePrefix("global")}fg:${themeData.fg};`;
    styles += `${formatCSSVariablePrefix("global")}bg:${themeData.bg};`;
    styles += getThemeVariables(themeData, prefix);
  } else {
    let themeData = highlighter2.getTheme(theme.dark);
    styles += `${formatCSSVariablePrefix("global")}dark:${themeData.fg};`;
    styles += `${formatCSSVariablePrefix("global")}dark-bg:${themeData.bg};`;
    styles += getThemeVariables(themeData, "dark");
    themeData = highlighter2.getTheme(theme.light);
    styles += `${formatCSSVariablePrefix("global")}light:${themeData.fg};`;
    styles += `${formatCSSVariablePrefix("global")}light-bg:${themeData.bg};`;
    styles += getThemeVariables(themeData, "light");
  }
  return styles;
}
function getThemeVariables(themeData, modePrefix) {
  modePrefix = modePrefix != null ? `${modePrefix}-` : "";
  let styles = "";
  const additionGreen = themeData.colors?.["gitDecoration.addedResourceForeground"] ?? themeData.colors?.["terminal.ansiGreen"];
  if (additionGreen != null) styles += `${formatCSSVariablePrefix("global")}${modePrefix}addition-color:${additionGreen};`;
  const deletionRed = themeData.colors?.["gitDecoration.deletedResourceForeground"] ?? themeData.colors?.["terminal.ansiRed"];
  if (deletionRed != null) styles += `${formatCSSVariablePrefix("global")}${modePrefix}deletion-color:${deletionRed};`;
  const modifiedBlue = themeData.colors?.["gitDecoration.modifiedResourceForeground"] ?? themeData.colors?.["terminal.ansiBlue"];
  if (modifiedBlue != null) styles += `${formatCSSVariablePrefix("global")}${modePrefix}modified-color:${modifiedBlue};`;
  return styles;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/getLineNodes.js
function getLineNodes(nodes) {
  let firstChild = nodes.children[0];
  while (firstChild != null) {
    if (firstChild.type === "element" && firstChild.tagName === "code") return firstChild.children;
    if ("children" in firstChild) firstChild = firstChild.children[0];
    else firstChild = null;
  }
  console.error(nodes);
  throw new Error("getLineNodes: Unable to find children");
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/iterateOverFile.js
function iterateOverFile({ lines, startingLine = 0, totalLines = Infinity, callback }) {
  const len = Math.min(startingLine + totalLines, lines.length);
  const lastLineIndex = (() => {
    const lastLine = lines.at(-1);
    if (lastLine === "" || lastLine === "\n" || lastLine === "\r\n" || lastLine === "\r") return Math.max(0, lines.length - 2);
    return lines.length - 1;
  })();
  for (let lineIndex = startingLine; lineIndex < len; lineIndex++) {
    const isLastLine = lineIndex === lastLineIndex;
    if (callback({
      lineIndex,
      lineNumber: lineIndex + 1,
      content: lines[lineIndex],
      isLastLine
    }) === true || isLastLine) break;
  }
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/splitFileContents.js
function splitFileContents(contents) {
  return contents !== "" ? contents.split(SPLIT_WITH_NEWLINES) : [];
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/renderFileWithHighlighter.js
var DEFAULT_PLAIN_TEXT_OPTIONS = { forcePlainText: false };
function renderFileWithHighlighter(file, highlighter2, { theme = DEFAULT_THEMES, tokenizeMaxLineLength }, { forcePlainText, startingLine, totalLines, lines } = DEFAULT_PLAIN_TEXT_OPTIONS) {
  if (forcePlainText) {
    startingLine ??= 0;
    totalLines ??= Infinity;
  } else {
    startingLine = 0;
    totalLines = Infinity;
  }
  const isWindowedHighlight = startingLine > 0 || totalLines < Infinity;
  const { state, transformers } = createTransformerWithState();
  const lang = forcePlainText ? "text" : file.lang ?? getFiletypeFromFileName(file.name);
  const baseThemeType = (() => {
    if (typeof theme === "string") return highlighter2.getTheme(theme).type;
  })();
  const themeStyles = getHighlighterThemeStyles({
    theme,
    highlighter: highlighter2
  });
  state.lineInfo = (shikiLineNumber) => ({
    type: "context",
    lineIndex: shikiLineNumber - 1 + startingLine,
    lineNumber: shikiLineNumber + startingLine
  });
  const hastConfig = (() => {
    if (typeof theme === "string") return {
      lang,
      theme,
      transformers,
      defaultColor: false,
      cssVariablePrefix: formatCSSVariablePrefix("token"),
      tokenizeMaxLineLength
    };
    return {
      lang,
      themes: theme,
      transformers,
      defaultColor: false,
      cssVariablePrefix: formatCSSVariablePrefix("token"),
      tokenizeMaxLineLength
    };
  })();
  const highlightedLines = getLineNodes(highlighter2.codeToHast(isWindowedHighlight ? extractWindowedFileContent(lines ?? splitFileContents(file.contents), startingLine, totalLines) : cleanLastNewline(file.contents), hastConfig));
  const code = isWindowedHighlight ? new Array(startingLine) : highlightedLines;
  if (isWindowedHighlight) code.push(...highlightedLines);
  return {
    code,
    themeStyles,
    baseThemeType
  };
}
function extractWindowedFileContent(lines, startingLine, totalLines) {
  let windowContent = "";
  iterateOverFile({
    lines,
    startingLine,
    totalLines,
    callback({ content }) {
      windowContent += content;
    }
  });
  return windowContent;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/areFilesEqual.js
function areFilesEqual(fileA, fileB) {
  return fileA?.cacheKey === fileB?.cacheKey && fileA?.contents === fileB?.contents && fileA?.name === fileB?.name && fileA?.lang === fileB?.lang;
}

// ../../node_modules/.bun/diff@8.0.3/node_modules/diff/libesm/diff/base.js
var Diff = class {
  diff(oldStr, newStr, options = {}) {
    let callback;
    if (typeof options === "function") {
      callback = options;
      options = {};
    } else if ("callback" in options) {
      callback = options.callback;
    }
    const oldString = this.castInput(oldStr, options);
    const newString = this.castInput(newStr, options);
    const oldTokens = this.removeEmpty(this.tokenize(oldString, options));
    const newTokens = this.removeEmpty(this.tokenize(newString, options));
    return this.diffWithOptionsObj(oldTokens, newTokens, options, callback);
  }
  diffWithOptionsObj(oldTokens, newTokens, options, callback) {
    var _a;
    const done = (value) => {
      value = this.postProcess(value, options);
      if (callback) {
        setTimeout(function() {
          callback(value);
        }, 0);
        return void 0;
      } else {
        return value;
      }
    };
    const newLen = newTokens.length, oldLen = oldTokens.length;
    let editLength = 1;
    let maxEditLength = newLen + oldLen;
    if (options.maxEditLength != null) {
      maxEditLength = Math.min(maxEditLength, options.maxEditLength);
    }
    const maxExecutionTime = (_a = options.timeout) !== null && _a !== void 0 ? _a : Infinity;
    const abortAfterTimestamp = Date.now() + maxExecutionTime;
    const bestPath = [{ oldPos: -1, lastComponent: void 0 }];
    let newPos = this.extractCommon(bestPath[0], newTokens, oldTokens, 0, options);
    if (bestPath[0].oldPos + 1 >= oldLen && newPos + 1 >= newLen) {
      return done(this.buildValues(bestPath[0].lastComponent, newTokens, oldTokens));
    }
    let minDiagonalToConsider = -Infinity, maxDiagonalToConsider = Infinity;
    const execEditLength = () => {
      for (let diagonalPath = Math.max(minDiagonalToConsider, -editLength); diagonalPath <= Math.min(maxDiagonalToConsider, editLength); diagonalPath += 2) {
        let basePath;
        const removePath = bestPath[diagonalPath - 1], addPath = bestPath[diagonalPath + 1];
        if (removePath) {
          bestPath[diagonalPath - 1] = void 0;
        }
        let canAdd = false;
        if (addPath) {
          const addPathNewPos = addPath.oldPos - diagonalPath;
          canAdd = addPath && 0 <= addPathNewPos && addPathNewPos < newLen;
        }
        const canRemove = removePath && removePath.oldPos + 1 < oldLen;
        if (!canAdd && !canRemove) {
          bestPath[diagonalPath] = void 0;
          continue;
        }
        if (!canRemove || canAdd && removePath.oldPos < addPath.oldPos) {
          basePath = this.addToPath(addPath, true, false, 0, options);
        } else {
          basePath = this.addToPath(removePath, false, true, 1, options);
        }
        newPos = this.extractCommon(basePath, newTokens, oldTokens, diagonalPath, options);
        if (basePath.oldPos + 1 >= oldLen && newPos + 1 >= newLen) {
          return done(this.buildValues(basePath.lastComponent, newTokens, oldTokens)) || true;
        } else {
          bestPath[diagonalPath] = basePath;
          if (basePath.oldPos + 1 >= oldLen) {
            maxDiagonalToConsider = Math.min(maxDiagonalToConsider, diagonalPath - 1);
          }
          if (newPos + 1 >= newLen) {
            minDiagonalToConsider = Math.max(minDiagonalToConsider, diagonalPath + 1);
          }
        }
      }
      editLength++;
    };
    if (callback) {
      (function exec() {
        setTimeout(function() {
          if (editLength > maxEditLength || Date.now() > abortAfterTimestamp) {
            return callback(void 0);
          }
          if (!execEditLength()) {
            exec();
          }
        }, 0);
      })();
    } else {
      while (editLength <= maxEditLength && Date.now() <= abortAfterTimestamp) {
        const ret = execEditLength();
        if (ret) {
          return ret;
        }
      }
    }
  }
  addToPath(path, added, removed, oldPosInc, options) {
    const last = path.lastComponent;
    if (last && !options.oneChangePerToken && last.added === added && last.removed === removed) {
      return {
        oldPos: path.oldPos + oldPosInc,
        lastComponent: { count: last.count + 1, added, removed, previousComponent: last.previousComponent }
      };
    } else {
      return {
        oldPos: path.oldPos + oldPosInc,
        lastComponent: { count: 1, added, removed, previousComponent: last }
      };
    }
  }
  extractCommon(basePath, newTokens, oldTokens, diagonalPath, options) {
    const newLen = newTokens.length, oldLen = oldTokens.length;
    let oldPos = basePath.oldPos, newPos = oldPos - diagonalPath, commonCount = 0;
    while (newPos + 1 < newLen && oldPos + 1 < oldLen && this.equals(oldTokens[oldPos + 1], newTokens[newPos + 1], options)) {
      newPos++;
      oldPos++;
      commonCount++;
      if (options.oneChangePerToken) {
        basePath.lastComponent = { count: 1, previousComponent: basePath.lastComponent, added: false, removed: false };
      }
    }
    if (commonCount && !options.oneChangePerToken) {
      basePath.lastComponent = { count: commonCount, previousComponent: basePath.lastComponent, added: false, removed: false };
    }
    basePath.oldPos = oldPos;
    return newPos;
  }
  equals(left, right, options) {
    if (options.comparator) {
      return options.comparator(left, right);
    } else {
      return left === right || !!options.ignoreCase && left.toLowerCase() === right.toLowerCase();
    }
  }
  removeEmpty(array) {
    const ret = [];
    for (let i = 0; i < array.length; i++) {
      if (array[i]) {
        ret.push(array[i]);
      }
    }
    return ret;
  }
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  castInput(value, options) {
    return value;
  }
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  tokenize(value, options) {
    return Array.from(value);
  }
  join(chars) {
    return chars.join("");
  }
  postProcess(changeObjects, options) {
    return changeObjects;
  }
  get useLongestToken() {
    return false;
  }
  buildValues(lastComponent, newTokens, oldTokens) {
    const components = [];
    let nextComponent;
    while (lastComponent) {
      components.push(lastComponent);
      nextComponent = lastComponent.previousComponent;
      delete lastComponent.previousComponent;
      lastComponent = nextComponent;
    }
    components.reverse();
    const componentLen = components.length;
    let componentPos = 0, newPos = 0, oldPos = 0;
    for (; componentPos < componentLen; componentPos++) {
      const component = components[componentPos];
      if (!component.removed) {
        if (!component.added && this.useLongestToken) {
          let value = newTokens.slice(newPos, newPos + component.count);
          value = value.map(function(value2, i) {
            const oldValue = oldTokens[oldPos + i];
            return oldValue.length > value2.length ? oldValue : value2;
          });
          component.value = this.join(value);
        } else {
          component.value = this.join(newTokens.slice(newPos, newPos + component.count));
        }
        newPos += component.count;
        if (!component.added) {
          oldPos += component.count;
        }
      } else {
        component.value = this.join(oldTokens.slice(oldPos, oldPos + component.count));
        oldPos += component.count;
      }
    }
    return components;
  }
};

// ../../node_modules/.bun/diff@8.0.3/node_modules/diff/libesm/diff/character.js
var CharacterDiff = class extends Diff {
};
var characterDiff = new CharacterDiff();
function diffChars(oldStr, newStr, options) {
  return characterDiff.diff(oldStr, newStr, options);
}

// ../../node_modules/.bun/diff@8.0.3/node_modules/diff/libesm/util/string.js
function longestCommonPrefix(str1, str2) {
  let i;
  for (i = 0; i < str1.length && i < str2.length; i++) {
    if (str1[i] != str2[i]) {
      return str1.slice(0, i);
    }
  }
  return str1.slice(0, i);
}
function longestCommonSuffix(str1, str2) {
  let i;
  if (!str1 || !str2 || str1[str1.length - 1] != str2[str2.length - 1]) {
    return "";
  }
  for (i = 0; i < str1.length && i < str2.length; i++) {
    if (str1[str1.length - (i + 1)] != str2[str2.length - (i + 1)]) {
      return str1.slice(-i);
    }
  }
  return str1.slice(-i);
}
function replacePrefix(string, oldPrefix, newPrefix) {
  if (string.slice(0, oldPrefix.length) != oldPrefix) {
    throw Error(`string ${JSON.stringify(string)} doesn't start with prefix ${JSON.stringify(oldPrefix)}; this is a bug`);
  }
  return newPrefix + string.slice(oldPrefix.length);
}
function replaceSuffix(string, oldSuffix, newSuffix) {
  if (!oldSuffix) {
    return string + newSuffix;
  }
  if (string.slice(-oldSuffix.length) != oldSuffix) {
    throw Error(`string ${JSON.stringify(string)} doesn't end with suffix ${JSON.stringify(oldSuffix)}; this is a bug`);
  }
  return string.slice(0, -oldSuffix.length) + newSuffix;
}
function removePrefix(string, oldPrefix) {
  return replacePrefix(string, oldPrefix, "");
}
function removeSuffix(string, oldSuffix) {
  return replaceSuffix(string, oldSuffix, "");
}
function maximumOverlap(string1, string2) {
  return string2.slice(0, overlapCount(string1, string2));
}
function overlapCount(a, b) {
  let startA = 0;
  if (a.length > b.length) {
    startA = a.length - b.length;
  }
  let endB = b.length;
  if (a.length < b.length) {
    endB = a.length;
  }
  const map = Array(endB);
  let k = 0;
  map[0] = 0;
  for (let j = 1; j < endB; j++) {
    if (b[j] == b[k]) {
      map[j] = map[k];
    } else {
      map[j] = k;
    }
    while (k > 0 && b[j] != b[k]) {
      k = map[k];
    }
    if (b[j] == b[k]) {
      k++;
    }
  }
  k = 0;
  for (let i = startA; i < a.length; i++) {
    while (k > 0 && a[i] != b[k]) {
      k = map[k];
    }
    if (a[i] == b[k]) {
      k++;
    }
  }
  return k;
}
function trailingWs(string) {
  let i;
  for (i = string.length - 1; i >= 0; i--) {
    if (!string[i].match(/\s/)) {
      break;
    }
  }
  return string.substring(i + 1);
}
function leadingWs(string) {
  const match = string.match(/^\s*/);
  return match ? match[0] : "";
}

// ../../node_modules/.bun/diff@8.0.3/node_modules/diff/libesm/diff/word.js
var extendedWordChars = "a-zA-Z0-9_\\u{AD}\\u{C0}-\\u{D6}\\u{D8}-\\u{F6}\\u{F8}-\\u{2C6}\\u{2C8}-\\u{2D7}\\u{2DE}-\\u{2FF}\\u{1E00}-\\u{1EFF}";
var tokenizeIncludingWhitespace = new RegExp(`[${extendedWordChars}]+|\\s+|[^${extendedWordChars}]`, "ug");
var WordDiff = class extends Diff {
  equals(left, right, options) {
    if (options.ignoreCase) {
      left = left.toLowerCase();
      right = right.toLowerCase();
    }
    return left.trim() === right.trim();
  }
  tokenize(value, options = {}) {
    let parts;
    if (options.intlSegmenter) {
      const segmenter = options.intlSegmenter;
      if (segmenter.resolvedOptions().granularity != "word") {
        throw new Error('The segmenter passed must have a granularity of "word"');
      }
      parts = [];
      for (const segmentObj of Array.from(segmenter.segment(value))) {
        const segment = segmentObj.segment;
        if (parts.length && /\s/.test(parts[parts.length - 1]) && /\s/.test(segment)) {
          parts[parts.length - 1] += segment;
        } else {
          parts.push(segment);
        }
      }
    } else {
      parts = value.match(tokenizeIncludingWhitespace) || [];
    }
    const tokens = [];
    let prevPart = null;
    parts.forEach((part) => {
      if (/\s/.test(part)) {
        if (prevPart == null) {
          tokens.push(part);
        } else {
          tokens.push(tokens.pop() + part);
        }
      } else if (prevPart != null && /\s/.test(prevPart)) {
        if (tokens[tokens.length - 1] == prevPart) {
          tokens.push(tokens.pop() + part);
        } else {
          tokens.push(prevPart + part);
        }
      } else {
        tokens.push(part);
      }
      prevPart = part;
    });
    return tokens;
  }
  join(tokens) {
    return tokens.map((token, i) => {
      if (i == 0) {
        return token;
      } else {
        return token.replace(/^\s+/, "");
      }
    }).join("");
  }
  postProcess(changes, options) {
    if (!changes || options.oneChangePerToken) {
      return changes;
    }
    let lastKeep = null;
    let insertion = null;
    let deletion = null;
    changes.forEach((change) => {
      if (change.added) {
        insertion = change;
      } else if (change.removed) {
        deletion = change;
      } else {
        if (insertion || deletion) {
          dedupeWhitespaceInChangeObjects(lastKeep, deletion, insertion, change);
        }
        lastKeep = change;
        insertion = null;
        deletion = null;
      }
    });
    if (insertion || deletion) {
      dedupeWhitespaceInChangeObjects(lastKeep, deletion, insertion, null);
    }
    return changes;
  }
};
var wordDiff = new WordDiff();
function dedupeWhitespaceInChangeObjects(startKeep, deletion, insertion, endKeep) {
  if (deletion && insertion) {
    const oldWsPrefix = leadingWs(deletion.value);
    const oldWsSuffix = trailingWs(deletion.value);
    const newWsPrefix = leadingWs(insertion.value);
    const newWsSuffix = trailingWs(insertion.value);
    if (startKeep) {
      const commonWsPrefix = longestCommonPrefix(oldWsPrefix, newWsPrefix);
      startKeep.value = replaceSuffix(startKeep.value, newWsPrefix, commonWsPrefix);
      deletion.value = removePrefix(deletion.value, commonWsPrefix);
      insertion.value = removePrefix(insertion.value, commonWsPrefix);
    }
    if (endKeep) {
      const commonWsSuffix = longestCommonSuffix(oldWsSuffix, newWsSuffix);
      endKeep.value = replacePrefix(endKeep.value, newWsSuffix, commonWsSuffix);
      deletion.value = removeSuffix(deletion.value, commonWsSuffix);
      insertion.value = removeSuffix(insertion.value, commonWsSuffix);
    }
  } else if (insertion) {
    if (startKeep) {
      const ws = leadingWs(insertion.value);
      insertion.value = insertion.value.substring(ws.length);
    }
    if (endKeep) {
      const ws = leadingWs(endKeep.value);
      endKeep.value = endKeep.value.substring(ws.length);
    }
  } else if (startKeep && endKeep) {
    const newWsFull = leadingWs(endKeep.value), delWsStart = leadingWs(deletion.value), delWsEnd = trailingWs(deletion.value);
    const newWsStart = longestCommonPrefix(newWsFull, delWsStart);
    deletion.value = removePrefix(deletion.value, newWsStart);
    const newWsEnd = longestCommonSuffix(removePrefix(newWsFull, newWsStart), delWsEnd);
    deletion.value = removeSuffix(deletion.value, newWsEnd);
    endKeep.value = replacePrefix(endKeep.value, newWsFull, newWsEnd);
    startKeep.value = replaceSuffix(startKeep.value, newWsFull, newWsFull.slice(0, newWsFull.length - newWsEnd.length));
  } else if (endKeep) {
    const endKeepWsPrefix = leadingWs(endKeep.value);
    const deletionWsSuffix = trailingWs(deletion.value);
    const overlap = maximumOverlap(deletionWsSuffix, endKeepWsPrefix);
    deletion.value = removeSuffix(deletion.value, overlap);
  } else if (startKeep) {
    const startKeepWsSuffix = trailingWs(startKeep.value);
    const deletionWsPrefix = leadingWs(deletion.value);
    const overlap = maximumOverlap(startKeepWsSuffix, deletionWsPrefix);
    deletion.value = removePrefix(deletion.value, overlap);
  }
}
var WordsWithSpaceDiff = class extends Diff {
  tokenize(value) {
    const regex = new RegExp(`(\\r?\\n)|[${extendedWordChars}]+|[^\\S\\n\\r]+|[^${extendedWordChars}]`, "ug");
    return value.match(regex) || [];
  }
};
var wordsWithSpaceDiff = new WordsWithSpaceDiff();
function diffWordsWithSpace(oldStr, newStr, options) {
  return wordsWithSpaceDiff.diff(oldStr, newStr, options);
}

// ../../node_modules/.bun/diff@8.0.3/node_modules/diff/libesm/diff/line.js
var LineDiff = class extends Diff {
  constructor() {
    super(...arguments);
    this.tokenize = tokenize;
  }
  equals(left, right, options) {
    if (options.ignoreWhitespace) {
      if (!options.newlineIsToken || !left.includes("\n")) {
        left = left.trim();
      }
      if (!options.newlineIsToken || !right.includes("\n")) {
        right = right.trim();
      }
    } else if (options.ignoreNewlineAtEof && !options.newlineIsToken) {
      if (left.endsWith("\n")) {
        left = left.slice(0, -1);
      }
      if (right.endsWith("\n")) {
        right = right.slice(0, -1);
      }
    }
    return super.equals(left, right, options);
  }
};
var lineDiff = new LineDiff();
function diffLines(oldStr, newStr, options) {
  return lineDiff.diff(oldStr, newStr, options);
}
function tokenize(value, options) {
  if (options.stripTrailingCr) {
    value = value.replace(/\r\n/g, "\n");
  }
  const retLines = [], linesAndNewlines = value.split(/(\n|\r\n)/);
  if (!linesAndNewlines[linesAndNewlines.length - 1]) {
    linesAndNewlines.pop();
  }
  for (let i = 0; i < linesAndNewlines.length; i++) {
    const line = linesAndNewlines[i];
    if (i % 2 && !options.newlineIsToken) {
      retLines[retLines.length - 1] += line;
    } else {
      retLines.push(line);
    }
  }
  return retLines;
}

// ../../node_modules/.bun/diff@8.0.3/node_modules/diff/libesm/diff/sentence.js
function isSentenceEndPunct(char) {
  return char == "." || char == "!" || char == "?";
}
var SentenceDiff = class extends Diff {
  tokenize(value) {
    var _a;
    const result = [];
    let tokenStartI = 0;
    for (let i = 0; i < value.length; i++) {
      if (i == value.length - 1) {
        result.push(value.slice(tokenStartI));
        break;
      }
      if (isSentenceEndPunct(value[i]) && value[i + 1].match(/\s/)) {
        result.push(value.slice(tokenStartI, i + 1));
        i = tokenStartI = i + 1;
        while ((_a = value[i + 1]) === null || _a === void 0 ? void 0 : _a.match(/\s/)) {
          i++;
        }
        result.push(value.slice(tokenStartI, i + 1));
        tokenStartI = i + 1;
      }
    }
    return result;
  }
};
var sentenceDiff = new SentenceDiff();

// ../../node_modules/.bun/diff@8.0.3/node_modules/diff/libesm/diff/css.js
var CssDiff = class extends Diff {
  tokenize(value) {
    return value.split(/([{}:;,]|\s+)/);
  }
};
var cssDiff = new CssDiff();

// ../../node_modules/.bun/diff@8.0.3/node_modules/diff/libesm/diff/json.js
var JsonDiff = class extends Diff {
  constructor() {
    super(...arguments);
    this.tokenize = tokenize;
  }
  get useLongestToken() {
    return true;
  }
  castInput(value, options) {
    const { undefinedReplacement, stringifyReplacer = (k, v) => typeof v === "undefined" ? undefinedReplacement : v } = options;
    return typeof value === "string" ? value : JSON.stringify(canonicalize(value, null, null, stringifyReplacer), null, "  ");
  }
  equals(left, right, options) {
    return super.equals(left.replace(/,([\r\n])/g, "$1"), right.replace(/,([\r\n])/g, "$1"), options);
  }
};
var jsonDiff = new JsonDiff();
function canonicalize(obj, stack, replacementStack, replacer, key) {
  stack = stack || [];
  replacementStack = replacementStack || [];
  if (replacer) {
    obj = replacer(key === void 0 ? "" : key, obj);
  }
  let i;
  for (i = 0; i < stack.length; i += 1) {
    if (stack[i] === obj) {
      return replacementStack[i];
    }
  }
  let canonicalizedObj;
  if ("[object Array]" === Object.prototype.toString.call(obj)) {
    stack.push(obj);
    canonicalizedObj = new Array(obj.length);
    replacementStack.push(canonicalizedObj);
    for (i = 0; i < obj.length; i += 1) {
      canonicalizedObj[i] = canonicalize(obj[i], stack, replacementStack, replacer, String(i));
    }
    stack.pop();
    replacementStack.pop();
    return canonicalizedObj;
  }
  if (obj && obj.toJSON) {
    obj = obj.toJSON();
  }
  if (typeof obj === "object" && obj !== null) {
    stack.push(obj);
    canonicalizedObj = {};
    replacementStack.push(canonicalizedObj);
    const sortedKeys = [];
    let key2;
    for (key2 in obj) {
      if (Object.prototype.hasOwnProperty.call(obj, key2)) {
        sortedKeys.push(key2);
      }
    }
    sortedKeys.sort();
    for (i = 0; i < sortedKeys.length; i += 1) {
      key2 = sortedKeys[i];
      canonicalizedObj[key2] = canonicalize(obj[key2], stack, replacementStack, replacer, key2);
    }
    stack.pop();
    replacementStack.pop();
  } else {
    canonicalizedObj = obj;
  }
  return canonicalizedObj;
}

// ../../node_modules/.bun/diff@8.0.3/node_modules/diff/libesm/diff/array.js
var ArrayDiff = class extends Diff {
  tokenize(value) {
    return value.slice();
  }
  join(value) {
    return value;
  }
  removeEmpty(value) {
    return value;
  }
};
var arrayDiff = new ArrayDiff();

// ../../node_modules/.bun/diff@8.0.3/node_modules/diff/libesm/patch/create.js
var INCLUDE_HEADERS = {
  includeIndex: true,
  includeUnderline: true,
  includeFileHeaders: true
};
function structuredPatch(oldFileName, newFileName, oldStr, newStr, oldHeader, newHeader, options) {
  let optionsObj;
  if (!options) {
    optionsObj = {};
  } else if (typeof options === "function") {
    optionsObj = { callback: options };
  } else {
    optionsObj = options;
  }
  if (typeof optionsObj.context === "undefined") {
    optionsObj.context = 4;
  }
  const context = optionsObj.context;
  if (optionsObj.newlineIsToken) {
    throw new Error("newlineIsToken may not be used with patch-generation functions, only with diffing functions");
  }
  if (!optionsObj.callback) {
    return diffLinesResultToPatch(diffLines(oldStr, newStr, optionsObj));
  } else {
    const { callback } = optionsObj;
    diffLines(oldStr, newStr, Object.assign(Object.assign({}, optionsObj), { callback: (diff) => {
      const patch = diffLinesResultToPatch(diff);
      callback(patch);
    } }));
  }
  function diffLinesResultToPatch(diff) {
    if (!diff) {
      return;
    }
    diff.push({ value: "", lines: [] });
    function contextLines(lines) {
      return lines.map(function(entry) {
        return " " + entry;
      });
    }
    const hunks = [];
    let oldRangeStart = 0, newRangeStart = 0, curRange = [], oldLine = 1, newLine = 1;
    for (let i = 0; i < diff.length; i++) {
      const current = diff[i], lines = current.lines || splitLines(current.value);
      current.lines = lines;
      if (current.added || current.removed) {
        if (!oldRangeStart) {
          const prev = diff[i - 1];
          oldRangeStart = oldLine;
          newRangeStart = newLine;
          if (prev) {
            curRange = context > 0 ? contextLines(prev.lines.slice(-context)) : [];
            oldRangeStart -= curRange.length;
            newRangeStart -= curRange.length;
          }
        }
        for (const line of lines) {
          curRange.push((current.added ? "+" : "-") + line);
        }
        if (current.added) {
          newLine += lines.length;
        } else {
          oldLine += lines.length;
        }
      } else {
        if (oldRangeStart) {
          if (lines.length <= context * 2 && i < diff.length - 2) {
            for (const line of contextLines(lines)) {
              curRange.push(line);
            }
          } else {
            const contextSize = Math.min(lines.length, context);
            for (const line of contextLines(lines.slice(0, contextSize))) {
              curRange.push(line);
            }
            const hunk = {
              oldStart: oldRangeStart,
              oldLines: oldLine - oldRangeStart + contextSize,
              newStart: newRangeStart,
              newLines: newLine - newRangeStart + contextSize,
              lines: curRange
            };
            hunks.push(hunk);
            oldRangeStart = 0;
            newRangeStart = 0;
            curRange = [];
          }
        }
        oldLine += lines.length;
        newLine += lines.length;
      }
    }
    for (const hunk of hunks) {
      for (let i = 0; i < hunk.lines.length; i++) {
        if (hunk.lines[i].endsWith("\n")) {
          hunk.lines[i] = hunk.lines[i].slice(0, -1);
        } else {
          hunk.lines.splice(i + 1, 0, "\\ No newline at end of file");
          i++;
        }
      }
    }
    return {
      oldFileName,
      newFileName,
      oldHeader,
      newHeader,
      hunks
    };
  }
}
function formatPatch(patch, headerOptions) {
  if (!headerOptions) {
    headerOptions = INCLUDE_HEADERS;
  }
  if (Array.isArray(patch)) {
    if (patch.length > 1 && !headerOptions.includeFileHeaders) {
      throw new Error("Cannot omit file headers on a multi-file patch. (The result would be unparseable; how would a tool trying to apply the patch know which changes are to which file?)");
    }
    return patch.map((p) => formatPatch(p, headerOptions)).join("\n");
  }
  const ret = [];
  if (headerOptions.includeIndex && patch.oldFileName == patch.newFileName) {
    ret.push("Index: " + patch.oldFileName);
  }
  if (headerOptions.includeUnderline) {
    ret.push("===================================================================");
  }
  if (headerOptions.includeFileHeaders) {
    ret.push("--- " + patch.oldFileName + (typeof patch.oldHeader === "undefined" ? "" : "	" + patch.oldHeader));
    ret.push("+++ " + patch.newFileName + (typeof patch.newHeader === "undefined" ? "" : "	" + patch.newHeader));
  }
  for (let i = 0; i < patch.hunks.length; i++) {
    const hunk = patch.hunks[i];
    if (hunk.oldLines === 0) {
      hunk.oldStart -= 1;
    }
    if (hunk.newLines === 0) {
      hunk.newStart -= 1;
    }
    ret.push("@@ -" + hunk.oldStart + "," + hunk.oldLines + " +" + hunk.newStart + "," + hunk.newLines + " @@");
    for (const line of hunk.lines) {
      ret.push(line);
    }
  }
  return ret.join("\n") + "\n";
}
function createTwoFilesPatch(oldFileName, newFileName, oldStr, newStr, oldHeader, newHeader, options) {
  if (typeof options === "function") {
    options = { callback: options };
  }
  if (!(options === null || options === void 0 ? void 0 : options.callback)) {
    const patchObj = structuredPatch(oldFileName, newFileName, oldStr, newStr, oldHeader, newHeader, options);
    if (!patchObj) {
      return;
    }
    return formatPatch(patchObj, options === null || options === void 0 ? void 0 : options.headerOptions);
  } else {
    const { callback } = options;
    structuredPatch(oldFileName, newFileName, oldStr, newStr, oldHeader, newHeader, Object.assign(Object.assign({}, options), { callback: (patchObj) => {
      if (!patchObj) {
        callback(void 0);
      } else {
        callback(formatPatch(patchObj, options.headerOptions));
      }
    } }));
  }
}
function splitLines(text) {
  const hasTrailingNl = text.endsWith("\n");
  const result = text.split("\n").map((line) => line + "\n");
  if (hasTrailingNl) {
    result.pop();
  } else {
    result.push(result.pop().slice(0, -1));
  }
  return result;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/parseDiffDecorations.js
function createDiffSpanDecoration({ line, spanStart, spanLength }) {
  return {
    start: {
      line,
      character: spanStart
    },
    end: {
      line,
      character: spanStart + spanLength
    },
    properties: { "data-diff-span": "" },
    alwaysWrap: true
  };
}
function pushOrJoinSpan({ item, arr, enableJoin, isNeutral = false, isLastItem = false }) {
  const lastItem = arr[arr.length - 1];
  if (lastItem == null || isLastItem || !enableJoin) {
    arr.push([isNeutral ? 0 : 1, item.value]);
    return;
  }
  const isLastItemNeutral = lastItem[0] === 0;
  if (isNeutral === isLastItemNeutral || isNeutral && item.value.length === 1 && !isLastItemNeutral) {
    lastItem[1] += item.value;
    return;
  }
  arr.push([isNeutral ? 0 : 1, item.value]);
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/iterateOverDiff.js
function iterateOverDiff({ diff, diffStyle, startingLine = 0, totalLines = Infinity, expandedHunks, collapsedContextThreshold = DEFAULT_COLLAPSED_CONTEXT_THRESHOLD, callback }) {
  const state = {
    finalHunk: diff.hunks.at(-1),
    viewportStart: startingLine,
    viewportEnd: startingLine + totalLines,
    isWindowedHighlight: startingLine > 0 || totalLines < Infinity,
    splitCount: 0,
    unifiedCount: 0,
    shouldBreak() {
      if (!state.isWindowedHighlight) return false;
      const breakUnified = state.unifiedCount >= startingLine + totalLines;
      const breakSplit = state.splitCount >= startingLine + totalLines;
      if (diffStyle === "unified") return breakUnified;
      else if (diffStyle === "split") return breakSplit;
      else return breakUnified && breakSplit;
    },
    shouldSkip(unifiedHeight, splitHeight) {
      if (!state.isWindowedHighlight) return false;
      const skipUnified = state.unifiedCount + unifiedHeight < startingLine;
      const skipSplit = state.splitCount + splitHeight < startingLine;
      if (diffStyle === "unified") return skipUnified;
      else if (diffStyle === "split") return skipSplit;
      else return skipUnified && skipSplit;
    },
    incrementCounts(unifiedValue, splitValue) {
      if (diffStyle === "unified" || diffStyle === "both") state.unifiedCount += unifiedValue;
      if (diffStyle === "split" || diffStyle === "both") state.splitCount += splitValue;
    },
    isInWindow(unifiedHeight, splitHeight) {
      if (!state.isWindowedHighlight) return true;
      const unifiedInWindow = state.isInUnifiedWindow(unifiedHeight);
      const splitInWindow = state.isInSplitWindow(splitHeight);
      if (diffStyle === "unified") return unifiedInWindow;
      else if (diffStyle === "split") return splitInWindow;
      else return unifiedInWindow || splitInWindow;
    },
    isInUnifiedWindow(unifiedHeight) {
      return !state.isWindowedHighlight || state.unifiedCount >= startingLine - unifiedHeight && state.unifiedCount < startingLine + totalLines;
    },
    isInSplitWindow(splitHeight) {
      return !state.isWindowedHighlight || state.splitCount >= startingLine - splitHeight && state.splitCount < startingLine + totalLines;
    },
    emit(props, silent = false) {
      if (!silent) if (diffStyle === "unified") state.incrementCounts(1, 0);
      else if (diffStyle === "split") state.incrementCounts(0, 1);
      else state.incrementCounts(1, 1);
      return callback(props) ?? false;
    }
  };
  hunkIterator: for (const [hunkIndex, hunk] of diff.hunks.entries()) {
    let getTrailingCollapsedAfter = function(unifiedLineIndex$1, splitLineIndex$1) {
      if (trailingRegion == null || trailingRegion.collapsedLines <= 0 || trailingRegion.fromStart + trailingRegion.fromEnd > 0) return 0;
      if (diffStyle === "unified") return unifiedLineIndex$1 === hunk.unifiedLineStart + hunk.unifiedLineCount - 1 ? trailingRegion.collapsedLines : 0;
      return splitLineIndex$1 === hunk.splitLineStart + hunk.splitLineCount - 1 ? trailingRegion.collapsedLines : 0;
    }, getPendingCollapsed = function() {
      if (leadingRegion.collapsedLines === 0) return 0;
      const value = leadingRegion.collapsedLines;
      leadingRegion.collapsedLines = 0;
      return value;
    };
    if (state.shouldBreak()) break;
    const leadingRegion = getExpandedRegion(diff.isPartial, hunk.collapsedBefore, expandedHunks, hunkIndex, collapsedContextThreshold);
    const trailingRegion = (() => {
      if (hunk !== state.finalHunk || !hasFinalCollapsedHunk(diff)) return;
      const additionRemaining = diff.additionLines.length - (hunk.additionLineIndex + hunk.additionCount);
      const deletionRemaining = diff.deletionLines.length - (hunk.deletionLineIndex + hunk.deletionCount);
      if (additionRemaining !== deletionRemaining) throw new Error(`iterateOverDiff: trailing context mismatch (additions=${additionRemaining}, deletions=${deletionRemaining}) for ${diff.name}`);
      const trailingRangeSize = Math.min(additionRemaining, deletionRemaining);
      return getExpandedRegion(diff.isPartial, trailingRangeSize, expandedHunks, diff.hunks.length, collapsedContextThreshold);
    })();
    const expandedLineCount = leadingRegion.fromStart + leadingRegion.fromEnd;
    if (!state.shouldSkip(expandedLineCount, expandedLineCount)) {
      let unifiedLineIndex$1 = hunk.unifiedLineStart - leadingRegion.rangeSize;
      let splitLineIndex$1 = hunk.splitLineStart - leadingRegion.rangeSize;
      let deletionLineIndex$1 = hunk.deletionLineIndex - leadingRegion.rangeSize;
      let additionLineIndex$1 = hunk.additionLineIndex - leadingRegion.rangeSize;
      let deletionLineNumber$1 = hunk.deletionStart - leadingRegion.rangeSize;
      let additionLineNumber$1 = hunk.additionStart - leadingRegion.rangeSize;
      let index = 0;
      while (index < leadingRegion.fromStart) {
        if (state.isInWindow(0, 0)) {
          if (state.emit({
            hunkIndex,
            hunk,
            collapsedBefore: 0,
            collapsedAfter: 0,
            type: "context-expanded",
            deletionLine: {
              lineNumber: deletionLineNumber$1 + index,
              lineIndex: deletionLineIndex$1 + index,
              noEOFCR: false,
              unifiedLineIndex: unifiedLineIndex$1 + index,
              splitLineIndex: splitLineIndex$1 + index
            },
            additionLine: {
              unifiedLineIndex: unifiedLineIndex$1 + index,
              splitLineIndex: splitLineIndex$1 + index,
              lineIndex: additionLineIndex$1 + index,
              lineNumber: additionLineNumber$1 + index,
              noEOFCR: false
            }
          })) break hunkIterator;
        } else state.incrementCounts(1, 1);
        index++;
      }
      unifiedLineIndex$1 = hunk.unifiedLineStart - leadingRegion.fromEnd;
      splitLineIndex$1 = hunk.splitLineStart - leadingRegion.fromEnd;
      deletionLineIndex$1 = hunk.deletionLineIndex - leadingRegion.fromEnd;
      additionLineIndex$1 = hunk.additionLineIndex - leadingRegion.fromEnd;
      deletionLineNumber$1 = hunk.deletionStart - leadingRegion.fromEnd;
      additionLineNumber$1 = hunk.additionStart - leadingRegion.fromEnd;
      index = 0;
      while (index < leadingRegion.fromEnd) {
        if (state.isInWindow(0, 0)) {
          if (state.emit({
            hunkIndex,
            hunk,
            collapsedBefore: getPendingCollapsed(),
            collapsedAfter: 0,
            type: "context-expanded",
            deletionLine: {
              lineNumber: deletionLineNumber$1 + index,
              lineIndex: deletionLineIndex$1 + index,
              noEOFCR: false,
              unifiedLineIndex: unifiedLineIndex$1 + index,
              splitLineIndex: splitLineIndex$1 + index
            },
            additionLine: {
              unifiedLineIndex: unifiedLineIndex$1 + index,
              splitLineIndex: splitLineIndex$1 + index,
              lineIndex: additionLineIndex$1 + index,
              lineNumber: additionLineNumber$1 + index,
              noEOFCR: false
            }
          })) break hunkIterator;
        } else state.incrementCounts(1, 1);
        index++;
      }
    } else {
      state.incrementCounts(expandedLineCount, expandedLineCount);
      getPendingCollapsed();
    }
    let unifiedLineIndex = hunk.unifiedLineStart;
    let splitLineIndex = hunk.splitLineStart;
    let deletionLineIndex = hunk.deletionLineIndex;
    let additionLineIndex = hunk.additionLineIndex;
    let deletionLineNumber = hunk.deletionStart;
    let additionLineNumber = hunk.additionStart;
    const lastContent = hunk.hunkContent.at(-1);
    for (const content of hunk.hunkContent) {
      if (state.shouldBreak()) break hunkIterator;
      const isLastContent = content === lastContent;
      if (content.type === "context") {
        if (!state.shouldSkip(content.lines, content.lines)) {
          let index = 0;
          while (index < content.lines) {
            if (state.isInWindow(0, 0)) {
              const isLastLine = isLastContent && index === content.lines - 1;
              const unifiedRowIndex = unifiedLineIndex + index;
              const splitRowIndex = splitLineIndex + index;
              if (state.emit({
                hunkIndex,
                hunk,
                collapsedBefore: getPendingCollapsed(),
                collapsedAfter: getTrailingCollapsedAfter(unifiedRowIndex, splitRowIndex),
                type: "context",
                deletionLine: {
                  lineNumber: deletionLineNumber + index,
                  lineIndex: deletionLineIndex + index,
                  noEOFCR: isLastLine && hunk.noEOFCRDeletions,
                  unifiedLineIndex: unifiedRowIndex,
                  splitLineIndex: splitRowIndex
                },
                additionLine: {
                  unifiedLineIndex: unifiedRowIndex,
                  splitLineIndex: splitRowIndex,
                  lineIndex: additionLineIndex + index,
                  lineNumber: additionLineNumber + index,
                  noEOFCR: isLastLine && hunk.noEOFCRAdditions
                }
              })) break hunkIterator;
            } else state.incrementCounts(1, 1);
            index++;
          }
        } else {
          state.incrementCounts(content.lines, content.lines);
          getPendingCollapsed();
        }
        unifiedLineIndex += content.lines;
        splitLineIndex += content.lines;
        deletionLineIndex += content.lines;
        additionLineIndex += content.lines;
        deletionLineNumber += content.lines;
        additionLineNumber += content.lines;
      } else {
        const splitCount = Math.max(content.deletions, content.additions);
        const unifiedCount = content.deletions + content.additions;
        if (!state.shouldSkip(unifiedCount, splitCount)) {
          const iterationRanges = getChangeIterationRanges(state, content, diffStyle);
          for (const [rangeStart, rangeEnd] of iterationRanges) for (let index = rangeStart; index < rangeEnd; index++) {
            const collapsedAfter = getTrailingCollapsedAfter(unifiedLineIndex + index, diffStyle === "unified" ? splitLineIndex + (index < content.deletions ? index : index - content.deletions) : splitLineIndex + index);
            if (state.emit(getChangeLineData({
              hunkIndex,
              hunk,
              collapsedBefore: getPendingCollapsed(),
              collapsedAfter,
              diffStyle,
              index,
              unifiedLineIndex,
              splitLineIndex,
              additionLineIndex,
              deletionLineIndex,
              additionLineNumber,
              deletionLineNumber,
              content,
              isLastContent,
              unifiedCount,
              splitCount
            }), true)) break hunkIterator;
          }
        }
        getPendingCollapsed();
        state.incrementCounts(unifiedCount, splitCount);
        unifiedLineIndex += unifiedCount;
        splitLineIndex += splitCount;
        deletionLineIndex += content.deletions;
        additionLineIndex += content.additions;
        deletionLineNumber += content.deletions;
        additionLineNumber += content.additions;
      }
    }
    if (trailingRegion != null) {
      const { collapsedLines, fromStart, fromEnd } = trailingRegion;
      const len = fromStart + fromEnd;
      let index = 0;
      while (index < len) {
        if (state.shouldBreak()) break hunkIterator;
        if (state.isInWindow(0, 0)) {
          const isLastLine = index === len - 1;
          if (state.emit({
            hunkIndex: diff.hunks.length,
            hunk: void 0,
            collapsedBefore: 0,
            collapsedAfter: isLastLine ? collapsedLines : 0,
            type: "context-expanded",
            deletionLine: {
              lineNumber: deletionLineNumber + index,
              lineIndex: deletionLineIndex + index,
              noEOFCR: false,
              unifiedLineIndex: unifiedLineIndex + index,
              splitLineIndex: splitLineIndex + index
            },
            additionLine: {
              unifiedLineIndex: unifiedLineIndex + index,
              splitLineIndex: splitLineIndex + index,
              lineIndex: additionLineIndex + index,
              lineNumber: additionLineNumber + index,
              noEOFCR: false
            }
          })) break hunkIterator;
        } else state.incrementCounts(1, 1);
        index++;
      }
    }
  }
}
function getExpandedRegion(isPartial, rangeSize, expandedHunks, hunkIndex, collapsedContextThreshold) {
  rangeSize = Math.max(rangeSize, 0);
  if (rangeSize === 0 || isPartial) return {
    fromStart: 0,
    fromEnd: 0,
    rangeSize,
    collapsedLines: Math.max(rangeSize, 0)
  };
  if (expandedHunks === true || rangeSize <= collapsedContextThreshold) return {
    fromStart: rangeSize,
    fromEnd: 0,
    rangeSize,
    collapsedLines: 0
  };
  const region = expandedHunks?.get(hunkIndex);
  const fromStart = Math.min(Math.max(region?.fromStart ?? 0, 0), rangeSize);
  const fromEnd = Math.min(Math.max(region?.fromEnd ?? 0, 0), rangeSize);
  const expandedCount = fromStart + fromEnd;
  const renderAll = expandedCount >= rangeSize;
  return {
    fromStart: renderAll ? rangeSize : fromStart,
    fromEnd: renderAll ? 0 : fromEnd,
    rangeSize,
    collapsedLines: Math.max(rangeSize - expandedCount, 0)
  };
}
function hasFinalCollapsedHunk(diff) {
  const lastHunk = diff.hunks.at(-1);
  if (lastHunk == null || diff.isPartial || diff.additionLines.length === 0 || diff.deletionLines.length === 0) return false;
  return lastHunk.additionLineIndex + lastHunk.additionCount < diff.additionLines.length || lastHunk.deletionLineIndex + lastHunk.deletionCount < diff.deletionLines.length;
}
function getChangeIterationRanges(state, content, diffStyle) {
  if (!state.isWindowedHighlight) return [[0, diffStyle === "unified" ? content.deletions + content.additions : Math.max(content.deletions, content.additions)]];
  const useUnified = diffStyle !== "split";
  const useSplit = diffStyle !== "unified";
  const iterationSpace = diffStyle === "unified" ? "unified" : "split";
  const iterationRanges = [];
  function getVisibleRange(start, count) {
    if (start + count <= state.viewportStart || start >= state.viewportEnd) return;
    const visibleStart = Math.max(0, state.viewportStart - start);
    const visibleEnd = Math.min(count, state.viewportEnd - start);
    return visibleEnd > visibleStart ? [visibleStart, visibleEnd] : void 0;
  }
  function mapRangeToIteration(range, kind) {
    if (iterationSpace === "split") return range;
    return kind === "additions" ? [range[0] + content.deletions, range[1] + content.deletions] : range;
  }
  function pushRange(range, kind) {
    if (range == null) return;
    const [start, end] = mapRangeToIteration(range, kind);
    if (end > start) iterationRanges.push([start, end]);
  }
  if (useUnified) {
    pushRange(getVisibleRange(state.unifiedCount, content.deletions), "deletions");
    pushRange(getVisibleRange(state.unifiedCount + content.deletions, content.additions), "additions");
  }
  if (useSplit) {
    pushRange(getVisibleRange(state.splitCount, content.deletions), "deletions");
    pushRange(getVisibleRange(state.splitCount, content.additions), "additions");
  }
  if (iterationRanges.length === 0) return iterationRanges;
  iterationRanges.sort((a, b) => a[0] - b[0]);
  const merged = [iterationRanges[0]];
  for (const [start, end] of iterationRanges.slice(1)) {
    const last = merged[merged.length - 1];
    if (start <= last[1]) last[1] = Math.max(last[1], end);
    else merged.push([start, end]);
  }
  return merged;
}
function getChangeLineData({ hunkIndex, hunk, collapsedAfter, collapsedBefore, diffStyle, index, unifiedLineIndex, splitLineIndex, additionLineIndex, deletionLineIndex, additionLineNumber, deletionLineNumber, content, isLastContent, unifiedCount, splitCount }) {
  const unifiedDeletionLineIndex = index < content.deletions ? unifiedLineIndex + index : void 0;
  const unifiedAdditionLineIndex = diffStyle === "unified" ? index >= content.deletions ? unifiedLineIndex + index : void 0 : index < content.additions ? unifiedLineIndex + content.deletions + index : void 0;
  const resolvedSplitLineIndex = diffStyle === "unified" ? splitLineIndex + (index < content.deletions ? index : index - content.deletions) : splitLineIndex + index;
  const deletionLineIndexValue = index < content.deletions ? deletionLineIndex + index : void 0;
  const deletionLineNumberValue = index < content.deletions ? deletionLineNumber + index : void 0;
  const additionLineIndexValue = diffStyle === "unified" ? index >= content.deletions ? additionLineIndex + (index - content.deletions) : void 0 : index < content.additions ? additionLineIndex + index : void 0;
  const additionLineNumberValue = diffStyle === "unified" ? index >= content.deletions ? additionLineNumber + (index - content.deletions) : void 0 : index < content.additions ? additionLineNumber + index : void 0;
  const noEOFCRDeletion = diffStyle === "unified" ? isLastContent && index === content.deletions - 1 && hunk.noEOFCRDeletions : isLastContent && index === splitCount - 1 && hunk.noEOFCRDeletions;
  const noEOFCRAddition = diffStyle === "unified" ? isLastContent && index === unifiedCount - 1 && hunk.noEOFCRAdditions : isLastContent && index === splitCount - 1 && hunk.noEOFCRAdditions;
  const deletionLine = deletionLineIndexValue != null && deletionLineNumberValue != null && unifiedDeletionLineIndex != null ? {
    lineNumber: deletionLineNumberValue,
    lineIndex: deletionLineIndexValue,
    noEOFCR: noEOFCRDeletion,
    unifiedLineIndex: unifiedDeletionLineIndex,
    splitLineIndex: resolvedSplitLineIndex
  } : void 0;
  const additionLine = additionLineIndexValue != null && additionLineNumberValue != null && unifiedAdditionLineIndex != null ? {
    unifiedLineIndex: unifiedAdditionLineIndex,
    splitLineIndex: resolvedSplitLineIndex,
    lineIndex: additionLineIndexValue,
    lineNumber: additionLineNumberValue,
    noEOFCR: noEOFCRAddition
  } : void 0;
  if (deletionLine == null && additionLine != null) return {
    type: "change",
    hunkIndex,
    hunk,
    collapsedAfter,
    collapsedBefore,
    deletionLine: void 0,
    additionLine
  };
  else if (deletionLine != null && additionLine == null) return {
    type: "change",
    hunkIndex,
    hunk,
    collapsedAfter,
    collapsedBefore,
    deletionLine,
    additionLine: void 0
  };
  if (deletionLine == null || additionLine == null) throw new Error("iterateOverDiff: missing change line data");
  return {
    type: "change",
    hunkIndex,
    hunk,
    collapsedAfter,
    collapsedBefore,
    deletionLine,
    additionLine
  };
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/renderDiffWithHighlighter.js
var DEFAULT_PLAIN_TEXT_OPTIONS2 = { forcePlainText: false };
function renderDiffWithHighlighter(diff, highlighter2, options, { forcePlainText, startingLine, totalLines, expandedHunks, collapsedContextThreshold = DEFAULT_COLLAPSED_CONTEXT_THRESHOLD } = DEFAULT_PLAIN_TEXT_OPTIONS2) {
  if (forcePlainText) {
    startingLine ??= 0;
    totalLines ??= Infinity;
  } else {
    startingLine = 0;
    totalLines = Infinity;
  }
  const isWindowedHighlight = startingLine > 0 || totalLines < Infinity;
  const baseThemeType = (() => {
    const theme = options.theme ?? DEFAULT_THEMES;
    if (typeof theme === "string") return highlighter2.getTheme(theme).type;
  })();
  const themeStyles = getHighlighterThemeStyles({
    theme: options.theme,
    highlighter: highlighter2
  });
  const lineDiffType = forcePlainText && !isWindowedHighlight && (diff.unifiedLineCount > 1e3 || diff.splitLineCount > 1e3) ? "none" : options.lineDiffType;
  const code = {
    deletionLines: [],
    additionLines: []
  };
  const shouldGroupAll = !forcePlainText && !diff.isPartial;
  const expandedHunksForIteration = forcePlainText ? expandedHunks : void 0;
  const buckets = /* @__PURE__ */ new Map();
  function getBucketForHunk(hunkIndex) {
    const index = shouldGroupAll ? 0 : hunkIndex;
    const bucket = buckets.get(index) ?? createBucket();
    buckets.set(index, bucket);
    return bucket;
  }
  function appendContent(lineContent, lineIndex, segments, contentWrapper) {
    if (isWindowedHighlight) {
      let segment = segments.at(-1);
      if (segment == null || segment.targetIndex + segment.count !== lineIndex) {
        segment = {
          targetIndex: lineIndex,
          originalOffset: contentWrapper.length,
          count: 0
        };
        segments.push(segment);
      }
      segment.count++;
    }
    contentWrapper.push(lineContent);
  }
  iterateOverDiff({
    diff,
    diffStyle: "both",
    startingLine,
    totalLines,
    expandedHunks: isWindowedHighlight ? expandedHunksForIteration : true,
    collapsedContextThreshold,
    callback: ({ hunkIndex, additionLine, deletionLine, type }) => {
      const bucket = getBucketForHunk(hunkIndex);
      const splitLineIndex = additionLine != null ? additionLine.splitLineIndex : deletionLine.splitLineIndex;
      if (type === "change" && additionLine != null && deletionLine != null) computeLineDiffDecorations({
        additionLine: diff.additionLines[additionLine.lineIndex],
        deletionLine: diff.deletionLines[deletionLine.lineIndex],
        deletionLineIndex: bucket.deletionContent.length,
        additionLineIndex: bucket.additionContent.length,
        deletionDecorations: bucket.deletionDecorations,
        additionDecorations: bucket.additionDecorations,
        lineDiffType
      });
      if (deletionLine != null) {
        appendContent(diff.deletionLines[deletionLine.lineIndex], deletionLine.lineIndex, bucket.deletionSegments, bucket.deletionContent);
        bucket.deletionInfo.push({
          type: type === "change" ? "change-deletion" : type,
          lineNumber: deletionLine.lineNumber,
          altLineNumber: type === "change" ? void 0 : additionLine.lineNumber ?? void 0,
          lineIndex: `${deletionLine.unifiedLineIndex},${splitLineIndex}`
        });
      }
      if (additionLine != null) {
        appendContent(diff.additionLines[additionLine.lineIndex], additionLine.lineIndex, bucket.additionSegments, bucket.additionContent);
        bucket.additionInfo.push({
          type: type === "change" ? "change-addition" : type,
          lineNumber: additionLine.lineNumber,
          altLineNumber: type === "change" ? void 0 : deletionLine.lineNumber ?? void 0,
          lineIndex: `${additionLine.unifiedLineIndex},${splitLineIndex}`
        });
      }
    }
  });
  for (const bucket of buckets.values()) {
    if (bucket.deletionContent.length === 0 && bucket.additionContent.length === 0) continue;
    const deletionFile = {
      name: diff.prevName ?? diff.name,
      contents: bucket.deletionContent.value
    };
    const additionFile = {
      name: diff.name,
      contents: bucket.additionContent.value
    };
    const { deletionLines, additionLines } = renderTwoFiles({
      deletionFile,
      deletionInfo: bucket.deletionInfo,
      deletionDecorations: bucket.deletionDecorations,
      additionFile,
      additionInfo: bucket.additionInfo,
      additionDecorations: bucket.additionDecorations,
      highlighter: highlighter2,
      options,
      languageOverride: forcePlainText ? "text" : diff.lang
    });
    if (shouldGroupAll) {
      code.deletionLines = deletionLines;
      code.additionLines = additionLines;
      continue;
    }
    if (bucket.deletionSegments.length > 0) for (const seg of bucket.deletionSegments) for (let i = 0; i < seg.count; i++) code.deletionLines[seg.targetIndex + i] = deletionLines[seg.originalOffset + i];
    else code.deletionLines.push(...deletionLines);
    if (bucket.additionSegments.length > 0) for (const seg of bucket.additionSegments) for (let i = 0; i < seg.count; i++) code.additionLines[seg.targetIndex + i] = additionLines[seg.originalOffset + i];
    else code.additionLines.push(...additionLines);
  }
  return {
    code,
    themeStyles,
    baseThemeType
  };
}
function computeLineDiffDecorations({ deletionLine, additionLine, deletionLineIndex, additionLineIndex, deletionDecorations, additionDecorations, lineDiffType }) {
  if (deletionLine == null || additionLine == null || lineDiffType === "none") return;
  deletionLine = cleanLastNewline(deletionLine);
  additionLine = cleanLastNewline(additionLine);
  const lineDiff2 = lineDiffType === "char" ? diffChars(deletionLine, additionLine) : diffWordsWithSpace(deletionLine, additionLine);
  const deletionSpans = [];
  const additionSpans = [];
  const enableJoin = lineDiffType === "word-alt";
  const lastItem = lineDiff2.at(-1);
  for (const item of lineDiff2) {
    const isLastItem = item === lastItem;
    if (!item.added && !item.removed) {
      pushOrJoinSpan({
        item,
        arr: deletionSpans,
        enableJoin,
        isNeutral: true,
        isLastItem
      });
      pushOrJoinSpan({
        item,
        arr: additionSpans,
        enableJoin,
        isNeutral: true,
        isLastItem
      });
    } else if (item.removed) pushOrJoinSpan({
      item,
      arr: deletionSpans,
      enableJoin,
      isLastItem
    });
    else pushOrJoinSpan({
      item,
      arr: additionSpans,
      enableJoin,
      isLastItem
    });
  }
  let spanIndex = 0;
  for (const span of deletionSpans) {
    if (span[0] === 1) deletionDecorations.push(createDiffSpanDecoration({
      line: deletionLineIndex,
      spanStart: spanIndex,
      spanLength: span[1].length
    }));
    spanIndex += span[1].length;
  }
  spanIndex = 0;
  for (const span of additionSpans) {
    if (span[0] === 1) additionDecorations.push(createDiffSpanDecoration({
      line: additionLineIndex,
      spanStart: spanIndex,
      spanLength: span[1].length
    }));
    spanIndex += span[1].length;
  }
}
function createBucket() {
  return {
    deletionContent: {
      push(value) {
        this.value += value;
        this.length++;
      },
      value: "",
      length: 0
    },
    additionContent: {
      push(value) {
        this.value += value;
        this.length++;
      },
      value: "",
      length: 0
    },
    deletionInfo: [],
    additionInfo: [],
    deletionDecorations: [],
    additionDecorations: [],
    deletionSegments: [],
    additionSegments: []
  };
}
function renderTwoFiles({ deletionFile, additionFile, deletionInfo, additionInfo, highlighter: highlighter2, deletionDecorations, additionDecorations, languageOverride, options: { theme: themeOrThemes = DEFAULT_THEMES, ...options } }) {
  const deletionLang = languageOverride ?? getFiletypeFromFileName(deletionFile.name);
  const additionLang = languageOverride ?? getFiletypeFromFileName(additionFile.name);
  const { state, transformers } = createTransformerWithState();
  const hastConfig = (() => {
    return typeof themeOrThemes === "string" ? {
      ...options,
      lang: "text",
      theme: themeOrThemes,
      transformers,
      decorations: void 0,
      defaultColor: false,
      cssVariablePrefix: formatCSSVariablePrefix("token")
    } : {
      ...options,
      lang: "text",
      themes: themeOrThemes,
      transformers,
      decorations: void 0,
      defaultColor: false,
      cssVariablePrefix: formatCSSVariablePrefix("token")
    };
  })();
  return {
    deletionLines: (() => {
      if (deletionFile.contents === "") return [];
      hastConfig.lang = deletionLang;
      state.lineInfo = deletionInfo;
      hastConfig.decorations = deletionDecorations;
      return getLineNodes(highlighter2.codeToHast(cleanLastNewline(deletionFile.contents), hastConfig));
    })(),
    additionLines: (() => {
      if (additionFile.contents === "") return [];
      hastConfig.lang = additionLang;
      hastConfig.decorations = additionDecorations;
      state.lineInfo = additionInfo;
      return getLineNodes(highlighter2.codeToHast(cleanLastNewline(additionFile.contents), hastConfig));
    })()
  };
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/languages/getResolvedLanguages.js
function getResolvedLanguages(languages) {
  const resolvedLanguages = [];
  for (const language of languages) {
    const resolvedLanguage = ResolvedLanguages.get(language);
    if (resolvedLanguage == null) throw new Error(`getResolvedLanguages: ${language} is not resolved. Please resolve languages before calling getResolvedLanguages`);
    resolvedLanguages.push(resolvedLanguage);
  }
  return resolvedLanguages;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/languages/hasResolvedLanguages.js
function hasResolvedLanguages(languages) {
  for (const language of Array.isArray(languages) ? languages : [languages]) if (!ResolvedLanguages.has(language)) return false;
  return true;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/languages/resolveLanguages.js
async function resolveLanguages(languages) {
  const resolvedLanguages = [];
  const languagesToResolve = [];
  for (const language of languages) {
    if (language === "text" || language === "ansi") continue;
    const maybeResolvedLanguage = getResolvedOrResolveLanguage(language) ?? resolveLanguage(language);
    if ("then" in maybeResolvedLanguage) languagesToResolve.push(maybeResolvedLanguage);
    else resolvedLanguages.push(maybeResolvedLanguage);
  }
  if (languagesToResolve.length > 0) await Promise.all(languagesToResolve).then((_resolvedLanguages) => {
    for (const resolvedLanguage of _resolvedLanguages) {
      if (resolvedLanguage == null) throw new Error("resolvedLanguages: unable to resolve language");
      resolvedLanguages.push(resolvedLanguage);
    }
  });
  return resolvedLanguages;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/themes/getResolvedThemes.js
function getResolvedThemes(themeNames) {
  const resolvedThemes = [];
  for (const themeName of themeNames) {
    const theme = ResolvedThemes.get(themeName);
    if (theme == null) throw new Error(`getAllResolvedThemes: ${themeName} is unresolved, you must resolve all necessary themes before calling this function`);
    resolvedThemes.push(theme);
  }
  return resolvedThemes;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/themes/resolveThemes.js
async function resolveThemes(themes) {
  const resolvedThemes = [];
  const themesToResolve = [];
  for (const themeName of themes) {
    const themeData = getResolvedOrResolveTheme(themeName) ?? resolveTheme(themeName);
    if ("then" in themeData) themesToResolve.push(themeData);
    else resolvedThemes.push(themeData);
  }
  if (themesToResolve.length > 0) await Promise.all(themesToResolve).then((resolved) => {
    for (const theme of resolved) if (theme != null) resolvedThemes.push(theme);
  });
  return resolvedThemes;
}

export {
  DIFFS_TAG_NAME,
  COMMIT_METADATA_SPLIT,
  GIT_DIFF_FILE_BREAK_REGEX,
  UNIFIED_DIFF_FILE_BREAK_REGEX,
  FILE_CONTEXT_BLOB,
  HUNK_HEADER,
  SPLIT_WITH_NEWLINES,
  FILENAME_HEADER_REGEX,
  FILENAME_HEADER_REGEX_GIT,
  ALTERNATE_FILE_NAMES_GIT,
  INDEX_LINE_METADATA,
  HEADER_PREFIX_SLOT_ID,
  HEADER_METADATA_SLOT_ID,
  DEFAULT_THEMES,
  UNSAFE_CSS_ATTRIBUTE,
  CORE_CSS_ATTRIBUTE,
  DEFAULT_COLLAPSED_CONTEXT_THRESHOLD,
  DEFAULT_VIRTUAL_FILE_METRICS,
  DEFAULT_EXPANDED_REGION,
  DEFAULT_RENDER_RANGE,
  EMPTY_RENDER_RANGE,
  createTextNodeElement,
  createHastElement,
  createIconElement,
  findCodeElement,
  createGutterWrapper,
  createGutterItem,
  createGutterGap,
  ResolvedLanguages,
  ResolvingLanguages,
  RegisteredCustomLanguages,
  AttachedLanguages,
  attachResolvedLanguages,
  cleanUpResolvedLanguages,
  isWorkerContext,
  resolveLanguage,
  getResolvedOrResolveLanguage,
  ResolvedThemes,
  ResolvingThemes,
  RegisteredCustomThemes,
  AttachedThemes,
  attachResolvedThemes,
  cleanUpResolvedThemes,
  resolveTheme,
  getResolvedOrResolveTheme,
  registerCustomTheme,
  getSharedHighlighter,
  isHighlighterLoaded,
  getHighlighterIfLoaded,
  isHighlighterLoading,
  isHighlighterNull,
  preloadHighlighter,
  disposeHighlighter,
  getThemes,
  hasResolvedThemes,
  areThemesEqual,
  CUSTOM_EXTENSION_TO_FILE_FORMAT,
  EXTENSION_TO_FILE_FORMAT,
  getFiletypeFromFileName,
  extendFileFormatMap,
  cleanLastNewline,
  processLine,
  createTransformerWithState,
  formatCSSVariablePrefix,
  getHighlighterThemeStyles,
  getLineNodes,
  iterateOverFile,
  splitFileContents,
  renderFileWithHighlighter,
  areFilesEqual,
  createTwoFilesPatch,
  createDiffSpanDecoration,
  pushOrJoinSpan,
  iterateOverDiff,
  renderDiffWithHighlighter,
  getResolvedLanguages,
  hasResolvedLanguages,
  resolveLanguages,
  getResolvedThemes,
  resolveThemes
};
//# sourceMappingURL=chunk-EXAVU4XE.js.map
