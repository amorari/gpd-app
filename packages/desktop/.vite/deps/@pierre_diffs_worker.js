import {
  DEFAULT_THEMES,
  areFilesEqual,
  areThemesEqual,
  attachResolvedThemes,
  getFiletypeFromFileName,
  getResolvedLanguages,
  getResolvedThemes,
  getSharedHighlighter,
  getThemes,
  hasResolvedLanguages,
  hasResolvedThemes,
  renderDiffWithHighlighter,
  renderFileWithHighlighter,
  resolveLanguages,
  resolveThemes
} from "./chunk-EXAVU4XE.js";
import "./chunk-Z2JJGLSS.js";
import {
  __commonJS,
  __toESM
} from "./chunk-G3PMV62Z.js";

// ../../node_modules/.bun/lru_map@0.4.1/node_modules/lru_map/dist/lru.js
var require_lru = __commonJS({
  "../../node_modules/.bun/lru_map@0.4.1/node_modules/lru_map/dist/lru.js"(exports, module) {
    !(function(g, c) {
      typeof exports == "object" && typeof module != "undefined" ? c(exports) : typeof define == "function" && define.amd ? define(["exports"], c) : c((g = g || self).lru_map = g.lru_map || {});
    })(exports, function(g) {
      const c = Symbol("newer"), e = Symbol("older");
      class n {
        constructor(a, b) {
          typeof a !== "number" && (b = a, a = 0), this.size = 0, this.limit = a, this.oldest = this.newest = void 0, this._keymap = /* @__PURE__ */ new Map(), b && (this.assign(b), a < 1 && (this.limit = this.size));
        }
        _markEntryAsUsed(a) {
          if (a === this.newest) return;
          a[c] && (a === this.oldest && (this.oldest = a[c]), a[c][e] = a[e]), a[e] && (a[e][c] = a[c]), a[c] = void 0, a[e] = this.newest, this.newest && (this.newest[c] = a), this.newest = a;
        }
        assign(a) {
          let b, d = this.limit || Number.MAX_VALUE;
          this._keymap.clear();
          let m = a[Symbol.iterator]();
          for (let h = m.next(); !h.done; h = m.next()) {
            let f = new l(h.value[0], h.value[1]);
            this._keymap.set(f.key, f), b ? (b[c] = f, f[e] = b) : this.oldest = f, b = f;
            if (d-- == 0) throw new Error("overflow");
          }
          this.newest = b, this.size = this._keymap.size;
        }
        get(a) {
          var b = this._keymap.get(a);
          return b ? (this._markEntryAsUsed(b), b.value) : void 0;
        }
        set(a, b) {
          var d = this._keymap.get(a);
          return d ? (d.value = b, this._markEntryAsUsed(d), this) : (this._keymap.set(a, d = new l(a, b)), this.newest ? (this.newest[c] = d, d[e] = this.newest) : this.oldest = d, this.newest = d, ++this.size, this.size > this.limit && this.shift(), this);
        }
        shift() {
          var a = this.oldest;
          if (a) return this.oldest[c] ? (this.oldest = this.oldest[c], this.oldest[e] = void 0) : (this.oldest = void 0, this.newest = void 0), a[c] = a[e] = void 0, this._keymap.delete(a.key), --this.size, [a.key, a.value];
        }
        find(a) {
          let b = this._keymap.get(a);
          return b ? b.value : void 0;
        }
        has(a) {
          return this._keymap.has(a);
        }
        delete(a) {
          var b = this._keymap.get(a);
          return b ? (this._keymap.delete(b.key), b[c] && b[e] ? (b[e][c] = b[c], b[c][e] = b[e]) : b[c] ? (b[c][e] = void 0, this.oldest = b[c]) : b[e] ? (b[e][c] = void 0, this.newest = b[e]) : this.oldest = this.newest = void 0, this.size--, b.value) : void 0;
        }
        clear() {
          this.oldest = this.newest = void 0, this.size = 0, this._keymap.clear();
        }
        keys() {
          return new j(this.oldest);
        }
        values() {
          return new k(this.oldest);
        }
        entries() {
          return this;
        }
        [Symbol.iterator]() {
          return new i(this.oldest);
        }
        forEach(a, b) {
          typeof b !== "object" && (b = this);
          let d = this.oldest;
          for (; d; ) a.call(b, d.value, d.key, this), d = d[c];
        }
        toJSON() {
          for (var a = new Array(this.size), b = 0, d = this.oldest; d; ) a[b++] = { key: d.key, value: d.value }, d = d[c];
          return a;
        }
        toString() {
          for (var a = "", b = this.oldest; b; ) a += String(b.key) + ":" + b.value, b = b[c], b && (a += " < ");
          return a;
        }
      }
      g.LRUMap = n;
      function l(a, b) {
        this.key = a, this.value = b, this[c] = void 0, this[e] = void 0;
      }
      function i(a) {
        this.entry = a;
      }
      i.prototype[Symbol.iterator] = function() {
        return this;
      }, i.prototype.next = function() {
        let a = this.entry;
        return a ? (this.entry = a[c], { done: false, value: [a.key, a.value] }) : { done: true, value: void 0 };
      };
      function j(a) {
        this.entry = a;
      }
      j.prototype[Symbol.iterator] = function() {
        return this;
      }, j.prototype.next = function() {
        let a = this.entry;
        return a ? (this.entry = a[c], { done: false, value: a.key }) : { done: true, value: void 0 };
      };
      function k(a) {
        this.entry = a;
      }
      k.prototype[Symbol.iterator] = function() {
        return this;
      }, k.prototype.next = function() {
        let a = this.entry;
        return a ? (this.entry = a[c], { done: false, value: a.value }) : { done: true, value: void 0 };
      };
    });
  }
});

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/worker/WorkerPoolManager.js
var import_lru_map = __toESM(require_lru(), 1);
var IGNORE_RESPONSE = Symbol("IGNORE_RESPONSE");
var WorkerPoolManager = class {
  highlighter;
  preferredHighlighter;
  renderOptions;
  initialized = false;
  workers = [];
  taskQueue = /* @__PURE__ */ new Map();
  pendingTasks = /* @__PURE__ */ new Map();
  nextRequestId = 0;
  themeSubscribers = /* @__PURE__ */ new Set();
  workersFailed = false;
  instanceRequestMap = /* @__PURE__ */ new Map();
  statSubscribers = /* @__PURE__ */ new Set();
  fileCache;
  diffCache;
  _queuedBroadcast;
  constructor(options, { langs, theme = DEFAULT_THEMES, lineDiffType = "word-alt", tokenizeMaxLineLength = 1e3, preferredHighlighter = "shiki-js" }) {
    this.options = options;
    this.preferredHighlighter = preferredHighlighter;
    this.renderOptions = {
      theme,
      lineDiffType,
      tokenizeMaxLineLength
    };
    this.fileCache = new import_lru_map.default.LRUMap(options.totalASTLRUCacheSize ?? 100);
    this.diffCache = new import_lru_map.default.LRUMap(options.totalASTLRUCacheSize ?? 100);
    this.initialize(langs);
  }
  isWorkingPool() {
    return !this.workersFailed;
  }
  getFileResultCache(file) {
    return file.cacheKey != null ? this.fileCache.get(file.cacheKey) : void 0;
  }
  getDiffResultCache(diff) {
    return diff.cacheKey != null ? this.diffCache.get(diff.cacheKey) : void 0;
  }
  inspectCaches() {
    const { fileCache, diffCache } = this;
    return {
      fileCache,
      diffCache
    };
  }
  evictFileFromCache(cacheKey) {
    try {
      return this.fileCache.delete(cacheKey) !== void 0;
    } finally {
      this.queueBroadcastStateChanges();
    }
  }
  evictDiffFromCache(cacheKey) {
    try {
      return this.diffCache.delete(cacheKey) !== void 0;
    } finally {
      this.queueBroadcastStateChanges();
    }
  }
  async setRenderOptions({ theme = DEFAULT_THEMES, lineDiffType = "word-alt", tokenizeMaxLineLength = 1e3 }) {
    const newRenderOptions = {
      theme,
      lineDiffType,
      tokenizeMaxLineLength
    };
    if (!this.isInitialized()) await this.initialize();
    const themesEqual = areThemesEqual(newRenderOptions.theme, this.renderOptions.theme);
    if (themesEqual && newRenderOptions.lineDiffType === this.renderOptions.lineDiffType && newRenderOptions.tokenizeMaxLineLength === this.renderOptions.tokenizeMaxLineLength) return;
    const themeNames = getThemes(theme);
    let resolvedThemes = [];
    if (!themesEqual) if (hasResolvedThemes(themeNames)) resolvedThemes = getResolvedThemes(themeNames);
    else resolvedThemes = await resolveThemes(themeNames);
    if (this.highlighter != null) {
      attachResolvedThemes(resolvedThemes, this.highlighter);
      await this.setRenderOptionsOnWorkers(newRenderOptions, resolvedThemes);
    } else {
      const [highlighter] = await Promise.all([getSharedHighlighter({
        themes: themeNames,
        langs: ["text"],
        preferredHighlighter: this.preferredHighlighter
      }), this.setRenderOptionsOnWorkers(newRenderOptions, resolvedThemes)]);
      this.highlighter = highlighter;
    }
    this.renderOptions = newRenderOptions;
    this.diffCache.clear();
    this.fileCache.clear();
    for (const instance of this.themeSubscribers) instance.rerender();
  }
  getFileRenderOptions() {
    const { tokenizeMaxLineLength, theme } = this.renderOptions;
    return {
      theme,
      tokenizeMaxLineLength
    };
  }
  getDiffRenderOptions() {
    return { ...this.renderOptions };
  }
  async setRenderOptionsOnWorkers(renderOptions, resolvedThemes) {
    if (this.workersFailed) return;
    if (!this.isInitialized()) await this.initialize();
    const taskPromises = [];
    for (const managedWorker of this.workers) {
      if (!managedWorker.initialized) {
        console.log({ managedWorker });
        throw new Error("setRenderOptionsOnWorkers: Somehow we have an uninitialized worker");
      }
      taskPromises.push(new Promise((resolve, reject) => {
        const id = this.generateRequestId();
        const task = {
          type: "set-render-options",
          id,
          request: {
            type: "set-render-options",
            id,
            renderOptions,
            resolvedThemes
          },
          resolve,
          reject,
          requestStart: Date.now()
        };
        this.pendingTasks.set(id, task);
        managedWorker.worker.postMessage(task.request);
      }));
    }
    await Promise.all(taskPromises);
  }
  subscribeToThemeChanges(instance) {
    this.themeSubscribers.add(instance);
    this.queueBroadcastStateChanges();
    return () => {
      this.unsubscribeToThemeChanges(instance);
      this.queueBroadcastStateChanges();
    };
  }
  unsubscribeToThemeChanges(instance) {
    this.themeSubscribers.delete(instance);
    this.queueBroadcastStateChanges();
  }
  subscribeToStatChanges(callback) {
    this.statSubscribers.add(callback);
    callback(this.getStats());
    return () => {
      this.statSubscribers.delete(callback);
    };
  }
  queueBroadcastStateChanges() {
    if (this._queuedBroadcast != null) return;
    this._queuedBroadcast = requestAnimationFrame(this._broadcastStateChanges);
  }
  _broadcastStateChanges = () => {
    if (this._queuedBroadcast != null) {
      cancelAnimationFrame(this._queuedBroadcast);
      this._queuedBroadcast = void 0;
    }
    const stats = this.getStats();
    for (const callback of this.statSubscribers) callback(stats);
  };
  cleanUpPendingTasks(instance) {
    this.taskQueue.delete(instance);
    const requestId = this.instanceRequestMap.get(instance);
    if (requestId != null) {
      this.pendingTasks.delete(requestId);
      this.instanceRequestMap.delete(instance);
    }
    this.queueBroadcastStateChanges();
  }
  isInitialized() {
    return this.initialized === true;
  }
  async initialize(languages = []) {
    if (this.initialized === true) return;
    else if (this.initialized === false) {
      this.initialized = new Promise((resolve, reject) => {
        (async () => {
          try {
            const themes = getThemes(this.renderOptions.theme);
            let resolvedThemes = [];
            if (hasResolvedThemes(themes)) resolvedThemes = getResolvedThemes(themes);
            else resolvedThemes = await resolveThemes(themes);
            let resolvedLanguages = [];
            if (hasResolvedLanguages(languages)) resolvedLanguages = getResolvedLanguages(languages);
            else resolvedLanguages = await resolveLanguages(languages);
            const [highlighter] = await Promise.all([getSharedHighlighter({
              themes,
              langs: ["text", ...languages],
              preferredHighlighter: this.preferredHighlighter
            }), this.initializeWorkers(resolvedThemes, resolvedLanguages)]);
            if (this.initialized === false) {
              this.terminateWorkers();
              throw new Error("WorkerPoolManager: workers failed to initialize");
            }
            this.highlighter = highlighter;
            this.initialized = true;
            this.diffCache.clear();
            this.fileCache.clear();
            this.drainQueue();
            this.queueBroadcastStateChanges();
            resolve();
          } catch (e) {
            this.initialized = false;
            this.workersFailed = true;
            this.queueBroadcastStateChanges();
            reject(e);
          }
        })();
      });
      this.queueBroadcastStateChanges();
    } else return this.initialized;
  }
  async initializeWorkers(resolvedThemes, resolvedLanguages) {
    this.workersFailed = false;
    const initPromises = [];
    if (this.workers.length > 0) this.terminateWorkers();
    for (let i = 0; i < (this.options.poolSize ?? 8); i++) {
      const worker = this.options.workerFactory();
      const managedWorker = {
        worker,
        request_id: void 0,
        initialized: false,
        langs: /* @__PURE__ */ new Set(["text", ...resolvedLanguages.map(({ name }) => name)])
      };
      worker.addEventListener("message", (event) => {
        this.handleWorkerMessage(managedWorker, event.data);
      });
      worker.addEventListener("error", (error) => console.error("Worker error:", error, managedWorker));
      this.workers.push(managedWorker);
      initPromises.push(new Promise((resolve, reject) => {
        const id = this.generateRequestId();
        const task = {
          type: "initialize",
          id,
          request: {
            type: "initialize",
            id,
            renderOptions: this.renderOptions,
            preferredHighlighter: this.preferredHighlighter,
            resolvedThemes,
            resolvedLanguages
          },
          resolve() {
            managedWorker.initialized = true;
            resolve();
          },
          reject,
          requestStart: Date.now()
        };
        this.pendingTasks.set(id, task);
        this.executeTask(managedWorker, task);
      }));
    }
    await Promise.all(initPromises);
  }
  drainQueue = () => {
    this._queuedDrain = void 0;
    if (this.initialized !== true || this.taskQueue.size === 0) return;
    for (const [instance, task] of this.taskQueue) {
      if (this.instanceRequestMap.has(instance)) continue;
      const langs = getLangsFromTask(task);
      const availableWorker = this.getAvailableWorker(langs);
      if (availableWorker == null) break;
      this.assignWorkerToTask(task, availableWorker);
      this.resolveLanguagesAndExecuteTask(availableWorker, task, langs);
    }
    this.queueBroadcastStateChanges();
  };
  highlightFileAST(instance, file) {
    if ((file.lang ?? getFiletypeFromFileName(file.name)) === "text") return;
    for (const tasks of [this.taskQueue, this.pendingTasks.values()]) for (const task of tasks) if ("instance" in task && task.instance === instance && task.request.type === "file" && areFilesEqual(file, task.request.file)) return;
    this.submitTask(instance, {
      type: "file",
      file
    });
  }
  getPlainFileAST(file, startingLine, totalLines, lines) {
    if (this.highlighter == null) {
      this.initialize();
      return;
    }
    return renderFileWithHighlighter(file, this.highlighter, this.renderOptions, {
      forcePlainText: true,
      startingLine,
      totalLines,
      lines
    });
  }
  highlightDiffAST(instance, diff) {
    if ((diff.lang ?? getFiletypeFromFileName(diff.name)) === "text") return;
    for (const tasks of [this.taskQueue, this.pendingTasks.values()]) for (const task of tasks) if ("instance" in task && task.instance === instance && task.request.type === "diff" && task.request.diff === diff) return;
    this.submitTask(instance, {
      type: "diff",
      diff
    });
  }
  getPlainDiffAST(diff, startingLine, totalLines, expandedHunks, collapsedContextThreshold) {
    return this.highlighter != null ? renderDiffWithHighlighter(diff, this.highlighter, this.renderOptions, {
      forcePlainText: true,
      startingLine,
      totalLines,
      expandedHunks,
      collapsedContextThreshold
    }) : void 0;
  }
  terminate() {
    this.terminateWorkers();
    this.fileCache.clear();
    this.diffCache.clear();
    this.instanceRequestMap.clear();
    this.taskQueue.clear();
    this.pendingTasks.clear();
    this.highlighter = void 0;
    this.initialized = false;
    this.workersFailed = false;
    this.queueBroadcastStateChanges();
  }
  terminateWorkers() {
    for (const managedWorker of this.workers) managedWorker.worker.terminate();
    this.workers.length = 0;
  }
  getStats() {
    return {
      managerState: (() => {
        if (this.initialized === false) return "waiting";
        if (this.initialized !== true) return "initializing";
        return "initialized";
      })(),
      totalWorkers: this.workers.length,
      workersFailed: this.workersFailed,
      busyWorkers: this.workers.filter((w) => w.request_id != null).length,
      queuedTasks: this.taskQueue.size,
      pendingTasks: this.pendingTasks.size,
      themeSubscribers: this.themeSubscribers.size,
      fileCacheSize: this.fileCache.size,
      diffCacheSize: this.diffCache.size
    };
  }
  submitTask(instance, request) {
    if (this.initialized === false) this.initialize();
    const id = this.generateRequestId();
    const requestStart = Date.now();
    const task = (() => {
      switch (request.type) {
        case "file":
          return {
            type: "file",
            id,
            request: {
              ...request,
              id
            },
            instance,
            requestStart
          };
        case "diff":
          return {
            type: "diff",
            id,
            request: {
              ...request,
              id
            },
            instance,
            requestStart
          };
      }
    })();
    this.taskQueue.set(instance, task);
    this.queueDrain();
  }
  async resolveLanguagesAndExecuteTask(availableWorker, task, langs) {
    try {
      const workerMissingLangs = langs.filter((lang) => !availableWorker.langs.has(lang));
      if (workerMissingLangs.length > 0) if (hasResolvedLanguages(workerMissingLangs)) task.request.resolvedLanguages = getResolvedLanguages(workerMissingLangs);
      else task.request.resolvedLanguages = await resolveLanguages(workerMissingLangs);
      this.executeTask(availableWorker, task);
    } catch {
      this.cleanWorkerAndTask(availableWorker, task);
    }
  }
  handleWorkerMessage(managedWorker, response) {
    const task = this.pendingTasks.get(response.id);
    try {
      if (task == null) throw IGNORE_RESPONSE;
      else if (response.type === "error") {
        const error = new Error(response.error);
        if (response.stack) error.stack = response.stack;
        if ("reject" in task) task.reject(error);
        else task.instance.onHighlightError(error);
        throw error;
      } else {
        if ("instance" in task && this.instanceRequestMap.get(task.instance) !== response.id) throw IGNORE_RESPONSE;
        switch (response.requestType) {
          case "initialize":
            if (task.type !== "initialize") throw new Error("handleWorkerMessage: task/response dont match");
            task.resolve();
            break;
          case "set-render-options":
            if (task.type !== "set-render-options") throw new Error("handleWorkerMessage: task/response dont match");
            task.resolve();
            break;
          case "file": {
            if (task.type !== "file") throw new Error("handleWorkerMessage: task/response dont match");
            const { result, options } = response;
            const { instance, request } = task;
            if (request.file.cacheKey != null) this.fileCache.set(request.file.cacheKey, {
              result,
              options
            });
            instance.onHighlightSuccess(request.file, result, options);
            break;
          }
          case "diff": {
            if (task.type !== "diff") throw new Error("handleWorkerMessage: task/response dont match");
            const { result, options } = response;
            const { instance, request } = task;
            if (request.diff.cacheKey != null) this.diffCache.set(request.diff.cacheKey, {
              result,
              options
            });
            instance.onHighlightSuccess(request.diff, result, options);
            break;
          }
        }
      }
    } catch (error) {
      if (error !== IGNORE_RESPONSE) console.error(error, task, response);
    }
    this.cleanWorkerAndTask(managedWorker, task);
    this.queueBroadcastStateChanges();
    if (this.taskQueue.size > 0) this.queueDrain();
  }
  _queuedDrain;
  queueDrain() {
    if (this._queuedDrain != null) return;
    this._queuedDrain = Promise.resolve().then(this.drainQueue);
    this.queueBroadcastStateChanges();
  }
  assignWorkerToTask(task, managedWorker) {
    managedWorker.request_id = task.id;
    if ("instance" in task) {
      this.taskQueue.delete(task.instance);
      this.instanceRequestMap.set(task.instance, task.id);
    }
    this.pendingTasks.set(task.id, task);
  }
  cleanWorkerAndTask(managedWorker, task) {
    managedWorker.request_id = void 0;
    if (task != null) {
      if ("instance" in task) this.instanceRequestMap.delete(task.instance);
      this.pendingTasks.delete(task.id);
    }
  }
  executeTask(managedWorker, task) {
    this.assignWorkerToTask(task, managedWorker);
    for (const lang of getLangsFromTask(task)) managedWorker.langs.add(lang);
    try {
      managedWorker.worker.postMessage(task.request);
    } catch (error) {
      this.cleanWorkerAndTask(managedWorker, task);
      console.error("Failed to post message to worker:", error);
      if ("instance" in task) task.instance.onHighlightError(error);
      else if ("reject" in task) task.reject(error);
    }
    this.queueBroadcastStateChanges();
  }
  getAvailableWorker(langs) {
    let worker;
    for (const managedWorker of this.workers) {
      if (managedWorker.request_id != null || !managedWorker.initialized) continue;
      worker = managedWorker;
      if (langs.length === 0) break;
      let hasEveryLang = true;
      for (const lang of langs) if (!managedWorker.langs.has(lang)) {
        hasEveryLang = false;
        break;
      }
      if (hasEveryLang) break;
    }
    return worker;
  }
  generateRequestId() {
    return `req_${++this.nextRequestId}`;
  }
};
function getLangsFromTask(task) {
  const langs = /* @__PURE__ */ new Set();
  if (task.type === "initialize" || task.type === "set-render-options") return [];
  switch (task.type) {
    case "file":
      langs.add(task.request.file.lang ?? getFiletypeFromFileName(task.request.file.name));
      break;
    case "diff":
      langs.add(task.request.diff.lang ?? getFiletypeFromFileName(task.request.diff.name));
      langs.add(task.request.diff.lang ?? getFiletypeFromFileName(task.request.diff.prevName ?? "-"));
      break;
  }
  langs.delete("text");
  return Array.from(langs);
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/worker/getOrCreateWorkerPoolSingleton.js
var workerPoolSingletone;
function getOrCreateWorkerPoolSingleton({ poolOptions, highlighterOptions }) {
  if (workerPoolSingletone == null) {
    workerPoolSingletone = new WorkerPoolManager(poolOptions, highlighterOptions);
    workerPoolSingletone.initialize();
  }
  return workerPoolSingletone;
}
function terminateWorkerPoolSingleton() {
  if (workerPoolSingletone == null) return;
  workerPoolSingletone.terminate();
  workerPoolSingletone = void 0;
}
export {
  WorkerPoolManager,
  getOrCreateWorkerPoolSingleton,
  terminateWorkerPoolSingleton
};
//# sourceMappingURL=@pierre_diffs_worker.js.map
