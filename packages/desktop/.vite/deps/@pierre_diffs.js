import {
  ALTERNATE_FILE_NAMES_GIT,
  AttachedLanguages,
  AttachedThemes,
  COMMIT_METADATA_SPLIT,
  CORE_CSS_ATTRIBUTE,
  CUSTOM_EXTENSION_TO_FILE_FORMAT,
  DEFAULT_COLLAPSED_CONTEXT_THRESHOLD,
  DEFAULT_EXPANDED_REGION,
  DEFAULT_RENDER_RANGE,
  DEFAULT_THEMES,
  DEFAULT_VIRTUAL_FILE_METRICS,
  DIFFS_TAG_NAME,
  EMPTY_RENDER_RANGE,
  EXTENSION_TO_FILE_FORMAT,
  FILENAME_HEADER_REGEX,
  FILENAME_HEADER_REGEX_GIT,
  FILE_CONTEXT_BLOB,
  GIT_DIFF_FILE_BREAK_REGEX,
  HEADER_METADATA_SLOT_ID,
  HEADER_PREFIX_SLOT_ID,
  HUNK_HEADER,
  INDEX_LINE_METADATA,
  RegisteredCustomLanguages,
  RegisteredCustomThemes,
  ResolvedLanguages,
  ResolvedThemes,
  ResolvingLanguages,
  ResolvingThemes,
  SPLIT_WITH_NEWLINES,
  UNIFIED_DIFF_FILE_BREAK_REGEX,
  UNSAFE_CSS_ATTRIBUTE,
  areFilesEqual,
  areThemesEqual,
  attachResolvedLanguages,
  attachResolvedThemes,
  cleanLastNewline,
  cleanUpResolvedLanguages,
  cleanUpResolvedThemes,
  createDiffSpanDecoration,
  createGutterGap,
  createGutterItem,
  createGutterWrapper,
  createHastElement,
  createIconElement,
  createTextNodeElement,
  createTransformerWithState,
  createTwoFilesPatch,
  disposeHighlighter,
  extendFileFormatMap,
  findCodeElement,
  formatCSSVariablePrefix,
  getFiletypeFromFileName,
  getHighlighterIfLoaded,
  getHighlighterThemeStyles,
  getLineNodes,
  getResolvedLanguages,
  getResolvedOrResolveLanguage,
  getResolvedOrResolveTheme,
  getResolvedThemes,
  getSharedHighlighter,
  getThemes,
  hasResolvedLanguages,
  hasResolvedThemes,
  isHighlighterLoaded,
  isHighlighterLoading,
  isHighlighterNull,
  isWorkerContext,
  iterateOverDiff,
  iterateOverFile,
  preloadHighlighter,
  processLine,
  pushOrJoinSpan,
  registerCustomTheme,
  renderDiffWithHighlighter,
  renderFileWithHighlighter,
  resolveLanguage,
  resolveLanguages,
  resolveTheme,
  resolveThemes,
  splitFileContents
} from "./chunk-EXAVU4XE.js";
import {
  codeToHtml,
  createCssVariablesTheme,
  getTokenStyleObject,
  stringifyTokenStyle,
  toHtml
} from "./chunk-Z2JJGLSS.js";
import "./chunk-G3PMV62Z.js";

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/areSelectionsEqual.js
function areSelectionsEqual(selectionA, selectionB) {
  return selectionA?.start === selectionB?.start && selectionA?.end === selectionB?.end && selectionA?.side === selectionB?.side && selectionA?.endSide === selectionB?.endSide;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/createGutterUtilityElement.js
function createGutterUtilityElement() {
  return createHastElement({
    tagName: "button",
    properties: {
      "data-utility-button": "",
      type: "button"
    },
    children: [createIconElement({
      name: "diffs-icon-plus",
      properties: { "data-icon": "" }
    })]
  });
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/areSelectionPointsEqual.js
function areSelectionPointsEqual(a, b) {
  return a.lineNumber === b.lineNumber && a.side === b.side;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/managers/InteractionManager.js
var InteractionManager = class {
  hoveredLine;
  pre;
  gutterUtilityContainer;
  gutterUtilityButton;
  gutterUtilitySlot;
  interactiveLinesAttr = false;
  interactiveLineNumbersAttr = false;
  hasPointerListeners = false;
  hasDocumentPointerListeners = false;
  selectedRange = null;
  renderedSelectionRange;
  selectionAnchor;
  queuedSelectionRender;
  pointerSession = { mode: "idle" };
  constructor(mode, options) {
    this.mode = mode;
    this.options = options;
  }
  setOptions(options) {
    this.options = options;
  }
  cleanUp() {
    this.pre?.removeEventListener("click", this.handlePointerClick);
    this.pre?.removeEventListener("pointerdown", this.handlePointerDown);
    this.pre?.removeEventListener("pointermove", this.handlePointerMove);
    this.pre?.removeEventListener("pointerleave", this.handlePointerLeave);
    this.pre?.removeAttribute("data-interactive-lines");
    this.pre?.removeAttribute("data-interactive-line-numbers");
    this.pre = void 0;
    this.gutterUtilityContainer?.remove();
    this.gutterUtilityContainer = void 0;
    this.gutterUtilityButton = void 0;
    this.gutterUtilitySlot = void 0;
    this.clearHoveredLine();
    this.detachDocumentPointerListeners();
    this.clearPointerSession();
    if (this.queuedSelectionRender != null) {
      cancelAnimationFrame(this.queuedSelectionRender);
      this.queuedSelectionRender = void 0;
    }
    this.interactiveLinesAttr = false;
    this.interactiveLineNumbersAttr = false;
    this.hasPointerListeners = false;
  }
  setup(pre) {
    this.setSelectionDirty();
    const { usesCustomGutterUtility = false, enableGutterUtility = false } = this.options;
    if (this.pre !== pre) {
      this.cleanUp();
      this.pre = pre;
    }
    if (enableGutterUtility) this.ensureGutterUtilityNode(usesCustomGutterUtility);
    else if (this.gutterUtilityContainer != null) {
      this.gutterUtilityContainer.remove();
      this.gutterUtilityContainer = void 0;
      this.gutterUtilityButton = void 0;
      this.gutterUtilitySlot = void 0;
      if (this.pointerSession.mode === "gutterSelecting") {
        this.clearPointerSession();
        this.detachDocumentPointerListeners();
      }
    }
    this.syncPointerListeners(pre);
    this.updateInteractiveLineAttributes();
    this.renderSelection();
  }
  setSelectionDirty() {
    this.renderedSelectionRange = void 0;
  }
  isSelectionDirty() {
    return this.renderedSelectionRange === null;
  }
  setSelection(range) {
    const isRangeChange = !(range === this.selectedRange || areSelectionsEqual(range ?? void 0, this.selectedRange ?? void 0));
    if (!this.isSelectionDirty() && !isRangeChange) return;
    this.selectedRange = range;
    this.renderSelection();
    if (isRangeChange) this.notifySelectionCommitted();
  }
  getSelection() {
    return this.selectedRange;
  }
  getHoveredLine = () => {
    if (this.hoveredLine != null) {
      if (this.mode === "diff" && this.hoveredLine.type === "diff-line") return {
        lineNumber: this.hoveredLine.lineNumber,
        side: this.hoveredLine.annotationSide
      };
      if (this.mode === "file" && this.hoveredLine.type === "line") return { lineNumber: this.hoveredLine.lineNumber };
    }
  };
  handlePointerClick = (event) => {
    const { onHunkExpand, onLineClick, onLineNumberClick } = this.options;
    if (onHunkExpand == null && onLineClick == null && onLineNumberClick == null) return;
    if (this.options.onGutterUtilityClick != null && isGutterUtilityPointerPath(event.composedPath())) return;
    debugLogIfEnabled(this.options.__debugPointerEvents, "click", "FileDiff.DEBUG.handlePointerClick:", event);
    this.handlePointerEvent({
      eventType: "click",
      event
    });
  };
  handlePointerMove = (event) => {
    const { lineHoverHighlight = "disabled", onLineEnter, onLineLeave, enableGutterUtility = false } = this.options;
    if (lineHoverHighlight === "disabled" && !enableGutterUtility && onLineEnter == null && onLineLeave == null) return;
    debugLogIfEnabled(this.options.__debugPointerEvents, "move", "FileDiff.DEBUG.handlePointerMove:", event);
    this.handlePointerEvent({
      eventType: "move",
      event
    });
  };
  handlePointerLeave = (event) => {
    const { __debugPointerEvents } = this.options;
    debugLogIfEnabled(__debugPointerEvents, "move", "FileDiff.DEBUG.handlePointerLeave: no event");
    if (this.hoveredLine == null) {
      debugLogIfEnabled(__debugPointerEvents, "move", "FileDiff.DEBUG.handlePointerLeave: returned early, no .hoveredLine");
      return;
    }
    this.gutterUtilityContainer?.remove();
    this.options.onLineLeave?.({
      ...this.hoveredLine,
      event
    });
    this.clearHoveredLine();
  };
  handlePointerEvent({ eventType, event }) {
    const { __debugPointerEvents } = this.options;
    const composedPath = event.composedPath();
    debugLogIfEnabled(__debugPointerEvents, eventType, "FileDiff.DEBUG.handlePointerEvent:", {
      eventType,
      composedPath
    });
    const target = this.resolvePointerTarget(composedPath);
    debugLogIfEnabled(__debugPointerEvents, eventType, "FileDiff.DEBUG.handlePointerEvent: resolvePointerTarget result:", target);
    const { onLineClick, onLineNumberClick, onLineEnter, onLineLeave, onHunkExpand } = this.options;
    switch (eventType) {
      case "move":
        if (isLinePointerTarget(target) && this.hoveredLine?.lineElement === target.lineElement) break;
        if (this.hoveredLine != null) {
          this.gutterUtilityContainer?.remove();
          onLineLeave?.({
            ...this.hoveredLine,
            event
          });
          this.clearHoveredLine();
        }
        if (isLinePointerTarget(target)) {
          this.setHoveredLine(this.toEventBaseProps(target));
          if (this.gutterUtilityContainer != null) target.numberElement.appendChild(this.gutterUtilityContainer);
          onLineEnter?.({
            ...this.hoveredLine,
            event
          });
        }
        break;
      case "click": {
        if (target == null) break;
        if (isExpandoPointerTarget(target) && onHunkExpand != null) {
          onHunkExpand(target.hunkIndex, target.direction, event.shiftKey);
          break;
        }
        if (!isLinePointerTarget(target)) break;
        const eventBase = this.toEventBaseProps(target);
        if (onLineNumberClick != null && target.numberColumn) onLineNumberClick({
          ...eventBase,
          event
        });
        else if (onLineClick != null) onLineClick({
          ...eventBase,
          event
        });
        break;
      }
    }
  }
  syncPointerListeners(pre) {
    const { __debugPointerEvents, lineHoverHighlight = "disabled", onLineClick, onLineNumberClick, onLineEnter, onLineLeave, onHunkExpand, enableGutterUtility = false, enableLineSelection = false, onGutterUtilityClick } = this.options;
    const enableGutterSelection = onGutterUtilityClick != null;
    const shouldAttachPointerListeners = lineHoverHighlight !== "disabled" || onLineClick != null || onLineNumberClick != null || onHunkExpand != null || onLineEnter != null || onLineLeave != null || enableGutterUtility || enableLineSelection || enableGutterSelection;
    if (shouldAttachPointerListeners && !this.hasPointerListeners) {
      pre.addEventListener("click", this.handlePointerClick);
      pre.addEventListener("pointerdown", this.handlePointerDown);
      pre.addEventListener("pointermove", this.handlePointerMove);
      pre.addEventListener("pointerleave", this.handlePointerLeave);
      this.hasPointerListeners = true;
      debugLogIfEnabled(__debugPointerEvents, "click", "FileDiff.DEBUG.attachEventListeners: Attaching click events for:", (() => {
        const reasons = [];
        if (__debugPointerEvents === "both" || __debugPointerEvents === "click") {
          if (onLineClick != null) reasons.push("onLineClick");
          if (onLineNumberClick != null) reasons.push("onLineNumberClick");
          if (onHunkExpand != null) reasons.push("expandable hunk separators");
        }
        return reasons;
      })());
      debugLogIfEnabled(__debugPointerEvents, "move", "FileDiff.DEBUG.attachEventListeners: Attaching pointer move event");
      debugLogIfEnabled(__debugPointerEvents, "move", "FileDiff.DEBUG.attachEventListeners: Attaching pointer leave event");
    } else if (!shouldAttachPointerListeners && this.hasPointerListeners) {
      pre.removeEventListener("click", this.handlePointerClick);
      pre.removeEventListener("pointerdown", this.handlePointerDown);
      pre.removeEventListener("pointermove", this.handlePointerMove);
      pre.removeEventListener("pointerleave", this.handlePointerLeave);
      this.hasPointerListeners = false;
    }
    const hasActiveLineSelectionSession = this.pointerSession.mode === "selecting" || this.pointerSession.mode === "pendingSingleLineUnselect";
    const hasActiveGutterSelectionSession = this.pointerSession.mode === "gutterSelecting";
    if (!enableLineSelection && hasActiveLineSelectionSession || !enableGutterSelection && hasActiveGutterSelectionSession) {
      this.clearPointerSession();
      this.detachDocumentPointerListeners();
      this.selectionAnchor = void 0;
      this.clearPendingSingleLineState();
    }
  }
  updateInteractiveLineAttributes() {
    if (this.pre == null) return;
    const { onLineClick, onLineNumberClick, enableLineSelection = false } = this.options;
    const shouldHaveInteractiveLines = onLineClick != null;
    const shouldHaveInteractiveLineNumbers = onLineNumberClick != null || enableLineSelection;
    if (shouldHaveInteractiveLines && !this.interactiveLinesAttr) {
      this.pre.setAttribute("data-interactive-lines", "");
      this.interactiveLinesAttr = true;
    } else if (!shouldHaveInteractiveLines && this.interactiveLinesAttr) {
      this.pre.removeAttribute("data-interactive-lines");
      this.interactiveLinesAttr = false;
    }
    if (shouldHaveInteractiveLineNumbers && !this.interactiveLineNumbersAttr) {
      this.pre.setAttribute("data-interactive-line-numbers", "");
      this.interactiveLineNumbersAttr = true;
    } else if (!shouldHaveInteractiveLineNumbers && this.interactiveLineNumbersAttr) {
      this.pre.removeAttribute("data-interactive-line-numbers");
      this.interactiveLineNumbersAttr = false;
    }
  }
  handlePointerDown = (event) => {
    if (event.pointerType === "mouse" && event.button !== 0 || this.pre == null || this.pointerSession.mode !== "idle") return;
    const path = event.composedPath();
    if (isGutterUtilityPointerPath(path) && this.options.onGutterUtilityClick != null) this.startGutterSelectionFromPointerDown(event, path);
    else this.startLineSelectionFromPointerDown(event, path);
  };
  startLineSelectionFromPointerDown(event, path) {
    const { enableLineSelection = false } = this.options;
    if (!enableLineSelection) return;
    const pointerInfo = this.getSelectionPointerInfo(path, true);
    if (pointerInfo == null) return;
    const { pre } = this;
    if (pre == null) return;
    event.preventDefault();
    const { lineNumber, eventSide, lineIndex } = pointerInfo;
    if (event.shiftKey && this.selectedRange != null) {
      const rowRange = this.getIndexesFromSelection(this.selectedRange, pre.getAttribute("data-diff-type") === "split");
      if (rowRange == null) return;
      const useStart = rowRange.start <= rowRange.end ? lineIndex >= rowRange.start : lineIndex <= rowRange.end;
      this.selectionAnchor = {
        lineNumber: useStart ? this.selectedRange.start : this.selectedRange.end,
        side: useStart ? this.selectedRange.side : this.selectedRange.endSide ?? this.selectedRange.side
      };
      this.updateSelection(lineNumber, eventSide, false);
      this.notifySelectionStart(this.selectedRange);
      this.pointerSession = {
        mode: "selecting",
        pointerId: event.pointerId
      };
      this.attachDocumentPointerListeners();
      return;
    }
    if (this.selectedRange?.start === lineNumber && this.selectedRange?.end === lineNumber) {
      const point = {
        lineNumber,
        side: eventSide
      };
      this.selectionAnchor = point;
      this.pointerSession = {
        mode: "pendingSingleLineUnselect",
        pointerId: event.pointerId,
        anchor: point,
        pending: point
      };
      this.attachDocumentPointerListeners();
      return;
    }
    this.selectedRange = null;
    this.selectionAnchor = {
      lineNumber,
      side: eventSide
    };
    this.updateSelection(lineNumber, eventSide, false);
    this.notifySelectionStart(this.selectedRange);
    this.pointerSession = {
      mode: "selecting",
      pointerId: event.pointerId
    };
    this.attachDocumentPointerListeners();
  }
  startGutterSelectionFromPointerDown(event, path) {
    const { enableLineSelection = false, onGutterUtilityClick } = this.options;
    if (onGutterUtilityClick == null) return;
    const point = this.getSelectionPointFromPath(path);
    if (point == null) return;
    event.preventDefault();
    event.stopPropagation();
    this.pointerSession = {
      mode: "gutterSelecting",
      pointerId: event.pointerId,
      anchor: point,
      current: point
    };
    if (enableLineSelection) {
      this.selectionAnchor = {
        lineNumber: point.lineNumber,
        side: point.side
      };
      this.updateSelection(point.lineNumber, point.side, false);
      this.notifySelectionStart(this.selectedRange);
    }
    this.attachDocumentPointerListeners();
  }
  handleDocumentPointerMove = (event) => {
    const { enableLineSelection = false } = this.options;
    switch (this.pointerSession.mode) {
      case "idle":
        return;
      case "gutterSelecting": {
        if (event.pointerId !== this.pointerSession.pointerId) return;
        const point = this.getSelectionPointFromPath(event.composedPath());
        if (point == null) return;
        this.pointerSession.current = point;
        if (enableLineSelection === true) this.updateSelection(point.lineNumber, point.side);
        return;
      }
      case "selecting": {
        if (event.pointerId !== this.pointerSession.pointerId) return;
        const pointerInfo = this.getSelectionPointerInfo(event.composedPath(), false);
        if (pointerInfo == null || this.selectionAnchor == null) return;
        this.updateSelection(pointerInfo.lineNumber, pointerInfo.eventSide);
        return;
      }
      case "pendingSingleLineUnselect": {
        if (event.pointerId !== this.pointerSession.pointerId) return;
        const pointerInfo = this.getSelectionPointerInfo(event.composedPath(), false);
        if (pointerInfo == null || this.selectionAnchor == null) return;
        const point = {
          lineNumber: pointerInfo.lineNumber,
          side: pointerInfo.eventSide
        };
        if (areSelectionPointsEqual(this.pointerSession.pending, point)) return;
        this.updateSelection(pointerInfo.lineNumber, pointerInfo.eventSide, false);
        this.notifySelectionStart(this.selectedRange);
        this.notifySelectionChangeDelta();
        this.pointerSession = {
          mode: "selecting",
          pointerId: event.pointerId
        };
        return;
      }
    }
  };
  handleDocumentPointerUp = (event) => {
    const { enableLineSelection = false, onGutterUtilityClick } = this.options;
    switch (this.pointerSession.mode) {
      case "idle":
        return;
      case "gutterSelecting": {
        if (event.pointerId !== this.pointerSession.pointerId) return;
        const point = this.getSelectionPointFromPath(event.composedPath());
        if (point != null) {
          this.pointerSession.current = point;
          if (enableLineSelection) this.updateSelection(point.lineNumber, point.side);
        }
        onGutterUtilityClick?.(this.buildSelectedLineRange(this.pointerSession.anchor, this.pointerSession.current));
        this.selectionAnchor = void 0;
        if (enableLineSelection) {
          this.notifySelectionEnd(this.selectedRange);
          this.notifySelectionCommitted();
        }
        this.clearPointerSession();
        this.detachDocumentPointerListeners();
        return;
      }
      case "pendingSingleLineUnselect":
        if (event.pointerId !== this.pointerSession.pointerId) return;
        this.updateSelection(null, void 0, false);
        this.selectionAnchor = void 0;
        this.clearPendingSingleLineState();
        this.detachDocumentPointerListeners();
        this.notifySelectionEnd(this.selectedRange);
        this.notifySelectionCommitted();
        return;
      case "selecting":
        if (event.pointerId !== this.pointerSession.pointerId) return;
        this.selectionAnchor = void 0;
        this.detachDocumentPointerListeners();
        this.clearPointerSession();
        this.notifySelectionEnd(this.selectedRange);
        this.notifySelectionCommitted();
    }
  };
  handleDocumentPointerCancel = (event) => {
    switch (this.pointerSession.mode) {
      case "idle":
        return;
      case "gutterSelecting":
      case "selecting":
      case "pendingSingleLineUnselect":
        if ("pointerId" in this.pointerSession) {
          if (event.pointerId !== this.pointerSession.pointerId) return;
        }
        this.selectionAnchor = void 0;
        this.clearPendingSingleLineState();
        this.clearPointerSession();
        this.detachDocumentPointerListeners();
    }
  };
  clearHoveredLine() {
    if (this.hoveredLine == null) return;
    this.hoveredLine.lineElement.removeAttribute("data-hovered");
    this.hoveredLine.numberElement.removeAttribute("data-hovered");
    this.hoveredLine = void 0;
  }
  setHoveredLine(hoveredLine) {
    const { lineHoverHighlight = "disabled" } = this.options;
    if (this.hoveredLine != null) this.clearHoveredLine();
    this.hoveredLine = hoveredLine;
    if (lineHoverHighlight !== "disabled") {
      if (lineHoverHighlight === "both" || lineHoverHighlight === "line") this.hoveredLine.lineElement.setAttribute("data-hovered", "");
      if (lineHoverHighlight === "both" || lineHoverHighlight === "number") this.hoveredLine.numberElement.setAttribute("data-hovered", "");
    }
  }
  ensureGutterUtilityNode(useCustomGutterUtility) {
    if (this.gutterUtilityContainer == null) {
      this.gutterUtilityContainer = document.createElement("div");
      this.gutterUtilityContainer.setAttribute("data-gutter-utility-slot", "");
    }
    if (useCustomGutterUtility) {
      if (this.gutterUtilityButton != null) {
        this.gutterUtilityButton.remove();
        this.gutterUtilityButton = void 0;
      }
      if (this.gutterUtilitySlot == null) {
        this.gutterUtilitySlot = document.createElement("slot");
        this.gutterUtilitySlot.name = "gutter-utility-slot";
      }
      if (this.gutterUtilitySlot.parentNode !== this.gutterUtilityContainer) this.gutterUtilityContainer.replaceChildren(this.gutterUtilitySlot);
    } else {
      this.gutterUtilitySlot?.remove();
      this.gutterUtilitySlot = void 0;
      if (this.gutterUtilityButton == null) {
        const tempDiv = document.createElement("div");
        tempDiv.innerHTML = toHtml(createGutterUtilityElement());
        const utilityButton = tempDiv.firstElementChild;
        if (!(utilityButton instanceof HTMLButtonElement)) throw new Error("InteractionManager.ensureGutterUtilityNode: Node element should be a button");
        utilityButton.remove();
        this.gutterUtilityButton = utilityButton;
      }
      if (this.gutterUtilityButton.parentNode !== this.gutterUtilityContainer) this.gutterUtilityContainer.replaceChildren(this.gutterUtilityButton);
    }
  }
  attachDocumentPointerListeners() {
    if (this.hasDocumentPointerListeners) return;
    document.addEventListener("pointermove", this.handleDocumentPointerMove);
    document.addEventListener("pointerup", this.handleDocumentPointerUp);
    document.addEventListener("pointercancel", this.handleDocumentPointerCancel);
    this.hasDocumentPointerListeners = true;
  }
  detachDocumentPointerListeners() {
    if (!this.hasDocumentPointerListeners) return;
    document.removeEventListener("pointermove", this.handleDocumentPointerMove);
    document.removeEventListener("pointerup", this.handleDocumentPointerUp);
    document.removeEventListener("pointercancel", this.handleDocumentPointerCancel);
    this.hasDocumentPointerListeners = false;
  }
  clearPointerSession() {
    this.pointerSession = { mode: "idle" };
  }
  clearPendingSingleLineState() {
    if (this.pointerSession.mode === "pendingSingleLineUnselect") this.pointerSession = { mode: "idle" };
  }
  getSelectionPointerInfo(path, requireNumberColumn) {
    const target = this.resolvePointerTarget(path);
    if (!isLinePointerTarget(target)) return;
    if (requireNumberColumn && !target.numberColumn) return;
    if (target.splitLineIndex == null) return;
    return {
      lineIndex: target.splitLineIndex,
      lineNumber: target.lineNumber,
      eventSide: this.mode === "diff" ? target.side : void 0
    };
  }
  getSelectionPointFromPath(path) {
    const target = this.resolvePointerTarget(path);
    if (!isLinePointerTarget(target)) return;
    return {
      lineNumber: target.lineNumber,
      side: this.mode === "diff" ? target.side : void 0
    };
  }
  getLineIndex(lineNumber, side) {
    const { getLineIndex } = this.options;
    return getLineIndex != null ? getLineIndex(lineNumber, side) : [lineNumber - 1, lineNumber - 1];
  }
  updateSelection(currentLine, side, emitChange = true) {
    const { selectedRange: previousRange } = this;
    let nextRange;
    if (currentLine == null) nextRange = null;
    else {
      const anchorSide = this.selectionAnchor?.side ?? side;
      const anchorLine = this.selectionAnchor?.lineNumber ?? currentLine;
      nextRange = this.buildSelectionRange(anchorLine, currentLine, anchorSide, side);
    }
    if (areSelectionsEqual(previousRange ?? void 0, nextRange ?? void 0)) return;
    this.selectedRange = nextRange;
    if (emitChange) this.notifySelectionChangeDelta();
    this.queuedSelectionRender ??= requestAnimationFrame(this.renderSelection);
  }
  getIndexesFromSelection(selectedRange, split) {
    if (this.pre == null) return;
    const startIndexes = this.getLineIndex(selectedRange.start, selectedRange.side);
    const finalIndexes = this.getLineIndex(selectedRange.end, selectedRange.endSide ?? selectedRange.side);
    return startIndexes != null && finalIndexes != null ? {
      start: split ? startIndexes[1] : startIndexes[0],
      end: split ? finalIndexes[1] : finalIndexes[0]
    } : void 0;
  }
  renderSelection = () => {
    if (this.queuedSelectionRender != null) {
      cancelAnimationFrame(this.queuedSelectionRender);
      this.queuedSelectionRender = void 0;
    }
    if (this.pre == null || this.renderedSelectionRange === this.selectedRange) return;
    const allSelected = this.pre.querySelectorAll("[data-selected-line]");
    for (const element of allSelected) element.removeAttribute("data-selected-line");
    this.renderedSelectionRange = this.selectedRange;
    if (this.selectedRange == null) return;
    const { children: codeElements } = this.pre;
    if (codeElements.length === 0) return;
    if (codeElements.length > 2) {
      console.error(codeElements);
      throw new Error("InteractionManager.renderSelection: Somehow there are more than 2 code elements...");
    }
    const split = this.pre.getAttribute("data-diff-type") === "split";
    const rowRange = this.getIndexesFromSelection(this.selectedRange, split);
    if (rowRange == null) {
      console.error({
        rowRange,
        selectedRange: this.selectedRange
      });
      throw new Error("InteractionManager.renderSelection: No valid rowRange");
    }
    const isSingle = rowRange.start === rowRange.end;
    const first = Math.min(rowRange.start, rowRange.end);
    const last = Math.max(rowRange.start, rowRange.end);
    for (const code of codeElements) {
      const [gutter, content] = code.children;
      const len = content.children.length;
      if (len !== gutter.children.length) throw new Error("InteractionManager.renderSelection: gutter and content children dont match, something is wrong");
      for (let i = 0; i < len; i++) {
        const contentElement = content.children[i];
        const gutterElement = gutter.children[i];
        if (!(contentElement instanceof HTMLElement) || !(gutterElement instanceof HTMLElement)) continue;
        const lineIndex = this.parseLineIndex(contentElement, split);
        if ((lineIndex ?? 0) > last) break;
        if (lineIndex == null || lineIndex < first) continue;
        let attributeValue = isSingle ? "single" : lineIndex === first ? "first" : lineIndex === last ? "last" : "";
        contentElement.setAttribute("data-selected-line", attributeValue);
        gutterElement.setAttribute("data-selected-line", attributeValue);
        if (gutterElement.nextSibling instanceof HTMLElement && contentElement.nextSibling instanceof HTMLElement && contentElement.nextSibling.hasAttribute("data-line-annotation")) {
          if (isSingle) {
            attributeValue = "last";
            contentElement.setAttribute("data-selected-line", "first");
          } else if (lineIndex === first) attributeValue = "";
          else if (lineIndex === last) contentElement.setAttribute("data-selected-line", "");
          contentElement.nextSibling.setAttribute("data-selected-line", attributeValue);
          gutterElement.nextSibling.setAttribute("data-selected-line", attributeValue);
        }
      }
    }
  };
  notifySelectionCommitted() {
    this.options.onLineSelected?.(this.selectedRange ?? null);
  }
  notifySelectionChangeDelta() {
    this.options.onLineSelectionChange?.(this.selectedRange ?? null);
  }
  notifySelectionStart(range) {
    this.options.onLineSelectionStart?.(range);
  }
  notifySelectionEnd(range) {
    this.options.onLineSelectionEnd?.(range);
  }
  toEventBaseProps(target) {
    if (this.mode === "file") return {
      type: "line",
      lineElement: target.lineElement,
      lineNumber: target.lineNumber,
      numberColumn: target.numberColumn,
      numberElement: target.numberElement
    };
    return {
      type: "diff-line",
      annotationSide: target.side,
      lineType: target.lineType,
      lineElement: target.lineElement,
      numberElement: target.numberElement,
      lineNumber: target.lineNumber,
      numberColumn: target.numberColumn
    };
  }
  buildSelectedLineRange(anchor, current) {
    return this.buildSelectionRange(anchor.lineNumber, current.lineNumber, anchor.side, current.side);
  }
  buildSelectionRange(start, end, side, endSide) {
    return {
      start,
      end,
      ...side != null ? { side } : {},
      ...side !== endSide && endSide != null ? { endSide } : {}
    };
  }
  resolvePointerTarget(path) {
    let numberColumn = false;
    let lineType;
    let codeElement;
    let lineElement;
    let lineIndexValue;
    let numberElement;
    let expandInfo;
    let lineNumber;
    for (const element of path) {
      if (!(element instanceof HTMLElement)) continue;
      const columnNumber = numberElement == null ? element.getAttribute("data-column-number") ?? void 0 : void 0;
      if (columnNumber != null) {
        numberElement = element;
        lineNumber = Number.parseInt(columnNumber, 10);
        numberColumn = true;
        lineType = getLineTypeFromElement(element);
        lineIndexValue = element.getAttribute("data-line-index") ?? void 0;
        continue;
      }
      const lineAttr = lineElement == null ? element.getAttribute("data-line") ?? void 0 : void 0;
      if (lineAttr != null) {
        lineElement = element;
        lineNumber = Number.parseInt(lineAttr, 10);
        lineType = getLineTypeFromElement(element);
        lineIndexValue = element.getAttribute("data-line-index") ?? void 0;
        continue;
      }
      if (expandInfo == null && element.hasAttribute("data-expand-button")) {
        expandInfo = {
          hunkIndex: void 0,
          direction: (() => {
            if (element.hasAttribute("data-expand-up")) return "up";
            if (element.hasAttribute("data-expand-down")) return "down";
            return "both";
          })()
        };
        continue;
      }
      const expandIndexValue = expandInfo != null ? element.getAttribute("data-expand-index") ?? void 0 : void 0;
      if (expandInfo != null && expandIndexValue != null) {
        const expandIndex = Number.parseInt(expandIndexValue, 10);
        if (!Number.isNaN(expandIndex)) expandInfo.hunkIndex = expandIndex;
        continue;
      }
      if (codeElement == null && element.hasAttribute("data-code")) {
        codeElement = element;
        break;
      }
    }
    if (expandInfo?.hunkIndex != null) return {
      type: "line-info",
      hunkIndex: expandInfo.hunkIndex,
      direction: expandInfo.direction
    };
    lineElement ??= lineIndexValue != null ? queryHTMLElement(codeElement, `[data-line][data-line-index="${lineIndexValue}"]`) : void 0;
    numberElement ??= lineIndexValue != null ? queryHTMLElement(codeElement, `[data-column-number][data-line-index="${lineIndexValue}"]`) : void 0;
    if (codeElement == null || lineElement == null || numberElement == null || lineType == null || lineNumber == null || Number.isNaN(lineNumber)) return;
    const splitLineIndex = this.parseLineIndex(lineElement, this.isSplitDiff());
    if (this.mode === "file") return {
      kind: "line",
      lineType,
      lineElement,
      lineNumber,
      numberColumn,
      numberElement,
      side: void 0,
      splitLineIndex
    };
    const annotationSide = (() => {
      switch (lineType) {
        case "change-deletion":
          return "deletions";
        case "change-addition":
          return "additions";
        default:
          return codeElement.hasAttribute("data-deletions") ? "deletions" : "additions";
      }
    })();
    return {
      kind: "line",
      lineType,
      lineElement,
      lineNumber,
      numberColumn,
      numberElement,
      side: annotationSide,
      splitLineIndex
    };
  }
  isSplitDiff() {
    return this.pre?.getAttribute("data-diff-type") === "split";
  }
  parseLineIndex(element, split) {
    const lineIndexes = (element.getAttribute("data-line-index") ?? "").split(",").map((value) => Number.parseInt(value, 10)).filter((value) => !Number.isNaN(value));
    if (split && lineIndexes.length === 2) return lineIndexes[1];
    if (!split) return lineIndexes[0];
  }
};
function pluckInteractionOptions({ enableGutterUtility, enableHoverUtility, lineHoverHighlight, onGutterUtilityClick, onLineClick, onLineEnter, onLineLeave, onLineNumberClick, renderGutterUtility, renderHoverUtility, __debugPointerEvents, enableLineSelection, onLineSelected, onLineSelectionStart, onLineSelectionChange, onLineSelectionEnd }, onHunkExpand, getLineIndex) {
  return {
    enableGutterUtility: resolveEnableGutterUtilityOption({
      enableGutterUtility,
      enableHoverUtility,
      renderGutterUtility,
      renderHoverUtility,
      onGutterUtilityClick
    }),
    usesCustomGutterUtility: renderGutterUtility != null || renderHoverUtility != null,
    lineHoverHighlight,
    onGutterUtilityClick,
    onHunkExpand,
    onLineClick,
    onLineEnter,
    onLineLeave,
    onLineNumberClick,
    __debugPointerEvents,
    enableLineSelection,
    onLineSelected,
    onLineSelectionStart,
    onLineSelectionChange,
    onLineSelectionEnd,
    getLineIndex
  };
}
function resolveEnableGutterUtilityOption({ enableGutterUtility, enableHoverUtility, renderGutterUtility, renderHoverUtility, onGutterUtilityClick }) {
  if (enableGutterUtility !== void 0 && enableHoverUtility !== void 0) throw new Error("Cannot use both 'enableGutterUtility' and deprecated 'enableHoverUtility'. Use only 'enableGutterUtility'.");
  if (renderGutterUtility != null && renderHoverUtility != null) throw new Error("Cannot use both 'renderGutterUtility' and deprecated 'renderHoverUtility'. Use only 'renderGutterUtility'.");
  if (onGutterUtilityClick != null && (renderGutterUtility != null || renderHoverUtility != null)) throw new Error("Cannot use both 'onGutterUtilityClick' and render utility callbacks ('renderGutterUtility'/'renderHoverUtility'). Use only one gutter utility API.");
  return enableGutterUtility ?? enableHoverUtility ?? false;
}
function isLinePointerTarget(target) {
  return target != null && "kind" in target && target.kind === "line";
}
function isExpandoPointerTarget(target) {
  return "type" in target && target.type === "line-info";
}
function queryHTMLElement(parent, query) {
  const element = parent?.querySelector(query);
  return element instanceof HTMLElement ? element : void 0;
}
function getLineTypeFromElement(element) {
  const lineType = element.getAttribute("data-line-type");
  if (lineType == null) return;
  switch (lineType) {
    case "change-deletion":
    case "change-addition":
    case "context":
    case "context-expanded":
      return lineType;
    default:
      return;
  }
}
function isGutterUtilityPointerPath(path) {
  for (const element of path) if (element instanceof HTMLElement && element.hasAttribute("data-utility-button")) return true;
  return false;
}
function debugLogIfEnabled(debugLogType = "none", logIfType, ...args) {
  switch (debugLogType) {
    case "none":
      return;
    case "both":
      break;
    case "click":
      if (logIfType !== "click") return;
      break;
    case "move":
      if (logIfType !== "move") return;
      break;
  }
  console.log(...args);
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/managers/ResizeManager.js
var ResizeManager = class {
  observedNodes = /* @__PURE__ */ new Map();
  timeoutID;
  queuedUpdates = /* @__PURE__ */ new Map();
  cleanUp() {
    this.resizeObserver?.disconnect();
    this.observedNodes.clear();
    if (this.timeoutID != null) clearTimeout(this.timeoutID);
  }
  resizeObserver;
  setup(pre, disableAnnotations) {
    this.resizeObserver ??= new ResizeObserver(this.handleResizeObserver);
    const codeElements = pre.querySelectorAll("code");
    const observedNodes = new Map(this.observedNodes);
    this.observedNodes.clear();
    for (const codeElement of codeElements) {
      let item = observedNodes.get(codeElement);
      if (item != null) {
        this.observedNodes.set(codeElement, item);
        observedNodes.delete(codeElement);
        continue;
      }
      let numberElement = codeElement.querySelector("[data-gutter]");
      if (!(numberElement instanceof HTMLElement)) numberElement = null;
      item = {
        type: "code",
        codeElement,
        numberElement,
        codeWidth: "auto",
        numberWidth: 0
      };
      this.observedNodes.set(codeElement, item);
      this.resizeObserver.observe(codeElement);
      if (numberElement != null) {
        this.observedNodes.set(numberElement, item);
        this.resizeObserver.observe(numberElement);
      }
    }
    if (codeElements.length > 1 && !disableAnnotations) {
      const annotationElements = pre.querySelectorAll('[data-line-annotation*=","]');
      const elementMap = /* @__PURE__ */ new Map();
      for (const element of annotationElements) {
        if (!(element instanceof HTMLElement)) continue;
        const { lineAnnotation = "" } = element.dataset;
        if (!/^\d+,\d+$/.test(lineAnnotation)) {
          console.error("DiffFileRenderer.setupResizeObserver: Invalid element or annotation", {
            lineAnnotation,
            element
          });
          continue;
        }
        let pairs = elementMap.get(lineAnnotation);
        if (pairs == null) {
          pairs = [];
          elementMap.set(lineAnnotation, pairs);
        }
        pairs.push(element);
      }
      for (const [key, pair] of elementMap) {
        if (pair.length !== 2) {
          console.error("DiffFileRenderer.setupResizeObserver: Bad Pair", key, pair);
          continue;
        }
        const [container1, container2] = pair;
        const child1 = container1.firstElementChild;
        const child2 = container2.firstElementChild;
        if (!(container1 instanceof HTMLElement) || !(container2 instanceof HTMLElement) || !(child1 instanceof HTMLElement) || !(child2 instanceof HTMLElement)) continue;
        let item = observedNodes.get(child1);
        if (item != null) {
          this.observedNodes.set(child1, item);
          this.observedNodes.set(child2, item);
          observedNodes.delete(child1);
          observedNodes.delete(child2);
          continue;
        }
        item = {
          type: "annotations",
          column1: {
            container: container1,
            child: child1,
            childHeight: child1.getBoundingClientRect().height
          },
          column2: {
            container: container2,
            child: child2,
            childHeight: child2.getBoundingClientRect().height
          },
          currentHeight: "auto"
        };
        const newHeight = Math.max(item.column1.childHeight, item.column2.childHeight);
        this.applyNewHeight(item, newHeight);
        this.observedNodes.set(child1, item);
        this.observedNodes.set(child2, item);
        this.resizeObserver.observe(child1);
        this.resizeObserver.observe(child2);
      }
    }
    for (const element of observedNodes.keys()) {
      if (element.isConnected) {
        element.style.removeProperty("--diffs-column-content-width");
        element.style.removeProperty("--diffs-column-number-width");
        element.style.removeProperty("--diffs-column-width");
        if (element.parentElement instanceof HTMLElement) element.parentElement.style.removeProperty("--diffs-annotation-min-height");
      }
      this.resizeObserver.unobserve(element);
    }
    observedNodes.clear();
  }
  handleResizeObserver = (entries) => {
    for (const entry of entries) {
      const { target, borderBoxSize } = entry;
      if (!(target instanceof HTMLElement)) {
        console.error("FileDiff.handleResizeObserver: Invalid element for ResizeObserver", entry);
        continue;
      }
      const item = this.observedNodes.get(target);
      if (item == null) {
        console.error("FileDiff.handleResizeObserver: Not a valid observed node", entry);
        continue;
      }
      const specs = borderBoxSize[0];
      if (item.type === "annotations") {
        const column = (() => {
          if (target === item.column1.child) return item.column1;
          if (target === item.column2.child) return item.column2;
        })();
        if (column == null) {
          console.error(`FileDiff.handleResizeObserver: Couldn't find a column for`, {
            item,
            target
          });
          continue;
        }
        column.childHeight = specs.blockSize;
        const newHeight = Math.max(item.column1.childHeight, item.column2.childHeight);
        this.applyNewHeight(item, newHeight);
      } else if (item.type === "code") {
        this.queuedUpdates.set(target, [item, specs]);
        this.queueColumnUpdate();
      }
    }
  };
  queueColumnUpdate() {
    if (this.timeoutID != null) clearTimeout(this.timeoutID);
    this.timeoutID = setTimeout(this.handleColumnChange, 1e3 / 30);
  }
  handleColumnChange = () => {
    this.timeoutID = void 0;
    for (const [target, [item, specs]] of this.queuedUpdates) if (target === item.codeElement) {
      const inlineSize = Math.max(Math.floor(specs.inlineSize), 0);
      if (inlineSize !== item.codeWidth) {
        item.codeWidth = inlineSize;
        const targetWidth = Math.max(item.codeWidth - item.numberWidth, 0);
        item.codeElement.style.setProperty("--diffs-column-content-width", `${targetWidth === 0 ? "auto" : `${targetWidth}px`}`);
        item.codeElement.style.setProperty("--diffs-column-width", `${item.codeWidth === 0 ? "auto" : `${item.codeWidth}px`}`);
      }
    } else if (target === item.numberElement) {
      const inlineSize = Math.max(Math.ceil(specs.inlineSize), 0);
      if (inlineSize !== item.numberWidth) {
        item.numberWidth = inlineSize;
        item.codeElement.style.setProperty("--diffs-column-number-width", `${item.numberWidth === 0 ? "auto" : `${item.numberWidth}px`}`);
        if (item.codeWidth !== "auto") {
          const targetWidth = Math.max(item.codeWidth - item.numberWidth, 0);
          item.codeElement.style.setProperty("--diffs-column-content-width", `${targetWidth === 0 ? "auto" : `${targetWidth}px`}`);
        }
      }
    }
    this.queuedUpdates.clear();
  };
  applyNewHeight(item, newHeight) {
    if (newHeight !== item.currentHeight) {
      item.currentHeight = Math.max(newHeight, 0);
      item.column1.container.style.setProperty("--diffs-annotation-min-height", `${item.currentHeight}px`);
      item.column2.container.style.setProperty("--diffs-annotation-min-height", `${item.currentHeight}px`);
    }
  }
};

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/languages/areLanguagesAttached.js
function areLanguagesAttached(languages) {
  for (const language of Array.isArray(languages) ? languages : [languages]) if (!AttachedLanguages.has(language)) return false;
  return true;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/themes/areThemesAttached.js
function areThemesAttached(themes) {
  for (const theme of getThemes(themes)) if (!AttachedThemes.has(theme)) return false;
  return true;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/areRenderRangesEqual.js
function areRenderRangesEqual(renderRangeA, renderRangeB) {
  if (renderRangeA == null || renderRangeB == null) return renderRangeA === renderRangeB;
  return renderRangeA.startingLine === renderRangeB.startingLine && renderRangeA.totalLines === renderRangeB.totalLines && renderRangeA.bufferBefore === renderRangeB.bufferBefore && renderRangeA.bufferAfter === renderRangeB.bufferAfter;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/createAnnotationElement.js
function createAnnotationElement(span) {
  return createHastElement({
    tagName: "div",
    children: [createHastElement({
      tagName: "div",
      children: span.annotations?.map((slotId) => createHastElement({
        tagName: "slot",
        properties: { name: slotId }
      })),
      properties: { "data-annotation-content": "" }
    })],
    properties: { "data-line-annotation": `${span.hunkIndex},${span.lineIndex}` }
  });
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/getIconForType.js
function getIconForType(type) {
  switch (type) {
    case "file":
      return "diffs-icon-file-code";
    case "change":
      return "diffs-icon-symbol-modified";
    case "new":
      return "diffs-icon-symbol-added";
    case "deleted":
      return "diffs-icon-symbol-deleted";
    case "rename-pure":
    case "rename-changed":
      return "diffs-icon-symbol-moved";
  }
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/createFileHeaderElement.js
function createFileHeaderElement({ fileOrDiff, themeStyles, themeType }) {
  const fileDiff = "type" in fileOrDiff ? fileOrDiff : void 0;
  const properties = {
    "data-diffs-header": "",
    "data-change-type": fileDiff?.type,
    "data-theme-type": themeType !== "system" ? themeType : void 0,
    style: themeStyles
  };
  return createHastElement({
    tagName: "div",
    children: [createHeaderElement({
      name: fileOrDiff.name,
      prevName: "prevName" in fileOrDiff ? fileOrDiff.prevName : void 0,
      iconType: fileDiff?.type ?? "file"
    }), createMetadataElement(fileDiff)],
    properties
  });
}
function createHeaderElement({ name, prevName, iconType }) {
  const children = [createHastElement({
    tagName: "slot",
    properties: { name: HEADER_PREFIX_SLOT_ID }
  }), createIconElement({
    name: getIconForType(iconType),
    properties: { "data-change-icon": iconType }
  })];
  if (prevName != null) {
    children.push(createHastElement({
      tagName: "div",
      children: [createTextNodeElement(prevName)],
      properties: { "data-prev-name": "" }
    }));
    children.push(createIconElement({
      name: "diffs-icon-arrow-right-short",
      properties: { "data-rename-icon": "" }
    }));
  }
  children.push(createHastElement({
    tagName: "div",
    children: [createTextNodeElement(name)],
    properties: { "data-title": "" }
  }));
  return createHastElement({
    tagName: "div",
    children,
    properties: { "data-header-content": "" }
  });
}
function createMetadataElement(fileDiff) {
  const children = [];
  if (fileDiff != null) {
    let additions = 0;
    let deletions = 0;
    for (const hunk of fileDiff.hunks) {
      additions += hunk.additionLines;
      deletions += hunk.deletionLines;
    }
    if (deletions > 0 || additions === 0) children.push(createHastElement({
      tagName: "span",
      children: [createTextNodeElement(`-${deletions}`)],
      properties: { "data-deletions-count": "" }
    }));
    if (additions > 0 || deletions === 0) children.push(createHastElement({
      tagName: "span",
      children: [createTextNodeElement(`+${additions}`)],
      properties: { "data-additions-count": "" }
    }));
  }
  children.push(createHastElement({
    tagName: "slot",
    properties: { name: HEADER_METADATA_SLOT_ID }
  }));
  return createHastElement({
    tagName: "div",
    children,
    properties: { "data-metadata": "" }
  });
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/createPreElement.js
function createPreElement(options) {
  return createHastElement({
    tagName: "pre",
    properties: createPreWrapperProperties(options)
  });
}
function createPreWrapperProperties({ diffIndicators, disableBackground, disableLineNumbers, overflow, split, themeType, themeStyles, totalLines, type }) {
  const properties = {
    "data-diff": type === "diff" ? "" : void 0,
    "data-file": type === "file" ? "" : void 0,
    "data-diff-type": type === "diff" ? split ? "split" : "single" : void 0,
    "data-overflow": overflow,
    "data-disable-line-numbers": disableLineNumbers ? "" : void 0,
    "data-background": !disableBackground ? "" : void 0,
    "data-indicators": diffIndicators === "bars" || diffIndicators === "classic" ? diffIndicators : void 0,
    "data-theme-type": themeType !== "system" ? themeType : void 0,
    style: themeStyles,
    tabIndex: 0
  };
  properties.style += `--diffs-min-number-column-width-default:${`${totalLines}`.length}ch;`;
  return properties;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/getHighlighterOptions.js
function getHighlighterOptions(lang, { theme, preferredHighlighter = "shiki-js" }) {
  return {
    langs: [lang ?? "text"],
    themes: getThemes(theme),
    preferredHighlighter
  };
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/getLineAnnotationName.js
function getLineAnnotationName(annotation) {
  return `annotation-${"side" in annotation ? `${annotation.side}-` : ""}${annotation.lineNumber}`;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/createContentColumn.js
function createContentColumn(children, rowCount) {
  return createHastElement({
    tagName: "div",
    children,
    properties: {
      "data-content": "",
      style: `grid-row: span ${rowCount}`
    }
  });
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/renderers/FileRenderer.js
var instanceId = -1;
var FileRenderer = class {
  __id = `file-renderer:${++instanceId}`;
  highlighter;
  renderCache;
  computedLang = "text";
  lineAnnotations = {};
  lineCache;
  constructor(options = { theme: DEFAULT_THEMES }, onRenderUpdate, workerManager) {
    this.options = options;
    this.onRenderUpdate = onRenderUpdate;
    this.workerManager = workerManager;
    if (workerManager?.isWorkingPool() !== true) this.highlighter = areThemesAttached(options.theme ?? DEFAULT_THEMES) ? getHighlighterIfLoaded() : void 0;
  }
  setOptions(options) {
    this.options = options;
  }
  mergeOptions(options) {
    this.options = {
      ...this.options,
      ...options
    };
  }
  setThemeType(themeType) {
    if ((this.options.themeType ?? "system") === themeType) return;
    this.mergeOptions({ themeType });
  }
  setLineAnnotations(lineAnnotations) {
    this.lineAnnotations = {};
    for (const annotation of lineAnnotations) {
      const arr = this.lineAnnotations[annotation.lineNumber] ?? [];
      this.lineAnnotations[annotation.lineNumber] = arr;
      arr.push(annotation);
    }
  }
  cleanUp() {
    this.renderCache = void 0;
    this.highlighter = void 0;
    this.workerManager = void 0;
    this.onRenderUpdate = void 0;
    this.lineCache = void 0;
  }
  hydrate(file) {
    const { options } = this.getRenderOptions(file);
    let cache = this.workerManager?.getFileResultCache(file);
    if (cache != null && !areRenderOptionsEqual(options, cache.options)) cache = void 0;
    this.renderCache ??= {
      file,
      options,
      highlighted: true,
      result: cache?.result,
      renderRange: void 0
    };
    if (this.workerManager?.isWorkingPool() === true && this.renderCache.result == null) this.workerManager.highlightFileAST(this, file);
    else this.asyncHighlight(file).then(({ result, options: options$1 }) => {
      this.onHighlightSuccess(file, result, options$1);
    });
  }
  getRenderOptions(file) {
    const options = (() => {
      if (this.workerManager?.isWorkingPool() === true) return this.workerManager.getFileRenderOptions();
      const { theme = DEFAULT_THEMES, tokenizeMaxLineLength = 1e3 } = this.options;
      return {
        theme,
        tokenizeMaxLineLength
      };
    })();
    const { renderCache } = this;
    if (renderCache?.result == null) return {
      options,
      forceRender: true
    };
    if (file !== renderCache.file || !areRenderOptionsEqual(options, renderCache.options)) return {
      options,
      forceRender: true
    };
    return {
      options,
      forceRender: false
    };
  }
  getOrCreateLineCache(file) {
    if (file.cacheKey == null) {
      this.lineCache = void 0;
      return splitFileContents(file.contents);
    }
    let { lineCache } = this;
    if (lineCache == null || lineCache.cacheKey !== file.cacheKey) lineCache = {
      cacheKey: file.cacheKey,
      lines: splitFileContents(file.contents)
    };
    this.lineCache = lineCache;
    return lineCache.lines;
  }
  renderFile(file = this.renderCache?.file, renderRange = DEFAULT_RENDER_RANGE) {
    if (file == null) return;
    const cache = this.workerManager?.getFileResultCache(file);
    if (cache != null && this.renderCache == null) this.renderCache = {
      file,
      highlighted: true,
      renderRange: void 0,
      ...cache
    };
    const { options, forceRender } = this.getRenderOptions(file);
    this.renderCache ??= {
      file,
      highlighted: false,
      options,
      result: void 0,
      renderRange: void 0
    };
    if (this.workerManager?.isWorkingPool() === true) {
      if (this.renderCache.result == null || !this.renderCache.highlighted && !areRenderRangesEqual(this.renderCache.renderRange, renderRange)) {
        this.renderCache.result = this.workerManager.getPlainFileAST(file, renderRange.startingLine, renderRange.totalLines, this.getOrCreateLineCache(file));
        this.renderCache.renderRange = renderRange;
      }
      if (renderRange.totalLines > 0 && (!this.renderCache.highlighted || forceRender)) this.workerManager.highlightFileAST(this, file);
    } else {
      this.computedLang = file.lang ?? getFiletypeFromFileName(file.name);
      const hasThemes = this.highlighter != null && areThemesAttached(options.theme);
      const hasLangs = this.highlighter != null && areLanguagesAttached(this.computedLang);
      if (this.highlighter != null && hasThemes && (forceRender || !this.renderCache.highlighted && hasLangs || this.renderCache.result == null)) {
        const { result, options: options$1 } = this.renderFileWithHighlighter(file, this.highlighter, !hasLangs);
        this.renderCache = {
          file,
          options: options$1,
          highlighted: hasLangs,
          result,
          renderRange: void 0
        };
      }
      if (!hasThemes || !hasLangs) this.asyncHighlight(file).then(({ result, options: options$1 }) => {
        this.onHighlightSuccess(file, result, options$1);
      });
    }
    return this.renderCache.result != null ? this.processFileResult(this.renderCache.file, renderRange, this.renderCache.result) : void 0;
  }
  async asyncRender(file, renderRange = DEFAULT_RENDER_RANGE) {
    const { result } = await this.asyncHighlight(file);
    return this.processFileResult(file, renderRange, result);
  }
  async asyncHighlight(file) {
    this.computedLang = file.lang ?? getFiletypeFromFileName(file.name);
    const hasThemes = this.highlighter != null && hasResolvedThemes(getThemes(this.options.theme));
    const hasLangs = this.highlighter != null && areLanguagesAttached(this.computedLang);
    if (this.highlighter == null || !hasThemes || !hasLangs) this.highlighter = await this.initializeHighlighter();
    return this.renderFileWithHighlighter(file, this.highlighter);
  }
  renderFileWithHighlighter(file, highlighter, forcePlainText = false) {
    const { options } = this.getRenderOptions(file);
    return {
      result: renderFileWithHighlighter(file, highlighter, options, { forcePlainText }),
      options
    };
  }
  processFileResult(file, renderRange, { code, themeStyles, baseThemeType }) {
    const { disableFileHeader = false } = this.options;
    const contentArray = [];
    const gutter = createGutterWrapper();
    const lines = this.getOrCreateLineCache(file);
    let rowCount = 0;
    iterateOverFile({
      lines,
      startingLine: renderRange.startingLine,
      totalLines: renderRange.totalLines,
      callback: ({ lineIndex, lineNumber }) => {
        const line = code[lineIndex];
        if (line == null) {
          const message = "FileRenderer.processFileResult: Line doesnt exist";
          console.error(message, {
            name: file.name,
            lineIndex,
            lineNumber,
            lines
          });
          throw new Error(message);
        }
        if (line != null) {
          gutter.children.push(createGutterItem("context", lineNumber, `${lineIndex}`));
          contentArray.push(line);
          rowCount++;
          const annotations = this.lineAnnotations[lineNumber];
          if (annotations != null) {
            gutter.children.push(createGutterGap("context", "annotation", 1));
            contentArray.push(createAnnotationElement({
              type: "annotation",
              hunkIndex: 0,
              lineIndex: lineNumber,
              annotations: annotations.map((annotation) => getLineAnnotationName(annotation))
            }));
            rowCount++;
          }
        }
      }
    });
    gutter.properties.style = `grid-row: span ${rowCount}`;
    return {
      gutterAST: gutter.children ?? [],
      contentAST: contentArray,
      preAST: this.createPreElement(lines.length, themeStyles, baseThemeType),
      headerAST: !disableFileHeader ? this.renderHeader(file, themeStyles, baseThemeType) : void 0,
      totalLines: lines.length,
      rowCount,
      themeStyles,
      baseThemeType,
      bufferBefore: renderRange.bufferBefore,
      bufferAfter: renderRange.bufferAfter,
      css: ""
    };
  }
  renderHeader(file, themeStyles, baseThemeType) {
    const { themeType = "system" } = this.options;
    return createFileHeaderElement({
      fileOrDiff: file,
      themeStyles,
      themeType: baseThemeType ?? themeType
    });
  }
  renderFullHTML(result) {
    return toHtml(this.renderFullAST(result));
  }
  renderFullAST(result, children = []) {
    children.push(createHastElement({
      tagName: "code",
      children: this.renderCodeAST(result),
      properties: { "data-code": "" }
    }));
    return {
      ...result.preAST,
      children
    };
  }
  renderCodeAST(result) {
    const gutter = createGutterWrapper();
    gutter.children = result.gutterAST;
    gutter.properties.style = `grid-row: span ${result.rowCount}`;
    return [gutter, createContentColumn(result.contentAST, result.rowCount)];
  }
  renderPartialHTML(children, includeCodeNode = false) {
    if (!includeCodeNode) return toHtml(children);
    return toHtml(createHastElement({
      tagName: "code",
      children,
      properties: { "data-code": "" }
    }));
  }
  async initializeHighlighter() {
    this.highlighter = await getSharedHighlighter(getHighlighterOptions(this.computedLang, this.options));
    return this.highlighter;
  }
  onHighlightSuccess(file, result, options) {
    if (this.renderCache == null) return;
    const triggerRenderUpdate = this.renderCache.file !== file || !this.renderCache.highlighted || !areRenderOptionsEqual(options, this.renderCache.options);
    this.renderCache = {
      file,
      options,
      highlighted: true,
      result,
      renderRange: void 0
    };
    if (triggerRenderUpdate) this.onRenderUpdate?.();
  }
  onHighlightError(error) {
    console.error(error);
  }
  createPreElement(totalLines, themeStyles, baseThemeType) {
    const { disableLineNumbers = false, overflow = "scroll", themeType = "system" } = this.options;
    return createPreElement({
      type: "file",
      diffIndicators: "none",
      disableBackground: true,
      disableLineNumbers,
      overflow,
      themeStyles,
      themeType: baseThemeType ?? themeType,
      split: false,
      totalLines
    });
  }
};
function areRenderOptionsEqual(optionsA, optionsB) {
  return areThemesEqual(optionsA.theme, optionsB.theme) && optionsA.tokenizeMaxLineLength === optionsB.tokenizeMaxLineLength;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/sprite.js
var SVGSpriteSheet = `<svg data-icon-sprite aria-hidden="true" width="0" height="0">
  <symbol id="diffs-icon-arrow-right-short" viewBox="0 0 16 16">
    <path d="M8.47 4.22a.75.75 0 0 0 0 1.06l1.97 1.97H3.75a.75.75 0 0 0 0 1.5h6.69l-1.97 1.97a.75.75 0 1 0 1.06 1.06l3.25-3.25a.75.75 0 0 0 0-1.06L9.53 4.22a.75.75 0 0 0-1.06 0"/>
  </symbol>
  <symbol id="diffs-icon-brand-github" viewBox="0 0 16 16">
    <path d="M8 0c4.42 0 8 3.58 8 8a8.01 8.01 0 0 1-5.45 7.59c-.4.08-.55-.17-.55-.38 0-.27.01-1.13.01-2.2 0-.75-.25-1.23-.54-1.48 1.78-.2 3.65-.88 3.65-3.95 0-.88-.31-1.59-.82-2.15.08-.2.36-1.02-.08-2.12 0 0-.67-.22-2.2.82-.64-.18-1.32-.27-2-.27s-1.36.09-2 .27c-1.53-1.03-2.2-.82-2.2-.82-.44 1.1-.16 1.92-.08 2.12-.51.56-.82 1.28-.82 2.15 0 3.06 1.86 3.75 3.64 3.95-.23.2-.44.55-.51 1.07-.46.21-1.61.55-2.33-.66-.15-.24-.6-.83-1.23-.82-.67.01-.27.38.01.53.34.19.73.9.82 1.13.16.45.68 1.31 2.69.94 0 .67.01 1.3.01 1.49 0 .21-.15.45-.55.38A7.995 7.995 0 0 1 0 8c0-4.42 3.58-8 8-8"/>
  </symbol>
  <symbol id="diffs-icon-chevron" viewBox="0 0 16 16">
    <path d="M1.47 4.47a.75.75 0 0 1 1.06 0L8 9.94l5.47-5.47a.75.75 0 1 1 1.06 1.06l-6 6a.75.75 0 0 1-1.06 0l-6-6a.75.75 0 0 1 0-1.06"/>
  </symbol>
  <symbol id="diffs-icon-chevrons-narrow" viewBox="0 0 10 16">
    <path d="M4.47 2.22a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1-1.06 1.06L5 3.81 2.28 6.53a.75.75 0 0 1-1.06-1.06zM1.22 9.47a.75.75 0 0 1 1.06 0L5 12.19l2.72-2.72a.75.75 0 0 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0l-3.25-3.25a.75.75 0 0 1 0-1.06"/>
  </symbol>
  <symbol id="diffs-icon-diff-split" viewBox="0 0 16 16">
    <path d="M14 0H8.5v16H14a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2m-1.5 6.5v1h1a.5.5 0 0 1 0 1h-1v1a.5.5 0 0 1-1 0v-1h-1a.5.5 0 0 1 0-1h1v-1a.5.5 0 0 1 1 0"/><path d="M2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h5.5V0zm.5 7.5h3a.5.5 0 0 1 0 1h-3a.5.5 0 0 1 0-1" opacity=".3"/>
  </symbol>
  <symbol id="diffs-icon-diff-unified" viewBox="0 0 16 16">
    <path fill-rule="evenodd" d="M16 14a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V8.5h16zm-8-4a.5.5 0 0 0-.5.5v1h-1a.5.5 0 0 0 0 1h1v1a.5.5 0 0 0 1 0v-1h1a.5.5 0 0 0 0-1h-1v-1A.5.5 0 0 0 8 10" clip-rule="evenodd"/><path fill-rule="evenodd" d="M14 0a2 2 0 0 1 2 2v5.5H0V2a2 2 0 0 1 2-2zM6.5 3.5a.5.5 0 0 0 0 1h3a.5.5 0 0 0 0-1z" clip-rule="evenodd" opacity=".4"/>
  </symbol>
  <symbol id="diffs-icon-expand" viewBox="0 0 16 16">
    <path d="M3.47 5.47a.75.75 0 0 1 1.06 0L8 8.94l3.47-3.47a.75.75 0 1 1 1.06 1.06l-4 4a.75.75 0 0 1-1.06 0l-4-4a.75.75 0 0 1 0-1.06"/>
  </symbol>
  <symbol id="diffs-icon-expand-all" viewBox="0 0 16 16">
    <path d="M11.47 9.47a.75.75 0 1 1 1.06 1.06l-4 4a.75.75 0 0 1-1.06 0l-4-4a.75.75 0 1 1 1.06-1.06L8 12.94zM7.526 1.418a.75.75 0 0 1 1.004.052l4 4a.75.75 0 1 1-1.06 1.06L8 3.06 4.53 6.53a.75.75 0 1 1-1.06-1.06l4-4z"/>
  </symbol>
  <symbol id="diffs-icon-file-code" viewBox="0 0 16 16">
    <path d="M10.75 0c.199 0 .39.08.53.22l3.5 3.5c.14.14.22.331.22.53v9A2.75 2.75 0 0 1 12.25 16h-8.5A2.75 2.75 0 0 1 1 13.25V2.75A2.75 2.75 0 0 1 3.75 0zm-7 1.5c-.69 0-1.25.56-1.25 1.25v10.5c0 .69.56 1.25 1.25 1.25h8.5c.69 0 1.25-.56 1.25-1.25V5h-1.25A2.25 2.25 0 0 1 10 2.75V1.5z"/><path d="M7.248 6.19a.75.75 0 0 1 .063 1.058L5.753 9l1.558 1.752a.75.75 0 0 1-1.122.996l-2-2.25a.75.75 0 0 1 0-.996l2-2.25a.75.75 0 0 1 1.06-.063M8.69 7.248a.75.75 0 1 1 1.12-.996l2 2.25a.75.75 0 0 1 0 .996l-2 2.25a.75.75 0 1 1-1.12-.996L10.245 9z"/>
  </symbol>
  <symbol id="diffs-icon-plus" viewBox="0 0 16 16">
    <path d="M8 3a.75.75 0 0 1 .75.75v3.5h3.5a.75.75 0 0 1 0 1.5h-3.5v3.5a.75.75 0 0 1-1.5 0v-3.5h-3.5a.75.75 0 0 1 0-1.5h3.5v-3.5A.75.75 0 0 1 8 3"/>
  </symbol>
  <symbol id="diffs-icon-symbol-added" viewBox="0 0 16 16">
    <path d="M8 4a.75.75 0 0 1 .75.75v2.5h2.5a.75.75 0 0 1 0 1.5h-2.5v2.5a.75.75 0 0 1-1.5 0v-2.5h-2.5a.75.75 0 0 1 0-1.5h2.5v-2.5A.75.75 0 0 1 8 4"/><path d="M1.788 4.296c.196-.88.478-1.381.802-1.706s.826-.606 1.706-.802C5.194 1.588 6.387 1.5 8 1.5s2.806.088 3.704.288c.88.196 1.381.478 1.706.802s.607.826.802 1.706c.2.898.288 2.091.288 3.704s-.088 2.806-.288 3.704c-.195.88-.478 1.381-.802 1.706s-.826.607-1.706.802c-.898.2-2.091.288-3.704.288s-2.806-.088-3.704-.288c-.88-.195-1.381-.478-1.706-.802s-.606-.826-.802-1.706C1.588 10.806 1.5 9.613 1.5 8s.088-2.806.288-3.704M8 0C1.412 0 0 1.412 0 8s1.412 8 8 8 8-1.412 8-8-1.412-8-8-8"/>
  </symbol>
  <symbol id="diffs-icon-symbol-deleted" viewBox="0 0 16 16">
    <path d="M4 8a.75.75 0 0 1 .75-.75h6.5a.75.75 0 0 1 0 1.5h-6.5A.75.75 0 0 1 4 8"/><path d="M1.788 4.296c.196-.88.478-1.381.802-1.706s.826-.606 1.706-.802C5.194 1.588 6.387 1.5 8 1.5s2.806.088 3.704.288c.88.196 1.381.478 1.706.802s.607.826.802 1.706c.2.898.288 2.091.288 3.704s-.088 2.806-.288 3.704c-.195.88-.478 1.381-.802 1.706s-.826.607-1.706.802c-.898.2-2.091.288-3.704.288s-2.806-.088-3.704-.288c-.88-.195-1.381-.478-1.706-.802s-.606-.826-.802-1.706C1.588 10.806 1.5 9.613 1.5 8s.088-2.806.288-3.704M8 0C1.412 0 0 1.412 0 8s1.412 8 8 8 8-1.412 8-8-1.412-8-8-8"/>
  </symbol>
  <symbol id="diffs-icon-symbol-diffstat" viewBox="0 0 16 16">
    <path d="M1.788 4.296c.196-.88.478-1.381.802-1.706s.826-.606 1.706-.802C5.194 1.588 6.387 1.5 8 1.5s2.806.088 3.704.288c.88.196 1.381.478 1.706.802s.607.826.802 1.706c.2.898.288 2.091.288 3.704s-.088 2.806-.288 3.704c-.195.88-.478 1.381-.802 1.706s-.826.607-1.706.802c-.898.2-2.091.288-3.704.288s-2.806-.088-3.704-.288c-.88-.195-1.381-.478-1.706-.802s-.606-.826-.802-1.706C1.588 10.806 1.5 9.613 1.5 8s.088-2.806.288-3.704M8 0C1.412 0 0 1.412 0 8s1.412 8 8 8 8-1.412 8-8-1.412-8-8-8"/><path d="M8.75 4.296a.75.75 0 0 0-1.5 0V6.25h-2a.75.75 0 0 0 0 1.5h2v1.5h1.5v-1.5h2a.75.75 0 0 0 0-1.5h-2zM5.25 10a.75.75 0 0 0 0 1.5h5.5a.75.75 0 0 0 0-1.5z"/>
  </symbol>
  <symbol id="diffs-icon-symbol-ignored" viewBox="0 0 16 16">
    <path d="M1.5 8c0 1.613.088 2.806.288 3.704.196.88.478 1.381.802 1.706s.826.607 1.706.802c.898.2 2.091.288 3.704.288s2.806-.088 3.704-.288c.88-.195 1.381-.478 1.706-.802s.607-.826.802-1.706c.2-.898.288-2.091.288-3.704s-.088-2.806-.288-3.704c-.195-.88-.478-1.381-.802-1.706s-.826-.606-1.706-.802C10.806 1.588 9.613 1.5 8 1.5s-2.806.088-3.704.288c-.88.196-1.381.478-1.706.802s-.606.826-.802 1.706C1.588 5.194 1.5 6.387 1.5 8M0 8c0-6.588 1.412-8 8-8s8 1.412 8 8-1.412 8-8 8-8-1.412-8-8m11.53-2.47a.75.75 0 0 0-1.06-1.06l-6 6a.75.75 0 1 0 1.06 1.06z"/>
  </symbol>
  <symbol id="diffs-icon-symbol-modified" viewBox="0 0 16 16">
    <path d="M1.5 8c0 1.613.088 2.806.288 3.704.196.88.478 1.381.802 1.706s.826.607 1.706.802c.898.2 2.091.288 3.704.288s2.806-.088 3.704-.288c.88-.195 1.381-.478 1.706-.802s.607-.826.802-1.706c.2-.898.288-2.091.288-3.704s-.088-2.806-.288-3.704c-.195-.88-.478-1.381-.802-1.706s-.826-.606-1.706-.802C10.806 1.588 9.613 1.5 8 1.5s-2.806.088-3.704.288c-.88.196-1.381.478-1.706.802s-.606.826-.802 1.706C1.588 5.194 1.5 6.387 1.5 8M0 8c0-6.588 1.412-8 8-8s8 1.412 8 8-1.412 8-8 8-8-1.412-8-8m8 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6"/>
  </symbol>
  <symbol id="diffs-icon-symbol-moved" viewBox="0 0 16 16">
    <path d="M1.788 4.296c.196-.88.478-1.381.802-1.706s.826-.606 1.706-.802C5.194 1.588 6.387 1.5 8 1.5s2.806.088 3.704.288c.88.196 1.381.478 1.706.802s.607.826.802 1.706c.2.898.288 2.091.288 3.704s-.088 2.806-.288 3.704c-.195.88-.478 1.381-.802 1.706s-.826.607-1.706.802c-.898.2-2.091.288-3.704.288s-2.806-.088-3.704-.288c-.88-.195-1.381-.478-1.706-.802s-.606-.826-.802-1.706C1.588 10.806 1.5 9.613 1.5 8s.088-2.806.288-3.704M8 0C1.412 0 0 1.412 0 8s1.412 8 8 8 8-1.412 8-8-1.412-8-8-8"/><path d="M8.495 4.695a.75.75 0 0 0-.05 1.06L10.486 8l-2.041 2.246a.75.75 0 0 0 1.11 1.008l2.5-2.75a.75.75 0 0 0 0-1.008l-2.5-2.75a.75.75 0 0 0-1.06-.051m-4 0a.75.75 0 0 0-.05 1.06l2.044 2.248-1.796 1.995a.75.75 0 0 0 1.114 1.004l2.25-2.5a.75.75 0 0 0-.002-1.007l-2.5-2.75a.75.75 0 0 0-1.06-.05"/>
  </symbol>
  <symbol id="diffs-icon-symbol-ref" viewBox="0 0 16 16">
    <path d="M1.5 8c0 1.613.088 2.806.288 3.704.196.88.478 1.381.802 1.706.286.286.71.54 1.41.73V1.86c-.7.19-1.124.444-1.41.73-.324.325-.606.826-.802 1.706C1.588 5.194 1.5 6.387 1.5 8m4 6.397c.697.07 1.522.103 2.5.103 1.613 0 2.806-.088 3.704-.288.88-.195 1.381-.478 1.706-.802s.607-.826.802-1.706c.2-.898.288-2.091.288-3.704s-.088-2.806-.288-3.704c-.195-.88-.478-1.381-.802-1.706s-.826-.606-1.706-.802C10.806 1.588 9.613 1.5 8 1.5c-.978 0-1.803.033-2.5.103zM0 8c0-6.588 1.412-8 8-8s8 1.412 8 8-1.412 8-8 8-8-1.412-8-8m7-2a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1z"/>
  </symbol>
</svg>`;

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/areLineAnnotationsEqual.js
function areLineAnnotationsEqual(annotationA, annotationB) {
  return annotationA.lineNumber === annotationB.lineNumber && annotationA.metadata === annotationB.metadata;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/arePrePropertiesEqual.js
function arePrePropertiesEqual(propsA, propsB) {
  if (propsA == null || propsB == null) return propsA === propsB;
  return propsA.type === propsB.type && propsA.diffIndicators === propsB.diffIndicators && propsA.disableBackground === propsB.disableBackground && propsA.disableLineNumbers === propsB.disableLineNumbers && propsA.overflow === propsB.overflow && propsA.split === propsB.split && propsA.themeStyles === propsB.themeStyles && propsA.themeType === propsB.themeType && propsA.totalLines === propsB.totalLines;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/createAnnotationWrapperNode.js
function createAnnotationWrapperNode(slot) {
  const wrapper = document.createElement("div");
  wrapper.dataset.annotationSlot = "";
  wrapper.slot = slot;
  wrapper.style.whiteSpace = "normal";
  return wrapper;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/createGutterUtilityContentNode.js
function createGutterUtilityContentNode() {
  const gutterUtilityContent = document.createElement("div");
  gutterUtilityContent.slot = "gutter-utility-slot";
  gutterUtilityContent.style.position = "absolute";
  gutterUtilityContent.style.top = "0";
  gutterUtilityContent.style.bottom = "0";
  gutterUtilityContent.style.textAlign = "center";
  gutterUtilityContent.style.whiteSpace = "normal";
  return gutterUtilityContent;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/createUnsafeCSSStyleNode.js
function createUnsafeCSSStyleNode() {
  const node = document.createElement("style");
  node.setAttribute(UNSAFE_CSS_ATTRIBUTE, "");
  return node;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/style.js
var style_default = "@layer base, theme, unsafe;\n\n@layer base {\n  :host {\n    --diffs-bg: #fff;\n    --diffs-fg: #000;\n    --diffs-font-fallback:\n      'SF Mono', Monaco, Consolas, 'Ubuntu Mono', 'Liberation Mono',\n      'Courier New', monospace;\n    --diffs-header-font-fallback:\n      system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue',\n      'Noto Sans', 'Liberation Sans', Arial, sans-serif;\n\n    --diffs-mixer: light-dark(black, white);\n    --diffs-gap-fallback: 8px;\n\n    /*\n    // Available CSS Color Overrides\n    --diffs-bg-buffer-override\n    --diffs-bg-hover-override\n    --diffs-bg-context-override\n    --diffs-bg-separator-override\n\n    --diffs-fg-number-override\n    --diffs-fg-number-addition-override\n    --diffs-fg-number-deletion-override\n\n    --diffs-deletion-color-override\n    --diffs-addition-color-override\n    --diffs-modified-color-override\n\n    --diffs-bg-deletion-override\n    --diffs-bg-deletion-number-override\n    --diffs-bg-deletion-hover-override\n    --diffs-bg-deletion-emphasis-override\n\n    --diffs-bg-addition-override\n    --diffs-bg-addition-number-override\n    --diffs-bg-addition-hover-override\n    --diffs-bg-addition-emphasis-override\n\n    // Line Selection Color Overrides (for enableLineSelection)\n    --diffs-selection-color-override\n    --diffs-bg-selection-override\n    --diffs-bg-selection-number-override\n    --diffs-bg-selection-background-override\n    --diffs-bg-selection-number-background-override\n\n    // Available CSS Layout Overrides\n    --diffs-gap-inline\n    --diffs-gap-block\n    --diffs-gap-style\n    --diffs-tab-size\n  */\n\n    color-scheme: light dark;\n    display: block;\n    font-family: var(\n      --diffs-header-font-family,\n      var(--diffs-header-font-fallback)\n    );\n    font-size: var(--diffs-font-size, 13px);\n    line-height: var(--diffs-line-height, 20px);\n    font-feature-settings: var(--diffs-font-features);\n  }\n\n  /* NOTE(mdo): Some semantic HTML elements (e.g. `pre`, `code`) have default\n * user-agent styles. These must be overridden to use our custom styles. */\n  pre,\n  code,\n  [data-error-wrapper] {\n    isolation: isolate;\n    margin: 0;\n    padding: 0;\n    display: block;\n    outline: none;\n    font-family: var(--diffs-font-family, var(--diffs-font-fallback));\n  }\n\n  pre,\n  code {\n    background-color: var(--diffs-bg);\n  }\n\n  code {\n    contain: content;\n  }\n\n  *,\n  *::before,\n  *::after {\n    box-sizing: border-box;\n  }\n\n  [data-icon-sprite] {\n    display: none;\n  }\n\n  /* NOTE(mdo): Headers and separators are within pre/code, so we need to reset\n   * their font-family explicitly. */\n  [data-diffs-header],\n  [data-separator] {\n    font-family: var(\n      --diffs-header-font-family,\n      var(--diffs-header-font-fallback)\n    );\n  }\n\n  [data-file-info] {\n    padding: 10px;\n    font-weight: 700;\n    color: var(--fg);\n    /* NOTE(amadeus): we cannot use 'in oklch' because current versions of cursor\n   * and vscode use an older build of chrome that appears to have a bug with\n   * color-mix and 'in oklch', so use 'in lab' instead */\n    background-color: color-mix(in lab, var(--bg) 98%, var(--fg));\n    border-block: 1px solid color-mix(in lab, var(--bg) 95%, var(--fg));\n  }\n\n  [data-diffs-header],\n  [data-diff],\n  [data-file],\n  [data-error-wrapper],\n  [data-virtualizer-buffer] {\n    --diffs-bg: light-dark(var(--diffs-light-bg), var(--diffs-dark-bg));\n    /* NOTE(amadeus): we cannot use 'in oklch' because current versions of cursor\n   * and vscode use an older build of chrome that appears to have a bug with\n   * color-mix and 'in oklch', so use 'in lab' instead */\n    --diffs-bg-buffer: var(\n      --diffs-bg-buffer-override,\n      light-dark(\n        color-mix(in lab, var(--diffs-bg) 92%, var(--diffs-mixer)),\n        color-mix(in lab, var(--diffs-bg) 92%, var(--diffs-mixer))\n      )\n    );\n    --diffs-bg-hover: var(\n      --diffs-bg-hover-override,\n      light-dark(\n        color-mix(in lab, var(--diffs-bg) 97%, var(--diffs-mixer)),\n        color-mix(in lab, var(--diffs-bg) 91%, var(--diffs-mixer))\n      )\n    );\n\n    --diffs-bg-context: var(\n      --diffs-bg-context-override,\n      light-dark(\n        color-mix(in lab, var(--diffs-bg) 98.5%, var(--diffs-mixer)),\n        color-mix(in lab, var(--diffs-bg) 92.5%, var(--diffs-mixer))\n      )\n    );\n    --diffs-bg-context-number: var(\n      --diffs-bg-context-number-override,\n      light-dark(\n        color-mix(in lab, var(--diffs-bg-context) 80%, var(--diffs-bg)),\n        color-mix(in lab, var(--diffs-bg-context) 60%, var(--diffs-bg))\n      )\n    );\n\n    --diffs-bg-separator: var(\n      --diffs-bg-separator-override,\n      light-dark(\n        color-mix(in lab, var(--diffs-bg) 96%, var(--diffs-mixer)),\n        color-mix(in lab, var(--diffs-bg) 85%, var(--diffs-mixer))\n      )\n    );\n\n    --diffs-fg: light-dark(var(--diffs-light), var(--diffs-dark));\n    --diffs-fg-number: var(\n      --diffs-fg-number-override,\n      light-dark(\n        color-mix(in lab, var(--diffs-fg) 65%, var(--diffs-bg)),\n        color-mix(in lab, var(--diffs-fg) 65%, var(--diffs-bg))\n      )\n    );\n\n    --diffs-deletion-base: var(\n      --diffs-deletion-color-override,\n      light-dark(\n        var(\n          --diffs-light-deletion-color,\n          var(--diffs-deletion-color, rgb(255, 0, 0))\n        ),\n        var(\n          --diffs-dark-deletion-color,\n          var(--diffs-deletion-color, rgb(255, 0, 0))\n        )\n      )\n    );\n    --diffs-addition-base: var(\n      --diffs-addition-color-override,\n      light-dark(\n        var(\n          --diffs-light-addition-color,\n          var(--diffs-addition-color, rgb(0, 255, 0))\n        ),\n        var(\n          --diffs-dark-addition-color,\n          var(--diffs-addition-color, rgb(0, 255, 0))\n        )\n      )\n    );\n    --diffs-modified-base: var(\n      --diffs-modified-color-override,\n      light-dark(\n        var(\n          --diffs-light-modified-color,\n          var(--diffs-modified-color, rgb(0, 0, 255))\n        ),\n        var(\n          --diffs-dark-modified-color,\n          var(--diffs-modified-color, rgb(0, 0, 255))\n        )\n      )\n    );\n\n    /* NOTE(amadeus): we cannot use 'in oklch' because current versions of cursor\n   * and vscode use an older build of chrome that appears to have a bug with\n   * color-mix and 'in oklch', so use 'in lab' instead */\n    --diffs-bg-deletion: var(\n      --diffs-bg-deletion-override,\n      light-dark(\n        color-mix(in lab, var(--diffs-bg) 88%, var(--diffs-deletion-base)),\n        color-mix(in lab, var(--diffs-bg) 80%, var(--diffs-deletion-base))\n      )\n    );\n    --diffs-bg-deletion-number: var(\n      --diffs-bg-deletion-number-override,\n      light-dark(\n        color-mix(in lab, var(--diffs-bg) 91%, var(--diffs-deletion-base)),\n        color-mix(in lab, var(--diffs-bg) 85%, var(--diffs-deletion-base))\n      )\n    );\n    --diffs-bg-deletion-hover: var(\n      --diffs-bg-deletion-hover-override,\n      light-dark(\n        color-mix(in lab, var(--diffs-bg) 80%, var(--diffs-deletion-base)),\n        color-mix(in lab, var(--diffs-bg) 75%, var(--diffs-deletion-base))\n      )\n    );\n    --diffs-bg-deletion-emphasis: var(\n      --diffs-bg-deletion-emphasis-override,\n      light-dark(\n        rgb(from var(--diffs-deletion-base) r g b / 0.15),\n        rgb(from var(--diffs-deletion-base) r g b / 0.2)\n      )\n    );\n\n    --diffs-bg-addition: var(\n      --diffs-bg-addition-override,\n      light-dark(\n        color-mix(in lab, var(--diffs-bg) 88%, var(--diffs-addition-base)),\n        color-mix(in lab, var(--diffs-bg) 80%, var(--diffs-addition-base))\n      )\n    );\n    --diffs-bg-addition-number: var(\n      --diffs-bg-addition-number-override,\n      light-dark(\n        color-mix(in lab, var(--diffs-bg) 91%, var(--diffs-addition-base)),\n        color-mix(in lab, var(--diffs-bg) 85%, var(--diffs-addition-base))\n      )\n    );\n    --diffs-bg-addition-hover: var(\n      --diffs-bg-addition-hover-override,\n      light-dark(\n        color-mix(in lab, var(--diffs-bg) 80%, var(--diffs-addition-base)),\n        color-mix(in lab, var(--diffs-bg) 70%, var(--diffs-addition-base))\n      )\n    );\n    --diffs-bg-addition-emphasis: var(\n      --diffs-bg-addition-emphasis-override,\n      light-dark(\n        rgb(from var(--diffs-addition-base) r g b / 0.15),\n        rgb(from var(--diffs-addition-base) r g b / 0.2)\n      )\n    );\n\n    --diffs-selection-base: var(--diffs-modified-base);\n    --diffs-selection-number-fg: light-dark(\n      color-mix(in lab, var(--diffs-selection-base) 65%, var(--diffs-mixer)),\n      color-mix(in lab, var(--diffs-selection-base) 75%, var(--diffs-mixer))\n    );\n    --diffs-bg-selection: var(\n      --diffs-bg-selection-override,\n      light-dark(\n        color-mix(in lab, var(--diffs-bg) 82%, var(--diffs-selection-base)),\n        color-mix(in lab, var(--diffs-bg) 75%, var(--diffs-selection-base))\n      )\n    );\n    --diffs-bg-selection-number: var(\n      --diffs-bg-selection-number-override,\n      light-dark(\n        color-mix(in lab, var(--diffs-bg) 75%, var(--diffs-selection-base)),\n        color-mix(in lab, var(--diffs-bg) 60%, var(--diffs-selection-base))\n      )\n    );\n\n    background-color: var(--diffs-bg);\n    color: var(--diffs-fg);\n  }\n\n  [data-diff],\n  [data-file] {\n    /* This feels a bit crazy to me... so I need to think about it a bit more... */\n    --diffs-grid-number-column-width: minmax(min-content, max-content);\n    --diffs-code-grid: var(--diffs-grid-number-column-width) 1fr;\n\n    &[data-dehydrated] {\n      --diffs-code-grid: var(--diffs-grid-number-column-width) minmax(0, 1fr);\n    }\n\n    &[data-theme-type='light'],\n    & {\n      [data-line] span {\n        color: light-dark(\n          var(--diffs-token-light, var(--diffs-light)),\n          var(--diffs-token-dark, var(--diffs-dark))\n        );\n        font-weight: var(--diffs-token-light-font-weight, inherit);\n        font-style: var(--diffs-token-light-font-style, inherit);\n        -webkit-text-decoration: var(--diffs-token-light-text-decoration, inherit);\n                text-decoration: var(--diffs-token-light-text-decoration, inherit);\n      }\n    }\n\n    &[data-theme-type='dark'] [data-line] span {\n      font-weight: var(--diffs-token-dark-font-weight, inherit);\n      font-style: var(--diffs-token-dark-font-style, inherit);\n      -webkit-text-decoration: var(--diffs-token-dark-text-decoration, inherit);\n              text-decoration: var(--diffs-token-dark-text-decoration, inherit);\n    }\n\n    &:hover [data-code]::-webkit-scrollbar-thumb {\n      background-color: var(--diffs-bg-context);\n    }\n  }\n\n  [data-line] span {\n    background-color: light-dark(\n      var(--diffs-token-light-bg, inherit),\n      var(--diffs-token-dark-bg, inherit)\n    );\n  }\n\n  [data-line],\n  [data-gutter-buffer],\n  [data-line-annotation],\n  [data-no-newline] {\n    color: var(--diffs-fg);\n    background-color: var(--diffs-line-bg, var(--diffs-bg));\n  }\n\n  [data-no-newline] {\n    -webkit-user-select: none;\n            user-select: none;\n\n    span {\n      opacity: 0.6;\n    }\n  }\n\n  @media (prefers-color-scheme: dark) {\n    [data-diffs-header],\n    [data-error-wrapper],\n    [data-diff],\n    [data-file] {\n      color-scheme: dark;\n    }\n\n    [data-content] [data-line] span {\n      font-weight: var(--diffs-token-dark-font-weight, inherit);\n      font-style: var(--diffs-token-dark-font-style, inherit);\n      -webkit-text-decoration: var(--diffs-token-dark-text-decoration, inherit);\n              text-decoration: var(--diffs-token-dark-text-decoration, inherit);\n    }\n  }\n\n  [data-diffs-header],\n  [data-diff],\n  [data-file] {\n    &[data-theme-type='light'] {\n      color-scheme: light;\n    }\n\n    &[data-theme-type='dark'] {\n      color-scheme: dark;\n    }\n  }\n\n  [data-diff-type='split'][data-overflow='scroll'] {\n    display: grid;\n    grid-template-columns: 1fr 1fr;\n\n    [data-additions] {\n      border-left: 1px solid var(--diffs-bg);\n    }\n\n    [data-deletions] {\n      border-right: 1px solid var(--diffs-bg);\n    }\n  }\n\n  [data-code] {\n    display: grid;\n    grid-auto-flow: dense;\n    grid-template-columns: var(--diffs-code-grid);\n    overflow: scroll clip;\n    overscroll-behavior-x: none;\n    tab-size: var(--diffs-tab-size, 2);\n    align-self: flex-start;\n    padding-top: var(--diffs-gap-block, var(--diffs-gap-fallback));\n    padding-bottom: max(\n      0px,\n      calc(var(--diffs-gap-block, var(--diffs-gap-fallback)) - 6px)\n    );\n  }\n\n  [data-container-size] {\n    container-type: inline-size;\n  }\n\n  [data-code]::-webkit-scrollbar {\n    width: 0;\n    height: 6px;\n  }\n\n  [data-code]::-webkit-scrollbar-track {\n    background: transparent;\n  }\n\n  [data-code]::-webkit-scrollbar-thumb {\n    background-color: transparent;\n    border: 1px solid transparent;\n    background-clip: content-box;\n    border-radius: 3px;\n  }\n\n  [data-code]::-webkit-scrollbar-corner {\n    background-color: transparent;\n  }\n\n  /*\n   * If we apply these rules globally it will mean that webkit will opt into the\n   * standards compliant version of custom css scrollbars, which we do not want\n   * because the custom stuff will look better\n  */\n  @supports (-moz-appearance: none) {\n    [data-code] {\n      scrollbar-width: thin;\n      scrollbar-color: var(--diffs-bg-context) transparent;\n      padding-bottom: var(--diffs-gap-block, var(--diffs-gap-fallback));\n    }\n  }\n\n  [data-diffs-header] ~ [data-diff],\n  [data-diffs-header] ~ [data-file] {\n    [data-code],\n    &[data-overflow='wrap'] {\n      padding-top: 0;\n    }\n  }\n\n  [data-gutter] {\n    display: grid;\n    grid-template-rows: subgrid;\n    grid-template-columns: subgrid;\n    grid-column: 1;\n    z-index: 3;\n    position: relative;\n    background-color: var(--diffs-bg);\n\n    [data-gutter-buffer],\n    [data-column-number] {\n      border-right: var(--diffs-gap-style, 2px solid var(--diffs-bg));\n    }\n  }\n\n  [data-content] {\n    display: grid;\n    grid-template-rows: subgrid;\n    grid-template-columns: subgrid;\n    grid-column: 2;\n    min-width: 0;\n  }\n\n  [data-diff-type='split'][data-overflow='wrap'] {\n    display: grid;\n    grid-auto-flow: dense;\n    grid-template-columns: repeat(2, var(--diffs-code-grid));\n    padding-block: var(--diffs-gap-block, var(--diffs-gap-fallback));\n\n    [data-deletions] {\n      display: contents;\n\n      [data-gutter] {\n        grid-column: 1;\n      }\n\n      [data-content] {\n        grid-column: 2;\n        border-right: 1px solid var(--diffs-bg);\n      }\n    }\n\n    [data-additions] {\n      display: contents;\n\n      [data-gutter] {\n        grid-column: 3;\n        border-left: 1px solid var(--diffs-bg);\n      }\n\n      [data-content] {\n        grid-column: 4;\n      }\n    }\n  }\n\n  [data-overflow='scroll'] [data-gutter] {\n    position: sticky;\n    left: 0;\n  }\n\n  [data-line-annotation][data-selected-line] {\n    background-color: unset;\n\n    &::before {\n      content: '';\n      /* FIXME(amadeus): This needs to be audited ... */\n      position: sticky;\n      top: 0;\n      left: 0;\n      display: block;\n      border-right: var(--diffs-gap-style, 1px solid var(--diffs-bg));\n      background-color: var(--diffs-bg-selection-number);\n    }\n\n    [data-annotation-content] {\n      background-color: var(--diffs-bg-selection);\n    }\n  }\n\n  [data-interactive-lines] [data-line] {\n    cursor: pointer;\n  }\n\n  [data-content-buffer],\n  [data-gutter-buffer] {\n    position: relative;\n    -webkit-user-select: none;\n            user-select: none;\n    min-height: 1lh;\n  }\n\n  [data-gutter-buffer='annotation'] {\n    min-height: 0;\n  }\n\n  [data-gutter-buffer='buffer'] {\n    background-size: 8px 8px;\n    background-position: 0 0;\n    background-origin: border-box;\n    background-color: var(--diffs-bg);\n    /* This is incredibley expensive... */\n    background-image: repeating-linear-gradient(\n      -45deg,\n      transparent,\n      transparent calc(3px * 1.414),\n      rgb(from var(--diffs-bg-buffer) r g b / 0.8) calc(3px * 1.414),\n      rgb(from var(--diffs-bg-buffer) r g b / 0.8) calc(4px * 1.414)\n    );\n  }\n\n  [data-content-buffer] {\n    grid-column: 1;\n    /* We multiply by 1.414 (√2) to better approximate the diagonal repeat distance */\n    background-size: 8px 8px;\n    background-position: 5px 0;\n    background-origin: border-box;\n    background-color: var(--diffs-bg);\n    /* This is incredibley expensive... */\n    background-image: repeating-linear-gradient(\n      -45deg,\n      transparent,\n      transparent calc(3px * 1.414),\n      var(--diffs-bg-buffer) calc(3px * 1.414),\n      var(--diffs-bg-buffer) calc(4px * 1.414)\n    );\n  }\n\n  [data-separator] {\n    box-sizing: content-box;\n    background-color: var(--diffs-bg);\n  }\n\n  [data-separator='simple'] {\n    min-height: 4px;\n  }\n\n  [data-separator='line-info'],\n  [data-separator='line-info-basic'],\n  [data-separator='metadata'],\n  [data-separator='simple'] {\n    background-color: var(--diffs-bg-separator);\n  }\n\n  [data-separator='line-info'],\n  [data-separator='line-info-basic'],\n  [data-separator='metadata'] {\n    height: 32px;\n    position: relative;\n  }\n\n  [data-separator-wrapper] {\n    -webkit-user-select: none;\n            user-select: none;\n    fill: currentColor;\n    position: absolute;\n    inset-inline: 0;\n    display: flex;\n    align-items: center;\n    background-color: var(--diffs-bg);\n    height: 100%;\n  }\n\n  [data-content] [data-separator-wrapper] {\n    display: none;\n  }\n\n  [data-separator='metadata'] [data-separator-wrapper] {\n    inset-inline: 100% auto;\n    padding-inline: 1ch;\n    height: 100%;\n    background-color: var(--diffs-bg-separator);\n    color: var(--diffs-fg-number);\n    white-space: nowrap;\n    overflow: hidden;\n    text-overflow: ellipsis;\n    min-width: min-content;\n  }\n\n  [data-separator='line-info'] {\n    margin-block: var(--diffs-gap-block, var(--diffs-gap-fallback));\n  }\n\n  [data-separator='line-info-basic'],\n  [data-separator='metadata'] {\n    margin-block: 0;\n  }\n\n  [data-separator='line-info'][data-separator-first] {\n    margin-top: 0;\n  }\n\n  [data-separator='line-info'][data-separator-last] {\n    margin-bottom: 0;\n  }\n\n  [data-expand-index] [data-separator-wrapper] {\n    display: grid;\n    grid-template-columns: 32px auto;\n  }\n\n  [data-expand-index] [data-separator-wrapper][data-separator-multi-button] {\n    grid-template-columns: 32px 32px auto;\n  }\n\n  [data-expand-button],\n  [data-separator-content] {\n    display: flex;\n    flex: 0 0 auto;\n    align-items: center;\n    background-color: var(--diffs-bg-separator);\n  }\n\n  [data-expand-button] {\n    justify-content: center;\n    flex-shrink: 0;\n    cursor: pointer;\n    min-width: 32px;\n    align-self: stretch;\n    color: var(--diffs-fg-number);\n    border-right: 2px solid var(--diffs-bg);\n\n    &:hover {\n      color: var(--diffs-fg);\n    }\n  }\n\n  [data-expand-down] [data-icon] {\n    transform: scaleY(-1);\n  }\n\n  [data-separator-content] {\n    flex: 1 1 auto;\n    padding: 0 1ch;\n    height: 100%;\n    color: var(--diffs-fg-number);\n\n    overflow: hidden;\n    justify-content: flex-start;\n  }\n\n  [data-separator='line-info'],\n  [data-separator='line-info-basic'] {\n    [data-separator-content] {\n      height: 100%;\n      -webkit-user-select: none;\n              user-select: none;\n      overflow: clip;\n    }\n  }\n\n  @supports (width: 1cqi) {\n    [data-unified] {\n      [data-separator='line-info'] [data-separator-wrapper] {\n        padding-inline: var(--diffs-gap-inline, var(--diffs-gap-fallback));\n        width: 100cqi;\n\n        [data-separator-content] {\n          border-radius: 6px;\n        }\n      }\n\n      [data-separator='line-info'][data-expand-index]\n        [data-separator-wrapper]\n        [data-separator-content] {\n        border-top-left-radius: unset;\n        border-bottom-left-radius: unset;\n      }\n    }\n\n    [data-gutter] {\n      [data-separator='line-info'] [data-separator-wrapper] {\n        padding-left: var(--diffs-gap-inline, var(--diffs-gap-fallback));\n      }\n\n      [data-separator='line-info'] [data-separator-content] {\n        border-top-left-radius: 6px;\n        border-bottom-left-radius: 6px;\n      }\n\n      [data-separator='line-info'][data-expand-index] [data-separator-content] {\n        border-top-left-radius: unset;\n        border-bottom-left-radius: unset;\n      }\n    }\n\n    [data-additions] {\n      [data-content] [data-separator='line-info'] {\n        background-color: var(--diffs-bg);\n\n        [data-separator-wrapper] {\n          display: none;\n        }\n      }\n\n      [data-gutter] [data-separator='line-info'] [data-separator-wrapper] {\n        display: block;\n        height: 100%;\n        background-color: var(--diffs-bg-separator);\n        border-top-right-radius: 6px;\n        border-bottom-right-radius: 6px;\n\n        [data-separator-content],\n        [data-expand-button] {\n          display: none;\n        }\n      }\n    }\n\n    [data-overflow='scroll']\n      [data-additions]\n      [data-gutter]\n      [data-separator='line-info']\n      [data-separator-wrapper] {\n      width: calc(100cqi - var(--diffs-gap-inline, var(--diffs-gap-fallback)));\n    }\n\n    [data-overflow='wrap']\n      [data-additions]\n      [data-content]\n      [data-separator='line-info']\n      [data-separator-wrapper] {\n      background-color: var(--diffs-bg-separator);\n      display: block;\n      height: 100%;\n      margin-right: var(--diffs-gap-inline, var(--diffs-gap-fallback));\n      border-top-right-radius: 6px;\n      border-bottom-right-radius: 6px;\n\n      [data-separator-content],\n      [data-expand-button] {\n        display: none;\n      }\n    }\n\n    [data-separator='line-info'] [data-separator-wrapper] {\n      [data-expand-both],\n      [data-expand-down],\n      [data-expand-up] {\n        border-top-left-radius: 6px;\n        border-bottom-left-radius: 6px;\n      }\n    }\n\n    @media (pointer: fine) {\n      [data-separator='line-info'] [data-separator-wrapper] {\n        &[data-separator-multi-button] {\n          [data-expand-up] {\n            border-top-left-radius: 6px;\n            border-bottom-left-radius: unset;\n          }\n\n          [data-expand-down] {\n            border-bottom-left-radius: 6px;\n            border-top-left-radius: unset;\n          }\n        }\n      }\n    }\n  }\n\n  @media (pointer: coarse) {\n    [data-separator='line-info-basic']\n      [data-separator-wrapper][data-separator-multi-button] {\n      grid-template-columns: 34px 34px auto;\n\n      [data-separator-content] {\n        grid-column: unset;\n        grid-row: unset;\n      }\n    }\n\n    @supports (width: 1cqi) {\n      [data-separator='line-info'] [data-separator-wrapper] {\n        [data-expand-both],\n        [data-expand-down],\n        [data-expand-up] {\n          border-top-left-radius: 6px;\n          border-bottom-left-radius: 6px;\n        }\n\n        &[data-separator-multi-button] {\n          [data-expand-up] {\n            border-top-left-radius: 6px;\n            border-bottom-left-radius: 6px;\n          }\n\n          [data-expand-down] {\n            border-bottom-left-radius: unset;\n            border-top-left-radius: unset;\n          }\n        }\n      }\n    }\n  }\n\n  @media (pointer: fine) {\n    [data-separator-wrapper][data-separator-multi-button] {\n      display: grid;\n      grid-template-rows: 50% 50%;\n\n      [data-separator-content] {\n        grid-column: 2;\n        grid-row: 1 / -1;\n        min-width: min-content;\n      }\n\n      [data-expand-button] {\n        grid-column: 1;\n      }\n    }\n\n    [data-separator='line-info'] [data-separator-wrapper],\n    [data-separator='line-info']\n      [data-separator-wrapper][data-separator-multi-button] {\n      grid-template-columns: 34px auto;\n    }\n\n    [data-separator='line-info-basic'][data-expand-index]\n      [data-separator-wrapper] {\n      grid-template-columns: 100% auto;\n    }\n\n    [data-separator='line-info'],\n    [data-separator='line-info-basic'] {\n      [data-separator-multi-button] {\n        [data-expand-up] {\n          border-bottom: 1px solid var(--diffs-bg);\n          border-right: 2px solid var(--diffs-bg);\n        }\n        [data-expand-down] {\n          border-top: 1px solid var(--diffs-bg);\n          border-right: 2px solid var(--diffs-bg);\n        }\n      }\n    }\n  }\n\n  [data-additions] [data-gutter] [data-separator-wrapper],\n  [data-additions] [data-separator='line-info-basic'] [data-separator-wrapper],\n  [data-content] [data-separator-wrapper] {\n    display: none;\n  }\n\n  [data-line-annotation],\n  [data-gutter-buffer='annotation'] {\n    --diffs-line-bg: var(--diffs-bg-context);\n  }\n\n  [data-line-annotation] {\n    min-height: var(--diffs-annotation-min-height, 0);\n    z-index: 2;\n  }\n\n  [data-separator='custom'] {\n    display: grid;\n    grid-template-columns: subgrid;\n  }\n\n  [data-line],\n  [data-column-number],\n  [data-no-newline] {\n    position: relative;\n    padding-inline: 1ch;\n  }\n\n  [data-indicators='classic'] [data-line] {\n    padding-inline-start: 2ch;\n  }\n\n  [data-indicators='classic'] {\n    [data-line-type='change-addition'],\n    [data-line-type='change-deletion'] {\n      &[data-no-newline],\n      &[data-line] {\n        &::before {\n          display: inline-block;\n          width: 1ch;\n          height: 1lh;\n          position: absolute;\n          top: 0;\n          left: 0;\n          -webkit-user-select: none;\n                  user-select: none;\n        }\n      }\n    }\n\n    [data-line-type='change-addition'] {\n      &[data-line],\n      &[data-no-newline] {\n        &::before {\n          content: '+';\n          color: var(--diffs-addition-base);\n        }\n      }\n    }\n\n    [data-line-type='change-deletion'] {\n      &[data-line],\n      &[data-no-newline] {\n        &::before {\n          content: '-';\n          color: var(--diffs-deletion-base);\n        }\n      }\n    }\n  }\n\n  [data-indicators='bars'] {\n    [data-line-type='change-deletion'],\n    [data-line-type='change-addition'] {\n      &[data-column-number] {\n        &::before {\n          content: '';\n          display: block;\n          width: 4px;\n          height: 100%;\n          position: absolute;\n          top: 0;\n          left: 0;\n          -webkit-user-select: none;\n                  user-select: none;\n          contain: strict;\n        }\n      }\n    }\n\n    [data-line-type='change-deletion'] {\n      &[data-column-number] {\n        &::before {\n          background-image: linear-gradient(\n            0deg,\n            var(--diffs-bg-deletion) 50%,\n            var(--diffs-deletion-base) 50%\n          );\n          background-repeat: repeat;\n          background-size: 2px 2px;\n          background-size: calc(1lh / round(1lh / 2px))\n            calc(1lh / round(1lh / 2px));\n        }\n      }\n    }\n\n    [data-line-type='change-addition'] {\n      &[data-column-number] {\n        &::before {\n          background-color: var(--diffs-addition-base);\n        }\n      }\n    }\n  }\n\n  [data-overflow='wrap'] {\n    [data-line],\n    [data-annotation-content] {\n      white-space: pre-wrap;\n      word-break: break-word;\n    }\n  }\n\n  [data-overflow='scroll'] [data-line] {\n    white-space: pre;\n    min-height: 1lh;\n  }\n\n  [data-column-number] {\n    box-sizing: content-box;\n    text-align: right;\n    -webkit-user-select: none;\n            user-select: none;\n    background-color: var(--diffs-bg);\n    color: var(--diffs-fg-number);\n    padding-left: 2ch;\n  }\n\n  [data-line-number-content] {\n    display: inline-block;\n    min-width: var(\n      --diffs-min-number-column-width,\n      var(--diffs-min-number-column-width-default, 3ch)\n    );\n  }\n\n  [data-disable-line-numbers] {\n    [data-column-number] {\n      min-width: 4px;\n      padding: 0;\n    }\n\n    [data-line-number-content] {\n      display: none;\n    }\n\n    [data-gutter-utility-slot] {\n      right: unset;\n      left: 0;\n      justify-content: flex-start;\n    }\n\n    &[data-indicators='bars'] [data-gutter-utility-slot] {\n      /* Using 5px here because theres a 1px separator after the bar */\n      left: 5px;\n    }\n  }\n\n  [data-file][data-disable-line-numbers] {\n    [data-gutter-buffer],\n    [data-column-number] {\n      min-width: 0;\n      border-right: 0;\n    }\n  }\n\n  [data-interactive-line-numbers] [data-column-number] {\n    cursor: pointer;\n  }\n\n  [data-diff-span] {\n    border-radius: 3px;\n    -webkit-box-decoration-break: clone;\n            box-decoration-break: clone;\n  }\n\n  [data-line-type='change-addition'] {\n    &[data-column-number] {\n      color: var(\n        --diffs-fg-number-addition-override,\n        var(--diffs-addition-base)\n      );\n    }\n\n    > [data-diff-span] {\n      background-color: var(--diffs-bg-addition-emphasis);\n    }\n  }\n\n  [data-line-type='change-deletion'] {\n    &[data-column-number] {\n      color: var(\n        --diffs-fg-number-deletion-override,\n        var(--diffs-deletion-base)\n      );\n    }\n\n    [data-diff-span] {\n      background-color: var(--diffs-bg-deletion-emphasis);\n    }\n  }\n\n  [data-background] [data-line-type='change-addition'] {\n    --diffs-line-bg: var(--diffs-bg-addition);\n\n    &[data-column-number] {\n      background-color: var(--diffs-bg-addition-number);\n    }\n  }\n\n  [data-background] [data-line-type='change-deletion'] {\n    --diffs-line-bg: var(--diffs-bg-deletion);\n\n    &[data-column-number] {\n      background-color: var(--diffs-bg-deletion-number);\n    }\n  }\n\n  @media (pointer: fine) {\n    [data-column-number],\n    [data-line] {\n      &[data-hovered] {\n        background-color: var(--diffs-bg-hover);\n      }\n    }\n\n    [data-background] {\n      [data-column-number],\n      [data-line] {\n        &[data-hovered] {\n          &[data-line-type='change-deletion'] {\n            background-color: var(--diffs-bg-deletion-hover);\n          }\n\n          &[data-line-type='change-addition'] {\n            background-color: var(--diffs-bg-addition-hover);\n          }\n        }\n      }\n    }\n  }\n\n  [data-diffs-header] {\n    position: relative;\n    display: flex;\n    flex-direction: row;\n    justify-content: space-between;\n    align-items: center;\n    gap: var(--diffs-gap-inline, var(--diffs-gap-fallback));\n    min-height: calc(\n      1lh + (var(--diffs-gap-block, var(--diffs-gap-fallback)) * 3)\n    );\n    padding-inline: 16px;\n    top: 0;\n    z-index: 2;\n  }\n\n  [data-header-content] {\n    display: flex;\n    flex-direction: row;\n    align-items: center;\n    gap: var(--diffs-gap-inline, var(--diffs-gap-fallback));\n    min-width: 0;\n    white-space: nowrap;\n  }\n\n  [data-header-content] [data-prev-name],\n  [data-header-content] [data-title] {\n    direction: rtl;\n    overflow: hidden;\n    text-overflow: ellipsis;\n    min-width: 0;\n    white-space: nowrap;\n  }\n\n  [data-prev-name] {\n    opacity: 0.7;\n  }\n\n  [data-rename-icon] {\n    fill: currentColor;\n    flex-shrink: 0;\n    flex-grow: 0;\n  }\n\n  [data-diffs-header] [data-metadata] {\n    display: flex;\n    align-items: center;\n    gap: 1ch;\n    white-space: nowrap;\n  }\n\n  [data-diffs-header] [data-additions-count] {\n    font-family: var(--diffs-font-family, var(--diffs-font-fallback));\n    color: var(--diffs-addition-base);\n  }\n\n  [data-diffs-header] [data-deletions-count] {\n    font-family: var(--diffs-font-family, var(--diffs-font-fallback));\n    color: var(--diffs-deletion-base);\n  }\n\n  [data-annotation-content] {\n    position: relative;\n    display: flow-root;\n    align-self: flex-start;\n    z-index: 2;\n    min-width: 0;\n    isolation: isolate;\n  }\n\n  /* Sticky positioning has a composite costs, so we should _only_ pay it if we\n   * need to */\n  [data-overflow='scroll'] [data-annotation-content] {\n    position: sticky;\n    width: var(--diffs-column-content-width, auto);\n    left: var(--diffs-column-number-width, 0);\n  }\n\n  /* Undo some of the stuff that the 'pre' tag does */\n  [data-annotation-slot] {\n    text-wrap-mode: wrap;\n    word-break: normal;\n    white-space-collapse: collapse;\n  }\n\n  [data-change-icon] {\n    fill: currentColor;\n    flex-shrink: 0;\n  }\n\n  [data-change-icon='change'],\n  [data-change-icon='rename-pure'],\n  [data-change-icon='rename-changed'] {\n    color: var(--diffs-modified-base);\n  }\n\n  [data-change-icon='new'] {\n    color: var(--diffs-addition-base);\n  }\n\n  [data-change-icon='deleted'] {\n    color: var(--diffs-deletion-base);\n  }\n\n  [data-change-icon='file'] {\n    opacity: 0.6;\n  }\n\n  /* Line selection highlighting */\n  [data-selected-line] {\n    &[data-gutter-buffer='annotation'],\n    &[data-column-number] {\n      color: var(--diffs-selection-number-fg);\n      background-color: var(--diffs-bg-selection-number);\n    }\n\n    &[data-line] {\n      background-color: var(--diffs-bg-selection);\n    }\n  }\n\n  [data-line-type='change-addition'],\n  [data-line-type='change-deletion'] {\n    &[data-selected-line] {\n      &[data-line],\n      &[data-line][data-hovered] {\n        background-color: light-dark(\n          color-mix(\n            in lab,\n            var(--diffs-line-bg, var(--diffs-bg)) 82%,\n            var(--diffs-selection-base)\n          ),\n          color-mix(\n            in lab,\n            var(--diffs-line-bg, var(--diffs-bg)) 75%,\n            var(--diffs-selection-base)\n          )\n        );\n      }\n\n      &[data-column-number],\n      &[data-column-number][data-hovered] {\n        color: var(--diffs-selection-number-fg);\n        background-color: light-dark(\n          color-mix(\n            in lab,\n            var(--diffs-line-bg, var(--diffs-bg)) 75%,\n            var(--diffs-selection-base)\n          ),\n          color-mix(\n            in lab,\n            var(--diffs-line-bg, var(--diffs-bg)) 60%,\n            var(--diffs-selection-base)\n          )\n        );\n      }\n    }\n  }\n\n  [data-gutter-utility-slot] {\n    position: absolute;\n    top: 0;\n    bottom: 0;\n    right: 0;\n    display: flex;\n    justify-content: flex-end;\n  }\n\n  [data-unmodified-lines] {\n    display: block;\n    overflow: hidden;\n    min-width: 0;\n    text-overflow: ellipsis;\n    white-space: nowrap;\n    flex: 0 1 auto;\n  }\n\n  [data-error-wrapper] {\n    overflow: auto;\n    padding: var(--diffs-gap-block, var(--diffs-gap-fallback))\n      var(--diffs-gap-inline, var(--diffs-gap-fallback));\n    max-height: 400px;\n    scrollbar-width: none;\n\n    [data-error-message] {\n      font-weight: bold;\n      font-size: 18px;\n      color: var(--diffs-deletion-base);\n    }\n\n    [data-error-stack] {\n      color: var(--diffs-fg-number);\n    }\n  }\n\n  [data-placeholder] {\n    contain: strict;\n  }\n\n  [data-utility-button] {\n    display: flex;\n    align-items: center;\n    justify-content: center;\n    border: none;\n    appearance: none;\n    width: 1lh;\n    height: 1lh;\n    margin-right: calc((1lh - 1ch) * -1);\n    padding: 0;\n    cursor: pointer;\n    font-size: var(--diffs-font-size, 13px);\n    line-height: var(--diffs-line-height, 20px);\n    border-radius: 4px;\n    background-color: var(--diffs-modified-base);\n    color: var(--diffs-bg);\n    fill: currentColor;\n    position: relative;\n    z-index: 4;\n  }\n}\n";

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/cssWrappers.js
var LAYER_ORDER = `@layer base, theme, unsafe;`;
function wrapCoreCSS(mainCSS) {
  return `${LAYER_ORDER}
${style_default}
@layer theme {
  ${mainCSS}
}`;
}
function wrapUnsafeCSS(unsafeCSS) {
  return `${LAYER_ORDER}
@layer unsafe {
  ${unsafeCSS}
}`;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/getOrCreateCodeNode.js
function getOrCreateCodeNode({ code, pre, columnType, rowSpan, containerSize = false } = {}) {
  if (code == null) {
    code = document.createElement("code");
    code.setAttribute("data-code", "");
    if (columnType != null) code.setAttribute(`data-${columnType}`, "");
    pre?.appendChild(code);
  }
  if (rowSpan != null) code.style.setProperty("grid-row", `span ${rowSpan}`);
  else code.style.removeProperty("grid-row");
  if (containerSize) code.setAttribute("data-container-size", "");
  else code.removeAttribute("data-container-size");
  return code;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/prerenderHTMLIfNecessary.js
function prerenderHTMLIfNecessary(element, html) {
  if (html == null) return;
  const shadowRoot = element.shadowRoot ?? element.attachShadow({ mode: "open" });
  if (shadowRoot.innerHTML === "") shadowRoot.innerHTML = html;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/setWrapperNodeProps.js
function setPreNodeProperties(pre, { type, diffIndicators, disableBackground, disableLineNumbers, overflow, split, themeStyles, themeType, totalLines }) {
  if (type === "diff") {
    pre.setAttribute("data-diff", "");
    pre.removeAttribute("data-file");
  } else {
    pre.setAttribute("data-file", "");
    pre.removeAttribute("data-diff");
  }
  if (themeType === "system") pre.removeAttribute("data-theme-type");
  else pre.setAttribute("data-theme-type", themeType);
  switch (diffIndicators) {
    case "bars":
    case "classic":
      pre.setAttribute("data-indicators", diffIndicators);
      break;
    case "none":
      pre.removeAttribute("data-indicators");
      break;
  }
  if (disableLineNumbers) pre.setAttribute("data-disable-line-numbers", "");
  else pre.removeAttribute("data-disable-line-numbers");
  if (disableBackground) pre.removeAttribute("data-background");
  else pre.setAttribute("data-background", "");
  if (type === "diff") pre.setAttribute("data-diff-type", split ? "split" : "single");
  else pre.removeAttribute("data-diff-type");
  pre.setAttribute("data-overflow", overflow);
  pre.tabIndex = 0;
  pre.style = themeStyles;
  pre.style.setProperty("--diffs-min-number-column-width-default", `${`${totalLines}`.length}ch`);
  return pre;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/components/web-components.js
if (typeof HTMLElement !== "undefined" && customElements.get(DIFFS_TAG_NAME) == null) {
  let sheet;
  class FileDiffContainer extends HTMLElement {
    constructor() {
      super();
      if (this.shadowRoot != null) return;
      const shadowRoot = this.attachShadow({ mode: "open" });
      if (sheet == null) {
        sheet = new CSSStyleSheet();
        sheet.replaceSync(style_default);
      }
      shadowRoot.adoptedStyleSheets = [sheet];
    }
  }
  customElements.define(DIFFS_TAG_NAME, FileDiffContainer);
}
var DiffsContainerLoaded = true;

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/components/File.js
var EMPTY_STRINGS = [];
var instanceId2 = -1;
var File = class {
  static LoadedCustomComponent = DiffsContainerLoaded;
  __id = `file:${++instanceId2}`;
  fileContainer;
  spriteSVG;
  pre;
  code;
  bufferBefore;
  bufferAfter;
  unsafeCSSStyle;
  gutterUtilityContent;
  errorWrapper;
  placeHolder;
  lastRenderedHeaderHTML;
  appliedPreAttributes;
  lastRowCount;
  headerElement;
  headerPrefix;
  headerMetadata;
  fileRenderer;
  resizeManager;
  interactionManager;
  annotationCache = /* @__PURE__ */ new Map();
  lineAnnotations = [];
  file;
  renderRange;
  constructor(options = { theme: DEFAULT_THEMES }, workerManager, isContainerManaged = false) {
    this.options = options;
    this.workerManager = workerManager;
    this.isContainerManaged = isContainerManaged;
    this.fileRenderer = new FileRenderer(options, this.handleHighlightRender, this.workerManager);
    this.resizeManager = new ResizeManager();
    this.interactionManager = new InteractionManager("file", pluckInteractionOptions(options));
    this.workerManager?.subscribeToThemeChanges(this);
  }
  handleHighlightRender = () => {
    this.rerender();
  };
  rerender() {
    if (this.file == null) return;
    this.render({
      file: this.file,
      forceRender: true,
      renderRange: this.renderRange
    });
  }
  setOptions(options) {
    if (options == null) return;
    this.options = options;
    this.interactionManager.setOptions(pluckInteractionOptions(options));
  }
  mergeOptions(options) {
    this.options = {
      ...this.options,
      ...options
    };
  }
  setThemeType(themeType) {
    if ((this.options.themeType ?? "system") === themeType) return;
    this.mergeOptions({ themeType });
    this.fileRenderer.setThemeType(themeType);
    if (this.headerElement != null) if (themeType === "system") delete this.headerElement.dataset.themeType;
    else this.headerElement.dataset.themeType = themeType;
    if (this.pre != null) switch (themeType) {
      case "system":
        delete this.pre.dataset.themeType;
        break;
      case "light":
      case "dark":
        this.pre.dataset.themeType = themeType;
        break;
    }
  }
  getHoveredLine = () => {
    return this.interactionManager.getHoveredLine();
  };
  setLineAnnotations(lineAnnotations) {
    this.lineAnnotations = lineAnnotations;
  }
  setSelectedLines(range) {
    this.interactionManager.setSelection(range);
  }
  cleanUp() {
    this.fileRenderer.cleanUp();
    this.resizeManager.cleanUp();
    this.interactionManager.cleanUp();
    this.workerManager?.unsubscribeToThemeChanges(this);
    this.workerManager = void 0;
    this.renderRange = void 0;
    this.file = void 0;
    if (!this.isContainerManaged) this.fileContainer?.parentNode?.removeChild(this.fileContainer);
    if (this.fileContainer?.shadowRoot != null) this.fileContainer.shadowRoot.innerHTML = "";
    this.fileContainer = void 0;
    this.pre = void 0;
    this.bufferBefore = void 0;
    this.bufferAfter = void 0;
    this.appliedPreAttributes = void 0;
    this.lastRowCount = void 0;
    this.headerElement = void 0;
    this.headerPrefix = void 0;
    this.headerMetadata = void 0;
    this.lastRenderedHeaderHTML = void 0;
    this.errorWrapper = void 0;
    this.unsafeCSSStyle = void 0;
    this.placeHolder = void 0;
  }
  hydrate(props) {
    const { fileContainer, prerenderedHTML } = props;
    prerenderHTMLIfNecessary(fileContainer, prerenderedHTML);
    for (const element of Array.from(fileContainer.shadowRoot?.children ?? [])) {
      if (element instanceof SVGElement) {
        this.spriteSVG = element;
        continue;
      }
      if (!(element instanceof HTMLElement)) continue;
      if (element instanceof HTMLPreElement) {
        this.pre = element;
        this.appliedPreAttributes = void 0;
        continue;
      }
      if (element instanceof HTMLStyleElement && element.hasAttribute(UNSAFE_CSS_ATTRIBUTE)) {
        this.unsafeCSSStyle = element;
        continue;
      }
      if ("diffsHeader" in element.dataset) {
        this.headerElement = element;
        this.lastRenderedHeaderHTML = void 0;
        continue;
      }
    }
    if (this.pre == null) this.render(props);
    else {
      const { file, lineAnnotations } = props;
      const { overflow = "scroll" } = this.options;
      this.fileContainer = fileContainer;
      delete this.pre.dataset.dehydrated;
      this.lineAnnotations = lineAnnotations ?? this.lineAnnotations;
      this.file = file;
      this.fileRenderer.hydrate(file);
      this.renderAnnotations();
      this.renderGutterUtility();
      this.injectUnsafeCSS();
      this.interactionManager.setup(this.pre);
      this.resizeManager.setup(this.pre, overflow === "wrap");
    }
  }
  getOrCreateLineCache(file = this.file) {
    return file != null ? this.fileRenderer.getOrCreateLineCache(file) : EMPTY_STRINGS;
  }
  render({ file, fileContainer, forceRender = false, containerWrapper, lineAnnotations, renderRange }) {
    const { collapsed = false } = this.options;
    const nextRenderRange = collapsed ? void 0 : renderRange;
    const previousRenderRange = this.renderRange;
    const annotationsChanged = lineAnnotations != null && (lineAnnotations.length > 0 || this.lineAnnotations.length > 0) ? lineAnnotations !== this.lineAnnotations : false;
    const didFileChange = !areFilesEqual(this.file, file);
    if (!collapsed && !forceRender && areRenderRangesEqual(nextRenderRange, this.renderRange) && !didFileChange && !annotationsChanged) return false;
    this.renderRange = nextRenderRange;
    this.file = file;
    this.fileRenderer.setOptions(this.options);
    if (lineAnnotations != null) this.setLineAnnotations(lineAnnotations);
    this.fileRenderer.setLineAnnotations(this.lineAnnotations);
    const { disableErrorHandling = false, disableFileHeader = false, overflow = "scroll" } = this.options;
    if (disableFileHeader) {
      if (this.headerElement != null) {
        this.headerElement.parentNode?.removeChild(this.headerElement);
        this.headerElement = void 0;
        this.lastRenderedHeaderHTML = void 0;
      }
      if (this.headerPrefix != null) {
        this.headerPrefix.parentNode?.removeChild(this.headerPrefix);
        this.headerPrefix = void 0;
      }
      if (this.headerMetadata != null) {
        this.headerMetadata.parentNode?.removeChild(this.headerMetadata);
        this.headerMetadata = void 0;
      }
    }
    fileContainer = this.getOrCreateFileContainerNode(fileContainer, containerWrapper);
    if (collapsed) {
      this.removeRenderedCode();
      this.clearAuxiliaryNodes();
      try {
        const fileResult = this.fileRenderer.renderFile(file, EMPTY_RENDER_RANGE);
        if (fileResult?.headerAST != null) this.applyHeaderToDOM(fileResult.headerAST, fileContainer);
        this.injectUnsafeCSS();
      } catch (error) {
        if (disableErrorHandling) throw error;
        console.error(error);
        if (error instanceof Error) this.applyErrorToDOM(error, fileContainer);
      }
      return true;
    }
    try {
      const pre = this.getOrCreatePreNode(fileContainer);
      if (!this.canPartiallyRender(forceRender, annotationsChanged, didFileChange) || !this.applyPartialRender(previousRenderRange, nextRenderRange)) {
        const fileResult = this.fileRenderer.renderFile(file, nextRenderRange);
        if (fileResult == null) {
          if (this.workerManager?.isInitialized() === false) this.workerManager.initialize().then(() => this.rerender());
          return false;
        }
        if (fileResult.headerAST != null) this.applyHeaderToDOM(fileResult.headerAST, fileContainer);
        this.applyFullRender(fileResult, pre);
      }
      this.applyBuffers(pre, nextRenderRange);
      this.injectUnsafeCSS();
      this.interactionManager.setup(pre);
      this.resizeManager.setup(pre, overflow === "wrap");
      this.renderAnnotations();
      this.renderGutterUtility();
    } catch (error) {
      if (disableErrorHandling) throw error;
      console.error(error);
      if (error instanceof Error) this.applyErrorToDOM(error, fileContainer);
    }
    return true;
  }
  removeRenderedCode() {
    this.resizeManager.cleanUp();
    this.interactionManager.cleanUp();
    this.bufferBefore?.remove();
    this.bufferBefore = void 0;
    this.bufferAfter?.remove();
    this.bufferAfter = void 0;
    this.code?.remove();
    this.code = void 0;
    this.pre?.remove();
    this.pre = void 0;
    this.appliedPreAttributes = void 0;
    this.lastRowCount = void 0;
  }
  clearAuxiliaryNodes() {
    for (const { element } of this.annotationCache.values()) element.parentNode?.removeChild(element);
    this.annotationCache.clear();
    this.gutterUtilityContent?.remove();
    this.gutterUtilityContent = void 0;
  }
  canPartiallyRender(forceRender, annotationsChanged, didContentChange) {
    if (forceRender || annotationsChanged || didContentChange) return false;
    return true;
  }
  renderPlaceholder(height) {
    if (this.fileContainer == null) return false;
    this.cleanChildNodes();
    if (this.placeHolder == null) {
      const shadowRoot = this.fileContainer.shadowRoot ?? this.fileContainer.attachShadow({ mode: "open" });
      this.placeHolder = document.createElement("div");
      this.placeHolder.dataset.placeholder = "";
      shadowRoot.appendChild(this.placeHolder);
    }
    this.placeHolder.style.setProperty("height", `${height}px`);
    return true;
  }
  cleanChildNodes() {
    this.resizeManager.cleanUp();
    this.interactionManager.cleanUp();
    this.bufferAfter?.remove();
    this.bufferBefore?.remove();
    this.code?.remove();
    this.errorWrapper?.remove();
    this.headerElement?.remove();
    this.gutterUtilityContent?.remove();
    this.headerPrefix?.remove();
    this.headerMetadata?.remove();
    this.pre?.remove();
    this.spriteSVG?.remove();
    this.unsafeCSSStyle?.remove();
    this.bufferAfter = void 0;
    this.bufferBefore = void 0;
    this.code = void 0;
    this.errorWrapper = void 0;
    this.headerElement = void 0;
    this.gutterUtilityContent = void 0;
    this.headerPrefix = void 0;
    this.headerMetadata = void 0;
    this.pre = void 0;
    this.spriteSVG = void 0;
    this.unsafeCSSStyle = void 0;
    this.lastRenderedHeaderHTML = void 0;
    this.lastRowCount = void 0;
  }
  renderAnnotations() {
    if (this.isContainerManaged || this.fileContainer == null) {
      for (const { element } of this.annotationCache.values()) element.parentNode?.removeChild(element);
      this.annotationCache.clear();
      return;
    }
    const staleAnnotations = new Map(this.annotationCache);
    const { renderAnnotation } = this.options;
    if (renderAnnotation != null && this.lineAnnotations.length > 0) for (const [index, annotation] of this.lineAnnotations.entries()) {
      const id = `${index}-${getLineAnnotationName(annotation)}`;
      let cache = this.annotationCache.get(id);
      if (cache == null || !areLineAnnotationsEqual(annotation, cache.annotation)) {
        cache?.element.parentElement?.removeChild(cache.element);
        const content = renderAnnotation(annotation);
        if (content == null) continue;
        cache = {
          element: createAnnotationWrapperNode(getLineAnnotationName(annotation)),
          annotation
        };
        cache.element.appendChild(content);
        this.fileContainer.appendChild(cache.element);
        this.annotationCache.set(id, cache);
      }
      staleAnnotations.delete(id);
    }
    for (const [id, { element }] of staleAnnotations.entries()) {
      this.annotationCache.delete(id);
      element.parentNode?.removeChild(element);
    }
  }
  renderGutterUtility() {
    const renderGutterUtility = this.options.renderGutterUtility ?? this.options.renderHoverUtility;
    if (this.fileContainer == null || renderGutterUtility == null) {
      this.gutterUtilityContent?.remove();
      this.gutterUtilityContent = void 0;
      return;
    }
    const element = renderGutterUtility(this.interactionManager.getHoveredLine);
    if (element != null && this.gutterUtilityContent != null) return;
    else if (element == null) {
      this.gutterUtilityContent?.parentNode?.removeChild(this.gutterUtilityContent);
      this.gutterUtilityContent = void 0;
      return;
    }
    const gutterUtilityContent = createGutterUtilityContentNode();
    gutterUtilityContent.appendChild(element);
    this.fileContainer.appendChild(gutterUtilityContent);
    this.gutterUtilityContent = gutterUtilityContent;
  }
  injectUnsafeCSS() {
    if (this.fileContainer?.shadowRoot == null) return;
    const { unsafeCSS } = this.options;
    if (unsafeCSS == null || unsafeCSS === "") {
      if (this.unsafeCSSStyle != null) {
        this.unsafeCSSStyle.parentNode?.removeChild(this.unsafeCSSStyle);
        this.unsafeCSSStyle = void 0;
      }
      return;
    }
    if (this.unsafeCSSStyle == null) {
      this.unsafeCSSStyle = createUnsafeCSSStyleNode();
      this.fileContainer.shadowRoot.appendChild(this.unsafeCSSStyle);
    }
    this.unsafeCSSStyle.innerText = wrapUnsafeCSS(unsafeCSS);
  }
  applyFullRender(result, pre) {
    this.cleanupErrorWrapper();
    this.applyPreNodeAttributes(pre, result);
    this.code = getOrCreateCodeNode({ code: this.code });
    this.code.innerHTML = this.fileRenderer.renderPartialHTML(this.fileRenderer.renderCodeAST(result));
    pre.replaceChildren(this.code);
    this.lastRowCount = result.rowCount;
  }
  applyPartialRender(previousRenderRange, renderRange) {
    if (previousRenderRange == null || renderRange == null) return false;
    const { file, code } = this;
    const columns = code != null ? this.getColumns(code) : void 0;
    if (file == null || code == null || columns == null) return false;
    const previousStart = previousRenderRange.startingLine;
    const nextStart = renderRange.startingLine;
    const previousEnd = previousRenderRange.totalLines === Infinity ? Number.POSITIVE_INFINITY : previousStart + previousRenderRange.totalLines;
    const nextEnd = renderRange.totalLines === Infinity ? Number.POSITIVE_INFINITY : nextStart + renderRange.totalLines;
    const overlapStart = Math.max(previousStart, nextStart);
    const overlapEnd = Math.min(previousEnd, nextEnd);
    if (overlapEnd <= overlapStart) return false;
    if (!this.trimDOMToOverlap(columns.gutter, overlapStart, overlapEnd) || !this.trimDOMToOverlap(columns.content, overlapStart, overlapEnd)) return false;
    let { length: rowCount } = columns.content.children;
    const renderChunk = (startingLine, totalLines) => {
      if (totalLines <= 0) return;
      return this.fileRenderer.renderFile(file, {
        startingLine,
        totalLines,
        bufferBefore: 0,
        bufferAfter: 0
      });
    };
    const prependResult = nextStart < overlapStart ? renderChunk(nextStart, overlapStart - nextStart) : void 0;
    if (prependResult === void 0 && nextStart < overlapStart) return false;
    const appendTotalLines = nextEnd === Number.POSITIVE_INFINITY ? Number.POSITIVE_INFINITY : Math.max(0, nextEnd - overlapEnd);
    const appendResult = nextEnd > overlapEnd ? renderChunk(overlapEnd, appendTotalLines) : void 0;
    if (appendResult === void 0 && nextEnd > overlapEnd) return false;
    this.cleanupErrorWrapper();
    if (prependResult != null) {
      columns.gutter.insertAdjacentHTML("afterbegin", this.fileRenderer.renderPartialHTML(prependResult.gutterAST));
      columns.content.insertAdjacentHTML("afterbegin", this.fileRenderer.renderPartialHTML(prependResult.contentAST));
      rowCount += prependResult.rowCount;
    }
    if (appendResult != null) {
      columns.gutter.insertAdjacentHTML("beforeend", this.fileRenderer.renderPartialHTML(appendResult.gutterAST));
      columns.content.insertAdjacentHTML("beforeend", this.fileRenderer.renderPartialHTML(appendResult.contentAST));
      rowCount += appendResult.rowCount;
    }
    if (this.lastRowCount !== rowCount) {
      columns.gutter.style.setProperty("grid-row", `span ${rowCount}`);
      columns.content.style.setProperty("grid-row", `span ${rowCount}`);
      this.lastRowCount = rowCount;
    }
    return true;
  }
  getColumns(code) {
    const gutter = code.children[0];
    const content = code.children[1];
    if (!(gutter instanceof HTMLElement) || !(content instanceof HTMLElement) || gutter.dataset.gutter == null || content.dataset.content == null) return;
    return {
      gutter,
      content
    };
  }
  trimDOMToOverlap(container, overlapStart, overlapEnd) {
    const boundaryIndices = this.getDOMBoundaryIndices(container, [overlapStart, overlapEnd]);
    const startIndex = boundaryIndices.get(overlapStart) ?? container.children.length;
    const endIndex = boundaryIndices.get(overlapEnd) ?? container.children.length;
    if (startIndex > endIndex) return false;
    for (let i = container.children.length - 1; i >= endIndex; i -= 1) container.children[i]?.remove();
    for (let i = startIndex - 1; i >= 0; i -= 1) container.children[i]?.remove();
    return true;
  }
  getDOMBoundaryIndices(container, boundaries) {
    const sortedBoundaries = [...new Set(boundaries)].sort((a, b) => a - b);
    const boundaryIndices = /* @__PURE__ */ new Map();
    if (sortedBoundaries.length === 0) return boundaryIndices;
    let boundaryIndex = 0;
    let nextBoundary = sortedBoundaries[boundaryIndex];
    const { children } = container;
    for (let i = 0; i < children.length; i += 1) {
      const child = children[i];
      if (!(child instanceof HTMLElement)) continue;
      const lineIndex = this.getLineIndexFromDOMNode(child);
      if (lineIndex == null) continue;
      while (nextBoundary != null && lineIndex >= nextBoundary) {
        boundaryIndices.set(nextBoundary, i);
        boundaryIndex += 1;
        nextBoundary = sortedBoundaries[boundaryIndex];
      }
      if (boundaryIndex >= sortedBoundaries.length) break;
    }
    for (const boundary of sortedBoundaries) if (!boundaryIndices.has(boundary)) boundaryIndices.set(boundary, children.length);
    return boundaryIndices;
  }
  getLineIndexFromDOMNode(node) {
    const lineIndexAttr = node.dataset.lineIndex;
    if (lineIndexAttr == null) return;
    const parsed = Number(lineIndexAttr);
    return Number.isNaN(parsed) ? void 0 : parsed;
  }
  applyBuffers(pre, renderRange) {
    const { disableVirtualizationBuffers = false } = this.options;
    if (disableVirtualizationBuffers || renderRange == null) {
      if (this.bufferBefore != null) {
        this.bufferBefore.parentNode?.removeChild(this.bufferBefore);
        this.bufferBefore = void 0;
      }
      if (this.bufferAfter != null) {
        this.bufferAfter.parentNode?.removeChild(this.bufferAfter);
        this.bufferAfter = void 0;
      }
      return;
    }
    if (renderRange.bufferBefore > 0) {
      if (this.bufferBefore == null) {
        this.bufferBefore = document.createElement("div");
        this.bufferBefore.dataset.virtualizerBuffer = "before";
        pre.before(this.bufferBefore);
      }
      this.bufferBefore.style.setProperty("height", `${renderRange.bufferBefore}px`);
      this.bufferBefore.style.setProperty("contain", "strict");
    } else if (this.bufferBefore != null) {
      this.bufferBefore.parentNode?.removeChild(this.bufferBefore);
      this.bufferBefore = void 0;
    }
    if (renderRange.bufferAfter > 0) {
      if (this.bufferAfter == null) {
        this.bufferAfter = document.createElement("div");
        this.bufferAfter.dataset.virtualizerBuffer = "after";
        pre.after(this.bufferAfter);
      }
      this.bufferAfter.style.setProperty("height", `${renderRange.bufferAfter}px`);
      this.bufferAfter.style.setProperty("contain", "strict");
    } else if (this.bufferAfter != null) {
      this.bufferAfter.parentNode?.removeChild(this.bufferAfter);
      this.bufferAfter = void 0;
    }
  }
  applyHeaderToDOM(headerAST, container) {
    const { file } = this;
    if (file == null) return;
    this.cleanupErrorWrapper();
    this.placeHolder?.remove();
    this.placeHolder = void 0;
    const headerHTML = toHtml(headerAST);
    if (headerHTML !== this.lastRenderedHeaderHTML) {
      const tempDiv = document.createElement("div");
      tempDiv.innerHTML = headerHTML;
      const newHeader = tempDiv.firstElementChild;
      if (!(newHeader instanceof HTMLElement)) return;
      if (this.headerElement != null) container.shadowRoot?.replaceChild(newHeader, this.headerElement);
      else container.shadowRoot?.prepend(newHeader);
      this.headerElement = newHeader;
      this.lastRenderedHeaderHTML = headerHTML;
    }
    if (this.isContainerManaged) return;
    const { renderHeaderPrefix, renderCustomMetadata } = this.options;
    if (this.headerPrefix != null) this.headerPrefix.parentNode?.removeChild(this.headerPrefix);
    if (this.headerMetadata != null) this.headerMetadata.parentNode?.removeChild(this.headerMetadata);
    const prefix = renderHeaderPrefix?.(file) ?? void 0;
    const content = renderCustomMetadata?.(file) ?? void 0;
    if (prefix != null) {
      this.headerPrefix = document.createElement("div");
      this.headerPrefix.slot = HEADER_PREFIX_SLOT_ID;
      if (prefix instanceof Element) this.headerPrefix.appendChild(prefix);
      else this.headerPrefix.innerText = `${prefix}`;
      container.appendChild(this.headerPrefix);
    }
    if (content != null) {
      this.headerMetadata = document.createElement("div");
      this.headerMetadata.slot = HEADER_METADATA_SLOT_ID;
      if (content instanceof Element) this.headerMetadata.appendChild(content);
      else this.headerMetadata.innerText = `${content}`;
      container.appendChild(this.headerMetadata);
    }
  }
  getOrCreateFileContainerNode(fileContainer, parentNode) {
    const previousContainer = this.fileContainer;
    this.fileContainer = fileContainer ?? this.fileContainer ?? document.createElement(DIFFS_TAG_NAME);
    if (previousContainer != null && previousContainer !== this.fileContainer) {
      this.lastRenderedHeaderHTML = void 0;
      this.headerElement = void 0;
    }
    if (parentNode != null && this.fileContainer.parentNode !== parentNode) parentNode.appendChild(this.fileContainer);
    if (this.spriteSVG == null) {
      const fragment = document.createElement("div");
      fragment.innerHTML = SVGSpriteSheet;
      const firstChild = fragment.firstChild;
      if (firstChild instanceof SVGElement) {
        this.spriteSVG = firstChild;
        this.fileContainer.shadowRoot?.appendChild(this.spriteSVG);
      }
    }
    return this.fileContainer;
  }
  getOrCreatePreNode(container) {
    const shadowRoot = container.shadowRoot ?? container.attachShadow({ mode: "open" });
    if (this.pre == null) {
      this.pre = document.createElement("pre");
      this.appliedPreAttributes = void 0;
      this.code = void 0;
      shadowRoot.appendChild(this.pre);
    } else if (this.pre.parentNode !== shadowRoot) {
      container.shadowRoot?.appendChild(this.pre);
      this.appliedPreAttributes = void 0;
    }
    this.placeHolder?.remove();
    this.placeHolder = void 0;
    return this.pre;
  }
  applyPreNodeAttributes(pre, { totalLines, themeStyles, baseThemeType }) {
    const { overflow = "scroll", themeType = "system", disableLineNumbers = false } = this.options;
    const preProperties = {
      type: "file",
      split: false,
      themeStyles,
      overflow,
      disableLineNumbers,
      themeType: baseThemeType ?? themeType,
      diffIndicators: "none",
      disableBackground: true,
      totalLines
    };
    if (arePrePropertiesEqual(preProperties, this.appliedPreAttributes)) return;
    setPreNodeProperties(pre, preProperties);
    this.appliedPreAttributes = preProperties;
  }
  applyErrorToDOM(error, container) {
    this.cleanupErrorWrapper();
    const pre = this.getOrCreatePreNode(container);
    pre.innerHTML = "";
    pre.parentNode?.removeChild(pre);
    this.pre = void 0;
    this.appliedPreAttributes = void 0;
    const shadowRoot = container.shadowRoot ?? container.attachShadow({ mode: "open" });
    this.errorWrapper ??= document.createElement("div");
    this.errorWrapper.dataset.errorWrapper = "";
    this.errorWrapper.innerHTML = "";
    shadowRoot.appendChild(this.errorWrapper);
    const errorMessage = document.createElement("div");
    errorMessage.dataset.errorMessage = "";
    errorMessage.innerText = error.message;
    this.errorWrapper.appendChild(errorMessage);
    const errorStack = document.createElement("pre");
    errorStack.dataset.errorStack = "";
    errorStack.innerText = error.stack ?? "No Error Stack";
    this.errorWrapper.appendChild(errorStack);
  }
  cleanupErrorWrapper() {
    this.errorWrapper?.parentNode?.removeChild(this.errorWrapper);
    this.errorWrapper = void 0;
  }
};

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/managers/ScrollSyncManager.js
var ScrollSyncManager = class {
  isDeletionsScrolling = false;
  isAdditionsScrolling = false;
  timeoutId = -1;
  codeDeletions;
  codeAdditions;
  enabled = false;
  cleanUp() {
    if (!this.enabled) return;
    this.codeDeletions?.removeEventListener("scroll", this.handleDeletionsScroll);
    this.codeAdditions?.removeEventListener("scroll", this.handleAdditionsScroll);
    clearTimeout(this.timeoutId);
    this.codeDeletions = void 0;
    this.codeAdditions = void 0;
    this.enabled = false;
  }
  setup(pre, codeDeletions, codeAdditions) {
    if (codeDeletions == null || codeAdditions == null) for (const element of pre.children ?? []) {
      if (!(element instanceof HTMLElement)) continue;
      if ("deletions" in element.dataset) codeDeletions = element;
      else if ("additions" in element.dataset) codeAdditions = element;
    }
    if (codeAdditions == null || codeDeletions == null) {
      this.cleanUp();
      return;
    }
    if (this.codeDeletions !== codeDeletions) {
      this.codeDeletions?.removeEventListener("scroll", this.handleDeletionsScroll);
      this.codeDeletions = codeDeletions;
      codeDeletions.addEventListener("scroll", this.handleDeletionsScroll, { passive: true });
    }
    if (this.codeAdditions !== codeAdditions) {
      this.codeAdditions?.removeEventListener("scroll", this.handleAdditionsScroll);
      this.codeAdditions = codeAdditions;
      codeAdditions.addEventListener("scroll", this.handleAdditionsScroll, { passive: true });
    }
    this.enabled = true;
  }
  handleDeletionsScroll = () => {
    if (this.isAdditionsScrolling) return;
    this.isDeletionsScrolling = true;
    clearTimeout(this.timeoutId);
    this.timeoutId = setTimeout(() => {
      this.isDeletionsScrolling = false;
    }, 300);
    this.codeAdditions?.scrollTo({ left: this.codeDeletions?.scrollLeft });
  };
  handleAdditionsScroll = () => {
    if (this.isDeletionsScrolling) return;
    this.isAdditionsScrolling = true;
    clearTimeout(this.timeoutId);
    this.timeoutId = setTimeout(() => {
      this.isAdditionsScrolling = false;
    }, 300);
    this.codeDeletions?.scrollTo({ left: this.codeAdditions?.scrollLeft });
  };
};

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/createEmptyRowBuffer.js
function createEmptyRowBuffer(size) {
  return createHastElement({
    tagName: "div",
    properties: {
      "data-content-buffer": "",
      "data-buffer-size": size,
      style: `grid-row: span ${size};min-height:calc(${size} * 1lh)`
    }
  });
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/createNoNewlineElement.js
function createNoNewlineElement(type) {
  return createHastElement({
    tagName: "div",
    children: [createHastElement({
      tagName: "span",
      children: [createTextNodeElement("No newline at end of file")]
    })],
    properties: {
      "data-no-newline": "",
      "data-line-type": type,
      "data-column-content": ""
    }
  });
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/createSeparator.js
function createExpandButton(type) {
  return createHastElement({
    tagName: "div",
    children: [createIconElement({
      name: type === "both" ? "diffs-icon-expand-all" : "diffs-icon-expand",
      properties: { "data-icon": "" }
    })],
    properties: {
      "data-expand-button": "",
      "data-expand-both": type === "both" ? "" : void 0,
      "data-expand-up": type === "up" ? "" : void 0,
      "data-expand-down": type === "down" ? "" : void 0
    }
  });
}
function createSeparator({ type, content, expandIndex, chunked = false, slotName, isFirstHunk, isLastHunk }) {
  const children = [];
  if (type === "metadata" && content != null) children.push(createHastElement({
    tagName: "div",
    children: [createTextNodeElement(content)],
    properties: { "data-separator-wrapper": "" }
  }));
  if ((type === "line-info" || type === "line-info-basic") && content != null) {
    const contentChildren = [];
    if (expandIndex != null) if (!chunked) contentChildren.push(createExpandButton(!isFirstHunk && !isLastHunk ? "both" : isFirstHunk ? "down" : "up"));
    else {
      if (!isFirstHunk) contentChildren.push(createExpandButton("up"));
      if (!isLastHunk) contentChildren.push(createExpandButton("down"));
    }
    contentChildren.push(createHastElement({
      tagName: "div",
      children: [createHastElement({
        tagName: "span",
        children: [createTextNodeElement(content)],
        properties: { "data-unmodified-lines": "" }
      })],
      properties: { "data-separator-content": "" }
    }));
    children.push(createHastElement({
      tagName: "div",
      children: contentChildren,
      properties: {
        "data-separator-wrapper": "",
        "data-separator-multi-button": contentChildren.length > 2 ? "" : void 0
      }
    }));
  }
  if (type === "custom" && slotName != null) children.push(createHastElement({
    tagName: "slot",
    properties: { name: slotName }
  }));
  return createHastElement({
    tagName: "div",
    children,
    properties: {
      "data-separator": children.length === 0 ? "simple" : type,
      "data-expand-index": expandIndex,
      "data-separator-first": isFirstHunk ? "" : void 0,
      "data-separator-last": isLastHunk ? "" : void 0
    }
  });
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/getHunkSeparatorSlotName.js
function getHunkSeparatorSlotName(type, hunkIndex) {
  return `hunk-separator-${type}-${hunkIndex}`;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/getTotalLineCountFromHunks.js
function getTotalLineCountFromHunks(hunks) {
  const lastHunk = hunks.at(-1);
  if (lastHunk == null) return 0;
  return Math.max(lastHunk.additionStart + lastHunk.additionCount, lastHunk.deletionStart + lastHunk.deletionCount);
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/isDefaultRenderRange.js
function isDefaultRenderRange(renderRange) {
  return renderRange.startingLine === 0 && renderRange.totalLines === Infinity && renderRange.bufferBefore === 0 && renderRange.bufferAfter === 0;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/renderers/DiffHunksRenderer.js
var instanceId3 = -1;
var DiffHunksRenderer = class {
  __id = `diff-hunks-renderer:${++instanceId3}`;
  highlighter;
  diff;
  expandedHunks = /* @__PURE__ */ new Map();
  deletionAnnotations = {};
  additionAnnotations = {};
  computedLang = "text";
  renderCache;
  constructor(options = { theme: DEFAULT_THEMES }, onRenderUpdate, workerManager) {
    this.options = options;
    this.onRenderUpdate = onRenderUpdate;
    this.workerManager = workerManager;
    if (workerManager?.isWorkingPool() !== true) this.highlighter = areThemesAttached(options.theme ?? DEFAULT_THEMES) ? getHighlighterIfLoaded() : void 0;
  }
  cleanUp() {
    this.highlighter = void 0;
    this.diff = void 0;
    this.renderCache = void 0;
    this.workerManager?.cleanUpPendingTasks(this);
    this.workerManager = void 0;
    this.onRenderUpdate = void 0;
  }
  recycle() {
    this.highlighter = void 0;
    this.diff = void 0;
    this.renderCache = void 0;
    this.workerManager?.cleanUpPendingTasks(this);
  }
  setOptions(options) {
    this.options = options;
  }
  mergeOptions(options) {
    this.options = {
      ...this.options,
      ...options
    };
  }
  setThemeType(themeType) {
    if (this.getOptionsWithDefaults().themeType === themeType) return;
    this.mergeOptions({ themeType });
  }
  expandHunk(index, direction) {
    const { expansionLineCount } = this.getOptionsWithDefaults();
    const region = { ...this.expandedHunks.get(index) ?? {
      fromStart: 0,
      fromEnd: 0
    } };
    if (direction === "up" || direction === "both") region.fromStart += expansionLineCount;
    if (direction === "down" || direction === "both") region.fromEnd += expansionLineCount;
    if (this.renderCache?.highlighted !== true) this.renderCache = void 0;
    this.expandedHunks.set(index, region);
  }
  expandHunkFully(index) {
    if (this.renderCache?.highlighted !== true) this.renderCache = void 0;
    this.expandedHunks.set(index, {
      fromStart: Number.POSITIVE_INFINITY,
      fromEnd: Number.POSITIVE_INFINITY
    });
  }
  getExpandedHunk(hunkIndex) {
    return this.expandedHunks.get(hunkIndex) ?? DEFAULT_EXPANDED_REGION;
  }
  getExpandedHunksMap() {
    return this.expandedHunks;
  }
  setLineAnnotations(lineAnnotations) {
    this.additionAnnotations = {};
    this.deletionAnnotations = {};
    for (const annotation of lineAnnotations) {
      const map = (() => {
        switch (annotation.side) {
          case "deletions":
            return this.deletionAnnotations;
          case "additions":
            return this.additionAnnotations;
        }
      })();
      const arr = map[annotation.lineNumber] ?? [];
      map[annotation.lineNumber] = arr;
      arr.push(annotation);
    }
  }
  getOptionsWithDefaults() {
    const { diffIndicators = "bars", diffStyle = "split", disableBackground = false, disableFileHeader = false, disableLineNumbers = false, disableVirtualizationBuffers = false, collapsed = false, expandUnchanged = false, collapsedContextThreshold = DEFAULT_COLLAPSED_CONTEXT_THRESHOLD, expansionLineCount = 100, hunkSeparators = "line-info", lineDiffType = "word-alt", maxLineDiffLength = 1e3, overflow = "scroll", theme = DEFAULT_THEMES, themeType = "system", tokenizeMaxLineLength = 1e3, useCSSClasses = false } = this.options;
    return {
      diffIndicators,
      diffStyle,
      disableBackground,
      disableFileHeader,
      disableLineNumbers,
      disableVirtualizationBuffers,
      collapsed,
      expandUnchanged,
      collapsedContextThreshold,
      expansionLineCount,
      hunkSeparators,
      lineDiffType,
      maxLineDiffLength,
      overflow,
      theme: this.workerManager?.getDiffRenderOptions().theme ?? theme,
      themeType,
      tokenizeMaxLineLength,
      useCSSClasses
    };
  }
  async initializeHighlighter() {
    this.highlighter = await getSharedHighlighter(getHighlighterOptions(this.computedLang, this.options));
    return this.highlighter;
  }
  hydrate(diff) {
    if (diff == null) return;
    this.diff = diff;
    const { options } = this.getRenderOptions(diff);
    let cache = this.workerManager?.getDiffResultCache(diff);
    if (cache != null && !areRenderOptionsEqual2(options, cache.options)) cache = void 0;
    this.renderCache ??= {
      diff,
      highlighted: true,
      options,
      result: cache?.result,
      renderRange: void 0
    };
    if (this.workerManager?.isWorkingPool() === true && this.renderCache.result == null) this.workerManager.highlightDiffAST(this, this.diff);
    else this.asyncHighlight(diff).then(({ result, options: options$1 }) => {
      this.onHighlightSuccess(diff, result, options$1);
    });
  }
  getRenderOptions(diff) {
    const options = (() => {
      if (this.workerManager?.isWorkingPool() === true) return this.workerManager.getDiffRenderOptions();
      const { theme, tokenizeMaxLineLength, lineDiffType } = this.getOptionsWithDefaults();
      return {
        theme,
        tokenizeMaxLineLength,
        lineDiffType
      };
    })();
    this.getOptionsWithDefaults();
    const { renderCache } = this;
    if (renderCache?.result == null) return {
      options,
      forceRender: true
    };
    if (diff !== renderCache.diff || !areRenderOptionsEqual2(options, renderCache.options)) return {
      options,
      forceRender: true
    };
    return {
      options,
      forceRender: false
    };
  }
  renderDiff(diff = this.renderCache?.diff, renderRange = DEFAULT_RENDER_RANGE) {
    if (diff == null) return;
    const { expandUnchanged = false, collapsedContextThreshold } = this.getOptionsWithDefaults();
    const cache = this.workerManager?.getDiffResultCache(diff);
    if (cache != null && this.renderCache == null) this.renderCache = {
      diff,
      highlighted: true,
      renderRange: void 0,
      ...cache
    };
    const { options, forceRender } = this.getRenderOptions(diff);
    this.renderCache ??= {
      diff,
      highlighted: false,
      options,
      result: void 0,
      renderRange: void 0
    };
    if (this.workerManager?.isWorkingPool() === true) {
      if (this.renderCache.result == null || !this.renderCache.highlighted && !areRenderRangesEqual(this.renderCache.renderRange, renderRange)) {
        this.renderCache.result = this.workerManager.getPlainDiffAST(diff, renderRange.startingLine, renderRange.totalLines, isDefaultRenderRange(renderRange) ? true : expandUnchanged ? true : this.expandedHunks, collapsedContextThreshold);
        this.renderCache.renderRange = renderRange;
      }
      if (renderRange.totalLines > 0 && (!this.renderCache.highlighted || forceRender)) this.workerManager.highlightDiffAST(this, diff);
    } else {
      this.computedLang = diff.lang ?? getFiletypeFromFileName(diff.name);
      const hasThemes = this.highlighter != null && areThemesAttached(options.theme);
      const hasLangs = this.highlighter != null && areLanguagesAttached(this.computedLang);
      if (this.highlighter != null && hasThemes && (forceRender || !this.renderCache.highlighted && hasLangs || this.renderCache.result == null)) {
        const { result, options: options$1 } = this.renderDiffWithHighlighter(diff, this.highlighter, !hasLangs);
        this.renderCache = {
          diff,
          options: options$1,
          highlighted: hasLangs,
          result,
          renderRange: void 0
        };
      }
      if (!hasThemes || !hasLangs) this.asyncHighlight(diff).then(({ result, options: options$1 }) => {
        this.onHighlightSuccess(diff, result, options$1);
      });
    }
    return this.renderCache.result != null ? this.processDiffResult(this.renderCache.diff, renderRange, this.renderCache.result) : void 0;
  }
  async asyncRender(diff, renderRange = DEFAULT_RENDER_RANGE) {
    const { result } = await this.asyncHighlight(diff);
    return this.processDiffResult(diff, renderRange, result);
  }
  createPreElement(split, totalLines, themeStyles, baseThemeType) {
    const { diffIndicators, disableBackground, disableLineNumbers, overflow, themeType } = this.getOptionsWithDefaults();
    return createPreElement({
      type: "diff",
      diffIndicators,
      disableBackground,
      disableLineNumbers,
      overflow,
      themeStyles,
      split,
      themeType: baseThemeType ?? themeType,
      totalLines
    });
  }
  async asyncHighlight(diff) {
    this.computedLang = diff.lang ?? getFiletypeFromFileName(diff.name);
    const hasThemes = this.highlighter != null && areThemesAttached(this.options.theme ?? DEFAULT_THEMES);
    const hasLangs = this.highlighter != null && areLanguagesAttached(this.computedLang);
    if (this.highlighter == null || !hasThemes || !hasLangs) this.highlighter = await this.initializeHighlighter();
    return this.renderDiffWithHighlighter(diff, this.highlighter);
  }
  renderDiffWithHighlighter(diff, highlighter, forcePlainText = false) {
    const { options } = this.getRenderOptions(diff);
    const { collapsedContextThreshold } = this.getOptionsWithDefaults();
    return {
      result: renderDiffWithHighlighter(diff, highlighter, options, {
        forcePlainText,
        expandedHunks: forcePlainText ? true : void 0,
        collapsedContextThreshold
      }),
      options
    };
  }
  onHighlightSuccess(diff, result, options) {
    if (this.renderCache == null) return;
    const triggerRenderUpdate = this.renderCache.diff !== diff || !this.renderCache.highlighted || !areRenderOptionsEqual2(this.renderCache.options, options);
    this.renderCache = {
      diff,
      options,
      highlighted: true,
      result,
      renderRange: void 0
    };
    if (triggerRenderUpdate) this.onRenderUpdate?.();
  }
  onHighlightError(error) {
    console.error(error);
  }
  processDiffResult(fileDiff, renderRange, { code, themeStyles, baseThemeType }) {
    const { diffStyle, disableFileHeader, expandUnchanged, expansionLineCount, collapsedContextThreshold, hunkSeparators } = this.getOptionsWithDefaults();
    this.diff = fileDiff;
    const unified = diffStyle === "unified";
    let additionsContentAST = [];
    let deletionsContentAST = [];
    let unifiedContentAST = [];
    const hunkData = [];
    const { additionLines, deletionLines } = code;
    const context = {
      rowCount: 0,
      hunkSeparators,
      additionsContentAST,
      deletionsContentAST,
      unifiedContentAST,
      unifiedGutterAST: createGutterWrapper(),
      deletionsGutterAST: createGutterWrapper(),
      additionsGutterAST: createGutterWrapper(),
      expansionLineCount,
      hunkData,
      incrementRowCount(count = 1) {
        context.rowCount += count;
      },
      pushToGutter(type, element) {
        switch (type) {
          case "unified":
            context.unifiedGutterAST.children.push(element);
            break;
          case "deletions":
            context.deletionsGutterAST.children.push(element);
            break;
          case "additions":
            context.additionsGutterAST.children.push(element);
            break;
        }
      }
    };
    const trailingRangeSize = calculateTrailingRangeSize(fileDiff);
    let pendingSplitSpanSize = 0;
    let pendingSplitMissing;
    function pushGutterLineNumber(type, lineType, lineNumber, lineIndex) {
      context.pushToGutter(type, createGutterItem(lineType, lineNumber, lineIndex));
    }
    function flushSplitSpan() {
      if (diffStyle === "unified") return;
      if (pendingSplitSpanSize <= 0 || pendingSplitMissing == null) {
        pendingSplitSpanSize = 0;
        pendingSplitMissing = void 0;
        return;
      }
      if (pendingSplitMissing === "additions") {
        context.pushToGutter("additions", createGutterGap(void 0, "buffer", pendingSplitSpanSize));
        additionsContentAST?.push(createEmptyRowBuffer(pendingSplitSpanSize));
      } else {
        context.pushToGutter("deletions", createGutterGap(void 0, "buffer", pendingSplitSpanSize));
        deletionsContentAST?.push(createEmptyRowBuffer(pendingSplitSpanSize));
      }
      pendingSplitSpanSize = 0;
      pendingSplitMissing = void 0;
    }
    function pushSeparators(props) {
      flushSplitSpan();
      if (diffStyle === "unified") pushSeparator("unified", props, context);
      else {
        pushSeparator("deletions", props, context);
        pushSeparator("additions", props, context);
      }
    }
    iterateOverDiff({
      diff: fileDiff,
      diffStyle,
      startingLine: renderRange.startingLine,
      totalLines: renderRange.totalLines,
      expandedHunks: expandUnchanged ? true : this.expandedHunks,
      collapsedContextThreshold,
      callback: ({ hunkIndex, hunk, collapsedBefore, collapsedAfter, additionLine, deletionLine, type }) => {
        const splitLineIndex = deletionLine != null ? deletionLine.splitLineIndex : additionLine.splitLineIndex;
        const unifiedLineIndex = additionLine != null ? additionLine.unifiedLineIndex : deletionLine.unifiedLineIndex;
        if (diffStyle === "split" && type !== "change") flushSplitSpan();
        if (collapsedBefore > 0) pushSeparators({
          hunkIndex,
          collapsedLines: collapsedBefore,
          rangeSize: Math.max(hunk?.collapsedBefore ?? 0, 0),
          hunkSpecs: hunk?.hunkSpecs,
          isFirstHunk: hunkIndex === 0,
          isLastHunk: false,
          isExpandable: !fileDiff.isPartial
        });
        const lineIndex = diffStyle === "unified" ? unifiedLineIndex : splitLineIndex;
        if (diffStyle === "unified") {
          const deletionLineContent = deletionLine != null ? deletionLines[deletionLine.lineIndex] : void 0;
          const additionLineContent = additionLine != null ? additionLines[additionLine.lineIndex] : void 0;
          if (deletionLineContent == null && additionLineContent == null) {
            const errorMessage = "DiffHunksRenderer.processDiffResult: deletionLine and additionLine are null, something is wrong";
            console.error(errorMessage, { file: fileDiff.name });
            throw new Error(errorMessage);
          }
          pushGutterLineNumber("unified", type === "change" ? additionLine != null ? "change-addition" : "change-deletion" : type, additionLine != null ? additionLine.lineNumber : deletionLine.lineNumber, `${unifiedLineIndex},${splitLineIndex}`);
          pushLineWithAnnotation({
            diffStyle: "unified",
            type,
            deletionLine: deletionLineContent,
            additionLine: additionLineContent,
            unifiedSpan: this.getAnnotations("unified", deletionLine?.lineNumber, additionLine?.lineNumber, hunkIndex, lineIndex),
            context
          });
        } else {
          const deletionLineContent = deletionLine != null ? deletionLines[deletionLine.lineIndex] : void 0;
          const additionLineContent = additionLine != null ? additionLines[additionLine.lineIndex] : void 0;
          if (deletionLineContent == null && additionLineContent == null) {
            const errorMessage = "DiffHunksRenderer.processDiffResult: deletionLine and additionLine are null, something is wrong";
            console.error(errorMessage, { file: fileDiff.name });
            throw new Error(errorMessage);
          }
          const missingSide = (() => {
            if (type === "change") {
              if (additionLineContent == null) return "additions";
              else if (deletionLineContent == null) return "deletions";
            }
          })();
          if (missingSide != null) {
            if (pendingSplitMissing != null && pendingSplitMissing !== missingSide) throw new Error("DiffHunksRenderer.processDiffResult: iterateOverDiff, invalid pending splits");
            pendingSplitMissing = missingSide;
            pendingSplitSpanSize++;
          }
          const annotationSpans = this.getAnnotations("split", deletionLine?.lineNumber, additionLine?.lineNumber, hunkIndex, lineIndex);
          if (annotationSpans != null && pendingSplitSpanSize > 0) flushSplitSpan();
          if (deletionLine != null) pushGutterLineNumber("deletions", type === "change" ? "change-deletion" : type, deletionLine.lineNumber, `${deletionLine.unifiedLineIndex},${splitLineIndex}`);
          if (additionLine != null) pushGutterLineNumber("additions", type === "change" ? "change-addition" : type, additionLine.lineNumber, `${additionLine.unifiedLineIndex},${splitLineIndex}`);
          pushLineWithAnnotation({
            diffStyle: "split",
            type,
            additionLine: additionLineContent,
            deletionLine: deletionLineContent,
            ...annotationSpans,
            context
          });
        }
        const noEOFCRDeletion = deletionLine?.noEOFCR ?? false;
        const noEOFCRAddition = additionLine?.noEOFCR ?? false;
        if (noEOFCRAddition || noEOFCRDeletion) {
          if (noEOFCRDeletion) {
            const noEOFType = type === "context" || type === "context-expanded" ? type : "change-deletion";
            if (diffStyle === "unified") {
              context.unifiedContentAST.push(createNoNewlineElement(noEOFType));
              context.pushToGutter("unified", createGutterGap(noEOFType, "metadata", 1));
            } else {
              context.deletionsContentAST.push(createNoNewlineElement(noEOFType));
              context.pushToGutter("deletions", createGutterGap(noEOFType, "metadata", 1));
              if (!noEOFCRAddition) {
                context.pushToGutter("additions", createGutterGap(void 0, "buffer", 1));
                context.additionsContentAST.push(createEmptyRowBuffer(1));
              }
            }
          }
          if (noEOFCRAddition) {
            const noEOFType = type === "context" || type === "context-expanded" ? type : "change-addition";
            if (diffStyle === "unified") {
              context.unifiedContentAST.push(createNoNewlineElement(noEOFType));
              context.pushToGutter("unified", createGutterGap(noEOFType, "metadata", 1));
            } else {
              context.additionsContentAST.push(createNoNewlineElement(noEOFType));
              context.pushToGutter("additions", createGutterGap(noEOFType, "metadata", 1));
              if (!noEOFCRDeletion) {
                context.pushToGutter("deletions", createGutterGap(void 0, "buffer", 1));
                context.deletionsContentAST.push(createEmptyRowBuffer(1));
              }
            }
          }
          context.incrementRowCount(1);
        }
        if (collapsedAfter > 0 && hunkSeparators !== "simple") pushSeparators({
          hunkIndex: type === "context-expanded" ? hunkIndex : hunkIndex + 1,
          collapsedLines: collapsedAfter,
          rangeSize: trailingRangeSize,
          hunkSpecs: void 0,
          isFirstHunk: false,
          isLastHunk: true,
          isExpandable: !fileDiff.isPartial
        });
        context.incrementRowCount(1);
      }
    });
    if (diffStyle === "split") flushSplitSpan();
    const totalLines = Math.max(getTotalLineCountFromHunks(fileDiff.hunks), fileDiff.additionLines.length ?? 0, fileDiff.deletionLines.length ?? 0);
    const hasBuffer = renderRange.bufferBefore > 0 || renderRange.bufferAfter > 0;
    const shouldIncludeAdditions = !unified && fileDiff.type !== "deleted";
    const shouldIncludeDeletions = !unified && fileDiff.type !== "new";
    const hasContent = context.rowCount > 0 || hasBuffer;
    additionsContentAST = shouldIncludeAdditions && hasContent ? additionsContentAST : void 0;
    deletionsContentAST = shouldIncludeDeletions && hasContent ? deletionsContentAST : void 0;
    unifiedContentAST = unified && hasContent ? unifiedContentAST : void 0;
    const preNode = this.createPreElement(deletionsContentAST != null && additionsContentAST != null, totalLines, themeStyles, baseThemeType);
    return {
      unifiedGutterAST: unified && hasContent ? context.unifiedGutterAST.children : void 0,
      unifiedContentAST,
      deletionsGutterAST: shouldIncludeDeletions && hasContent ? context.deletionsGutterAST.children : void 0,
      deletionsContentAST,
      additionsGutterAST: shouldIncludeAdditions && hasContent ? context.additionsGutterAST.children : void 0,
      additionsContentAST,
      hunkData,
      preNode,
      themeStyles,
      baseThemeType,
      headerElement: !disableFileHeader ? this.renderHeader(this.diff, themeStyles, baseThemeType) : void 0,
      totalLines,
      rowCount: context.rowCount,
      bufferBefore: renderRange.bufferBefore,
      bufferAfter: renderRange.bufferAfter,
      css: ""
    };
  }
  renderCodeAST(type, result) {
    const gutterAST = type === "unified" ? result.unifiedGutterAST : type === "deletions" ? result.deletionsGutterAST : result.additionsGutterAST;
    const contentAST = type === "unified" ? result.unifiedContentAST : type === "deletions" ? result.deletionsContentAST : result.additionsContentAST;
    if (gutterAST == null || contentAST == null) return;
    const gutter = createGutterWrapper(gutterAST);
    gutter.properties.style = `grid-row: span ${result.rowCount}`;
    return [gutter, createContentColumn(contentAST, result.rowCount)];
  }
  renderFullAST(result, children = []) {
    const containerSize = this.getOptionsWithDefaults().hunkSeparators === "line-info";
    const unifiedAST = this.renderCodeAST("unified", result);
    if (unifiedAST != null) {
      children.push(createHastElement({
        tagName: "code",
        children: unifiedAST,
        properties: {
          "data-code": "",
          "data-container-size": containerSize ? "" : void 0,
          "data-unified": ""
        }
      }));
      return {
        ...result.preNode,
        children
      };
    }
    const deletionsAST = this.renderCodeAST("deletions", result);
    if (deletionsAST != null) children.push(createHastElement({
      tagName: "code",
      children: deletionsAST,
      properties: {
        "data-code": "",
        "data-container-size": containerSize ? "" : void 0,
        "data-deletions": ""
      }
    }));
    const additionsAST = this.renderCodeAST("additions", result);
    if (additionsAST != null) children.push(createHastElement({
      tagName: "code",
      children: additionsAST,
      properties: {
        "data-code": "",
        "data-container-size": containerSize ? "" : void 0,
        "data-additions": ""
      }
    }));
    return {
      ...result.preNode,
      children
    };
  }
  renderFullHTML(result, tempChildren = []) {
    return toHtml(this.renderFullAST(result, tempChildren));
  }
  renderPartialHTML(children, columnType) {
    if (columnType == null) return toHtml(children);
    return toHtml(createHastElement({
      tagName: "code",
      children,
      properties: {
        "data-code": "",
        "data-container-size": this.getOptionsWithDefaults().hunkSeparators === "line-info" ? "" : void 0,
        [`data-${columnType}`]: ""
      }
    }));
  }
  getAnnotations(type, deletionLineNumber, additionLineNumber, hunkIndex, lineIndex) {
    const deletionSpan = {
      type: "annotation",
      hunkIndex,
      lineIndex,
      annotations: []
    };
    if (deletionLineNumber != null) for (const anno of this.deletionAnnotations[deletionLineNumber] ?? []) deletionSpan.annotations.push(getLineAnnotationName(anno));
    const additionSpan = {
      type: "annotation",
      hunkIndex,
      lineIndex,
      annotations: []
    };
    if (additionLineNumber != null) for (const anno of this.additionAnnotations[additionLineNumber] ?? []) (type === "unified" ? deletionSpan : additionSpan).annotations.push(getLineAnnotationName(anno));
    if (type === "unified") {
      if (deletionSpan.annotations.length > 0) return deletionSpan;
      return;
    }
    if (additionSpan.annotations.length === 0 && deletionSpan.annotations.length === 0) return;
    return {
      deletionSpan,
      additionSpan
    };
  }
  renderHeader(diff, themeStyles, baseThemeType) {
    const { themeType } = this.getOptionsWithDefaults();
    return createFileHeaderElement({
      fileOrDiff: diff,
      themeStyles,
      themeType: baseThemeType ?? themeType
    });
  }
};
function areRenderOptionsEqual2(optionsA, optionsB) {
  return areThemesEqual(optionsA.theme, optionsB.theme) && optionsA.tokenizeMaxLineLength === optionsB.tokenizeMaxLineLength && optionsA.lineDiffType === optionsB.lineDiffType;
}
function getModifiedLinesString(lines) {
  return `${lines} unmodified line${lines > 1 ? "s" : ""}`;
}
function pushLineWithAnnotation({ diffStyle, type, deletionLine, additionLine, unifiedSpan, deletionSpan, additionSpan, context }) {
  let hasAnnotationRow = false;
  if (diffStyle === "unified") {
    if (additionLine != null) context.unifiedContentAST.push(additionLine);
    else if (deletionLine != null) context.unifiedContentAST.push(deletionLine);
    if (unifiedSpan != null) {
      const lineType = type === "change" ? deletionLine != null ? "change-deletion" : "change-addition" : type;
      context.unifiedContentAST.push(createAnnotationElement(unifiedSpan));
      context.pushToGutter("unified", createGutterGap(lineType, "annotation", 1));
      hasAnnotationRow = true;
    }
  } else if (diffStyle === "split") {
    if (deletionLine != null) context.deletionsContentAST.push(deletionLine);
    if (additionLine != null) context.additionsContentAST.push(additionLine);
    if (deletionSpan != null) {
      const lineType = type === "change" ? deletionLine != null ? "change-deletion" : "context" : type;
      context.deletionsContentAST.push(createAnnotationElement(deletionSpan));
      context.pushToGutter("deletions", createGutterGap(lineType, "annotation", 1));
      hasAnnotationRow = true;
    }
    if (additionSpan != null) {
      const lineType = type === "change" ? additionLine != null ? "change-addition" : "context" : type;
      context.additionsContentAST.push(createAnnotationElement(additionSpan));
      context.pushToGutter("additions", createGutterGap(lineType, "annotation", 1));
      hasAnnotationRow = true;
    }
  }
  if (hasAnnotationRow) context.incrementRowCount(1);
}
function pushSeparator(type, { hunkIndex, collapsedLines, rangeSize, hunkSpecs, isFirstHunk, isLastHunk, isExpandable }, context) {
  if (collapsedLines <= 0) return;
  const linesAST = type === "unified" ? context.unifiedContentAST : type === "deletions" ? context.deletionsContentAST : context.additionsContentAST;
  if (context.hunkSeparators === "metadata") {
    if (hunkSpecs != null) {
      context.pushToGutter(type, createSeparator({
        type: "metadata",
        content: hunkSpecs,
        isFirstHunk,
        isLastHunk
      }));
      linesAST.push(createSeparator({
        type: "metadata",
        content: hunkSpecs,
        isFirstHunk,
        isLastHunk
      }));
      if (type !== "additions") context.incrementRowCount(1);
    }
    return;
  }
  if (context.hunkSeparators === "simple") {
    if (hunkIndex > 0) {
      context.pushToGutter(type, createSeparator({
        type: "simple",
        isFirstHunk,
        isLastHunk: false
      }));
      linesAST.push(createSeparator({
        type: "simple",
        isFirstHunk,
        isLastHunk: false
      }));
      if (type !== "additions") context.incrementRowCount(1);
    }
    return;
  }
  const slotName = getHunkSeparatorSlotName(type, hunkIndex);
  const chunked = rangeSize > context.expansionLineCount;
  const expandIndex = isExpandable ? hunkIndex : void 0;
  context.pushToGutter(type, createSeparator({
    type: context.hunkSeparators,
    content: getModifiedLinesString(collapsedLines),
    expandIndex,
    chunked,
    slotName,
    isFirstHunk,
    isLastHunk
  }));
  linesAST.push(createSeparator({
    type: context.hunkSeparators,
    content: getModifiedLinesString(collapsedLines),
    expandIndex,
    chunked,
    slotName,
    isFirstHunk,
    isLastHunk
  }));
  if (type !== "additions") context.incrementRowCount(1);
  context.hunkData.push({
    slotName,
    hunkIndex,
    lines: collapsedLines,
    type,
    expandable: isExpandable ? {
      up: !isFirstHunk,
      down: !isLastHunk,
      chunked
    } : void 0
  });
}
function calculateTrailingRangeSize(fileDiff) {
  const lastHunk = fileDiff.hunks.at(-1);
  if (lastHunk == null || fileDiff.isPartial || fileDiff.additionLines.length === 0 || fileDiff.deletionLines.length === 0) return 0;
  const additionRemaining = fileDiff.additionLines.length - (lastHunk.additionLineIndex + lastHunk.additionCount);
  const deletionRemaining = fileDiff.deletionLines.length - (lastHunk.deletionLineIndex + lastHunk.deletionCount);
  if (additionRemaining !== deletionRemaining) throw new Error(`DiffHunksRenderer.processDiffResult: trailing context mismatch (additions=${additionRemaining}, deletions=${deletionRemaining}) for ${fileDiff.name}`);
  return Math.min(additionRemaining, deletionRemaining);
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/areDiffLineAnnotationsEqual.js
function areDiffLineAnnotationsEqual(annotationA, annotationB) {
  return annotationA.lineNumber === annotationB.lineNumber && annotationA.side === annotationB.side && annotationA.metadata === annotationB.metadata;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/areHunkDataEqual.js
function areHunkDataEqual(hunkA, hunkB) {
  return hunkA.slotName === hunkB.slotName && hunkA.hunkIndex === hunkB.hunkIndex && hunkA.lines === hunkB.lines && hunkA.type === hunkB.type && hunkA.expandable?.chunked === hunkB.expandable?.chunked && hunkA.expandable?.up === hunkB.expandable?.up && hunkA.expandable?.down === hunkB.expandable?.down;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/parseLineType.js
function parseLineType(line) {
  const firstChar = line[0];
  if (firstChar !== "+" && firstChar !== "-" && firstChar !== " " && firstChar !== "\\") {
    console.error(`parseLineType: Invalid firstChar: "${firstChar}", full line: "${line}"`);
    return;
  }
  const processedLine = line.substring(1);
  return {
    line: processedLine === "" ? "\n" : processedLine,
    type: firstChar === " " ? "context" : firstChar === "\\" ? "metadata" : firstChar === "+" ? "addition" : "deletion"
  };
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/parsePatchFiles.js
function processPatch(data, cacheKeyPrefix, throwOnError = false) {
  const isGitDiff = GIT_DIFF_FILE_BREAK_REGEX.test(data);
  const rawFiles = data.split(isGitDiff ? GIT_DIFF_FILE_BREAK_REGEX : UNIFIED_DIFF_FILE_BREAK_REGEX);
  let patchMetadata;
  const files = [];
  for (const fileOrPatchMetadata of rawFiles) {
    if (isGitDiff && !GIT_DIFF_FILE_BREAK_REGEX.test(fileOrPatchMetadata)) {
      if (patchMetadata == null) patchMetadata = fileOrPatchMetadata;
      else if (throwOnError) throw Error("parsePatchContent: unknown file blob");
      else console.error("parsePatchContent: unknown file blob:", fileOrPatchMetadata);
      continue;
    } else if (!isGitDiff && !UNIFIED_DIFF_FILE_BREAK_REGEX.test(fileOrPatchMetadata)) {
      if (patchMetadata == null) patchMetadata = fileOrPatchMetadata;
      else if (throwOnError) throw Error("parsePatchContent: unknown file blob");
      else console.error("parsePatchContent: unknown file blob:", fileOrPatchMetadata);
      continue;
    }
    const currentFile = processFile(fileOrPatchMetadata, {
      cacheKey: cacheKeyPrefix != null ? `${cacheKeyPrefix}-${files.length}` : void 0,
      isGitDiff,
      throwOnError
    });
    if (currentFile != null) files.push(currentFile);
  }
  return {
    patchMetadata,
    files
  };
}
function processFile(fileDiffString, { cacheKey, isGitDiff = GIT_DIFF_FILE_BREAK_REGEX.test(fileDiffString), oldFile, newFile, throwOnError = false } = {}) {
  let lastHunkEnd = 0;
  const hunks = fileDiffString.split(FILE_CONTEXT_BLOB);
  let currentFile;
  const isPartial = oldFile == null || newFile == null;
  let deletionLineIndex = 0;
  let additionLineIndex = 0;
  for (const hunk of hunks) {
    const lines = hunk.split(SPLIT_WITH_NEWLINES);
    const firstLine = lines.shift();
    if (firstLine == null) {
      if (throwOnError) throw Error("parsePatchContent: invalid hunk");
      else console.error("parsePatchContent: invalid hunk", hunk);
      continue;
    }
    const fileHeaderMatch = firstLine.match(HUNK_HEADER);
    let additionLines = 0;
    let deletionLines = 0;
    if (fileHeaderMatch == null || currentFile == null) {
      if (currentFile != null) {
        if (throwOnError) throw Error("parsePatchContent: Invalid hunk");
        else console.error("parsePatchContent: Invalid hunk", hunk);
        continue;
      }
      currentFile = {
        name: "",
        type: "change",
        hunks: [],
        splitLineCount: 0,
        unifiedLineCount: 0,
        isPartial,
        additionLines: !isPartial && oldFile != null && newFile != null ? newFile.contents.split(SPLIT_WITH_NEWLINES) : [],
        deletionLines: !isPartial && oldFile != null && newFile != null ? oldFile.contents.split(SPLIT_WITH_NEWLINES) : [],
        cacheKey
      };
      if (currentFile.additionLines.length === 1 && newFile?.contents === "") currentFile.additionLines.length = 0;
      if (currentFile.deletionLines.length === 1 && oldFile?.contents === "") currentFile.deletionLines.length = 0;
      lines.unshift(firstLine);
      for (const line of lines) {
        const filenameMatch = line.match(isGitDiff ? FILENAME_HEADER_REGEX_GIT : FILENAME_HEADER_REGEX);
        if (line.startsWith("diff --git")) {
          const [, , prevName, , name] = line.trim().match(ALTERNATE_FILE_NAMES_GIT) ?? [];
          currentFile.name = name.trim();
          if (prevName !== name) currentFile.prevName = prevName.trim();
        } else if (filenameMatch != null) {
          const [, type, fileName] = filenameMatch;
          if (type === "---" && fileName !== "/dev/null") {
            currentFile.prevName = fileName.trim();
            currentFile.name = fileName.trim();
          } else if (type === "+++" && fileName !== "/dev/null") currentFile.name = fileName.trim();
        } else if (isGitDiff) {
          if (line.startsWith("new mode ")) currentFile.mode = line.replace("new mode", "").trim();
          if (line.startsWith("old mode ")) currentFile.prevMode = line.replace("old mode", "").trim();
          if (line.startsWith("new file mode")) {
            currentFile.type = "new";
            currentFile.mode = line.replace("new file mode", "").trim();
          }
          if (line.startsWith("deleted file mode")) {
            currentFile.type = "deleted";
            currentFile.mode = line.replace("deleted file mode", "").trim();
          }
          if (line.startsWith("similarity index")) if (line.startsWith("similarity index 100%")) currentFile.type = "rename-pure";
          else currentFile.type = "rename-changed";
          if (line.startsWith("index ")) {
            const [, prevObjectId, newObjectId, mode] = line.trim().match(INDEX_LINE_METADATA) ?? [];
            if (prevObjectId != null) currentFile.prevObjectId = prevObjectId;
            if (newObjectId != null) currentFile.newObjectId = newObjectId;
            if (mode != null) currentFile.mode = mode;
          }
          if (line.startsWith("rename from ")) currentFile.prevName = line.replace("rename from ", "");
          if (line.startsWith("rename to ")) currentFile.name = line.replace("rename to ", "").trim();
        }
      }
      continue;
    }
    let currentContent;
    let lastLineType;
    while (lines.length > 0 && (lines[lines.length - 1] === "\n" || lines[lines.length - 1] === "\r" || lines[lines.length - 1] === "\r\n" || lines[lines.length - 1] === "")) lines.pop();
    const additionStart = parseInt(fileHeaderMatch[3]);
    const deletionStart = parseInt(fileHeaderMatch[1]);
    deletionLineIndex = isPartial ? deletionLineIndex : deletionStart - 1;
    additionLineIndex = isPartial ? additionLineIndex : additionStart - 1;
    const hunkData = {
      collapsedBefore: 0,
      splitLineCount: 0,
      splitLineStart: 0,
      unifiedLineCount: 0,
      unifiedLineStart: 0,
      additionCount: parseInt(fileHeaderMatch[4] ?? "1"),
      additionStart,
      additionLines,
      deletionCount: parseInt(fileHeaderMatch[2] ?? "1"),
      deletionStart,
      deletionLines,
      deletionLineIndex,
      additionLineIndex,
      hunkContent: [],
      hunkContext: fileHeaderMatch[5],
      hunkSpecs: firstLine,
      noEOFCRAdditions: false,
      noEOFCRDeletions: false
    };
    if (isNaN(hunkData.additionCount) || isNaN(hunkData.deletionCount) || isNaN(hunkData.additionStart) || isNaN(hunkData.deletionStart)) {
      if (throwOnError) throw Error("parsePatchContent: invalid hunk metadata");
      else console.error("parsePatchContent: invalid hunk metadata", hunkData);
      continue;
    }
    for (const rawLine of lines) {
      const parsedLine = parseLineType(rawLine);
      if (parsedLine == null) {
        console.error("processFile: invalid rawLine:", rawLine);
        continue;
      }
      const { type, line } = parsedLine;
      if (type === "addition") {
        if (currentContent == null || currentContent.type !== "change") {
          currentContent = createContentGroup("change", deletionLineIndex, additionLineIndex);
          hunkData.hunkContent.push(currentContent);
        }
        additionLineIndex++;
        if (isPartial) currentFile.additionLines.push(line);
        currentContent.additions++;
        additionLines++;
        lastLineType = "addition";
      } else if (type === "deletion") {
        if (currentContent == null || currentContent.type !== "change") {
          currentContent = createContentGroup("change", deletionLineIndex, additionLineIndex);
          hunkData.hunkContent.push(currentContent);
        }
        deletionLineIndex++;
        if (isPartial) currentFile.deletionLines.push(line);
        currentContent.deletions++;
        deletionLines++;
        lastLineType = "deletion";
      } else if (type === "context") {
        if (currentContent == null || currentContent.type !== "context") {
          currentContent = createContentGroup("context", deletionLineIndex, additionLineIndex);
          hunkData.hunkContent.push(currentContent);
        }
        additionLineIndex++;
        deletionLineIndex++;
        if (isPartial) {
          currentFile.deletionLines.push(line);
          currentFile.additionLines.push(line);
        }
        currentContent.lines++;
        lastLineType = "context";
      } else if (type === "metadata" && currentContent != null) {
        if (currentContent.type === "context") {
          hunkData.noEOFCRAdditions = true;
          hunkData.noEOFCRDeletions = true;
        } else if (lastLineType === "deletion") hunkData.noEOFCRDeletions = true;
        else if (lastLineType === "addition") hunkData.noEOFCRAdditions = true;
        if (isPartial && (lastLineType === "addition" || lastLineType === "context")) {
          const lastIndex = currentFile.additionLines.length - 1;
          if (lastIndex >= 0) currentFile.additionLines[lastIndex] = cleanLastNewline(currentFile.additionLines[lastIndex]);
        }
        if (isPartial && (lastLineType === "deletion" || lastLineType === "context")) {
          const lastIndex = currentFile.deletionLines.length - 1;
          if (lastIndex >= 0) currentFile.deletionLines[lastIndex] = cleanLastNewline(currentFile.deletionLines[lastIndex]);
        }
      }
    }
    hunkData.additionLines = additionLines;
    hunkData.deletionLines = deletionLines;
    hunkData.collapsedBefore = Math.max(hunkData.additionStart - 1 - lastHunkEnd, 0);
    currentFile.hunks.push(hunkData);
    lastHunkEnd = hunkData.additionStart + hunkData.additionCount - 1;
    for (const content of hunkData.hunkContent) if (content.type === "context") {
      hunkData.splitLineCount += content.lines;
      hunkData.unifiedLineCount += content.lines;
    } else {
      hunkData.splitLineCount += Math.max(content.additions, content.deletions);
      hunkData.unifiedLineCount += content.deletions + content.additions;
    }
    hunkData.splitLineStart = currentFile.splitLineCount + hunkData.collapsedBefore;
    hunkData.unifiedLineStart = currentFile.unifiedLineCount + hunkData.collapsedBefore;
    currentFile.splitLineCount += hunkData.collapsedBefore + hunkData.splitLineCount;
    currentFile.unifiedLineCount += hunkData.collapsedBefore + hunkData.unifiedLineCount;
  }
  if (currentFile == null) return;
  if (currentFile.hunks.length > 0 && !isPartial && currentFile.additionLines.length > 0 && currentFile.deletionLines.length > 0) {
    const lastHunk = currentFile.hunks[currentFile.hunks.length - 1];
    const lastHunkEnd$1 = lastHunk.additionStart + lastHunk.additionCount - 1;
    const totalFileLines = currentFile.additionLines.length;
    const collapsedAfter = Math.max(totalFileLines - lastHunkEnd$1, 0);
    currentFile.splitLineCount += collapsedAfter;
    currentFile.unifiedLineCount += collapsedAfter;
  }
  if (!isGitDiff) {
    if (currentFile.prevName != null && currentFile.name !== currentFile.prevName) if (currentFile.hunks.length > 0) currentFile.type = "rename-changed";
    else currentFile.type = "rename-pure";
    else if (newFile != null && newFile.contents === "") currentFile.type = "deleted";
    else if (oldFile != null && oldFile.contents === "") currentFile.type = "new";
  }
  if (currentFile.type !== "rename-pure" && currentFile.type !== "rename-changed") currentFile.prevName = void 0;
  return currentFile;
}
function parsePatchFiles(data, cacheKeyPrefix, throwOnError = false) {
  const patches = [];
  for (const patch of data.split(COMMIT_METADATA_SPLIT)) try {
    patches.push(processPatch(patch, cacheKeyPrefix != null ? `${cacheKeyPrefix}-${patches.length}` : void 0, throwOnError));
  } catch (error) {
    if (throwOnError) throw error;
    else console.error(error);
  }
  return patches;
}
function createContentGroup(type, deletionLineIndex, additionLineIndex) {
  if (type === "change") return {
    type: "change",
    additions: 0,
    deletions: 0,
    additionLineIndex,
    deletionLineIndex
  };
  return {
    type: "context",
    lines: 0,
    additionLineIndex,
    deletionLineIndex
  };
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/parseDiffFromFile.js
function parseDiffFromFile(oldFile, newFile, options, throwOnError = false) {
  const fileData = processFile(createTwoFilesPatch(oldFile.name, newFile.name, oldFile.contents, newFile.contents, oldFile.header, newFile.header, options), {
    cacheKey: (() => {
      if (oldFile.cacheKey != null && newFile.cacheKey != null) return `${oldFile.cacheKey}:${newFile.cacheKey}`;
    })(),
    oldFile,
    newFile,
    throwOnError
  });
  if (fileData == null) throw new Error("parseDiffFrom: FileInvalid diff -- probably need to fix something -- if the files are the same maybe?");
  return fileData;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/components/FileDiff.js
var instanceId4 = -1;
var FileDiff = class {
  static LoadedCustomComponent = DiffsContainerLoaded;
  __id = `file-diff:${++instanceId4}`;
  fileContainer;
  spriteSVG;
  pre;
  codeUnified;
  codeDeletions;
  codeAdditions;
  bufferBefore;
  bufferAfter;
  unsafeCSSStyle;
  gutterUtilityContent;
  headerElement;
  headerPrefix;
  headerMetadata;
  separatorCache = /* @__PURE__ */ new Map();
  errorWrapper;
  placeHolder;
  hunksRenderer;
  resizeManager;
  scrollSyncManager;
  interactionManager;
  annotationCache = /* @__PURE__ */ new Map();
  lineAnnotations = [];
  deletionFile;
  additionFile;
  fileDiff;
  renderRange;
  appliedPreAttributes;
  lastRenderedHeaderHTML;
  lastRowCount;
  enabled = true;
  constructor(options = { theme: DEFAULT_THEMES }, workerManager, isContainerManaged = false) {
    this.options = options;
    this.workerManager = workerManager;
    this.isContainerManaged = isContainerManaged;
    this.hunksRenderer = new DiffHunksRenderer({
      ...options,
      hunkSeparators: typeof options.hunkSeparators === "function" ? "custom" : options.hunkSeparators
    }, this.handleHighlightRender, this.workerManager);
    this.resizeManager = new ResizeManager();
    this.scrollSyncManager = new ScrollSyncManager();
    this.interactionManager = new InteractionManager("diff", pluckInteractionOptions(options, typeof options.hunkSeparators === "function" || (options.hunkSeparators ?? "line-info") === "line-info" || options.hunkSeparators === "line-info-basic" ? this.handleExpandHunk : void 0, this.getLineIndex));
    this.workerManager?.subscribeToThemeChanges(this);
    this.enabled = true;
  }
  handleHighlightRender = () => {
    this.rerender();
  };
  getLineIndex = (lineNumber, side = "additions") => {
    if (this.fileDiff == null) return;
    const lastHunk = this.fileDiff.hunks.at(-1);
    let targetUnifiedIndex;
    let targetSplitIndex;
    hunkIterator: for (const hunk of this.fileDiff.hunks) {
      let currentLineNumber = side === "deletions" ? hunk.deletionStart : hunk.additionStart;
      const hunkCount = side === "deletions" ? hunk.deletionCount : hunk.additionCount;
      let splitIndex = hunk.splitLineStart;
      let unifiedIndex = hunk.unifiedLineStart;
      if (lineNumber < currentLineNumber) {
        const difference = currentLineNumber - lineNumber;
        targetUnifiedIndex = Math.max(unifiedIndex - difference, 0);
        targetSplitIndex = Math.max(splitIndex - difference, 0);
        break hunkIterator;
      }
      if (lineNumber >= currentLineNumber + hunkCount) {
        if (hunk === lastHunk) {
          const difference = lineNumber - (currentLineNumber + hunkCount);
          targetUnifiedIndex = unifiedIndex + hunk.unifiedLineCount + difference;
          targetSplitIndex = splitIndex + hunk.splitLineCount + difference;
          break hunkIterator;
        }
        continue;
      }
      for (const content of hunk.hunkContent) if (content.type === "context") if (lineNumber < currentLineNumber + content.lines) {
        const difference = lineNumber - currentLineNumber;
        targetSplitIndex = splitIndex + difference;
        targetUnifiedIndex = unifiedIndex + difference;
        break hunkIterator;
      } else {
        currentLineNumber += content.lines;
        splitIndex += content.lines;
        unifiedIndex += content.lines;
      }
      else {
        const sideCount = side === "deletions" ? content.deletions : content.additions;
        if (lineNumber < currentLineNumber + sideCount) {
          const indexDifference = lineNumber - currentLineNumber;
          targetUnifiedIndex = unifiedIndex + (side === "additions" ? content.deletions : 0) + indexDifference;
          targetSplitIndex = splitIndex + indexDifference;
          break hunkIterator;
        } else {
          currentLineNumber += sideCount;
          splitIndex += Math.max(content.deletions, content.additions);
          unifiedIndex += content.deletions + content.additions;
        }
      }
      break hunkIterator;
    }
    if (targetUnifiedIndex == null || targetSplitIndex == null) return;
    return [targetUnifiedIndex, targetSplitIndex];
  };
  setOptions(options) {
    if (options == null) return;
    this.options = options;
    this.hunksRenderer.setOptions({
      ...this.options,
      hunkSeparators: typeof options.hunkSeparators === "function" ? "custom" : options.hunkSeparators
    });
    this.interactionManager.setOptions(pluckInteractionOptions(options, typeof options.hunkSeparators === "function" || (options.hunkSeparators ?? "line-info") === "line-info" || options.hunkSeparators === "line-info-basic" ? this.handleExpandHunk : void 0, this.getLineIndex));
  }
  mergeOptions(options) {
    this.options = {
      ...this.options,
      ...options
    };
  }
  setThemeType(themeType) {
    if ((this.options.themeType ?? "system") === themeType) return;
    this.mergeOptions({ themeType });
    this.hunksRenderer.setThemeType(themeType);
    if (this.headerElement != null) if (themeType === "system") delete this.headerElement.dataset.themeType;
    else this.headerElement.dataset.themeType = themeType;
    if (this.pre != null) switch (themeType) {
      case "system":
        delete this.pre.dataset.themeType;
        break;
      case "light":
      case "dark":
        this.pre.dataset.themeType = themeType;
        break;
    }
  }
  getHoveredLine = () => {
    return this.interactionManager.getHoveredLine();
  };
  setLineAnnotations(lineAnnotations) {
    this.lineAnnotations = lineAnnotations;
  }
  canPartiallyRender(forceRender, annotationsChanged, didContentChange) {
    if (forceRender || annotationsChanged || didContentChange || typeof this.options.hunkSeparators === "function") return false;
    return true;
  }
  setSelectedLines(range) {
    this.interactionManager.setSelection(range);
  }
  cleanUp(recycle = false) {
    this.resizeManager.cleanUp();
    this.interactionManager.cleanUp();
    this.scrollSyncManager.cleanUp();
    this.workerManager?.unsubscribeToThemeChanges(this);
    this.renderRange = void 0;
    if (!this.isContainerManaged) this.fileContainer?.parentNode?.removeChild(this.fileContainer);
    if (this.fileContainer?.shadowRoot != null) this.fileContainer.shadowRoot.innerHTML = "";
    this.fileContainer = void 0;
    if (this.pre != null) {
      this.pre.innerHTML = "";
      this.pre = void 0;
    }
    this.codeUnified = void 0;
    this.codeDeletions = void 0;
    this.codeAdditions = void 0;
    this.bufferBefore = void 0;
    this.bufferAfter = void 0;
    this.appliedPreAttributes = void 0;
    this.headerElement = void 0;
    this.headerPrefix = void 0;
    this.headerMetadata = void 0;
    this.lastRenderedHeaderHTML = void 0;
    this.errorWrapper = void 0;
    this.spriteSVG = void 0;
    this.lastRowCount = void 0;
    if (recycle) this.hunksRenderer.recycle();
    else {
      this.hunksRenderer.cleanUp();
      this.workerManager = void 0;
      this.fileDiff = void 0;
      this.deletionFile = void 0;
      this.additionFile = void 0;
    }
    this.enabled = false;
  }
  virtualizedSetup() {
    this.enabled = true;
    this.workerManager?.subscribeToThemeChanges(this);
  }
  hydrate(props) {
    const { overflow = "scroll", diffStyle = "split" } = this.options;
    const { fileContainer, prerenderedHTML } = props;
    prerenderHTMLIfNecessary(fileContainer, prerenderedHTML);
    for (const element of fileContainer.shadowRoot?.children ?? []) {
      if (element instanceof SVGElement) {
        this.spriteSVG = element;
        continue;
      }
      if (!(element instanceof HTMLElement)) continue;
      if (element instanceof HTMLPreElement) {
        this.pre = element;
        for (const code of element.children) {
          if (!(code instanceof HTMLElement) || code.tagName.toLowerCase() !== "code") continue;
          if ("deletions" in code.dataset) this.codeDeletions = code;
          if ("additions" in code.dataset) this.codeAdditions = code;
          if ("unified" in code.dataset) this.codeUnified = code;
        }
        continue;
      }
      if ("diffsHeader" in element.dataset) {
        this.headerElement = element;
        continue;
      }
      if (element instanceof HTMLStyleElement && element.hasAttribute(UNSAFE_CSS_ATTRIBUTE)) {
        this.unsafeCSSStyle = element;
        continue;
      }
    }
    if (this.pre != null) this.syncCodeNodesFromPre(this.pre);
    if (this.pre == null) this.render(props);
    else {
      const { lineAnnotations, oldFile, newFile, fileDiff } = props;
      this.fileContainer = fileContainer;
      delete this.pre.dataset.dehydrated;
      this.lineAnnotations = lineAnnotations ?? this.lineAnnotations;
      this.additionFile = newFile;
      this.deletionFile = oldFile;
      this.fileDiff = fileDiff ?? (oldFile != null && newFile != null ? parseDiffFromFile(oldFile, newFile) : void 0);
      this.hunksRenderer.hydrate(this.fileDiff);
      this.renderAnnotations();
      this.renderGutterUtility();
      this.injectUnsafeCSS();
      this.interactionManager.setup(this.pre);
      this.resizeManager.setup(this.pre, overflow === "wrap");
      if (overflow === "scroll" && diffStyle === "split") this.scrollSyncManager.setup(this.pre, this.codeDeletions, this.codeAdditions);
    }
  }
  rerender() {
    if (!this.enabled || this.fileDiff == null && this.additionFile == null && this.deletionFile == null) return;
    this.render({
      oldFile: this.deletionFile,
      newFile: this.additionFile,
      fileDiff: this.fileDiff,
      forceRender: true,
      renderRange: this.renderRange
    });
  }
  handleExpandHunk = (hunkIndex, direction, expandFully = false) => {
    if (expandFully) {
      this.expandHunkFully(hunkIndex);
      return;
    }
    this.expandHunk(hunkIndex, direction);
  };
  expandHunk(hunkIndex, direction) {
    this.hunksRenderer.expandHunk(hunkIndex, direction);
    this.rerender();
  }
  expandHunkFully(hunkIndex) {
    this.hunksRenderer.expandHunkFully(hunkIndex);
    this.rerender();
  }
  render({ oldFile, newFile, fileDiff, forceRender = false, lineAnnotations, fileContainer, containerWrapper, renderRange }) {
    if (!this.enabled) throw new Error("FileDiff.render: attempting to call render after cleaned up");
    const { collapsed = false } = this.options;
    const nextRenderRange = collapsed ? void 0 : renderRange;
    const filesDidChange = oldFile != null && newFile != null && (!areFilesEqual(oldFile, this.deletionFile) || !areFilesEqual(newFile, this.additionFile));
    let diffDidChange = fileDiff != null && fileDiff !== this.fileDiff;
    const annotationsChanged = lineAnnotations != null && (lineAnnotations.length > 0 || this.lineAnnotations.length > 0) ? lineAnnotations !== this.lineAnnotations : false;
    if (!collapsed && areRenderRangesEqual(nextRenderRange, this.renderRange) && !forceRender && !annotationsChanged && (fileDiff != null && fileDiff === this.fileDiff || fileDiff == null && !filesDidChange)) return false;
    const { renderRange: previousRenderRange } = this;
    this.renderRange = nextRenderRange;
    this.deletionFile = oldFile;
    this.additionFile = newFile;
    if (fileDiff != null) this.fileDiff = fileDiff;
    else if (oldFile != null && newFile != null && filesDidChange) {
      diffDidChange = true;
      this.fileDiff = parseDiffFromFile(oldFile, newFile);
    }
    if (lineAnnotations != null) this.setLineAnnotations(lineAnnotations);
    if (this.fileDiff == null) return false;
    this.hunksRenderer.setOptions({
      ...this.options,
      hunkSeparators: typeof this.options.hunkSeparators === "function" ? "custom" : this.options.hunkSeparators
    });
    this.hunksRenderer.setLineAnnotations(this.lineAnnotations);
    const { diffStyle = "split", disableErrorHandling = false, disableFileHeader = false, overflow = "scroll" } = this.options;
    if (disableFileHeader) {
      if (this.headerElement != null) {
        this.headerElement.parentNode?.removeChild(this.headerElement);
        this.headerElement = void 0;
        this.lastRenderedHeaderHTML = void 0;
      }
      if (this.headerPrefix != null) {
        this.headerPrefix.parentNode?.removeChild(this.headerPrefix);
        this.headerPrefix = void 0;
      }
      if (this.headerMetadata != null) {
        this.headerMetadata.parentNode?.removeChild(this.headerMetadata);
        this.headerMetadata = void 0;
      }
    }
    fileContainer = this.getOrCreateFileContainer(fileContainer, containerWrapper);
    if (collapsed) {
      this.removeRenderedCode();
      this.clearAuxiliaryNodes();
      try {
        const hunksResult = this.hunksRenderer.renderDiff(this.fileDiff, EMPTY_RENDER_RANGE);
        if (hunksResult?.headerElement != null) this.applyHeaderToDOM(hunksResult.headerElement, fileContainer);
        this.renderSeparators([]);
        this.injectUnsafeCSS();
      } catch (error) {
        if (disableErrorHandling) throw error;
        console.error(error);
        if (error instanceof Error) this.applyErrorToDOM(error, fileContainer);
      }
      return true;
    }
    try {
      const pre = this.getOrCreatePreNode(fileContainer);
      if (!(this.canPartiallyRender(forceRender, annotationsChanged, filesDidChange || diffDidChange) && this.applyPartialRender({
        previousRenderRange,
        renderRange: nextRenderRange
      }))) {
        const hunksResult = this.hunksRenderer.renderDiff(this.fileDiff, nextRenderRange);
        if (hunksResult == null) {
          if (this.workerManager?.isInitialized() === false) this.workerManager.initialize().then(() => this.rerender());
          return false;
        }
        if (hunksResult.headerElement != null) this.applyHeaderToDOM(hunksResult.headerElement, fileContainer);
        if (hunksResult.additionsContentAST != null || hunksResult.deletionsContentAST != null || hunksResult.unifiedContentAST != null) this.applyHunksToDOM(pre, hunksResult);
        else if (this.pre != null) {
          this.pre.parentNode?.removeChild(this.pre);
          this.pre = void 0;
        }
        this.renderSeparators(hunksResult.hunkData);
      }
      this.applyBuffers(pre, nextRenderRange);
      this.injectUnsafeCSS();
      this.renderAnnotations();
      this.renderGutterUtility();
      this.interactionManager.setup(pre);
      this.resizeManager.setup(pre, overflow === "wrap");
      if (overflow === "scroll" && diffStyle === "split") this.scrollSyncManager.setup(pre, this.codeDeletions, this.codeAdditions);
      else this.scrollSyncManager.cleanUp();
    } catch (error) {
      if (disableErrorHandling) throw error;
      console.error(error);
      if (error instanceof Error) this.applyErrorToDOM(error, fileContainer);
    }
    return true;
  }
  removeRenderedCode() {
    this.resizeManager.cleanUp();
    this.scrollSyncManager.cleanUp();
    this.interactionManager.cleanUp();
    this.bufferBefore?.remove();
    this.bufferBefore = void 0;
    this.bufferAfter?.remove();
    this.bufferAfter = void 0;
    this.codeUnified?.remove();
    this.codeUnified = void 0;
    this.codeDeletions?.remove();
    this.codeDeletions = void 0;
    this.codeAdditions?.remove();
    this.codeAdditions = void 0;
    this.pre?.remove();
    this.pre = void 0;
    this.appliedPreAttributes = void 0;
    this.lastRowCount = void 0;
  }
  clearAuxiliaryNodes() {
    for (const { element } of this.separatorCache.values()) element.parentNode?.removeChild(element);
    this.separatorCache.clear();
    for (const { element } of this.annotationCache.values()) element.parentNode?.removeChild(element);
    this.annotationCache.clear();
    this.gutterUtilityContent?.remove();
    this.gutterUtilityContent = void 0;
  }
  renderPlaceholder(height) {
    if (this.fileContainer == null) return false;
    this.cleanChildNodes();
    if (this.placeHolder == null) {
      const shadowRoot = this.fileContainer.shadowRoot ?? this.fileContainer.attachShadow({ mode: "open" });
      this.placeHolder = document.createElement("div");
      this.placeHolder.dataset.placeholder = "";
      shadowRoot.appendChild(this.placeHolder);
    }
    this.placeHolder.style.setProperty("height", `${height}px`);
    return true;
  }
  cleanChildNodes() {
    this.resizeManager.cleanUp();
    this.scrollSyncManager.cleanUp();
    this.interactionManager.cleanUp();
    this.bufferAfter?.remove();
    this.bufferBefore?.remove();
    this.codeAdditions?.remove();
    this.codeDeletions?.remove();
    this.codeUnified?.remove();
    this.errorWrapper?.remove();
    this.headerElement?.remove();
    this.gutterUtilityContent?.remove();
    this.headerPrefix?.remove();
    this.headerMetadata?.remove();
    this.pre?.remove();
    this.spriteSVG?.remove();
    this.unsafeCSSStyle?.remove();
    this.bufferAfter = void 0;
    this.bufferBefore = void 0;
    this.codeAdditions = void 0;
    this.codeDeletions = void 0;
    this.codeUnified = void 0;
    this.errorWrapper = void 0;
    this.headerElement = void 0;
    this.gutterUtilityContent = void 0;
    this.headerPrefix = void 0;
    this.headerMetadata = void 0;
    this.pre = void 0;
    this.spriteSVG = void 0;
    this.unsafeCSSStyle = void 0;
    this.lastRenderedHeaderHTML = void 0;
    this.lastRowCount = void 0;
  }
  renderSeparators(hunkData) {
    const { hunkSeparators } = this.options;
    if (this.isContainerManaged || this.fileContainer == null || typeof hunkSeparators !== "function") {
      for (const { element } of this.separatorCache.values()) element.parentNode?.removeChild(element);
      this.separatorCache.clear();
      return;
    }
    const staleSeparators = new Map(this.separatorCache);
    for (const hunk of hunkData) {
      const id = hunk.slotName;
      let cache = this.separatorCache.get(id);
      if (cache == null || !areHunkDataEqual(hunk, cache.hunkData)) {
        cache?.element.parentNode?.removeChild(cache.element);
        const element = document.createElement("div");
        element.style.display = "contents";
        element.slot = hunk.slotName;
        element.appendChild(hunkSeparators(hunk, this));
        this.fileContainer.appendChild(element);
        cache = {
          element,
          hunkData: hunk
        };
        this.separatorCache.set(id, cache);
      }
      staleSeparators.delete(id);
    }
    for (const [id, { element }] of staleSeparators.entries()) {
      this.separatorCache.delete(id);
      element.parentNode?.removeChild(element);
    }
  }
  renderAnnotations() {
    if (this.isContainerManaged || this.fileContainer == null) {
      for (const { element } of this.annotationCache.values()) element.parentNode?.removeChild(element);
      this.annotationCache.clear();
      return;
    }
    const staleAnnotations = new Map(this.annotationCache);
    const { renderAnnotation } = this.options;
    if (renderAnnotation != null && this.lineAnnotations.length > 0) for (const [index, annotation] of this.lineAnnotations.entries()) {
      const id = `${index}-${getLineAnnotationName(annotation)}`;
      let cache = this.annotationCache.get(id);
      if (cache == null || !areDiffLineAnnotationsEqual(annotation, cache.annotation)) {
        cache?.element.parentElement?.removeChild(cache.element);
        const content = renderAnnotation(annotation);
        if (content == null) continue;
        cache = {
          element: createAnnotationWrapperNode(getLineAnnotationName(annotation)),
          annotation
        };
        cache.element.appendChild(content);
        this.fileContainer.appendChild(cache.element);
        this.annotationCache.set(id, cache);
      }
      staleAnnotations.delete(id);
    }
    for (const [id, { element }] of staleAnnotations.entries()) {
      this.annotationCache.delete(id);
      element.parentNode?.removeChild(element);
    }
  }
  renderGutterUtility() {
    const renderGutterUtility = this.options.renderGutterUtility ?? this.options.renderHoverUtility;
    if (this.fileContainer == null || renderGutterUtility == null) {
      this.gutterUtilityContent?.remove();
      this.gutterUtilityContent = void 0;
      return;
    }
    const element = renderGutterUtility(this.interactionManager.getHoveredLine);
    if (element != null && this.gutterUtilityContent != null) return;
    else if (element == null) {
      this.gutterUtilityContent?.parentNode?.removeChild(this.gutterUtilityContent);
      this.gutterUtilityContent = void 0;
      return;
    }
    const gutterUtilityContent = createGutterUtilityContentNode();
    gutterUtilityContent.appendChild(element);
    this.fileContainer.appendChild(gutterUtilityContent);
    this.gutterUtilityContent = gutterUtilityContent;
  }
  getOrCreateFileContainer(fileContainer, parentNode) {
    const previousContainer = this.fileContainer;
    this.fileContainer = fileContainer ?? this.fileContainer ?? document.createElement(DIFFS_TAG_NAME);
    if (previousContainer != null && previousContainer !== this.fileContainer) {
      this.lastRenderedHeaderHTML = void 0;
      this.headerElement = void 0;
    }
    if (parentNode != null && this.fileContainer.parentNode !== parentNode) parentNode.appendChild(this.fileContainer);
    if (this.spriteSVG == null) {
      const fragment = document.createElement("div");
      fragment.innerHTML = SVGSpriteSheet;
      const firstChild = fragment.firstChild;
      if (firstChild instanceof SVGElement) {
        this.spriteSVG = firstChild;
        this.fileContainer.shadowRoot?.appendChild(this.spriteSVG);
      }
    }
    return this.fileContainer;
  }
  getFileContainer() {
    return this.fileContainer;
  }
  getOrCreatePreNode(container) {
    const shadowRoot = container.shadowRoot ?? container.attachShadow({ mode: "open" });
    if (this.pre == null) {
      this.pre = document.createElement("pre");
      this.appliedPreAttributes = void 0;
      this.codeUnified = void 0;
      this.codeDeletions = void 0;
      this.codeAdditions = void 0;
      shadowRoot.appendChild(this.pre);
    } else if (this.pre.parentNode !== shadowRoot) {
      shadowRoot.appendChild(this.pre);
      this.appliedPreAttributes = void 0;
    }
    this.placeHolder?.remove();
    this.placeHolder = void 0;
    return this.pre;
  }
  syncCodeNodesFromPre(pre) {
    this.codeUnified = void 0;
    this.codeDeletions = void 0;
    this.codeAdditions = void 0;
    for (const child of Array.from(pre.children)) {
      if (!(child instanceof HTMLElement)) continue;
      if ("unified" in child.dataset) this.codeUnified = child;
      else if ("deletions" in child.dataset) this.codeDeletions = child;
      else if ("additions" in child.dataset) this.codeAdditions = child;
    }
  }
  applyHeaderToDOM(headerAST, container) {
    this.cleanupErrorWrapper();
    this.placeHolder?.remove();
    this.placeHolder = void 0;
    const headerHTML = toHtml(headerAST);
    if (headerHTML !== this.lastRenderedHeaderHTML) {
      const tempDiv = document.createElement("div");
      tempDiv.innerHTML = headerHTML;
      const newHeader = tempDiv.firstElementChild;
      if (!(newHeader instanceof HTMLElement)) return;
      if (this.headerElement != null) container.shadowRoot?.replaceChild(newHeader, this.headerElement);
      else container.shadowRoot?.prepend(newHeader);
      this.headerElement = newHeader;
      this.lastRenderedHeaderHTML = headerHTML;
    }
    if (this.isContainerManaged) return;
    const { renderHeaderPrefix, renderHeaderMetadata } = this.options;
    if (this.headerPrefix != null) this.headerPrefix.parentNode?.removeChild(this.headerPrefix);
    if (this.headerMetadata != null) this.headerMetadata.parentNode?.removeChild(this.headerMetadata);
    const prefix = renderHeaderPrefix?.({
      deletionFile: this.deletionFile,
      additionFile: this.additionFile,
      fileDiff: this.fileDiff
    }) ?? void 0;
    const content = renderHeaderMetadata?.({
      deletionFile: this.deletionFile,
      additionFile: this.additionFile,
      fileDiff: this.fileDiff
    }) ?? void 0;
    if (prefix != null) {
      this.headerPrefix = document.createElement("div");
      this.headerPrefix.slot = HEADER_PREFIX_SLOT_ID;
      if (prefix instanceof Element) this.headerPrefix.appendChild(prefix);
      else this.headerPrefix.innerText = `${prefix}`;
      container.appendChild(this.headerPrefix);
    }
    if (content != null) {
      this.headerMetadata = document.createElement("div");
      this.headerMetadata.slot = HEADER_METADATA_SLOT_ID;
      if (content instanceof Element) this.headerMetadata.appendChild(content);
      else this.headerMetadata.innerText = `${content}`;
      container.appendChild(this.headerMetadata);
    }
  }
  injectUnsafeCSS() {
    if (this.fileContainer?.shadowRoot == null) return;
    const { unsafeCSS } = this.options;
    if (unsafeCSS == null || unsafeCSS === "") return;
    if (this.unsafeCSSStyle == null) {
      this.unsafeCSSStyle = createUnsafeCSSStyleNode();
      this.fileContainer.shadowRoot.appendChild(this.unsafeCSSStyle);
    }
    this.unsafeCSSStyle.innerText = wrapUnsafeCSS(unsafeCSS);
  }
  applyHunksToDOM(pre, result) {
    const { overflow = "scroll" } = this.options;
    const containerSize = (this.options.hunkSeparators ?? "line-info") === "line-info";
    const rowSpan = overflow === "wrap" ? result.rowCount : void 0;
    this.cleanupErrorWrapper();
    this.applyPreNodeAttributes(pre, result);
    let shouldReplace = false;
    const codeElements = [];
    const unifiedAST = this.hunksRenderer.renderCodeAST("unified", result);
    const deletionsAST = this.hunksRenderer.renderCodeAST("deletions", result);
    const additionsAST = this.hunksRenderer.renderCodeAST("additions", result);
    if (unifiedAST != null) {
      shouldReplace = this.codeUnified == null || this.codeAdditions != null || this.codeDeletions != null;
      this.codeDeletions?.remove();
      this.codeDeletions = void 0;
      this.codeAdditions?.remove();
      this.codeAdditions = void 0;
      this.codeUnified = getOrCreateCodeNode({
        code: this.codeUnified,
        columnType: "unified",
        rowSpan,
        containerSize
      });
      this.codeUnified.innerHTML = this.hunksRenderer.renderPartialHTML(unifiedAST);
      codeElements.push(this.codeUnified);
    } else if (deletionsAST != null || additionsAST != null) {
      if (deletionsAST != null) {
        shouldReplace = this.codeDeletions == null || this.codeUnified != null;
        this.codeUnified?.remove();
        this.codeUnified = void 0;
        this.codeDeletions = getOrCreateCodeNode({
          code: this.codeDeletions,
          columnType: "deletions",
          rowSpan,
          containerSize
        });
        this.codeDeletions.innerHTML = this.hunksRenderer.renderPartialHTML(deletionsAST);
        codeElements.push(this.codeDeletions);
      } else {
        this.codeDeletions?.remove();
        this.codeDeletions = void 0;
      }
      if (additionsAST != null) {
        shouldReplace = shouldReplace || this.codeAdditions == null || this.codeUnified != null;
        this.codeUnified?.remove();
        this.codeUnified = void 0;
        this.codeAdditions = getOrCreateCodeNode({
          code: this.codeAdditions,
          columnType: "additions",
          rowSpan,
          containerSize
        });
        this.codeAdditions.innerHTML = this.hunksRenderer.renderPartialHTML(additionsAST);
        codeElements.push(this.codeAdditions);
      } else {
        this.codeAdditions?.remove();
        this.codeAdditions = void 0;
      }
    } else {
      this.codeUnified?.remove();
      this.codeUnified = void 0;
      this.codeDeletions?.remove();
      this.codeDeletions = void 0;
      this.codeAdditions?.remove();
      this.codeAdditions = void 0;
    }
    if (codeElements.length === 0) pre.textContent = "";
    else if (shouldReplace) pre.replaceChildren(...codeElements);
    this.lastRowCount = result.rowCount;
  }
  applyPartialRender({ previousRenderRange, renderRange }) {
    const { pre, codeUnified, codeAdditions, codeDeletions, options: { diffStyle = "split" } } = this;
    if (pre == null || previousRenderRange == null || renderRange == null || !Number.isFinite(previousRenderRange.totalLines) || !Number.isFinite(renderRange.totalLines) || this.lastRowCount == null) return false;
    const codeElements = this.getCodeColumns(diffStyle, codeUnified, codeDeletions, codeAdditions);
    if (codeElements == null) return false;
    const previousStart = previousRenderRange.startingLine;
    const nextStart = renderRange.startingLine;
    const previousEnd = previousStart + previousRenderRange.totalLines;
    const nextEnd = nextStart + renderRange.totalLines;
    const overlapStart = Math.max(previousStart, nextStart);
    const overlapEnd = Math.min(previousEnd, nextEnd);
    if (overlapEnd <= overlapStart) return false;
    const trimStart = Math.max(0, overlapStart - previousStart);
    const trimEnd = Math.max(0, previousEnd - overlapEnd);
    const trimResult = this.trimColumns({
      columns: codeElements,
      trimStart,
      trimEnd,
      previousStart,
      overlapStart,
      overlapEnd,
      diffStyle
    });
    if (trimResult < 0) throw new Error("applyPartialRender: failed to trim to overlap");
    if (this.lastRowCount < trimResult) throw new Error("applyPartialRender: trimmed beyond DOM row count");
    let rowCount = this.lastRowCount - trimResult;
    const renderChunk = (startingLine, totalLines) => {
      if (totalLines <= 0 || this.fileDiff == null) return;
      return this.hunksRenderer.renderDiff(this.fileDiff, {
        startingLine,
        totalLines,
        bufferBefore: 0,
        bufferAfter: 0
      });
    };
    const prependResult = renderChunk(nextStart, Math.max(overlapStart - nextStart, 0));
    if (prependResult == null && nextStart < overlapStart) return false;
    const appendResult = renderChunk(overlapEnd, Math.max(nextEnd - overlapEnd, 0));
    if (appendResult == null && nextEnd > overlapEnd) return false;
    const applyChunk = (result, insertPosition) => {
      if (result == null) return;
      if (diffStyle === "unified" && !Array.isArray(codeElements)) this.insertPartialHTML(diffStyle, codeElements, result, insertPosition);
      else if (diffStyle === "split" && Array.isArray(codeElements)) this.insertPartialHTML(diffStyle, codeElements, result, insertPosition);
      else throw new Error("FileDiff.applyPartialRender.applyChunk: invalid chunk application");
      rowCount += result.rowCount;
    };
    this.cleanupErrorWrapper();
    applyChunk(prependResult, "afterbegin");
    applyChunk(appendResult, "beforeend");
    if (this.lastRowCount !== rowCount) {
      this.applyRowSpan(diffStyle, codeElements, rowCount);
      this.lastRowCount = rowCount;
    }
    return true;
  }
  insertPartialHTML(diffStyle, columns, result, insertPosition) {
    if (diffStyle === "unified" && !Array.isArray(columns)) {
      const unifiedAST = this.hunksRenderer.renderCodeAST("unified", result);
      this.renderPartialColumn(columns, unifiedAST, insertPosition);
    } else if (diffStyle === "split" && Array.isArray(columns)) {
      const deletionsAST = this.hunksRenderer.renderCodeAST("deletions", result);
      const additionsAST = this.hunksRenderer.renderCodeAST("additions", result);
      this.renderPartialColumn(columns[0], deletionsAST, insertPosition);
      this.renderPartialColumn(columns[1], additionsAST, insertPosition);
    } else throw new Error("FileDiff.insertPartialHTML: Invalid argument composition");
  }
  renderPartialColumn(column, ast, insertPosition) {
    if (column == null || ast == null) return;
    const gutterChildren = getElementChildren(ast[0]);
    const contentChildren = getElementChildren(ast[1]);
    if (gutterChildren == null || contentChildren == null) throw new Error("FileDiff.insertPartialHTML: Unexpected AST structure");
    const firstHASTElement = contentChildren.at(0);
    if (insertPosition === "beforeend" && firstHASTElement?.type === "element" && typeof firstHASTElement.properties["data-buffer-size"] === "number") this.mergeBuffersIfNecessary(firstHASTElement.properties["data-buffer-size"], column.content.children[column.content.children.length - 1], column.gutter.children[column.gutter.children.length - 1], gutterChildren, contentChildren, true);
    const lastHASTElement = contentChildren.at(-1);
    if (insertPosition === "afterbegin" && lastHASTElement?.type === "element" && typeof lastHASTElement.properties["data-buffer-size"] === "number") this.mergeBuffersIfNecessary(lastHASTElement.properties["data-buffer-size"], column.content.children[0], column.gutter.children[0], gutterChildren, contentChildren, false);
    column.gutter.insertAdjacentHTML(insertPosition, this.hunksRenderer.renderPartialHTML(gutterChildren));
    column.content.insertAdjacentHTML(insertPosition, this.hunksRenderer.renderPartialHTML(contentChildren));
  }
  mergeBuffersIfNecessary(adjustmentSize, contentElement, gutterElement, gutterChildren, contentChildren, fromStart) {
    if (!(contentElement instanceof HTMLElement) || !(gutterElement instanceof HTMLElement)) return;
    const currentSize = this.getBufferSize(contentElement.dataset);
    if (currentSize == null) return;
    if (fromStart) {
      gutterChildren.shift();
      contentChildren.shift();
    } else {
      gutterChildren.pop();
      contentChildren.pop();
    }
    this.updateBufferSize(contentElement, currentSize + adjustmentSize);
    this.updateBufferSize(gutterElement, currentSize + adjustmentSize);
  }
  applyRowSpan(diffStyle, columns, rowCount) {
    const applySpan = (column) => {
      if (column == null) return;
      column.gutter.style.setProperty("grid-row", `span ${rowCount}`);
      column.content.style.setProperty("grid-row", `span ${rowCount}`);
    };
    if (diffStyle === "unified" && !Array.isArray(columns)) applySpan(columns);
    else if (diffStyle === "split" && Array.isArray(columns)) {
      applySpan(columns[0]);
      applySpan(columns[1]);
    } else throw new Error("dun fuuuuked up");
  }
  trimColumnRows(columns, preTrimCount, postTrimStart) {
    let visibleLineIndex = 0;
    let rowCount = 0;
    let rowIndex = 0;
    let pendingMetadataTrim = false;
    const hasPostTrim = postTrimStart >= 0;
    if (columns == null) return 0;
    const contentChildren = Array.from(columns.content.children);
    const gutterChildren = Array.from(columns.gutter.children);
    if (contentChildren.length !== gutterChildren.length) throw new Error("FileDiff.trimColumnRows: columns do not match");
    while (rowIndex < contentChildren.length) {
      if (preTrimCount <= 0 && !hasPostTrim && !pendingMetadataTrim) break;
      const gutterElement = gutterChildren[rowIndex];
      const contentElement = contentChildren[rowIndex];
      rowIndex++;
      if (!(gutterElement instanceof HTMLElement) || !(contentElement instanceof HTMLElement)) {
        console.error({
          gutterElement,
          contentElement
        });
        throw new Error("FileDiff.trimColumnRows: invalid row elements");
      }
      if (pendingMetadataTrim) {
        pendingMetadataTrim = false;
        if (gutterElement.dataset.gutterBuffer === "annotation" && "lineAnnotation" in contentElement.dataset || gutterElement.dataset.gutterBuffer === "metadata" && "noNewline" in contentElement.dataset) {
          gutterElement.remove();
          contentElement.remove();
          rowCount++;
          continue;
        }
      }
      if ("lineIndex" in gutterElement.dataset && "lineIndex" in contentElement.dataset) {
        if (preTrimCount > 0 || hasPostTrim && visibleLineIndex >= postTrimStart) {
          gutterElement.remove();
          contentElement.remove();
          if (preTrimCount > 0) {
            preTrimCount--;
            if (preTrimCount === 0) pendingMetadataTrim = true;
          }
          rowCount++;
        }
        visibleLineIndex++;
        continue;
      }
      if ("separator" in gutterElement.dataset && "separator" in contentElement.dataset) {
        if (preTrimCount > 0 || hasPostTrim && visibleLineIndex >= postTrimStart) {
          gutterElement.remove();
          contentElement.remove();
          rowCount++;
        }
        continue;
      }
      if (gutterElement.dataset.gutterBuffer === "annotation" && "lineAnnotation" in contentElement.dataset) {
        if (preTrimCount > 0 || hasPostTrim && visibleLineIndex >= postTrimStart) {
          gutterElement.remove();
          contentElement.remove();
          rowCount++;
        }
        continue;
      }
      if (gutterElement.dataset.gutterBuffer === "metadata" && "noNewline" in contentElement.dataset) {
        if (preTrimCount > 0 || hasPostTrim && visibleLineIndex >= postTrimStart) {
          gutterElement.remove();
          contentElement.remove();
          rowCount++;
        }
        continue;
      }
      if (gutterElement.dataset.gutterBuffer === "buffer" && "contentBuffer" in contentElement.dataset) {
        const totalRows = this.getBufferSize(contentElement.dataset);
        if (totalRows == null) throw new Error("FileDiff.trimColumnRows: invalid element");
        if (preTrimCount > 0) {
          const rowsToRemove = Math.min(preTrimCount, totalRows);
          const newSize = totalRows - rowsToRemove;
          if (newSize > 0) {
            this.updateBufferSize(gutterElement, newSize);
            this.updateBufferSize(contentElement, newSize);
            rowCount += rowsToRemove;
          } else {
            gutterElement.remove();
            contentElement.remove();
            rowCount += totalRows;
          }
          preTrimCount -= rowsToRemove;
        } else if (hasPostTrim) {
          const bufferStart = visibleLineIndex;
          const bufferEnd = visibleLineIndex + totalRows - 1;
          if (postTrimStart <= bufferStart) {
            gutterElement.remove();
            contentElement.remove();
            rowCount += totalRows;
          } else if (postTrimStart <= bufferEnd) {
            const rowsToRemove = bufferEnd - postTrimStart + 1;
            const newSize = totalRows - rowsToRemove;
            this.updateBufferSize(gutterElement, newSize);
            this.updateBufferSize(contentElement, newSize);
            rowCount += rowsToRemove;
          }
        }
        visibleLineIndex += totalRows;
        continue;
      }
      console.error({
        gutterElement,
        contentElement
      });
      throw new Error("FileDiff.trimColumnRows: unknown row elements");
    }
    return rowCount;
  }
  trimColumns({ columns, diffStyle, overlapEnd, overlapStart, previousStart, trimEnd, trimStart }) {
    const preTrimCount = Math.max(0, overlapStart - previousStart);
    const postTrimStart = overlapEnd - previousStart;
    if (postTrimStart < 0) throw new Error("FileDiff.trimColumns: overlap ends before previous");
    const shouldTrimStart = trimStart > 0;
    const shouldTrimEnd = trimEnd > 0;
    if (!shouldTrimStart && !shouldTrimEnd) return 0;
    const effectivePreTrimCount = shouldTrimStart ? preTrimCount : 0;
    const effectivePostTrimStart = shouldTrimEnd ? postTrimStart : -1;
    if (diffStyle === "unified" && !Array.isArray(columns)) return this.trimColumnRows(columns, effectivePreTrimCount, effectivePostTrimStart);
    else if (diffStyle === "split" && Array.isArray(columns)) {
      const deletionsTrim = this.trimColumnRows(columns[0], effectivePreTrimCount, effectivePostTrimStart);
      const additionsTrim = this.trimColumnRows(columns[1], effectivePreTrimCount, effectivePostTrimStart);
      if (columns[0] != null && columns[1] != null && deletionsTrim !== additionsTrim) throw new Error("FileDiff.trimColumns: split columns out of sync");
      return columns[0] != null ? deletionsTrim : additionsTrim;
    } else {
      console.error({
        diffStyle,
        columns
      });
      throw new Error("FileDiff.trimColumns: Invalid columns for diffType");
    }
  }
  getBufferSize(properties) {
    const parsed = Number.parseInt(properties?.bufferSize ?? "", 10);
    return Number.isNaN(parsed) ? void 0 : parsed;
  }
  updateBufferSize(element, size) {
    element.dataset.bufferSize = `${size}`;
    element.style.setProperty("grid-row", `span ${size}`);
    element.style.setProperty("min-height", `calc(${size} * 1lh)`);
  }
  getCodeColumns(diffStyle, codeUnified, codeDeletions, codeAdditions) {
    function getColumns(code) {
      if (code == null) return;
      const gutter = code.children[0];
      const content = code.children[1];
      if (!(gutter instanceof HTMLElement) || !(content instanceof HTMLElement) || gutter.dataset.gutter == null || content.dataset.content == null) return;
      return {
        gutter,
        content
      };
    }
    if (diffStyle === "unified") return getColumns(codeUnified);
    else {
      const deletions = getColumns(codeDeletions);
      const additions = getColumns(codeAdditions);
      return deletions != null || additions != null ? [deletions, additions] : void 0;
    }
  }
  applyBuffers(pre, renderRange) {
    const { disableVirtualizationBuffers = false } = this.options;
    if (disableVirtualizationBuffers || renderRange == null) {
      if (this.bufferBefore != null) {
        this.bufferBefore.parentNode?.removeChild(this.bufferBefore);
        this.bufferBefore = void 0;
      }
      if (this.bufferAfter != null) {
        this.bufferAfter.parentNode?.removeChild(this.bufferAfter);
        this.bufferAfter = void 0;
      }
      return;
    }
    if (renderRange.bufferBefore > 0) {
      if (this.bufferBefore == null) {
        this.bufferBefore = document.createElement("div");
        this.bufferBefore.dataset.virtualizerBuffer = "before";
        pre.before(this.bufferBefore);
      }
      this.bufferBefore.style.setProperty("height", `${renderRange.bufferBefore}px`);
      this.bufferBefore.style.setProperty("contain", "strict");
    } else if (this.bufferBefore != null) {
      this.bufferBefore.parentNode?.removeChild(this.bufferBefore);
      this.bufferBefore = void 0;
    }
    if (renderRange.bufferAfter > 0) {
      if (this.bufferAfter == null) {
        this.bufferAfter = document.createElement("div");
        this.bufferAfter.dataset.virtualizerBuffer = "after";
        pre.after(this.bufferAfter);
      }
      this.bufferAfter.style.setProperty("height", `${renderRange.bufferAfter}px`);
      this.bufferAfter.style.setProperty("contain", "strict");
    } else if (this.bufferAfter != null) {
      this.bufferAfter.parentNode?.removeChild(this.bufferAfter);
      this.bufferAfter = void 0;
    }
  }
  applyPreNodeAttributes(pre, { themeStyles, baseThemeType, additionsContentAST, deletionsContentAST, totalLines }) {
    const { diffIndicators = "bars", disableBackground = false, disableLineNumbers = false, overflow = "scroll", themeType = "system", diffStyle = "split" } = this.options;
    const preProperties = {
      type: "diff",
      diffIndicators,
      disableBackground,
      disableLineNumbers,
      overflow,
      split: diffStyle === "unified" ? false : additionsContentAST != null && deletionsContentAST != null,
      themeStyles,
      themeType: baseThemeType ?? themeType,
      totalLines
    };
    if (arePrePropertiesEqual(preProperties, this.appliedPreAttributes)) return;
    setPreNodeProperties(pre, preProperties);
    this.appliedPreAttributes = preProperties;
  }
  applyErrorToDOM(error, container) {
    this.cleanupErrorWrapper();
    const pre = this.getOrCreatePreNode(container);
    pre.innerHTML = "";
    pre.parentNode?.removeChild(pre);
    this.pre = void 0;
    this.appliedPreAttributes = void 0;
    const shadowRoot = container.shadowRoot ?? container.attachShadow({ mode: "open" });
    this.errorWrapper ??= document.createElement("div");
    this.errorWrapper.dataset.errorWrapper = "";
    this.errorWrapper.innerHTML = "";
    shadowRoot.appendChild(this.errorWrapper);
    const errorMessage = document.createElement("div");
    errorMessage.dataset.errorMessage = "";
    errorMessage.innerText = error.message;
    this.errorWrapper.appendChild(errorMessage);
    const errorStack = document.createElement("pre");
    errorStack.dataset.errorStack = "";
    errorStack.innerText = error.stack ?? "No Error Stack";
    this.errorWrapper.appendChild(errorStack);
  }
  cleanupErrorWrapper() {
    this.errorWrapper?.parentNode?.removeChild(this.errorWrapper);
    this.errorWrapper = void 0;
  }
};
function getElementChildren(node) {
  if (node == null || node.type !== "element") return;
  return node.children ?? [];
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/managers/UniversalRenderingManager.js
var queuedCallbacks = /* @__PURE__ */ new Set();
var callbacks = /* @__PURE__ */ new Set();
var frameId = null;
var isRendering = false;
function queueRender(callback) {
  if (isRendering) {
    queuedCallbacks.add(callback);
    return;
  }
  callbacks.add(callback);
  frameId ??= requestAnimationFrame(render);
}
function render(time) {
  isRendering = true;
  for (const callback of callbacks) try {
    callback(time);
  } catch (error) {
    console.error(error);
  }
  callbacks.clear();
  if (queuedCallbacks.size > 0) {
    callbacks = new Set(queuedCallbacks);
    queuedCallbacks.clear();
    frameId = requestAnimationFrame(render);
  } else frameId = null;
  isRendering = false;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/shiki-stream/tokenizer.js
var ShikiStreamTokenizer = class ShikiStreamTokenizer2 {
  options;
  tokensStable = [];
  tokensUnstable = [];
  lastUnstableCodeChunk = "";
  lastStableGrammarState;
  constructor(options) {
    this.options = options;
  }
  /**
  * Enqueue a chunk of code to the buffer.
  */
  async enqueue(chunk) {
    const chunkLines = (this.lastUnstableCodeChunk + chunk).split("\n");
    const stable = [];
    let unstable = [];
    const recall = this.tokensUnstable.length;
    chunkLines.forEach((line, i) => {
      const isLastLine = i === chunkLines.length - 1;
      const result = this.options.highlighter.codeToTokens(line, {
        ...this.options,
        grammarState: this.lastStableGrammarState
      });
      const tokens = result.tokens[0];
      if (!isLastLine) tokens.push({
        content: "\n",
        offset: 0
      });
      if (!isLastLine) {
        this.lastStableGrammarState = result.grammarState;
        stable.push(...tokens);
      } else {
        unstable = tokens;
        this.lastUnstableCodeChunk = line;
      }
    });
    this.tokensStable.push(...stable);
    this.tokensUnstable = unstable;
    return {
      recall,
      stable,
      unstable
    };
  }
  close() {
    const stable = this.tokensUnstable;
    this.tokensUnstable = [];
    this.lastUnstableCodeChunk = "";
    this.lastStableGrammarState = void 0;
    return { stable };
  }
  clear() {
    this.tokensStable = [];
    this.tokensUnstable = [];
    this.lastUnstableCodeChunk = "";
    this.lastStableGrammarState = void 0;
  }
  clone() {
    const clone = new ShikiStreamTokenizer2(this.options);
    clone.lastUnstableCodeChunk = this.lastUnstableCodeChunk;
    clone.tokensUnstable = this.tokensUnstable;
    clone.tokensStable = this.tokensStable;
    clone.lastStableGrammarState = this.lastStableGrammarState;
    return clone;
  }
};

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/shiki-stream/stream.js
var CodeToTokenTransformStream = class extends TransformStream {
  tokenizer;
  options;
  constructor(options) {
    const tokenizer = new ShikiStreamTokenizer(options);
    const { allowRecalls = false } = options;
    super({
      async transform(chunk, controller) {
        const { stable, unstable: buffer, recall } = await tokenizer.enqueue(chunk);
        if (allowRecalls && recall > 0) controller.enqueue({ recall });
        for (const token of stable) controller.enqueue(token);
        if (allowRecalls) for (const token of buffer) controller.enqueue(token);
      },
      async flush(controller) {
        const { stable } = tokenizer.close();
        if (!allowRecalls) for (const token of stable) controller.enqueue(token);
      }
    });
    this.tokenizer = tokenizer;
    this.options = options;
  }
};

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/createSpanNodeFromToken.js
function createSpanFromToken(token) {
  const element = document.createElement("span");
  element.style = stringifyTokenStyle(token.htmlStyle ?? getTokenStyleObject(token));
  element.textContent = token.content;
  return element;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/components/FileStream.js
var instanceId5 = -1;
var FileStream = class {
  __id = `file-stream:${++instanceId5}`;
  highlighter;
  stream;
  abortController;
  fileContainer;
  pre;
  code;
  gutterElement;
  contentElement;
  currentRowCount = 0;
  constructor(options = { theme: DEFAULT_THEMES }) {
    this.options = options;
    this.currentLineIndex = this.options.startingLineIndex ?? 1;
  }
  cleanUp() {
    this.abortController?.abort();
    this.abortController = void 0;
  }
  setThemeType(themeType) {
    if ((this.options.themeType ?? "system") === themeType) return;
    this.options = {
      ...this.options,
      themeType
    };
    if (this.pre != null) switch (themeType) {
      case "system":
        delete this.pre.dataset.themeType;
        break;
      case "light":
      case "dark":
        this.pre.dataset.themeType = themeType;
        break;
    }
  }
  async initializeHighlighter() {
    this.highlighter = await getSharedHighlighter(getHighlighterOptions(this.options.lang, this.options));
    return this.highlighter;
  }
  queuedSetupArgs;
  async setup(_source, _wrapper) {
    const isSettingUp = this.queuedSetupArgs != null;
    this.queuedSetupArgs = [_source, _wrapper];
    if (isSettingUp) return;
    this.highlighter ??= await this.initializeHighlighter();
    const [source, wrapper] = this.queuedSetupArgs;
    this.queuedSetupArgs = void 0;
    const stream = source;
    this.setupStream(stream, wrapper, this.highlighter);
  }
  setupStream(stream, wrapper, highlighter) {
    const { disableLineNumbers = false, overflow = "scroll", theme = DEFAULT_THEMES, themeType = "system" } = this.options;
    const fileContainer = this.getOrCreateFileContainer();
    if (fileContainer.parentElement == null) wrapper.appendChild(fileContainer);
    this.pre ??= document.createElement("pre");
    if (this.pre.parentElement == null) fileContainer.shadowRoot?.appendChild(this.pre);
    const themeStyles = getHighlighterThemeStyles({
      theme,
      highlighter
    });
    const baseThemeType = typeof theme === "string" ? highlighter.getTheme(theme).type : void 0;
    const pre = setPreNodeProperties(this.pre, {
      type: "file",
      diffIndicators: "none",
      disableBackground: true,
      disableLineNumbers,
      overflow,
      split: false,
      themeType: baseThemeType ?? themeType,
      themeStyles,
      totalLines: 0
    });
    pre.innerHTML = "";
    this.pre = pre;
    this.code = getOrCreateCodeNode({
      code: this.code,
      pre
    });
    this.gutterElement = void 0;
    this.contentElement = void 0;
    this.currentRowCount = 0;
    this.currentLineElement = void 0;
    this.currentLineIndex = this.options.startingLineIndex ?? 1;
    this.abortController?.abort();
    this.abortController = new AbortController();
    const { onStreamStart, onStreamClose, onStreamAbort } = this.options;
    this.stream = stream;
    this.stream.pipeThrough(typeof theme === "string" ? new CodeToTokenTransformStream({
      ...this.options,
      theme,
      highlighter,
      allowRecalls: true,
      defaultColor: false,
      cssVariablePrefix: formatCSSVariablePrefix("token")
    }) : new CodeToTokenTransformStream({
      ...this.options,
      themes: theme,
      highlighter,
      allowRecalls: true,
      defaultColor: false,
      cssVariablePrefix: formatCSSVariablePrefix("token")
    })).pipeTo(new WritableStream({
      start(controller) {
        onStreamStart?.(controller);
      },
      close() {
        onStreamClose?.();
      },
      abort(reason) {
        onStreamAbort?.(reason);
      },
      write: this.handleWrite
    }), { signal: this.abortController.signal }).catch((error) => {
      if (error.name !== "AbortError") console.error("FileStream pipe error:", error);
    });
  }
  queuedTokens = [];
  handleWrite = (token) => {
    if ("recall" in token && this.queuedTokens.length >= token.recall) this.queuedTokens.length = this.queuedTokens.length - token.recall;
    else this.queuedTokens.push(token);
    queueRender(this.render);
    this.options.onStreamWrite?.(token);
  };
  currentLineIndex;
  currentLineElement;
  render = () => {
    this.options.onPreRender?.(this);
    const { gutter, content } = this.getOrCreateStreamColumns();
    const gutterFragment = document.createDocumentFragment();
    const contentFragment = document.createDocumentFragment();
    for (const token of this.queuedTokens) if ("recall" in token) {
      if (this.currentLineElement == null) throw new Error("FileStream.render: no current line element, shouldnt be possible to get here");
      if (token.recall > this.currentLineElement.childNodes.length) throw new Error(`FileStream.render: Token recall exceed the current line, there's probably a bug...`);
      for (let i = 0; i < token.recall; i++) this.currentLineElement.lastChild?.remove();
    } else {
      const span = createSpanFromToken(token);
      if (this.currentLineElement == null) {
        const { gutterLine, contentLine } = this.createLine();
        gutterFragment.appendChild(gutterLine);
        contentFragment.appendChild(contentLine);
      }
      this.currentLineElement?.appendChild(span);
      if (token.content === "\n") {
        this.currentLineIndex++;
        const { gutterLine, contentLine } = this.createLine();
        gutterFragment.appendChild(gutterLine);
        contentFragment.appendChild(contentLine);
      }
    }
    if (gutterFragment.childNodes.length > 0) gutter.appendChild(gutterFragment);
    if (contentFragment.childNodes.length > 0) content.appendChild(contentFragment);
    this.queuedTokens.length = 0;
    this.options.onPostRender?.(this);
  };
  getOrCreateStreamColumns() {
    if (this.code == null) throw new Error("FileStream: expected code element to exist");
    if (this.gutterElement != null && this.contentElement != null) return {
      gutter: this.gutterElement,
      content: this.contentElement
    };
    const gutter = document.createElement("div");
    gutter.dataset.gutter = "";
    const content = document.createElement("div");
    content.dataset.content = "";
    this.code.appendChild(gutter);
    this.code.appendChild(content);
    this.gutterElement = gutter;
    this.contentElement = content;
    return {
      gutter,
      content
    };
  }
  updateRowSpan() {
    if (this.gutterElement != null) this.gutterElement.style.gridRow = `span ${this.currentRowCount}`;
    if (this.contentElement != null) this.contentElement.style.gridRow = `span ${this.currentRowCount}`;
  }
  createLine() {
    const lineNumber = this.currentLineIndex;
    const lineIndex = `${lineNumber - 1}`;
    const gutterLine = document.createElement("div");
    gutterLine.dataset.columnNumber = `${lineNumber}`;
    gutterLine.dataset.lineType = "context";
    gutterLine.dataset.lineIndex = lineIndex;
    const numberContent = document.createElement("span");
    numberContent.dataset.lineNumberContent = "";
    numberContent.textContent = `${lineNumber}`;
    gutterLine.appendChild(numberContent);
    const contentLine = document.createElement("div");
    contentLine.dataset.line = `${lineNumber}`;
    contentLine.dataset.lineType = "context";
    contentLine.dataset.lineIndex = lineIndex;
    this.currentRowCount += 1;
    this.updateRowSpan();
    this.currentLineElement = contentLine;
    return {
      gutterLine,
      contentLine
    };
  }
  getOrCreateFileContainer(fileContainer) {
    if (fileContainer != null && fileContainer === this.fileContainer || fileContainer == null && this.fileContainer != null) return this.fileContainer;
    this.fileContainer = fileContainer ?? document.createElement(DIFFS_TAG_NAME);
    return this.fileContainer;
  }
};

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/components/VirtualizedFile.js
var instanceId6 = -1;
var VirtualizedFile = class extends File {
  __id = `virtualized-file:${++instanceId6}`;
  top;
  height = 0;
  heightCache = /* @__PURE__ */ new Map();
  isVisible = false;
  constructor(options, virtualizer, metrics = DEFAULT_VIRTUAL_FILE_METRICS, workerManager, isContainerManaged = false) {
    super(options, workerManager, isContainerManaged);
    this.virtualizer = virtualizer;
    this.metrics = metrics;
  }
  getLineHeight(lineIndex, hasMetadataLine = false) {
    const cached = this.heightCache.get(lineIndex);
    if (cached != null) return cached;
    const multiplier = hasMetadataLine ? 2 : 1;
    return this.metrics.lineHeight * multiplier;
  }
  setOptions(options) {
    if (options == null) return;
    const previousOverflow = this.options.overflow;
    const previousCollapsed = this.options.collapsed;
    super.setOptions(options);
    if (previousOverflow !== this.options.overflow || previousCollapsed !== this.options.collapsed) {
      this.heightCache.clear();
      this.computeApproximateSize();
      this.renderRange = void 0;
    }
    this.virtualizer.instanceChanged(this);
  }
  reconcileHeights() {
    if (this.fileContainer == null || this.file == null) {
      this.height = 0;
      return;
    }
    const { overflow = "scroll" } = this.options;
    this.top = this.virtualizer.getOffsetInScrollContainer(this.fileContainer);
    if (overflow === "scroll" && this.lineAnnotations.length === 0 && !this.virtualizer.config.resizeDebugging) return;
    let hasLineHeightChange = false;
    if (this.code == null) return;
    const content = this.code.children[1];
    if (!(content instanceof HTMLElement)) return;
    for (const line of content.children) {
      if (!(line instanceof HTMLElement)) continue;
      const lineIndexAttr = line.dataset.lineIndex;
      if (lineIndexAttr == null) continue;
      const lineIndex = Number(lineIndexAttr);
      let measuredHeight = line.getBoundingClientRect().height;
      let hasMetadata = false;
      if (line.nextElementSibling instanceof HTMLElement && ("lineAnnotation" in line.nextElementSibling.dataset || "noNewline" in line.nextElementSibling.dataset)) {
        if ("noNewline" in line.nextElementSibling.dataset) hasMetadata = true;
        measuredHeight += line.nextElementSibling.getBoundingClientRect().height;
      }
      const expectedHeight = this.getLineHeight(lineIndex, hasMetadata);
      if (measuredHeight === expectedHeight) continue;
      hasLineHeightChange = true;
      if (measuredHeight === this.metrics.lineHeight * (hasMetadata ? 2 : 1)) this.heightCache.delete(lineIndex);
      else this.heightCache.set(lineIndex, measuredHeight);
    }
    if (hasLineHeightChange || this.virtualizer.config.resizeDebugging) this.computeApproximateSize();
  }
  onRender = (dirty) => {
    if (this.fileContainer == null || this.file == null) return false;
    if (dirty) this.top = this.virtualizer.getOffsetInScrollContainer(this.fileContainer);
    return this.render({ file: this.file });
  };
  cleanUp() {
    if (this.fileContainer != null) this.virtualizer.disconnect(this.fileContainer);
    super.cleanUp();
  }
  computeApproximateSize() {
    const isFirstCompute = this.height === 0;
    this.height = 0;
    if (this.file == null) return;
    const { disableFileHeader = false, collapsed = false, overflow = "scroll" } = this.options;
    const { diffHeaderHeight, fileGap, lineHeight } = this.metrics;
    const lines = this.getOrCreateLineCache(this.file);
    if (!disableFileHeader) this.height += diffHeaderHeight;
    else this.height += fileGap;
    if (collapsed) return;
    if (overflow === "scroll" && this.lineAnnotations.length === 0) this.height += this.getOrCreateLineCache(this.file).length * lineHeight;
    else iterateOverFile({
      lines,
      callback: ({ lineIndex }) => {
        this.height += this.getLineHeight(lineIndex, false);
      }
    });
    if (lines.length > 0) this.height += fileGap;
    if (this.fileContainer != null && this.virtualizer.config.resizeDebugging && !isFirstCompute) {
      const rect = this.fileContainer.getBoundingClientRect();
      if (rect.height !== this.height) console.log("VirtualizedFile.computeApproximateSize: computed height doesnt match", {
        name: this.file.name,
        elementHeight: rect.height,
        computedHeight: this.height
      });
      else console.log("VirtualizedFile.computeApproximateSize: computed height IS CORRECT");
    }
  }
  setVisibility(visible) {
    if (this.fileContainer == null) return;
    if (visible && !this.isVisible) {
      this.top = this.virtualizer.getOffsetInScrollContainer(this.fileContainer);
      this.isVisible = true;
    } else if (!visible && this.isVisible) {
      this.isVisible = false;
      this.rerender();
    }
  }
  render({ fileContainer, file, ...props }) {
    const isFirstRender = this.fileContainer == null;
    this.file ??= file;
    fileContainer = this.getOrCreateFileContainerNode(fileContainer);
    if (this.file == null) {
      console.error("VirtualizedFile.render: attempting to virtually render when we dont have file");
      return false;
    }
    if (isFirstRender) {
      this.computeApproximateSize();
      this.virtualizer.connect(fileContainer, this);
      this.top ??= this.virtualizer.getOffsetInScrollContainer(fileContainer);
      this.isVisible = this.virtualizer.isInstanceVisible(this.top, this.height);
    } else this.top ??= this.virtualizer.getOffsetInScrollContainer(fileContainer);
    if (!this.isVisible) return this.renderPlaceholder(this.height);
    const windowSpecs = this.virtualizer.getWindowSpecs();
    const renderRange = this.computeRenderRangeFromWindow(this.file, this.top, windowSpecs);
    return super.render({
      file: this.file,
      fileContainer,
      renderRange,
      ...props
    });
  }
  computeRenderRangeFromWindow(file, fileTop, { top, bottom }) {
    const { disableFileHeader = false, overflow = "scroll" } = this.options;
    const { diffHeaderHeight, fileGap, hunkLineCount, lineHeight } = this.metrics;
    const lines = this.getOrCreateLineCache(file);
    const lineCount = lines.length;
    const fileHeight = this.height;
    const headerRegion = disableFileHeader ? fileGap : diffHeaderHeight;
    if (fileTop < top - fileHeight || fileTop > bottom) return {
      startingLine: 0,
      totalLines: 0,
      bufferBefore: 0,
      bufferAfter: fileHeight - headerRegion - fileGap
    };
    if (lineCount <= hunkLineCount) return {
      startingLine: 0,
      totalLines: hunkLineCount,
      bufferBefore: 0,
      bufferAfter: 0
    };
    const estimatedTargetLines = Math.ceil(Math.max(bottom - top, 0) / lineHeight);
    const totalLines = Math.ceil(estimatedTargetLines / hunkLineCount) * hunkLineCount + hunkLineCount * 2;
    const totalHunks = totalLines / hunkLineCount;
    const viewportCenter = (top + bottom) / 2;
    if (overflow === "scroll" && this.lineAnnotations.length === 0) {
      const centerLine = Math.floor((viewportCenter - (fileTop + headerRegion)) / lineHeight);
      const idealStartHunk$1 = Math.floor(centerLine / hunkLineCount) - Math.floor(totalHunks / 2);
      const totalHunksInFile = Math.ceil(lineCount / hunkLineCount);
      const startingLine$1 = Math.max(0, Math.min(idealStartHunk$1, totalHunksInFile)) * hunkLineCount;
      const clampedTotalLines$1 = idealStartHunk$1 < 0 ? totalLines + idealStartHunk$1 * hunkLineCount : totalLines;
      const bufferBefore$1 = startingLine$1 * lineHeight;
      const renderedLines = Math.min(clampedTotalLines$1, lineCount - startingLine$1);
      return {
        startingLine: startingLine$1,
        totalLines: clampedTotalLines$1,
        bufferBefore: bufferBefore$1,
        bufferAfter: Math.max(0, (lineCount - startingLine$1 - renderedLines) * lineHeight)
      };
    }
    const overflowHunks = totalHunks;
    const hunkOffsets = [];
    let absoluteLineTop = fileTop + headerRegion;
    let currentLine = 0;
    let firstVisibleHunk;
    let centerHunk;
    let overflowCounter;
    iterateOverFile({
      lines,
      callback: ({ lineIndex }) => {
        const isAtHunkBoundary = currentLine % hunkLineCount === 0;
        if (isAtHunkBoundary) {
          hunkOffsets.push(absoluteLineTop - (fileTop + headerRegion));
          if (overflowCounter != null) {
            if (overflowCounter <= 0) return true;
            overflowCounter--;
          }
        }
        const lineHeight$1 = this.getLineHeight(lineIndex, false);
        const currentHunk = Math.floor(currentLine / hunkLineCount);
        if (absoluteLineTop > top - lineHeight$1 && absoluteLineTop < bottom) firstVisibleHunk ??= currentHunk;
        if (absoluteLineTop + lineHeight$1 > viewportCenter) centerHunk ??= currentHunk;
        if (overflowCounter == null && absoluteLineTop >= bottom && isAtHunkBoundary) overflowCounter = overflowHunks;
        currentLine++;
        absoluteLineTop += lineHeight$1;
        return false;
      }
    });
    if (firstVisibleHunk == null) return {
      startingLine: 0,
      totalLines: 0,
      bufferBefore: 0,
      bufferAfter: fileHeight - headerRegion - fileGap
    };
    const collectedHunks = hunkOffsets.length;
    centerHunk ??= firstVisibleHunk;
    const idealStartHunk = Math.round(centerHunk - totalHunks / 2);
    const maxStartHunk = Math.max(0, collectedHunks - totalHunks);
    const startHunk = Math.max(0, Math.min(idealStartHunk, maxStartHunk));
    const startingLine = startHunk * hunkLineCount;
    const clampedTotalLines = idealStartHunk < 0 ? totalLines + idealStartHunk * hunkLineCount : totalLines;
    const bufferBefore = hunkOffsets[startHunk] ?? 0;
    const finalHunkIndex = startHunk + clampedTotalLines / hunkLineCount;
    return {
      startingLine,
      totalLines: clampedTotalLines,
      bufferBefore,
      bufferAfter: finalHunkIndex < hunkOffsets.length ? fileHeight - headerRegion - hunkOffsets[finalHunkIndex] - fileGap : fileHeight - (absoluteLineTop - fileTop) - fileGap
    };
  }
};

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/resolveVirtualFileMetrics.js
function resolveVirtualFileMetrics(hunkSeparators, metricsOverride) {
  const metrics = {
    ...DEFAULT_VIRTUAL_FILE_METRICS,
    ...metricsOverride
  };
  metrics.hunkSeparatorHeight = getHunkSeparatorHeight(hunkSeparators, metricsOverride?.hunkSeparatorHeight);
  return metrics;
}
function getHunkSeparatorHeight(type, customHeight) {
  if (customHeight != null) return customHeight;
  switch (type) {
    case "simple":
      return 4;
    case "metadata":
    case "line-info":
    case "line-info-basic":
    case "custom":
      return 32;
  }
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/components/VirtualizedFileDiff.js
var instanceId7 = -1;
var VirtualizedFileDiff = class extends FileDiff {
  __id = `little-virtualized-file-diff:${++instanceId7}`;
  top;
  height = 0;
  metrics;
  heightCache = /* @__PURE__ */ new Map();
  isVisible = false;
  virtualizer;
  constructor(options, virtualizer, metrics, workerManager, isContainerManaged = false) {
    super(options, workerManager, isContainerManaged);
    const { hunkSeparators = "line-info" } = this.options;
    this.virtualizer = virtualizer;
    this.metrics = resolveVirtualFileMetrics(typeof hunkSeparators === "function" ? "custom" : hunkSeparators, metrics);
  }
  getLineHeight(lineIndex, hasMetadataLine = false) {
    const cached = this.heightCache.get(lineIndex);
    if (cached != null) return cached;
    const multiplier = hasMetadataLine ? 2 : 1;
    return this.metrics.lineHeight * multiplier;
  }
  setOptions(options) {
    if (options == null) return;
    const previousDiffStyle = this.options.diffStyle;
    const previousOverflow = this.options.overflow;
    const previousCollapsed = this.options.collapsed;
    super.setOptions(options);
    if (previousDiffStyle !== this.options.diffStyle || previousOverflow !== this.options.overflow || previousCollapsed !== this.options.collapsed) {
      this.heightCache.clear();
      this.computeApproximateSize();
      this.renderRange = void 0;
    }
    this.virtualizer.instanceChanged(this);
  }
  reconcileHeights() {
    const { overflow = "scroll" } = this.options;
    if (this.fileContainer != null) this.top = this.virtualizer.getOffsetInScrollContainer(this.fileContainer);
    if (this.fileContainer == null || this.fileDiff == null) {
      this.height = 0;
      return;
    }
    if (overflow === "scroll" && this.lineAnnotations.length === 0 && !this.virtualizer.config.resizeDebugging) return;
    const diffStyle = this.getDiffStyle();
    let hasLineHeightChange = false;
    const codeGroups = diffStyle === "split" ? [this.codeDeletions, this.codeAdditions] : [this.codeUnified];
    for (const codeGroup of codeGroups) {
      if (codeGroup == null) continue;
      const content = codeGroup.children[1];
      if (!(content instanceof HTMLElement)) continue;
      for (const line of content.children) {
        if (!(line instanceof HTMLElement)) continue;
        const lineIndexAttr = line.dataset.lineIndex;
        if (lineIndexAttr == null) continue;
        const lineIndex = parseLineIndex(lineIndexAttr, diffStyle);
        let measuredHeight = line.getBoundingClientRect().height;
        let hasMetadata = false;
        if (line.nextElementSibling instanceof HTMLElement && ("lineAnnotation" in line.nextElementSibling.dataset || "noNewline" in line.nextElementSibling.dataset)) {
          if ("noNewline" in line.nextElementSibling.dataset) hasMetadata = true;
          measuredHeight += line.nextElementSibling.getBoundingClientRect().height;
        }
        const expectedHeight = this.getLineHeight(lineIndex, hasMetadata);
        if (measuredHeight === expectedHeight) continue;
        hasLineHeightChange = true;
        if (measuredHeight === this.metrics.lineHeight * (hasMetadata ? 2 : 1)) this.heightCache.delete(lineIndex);
        else this.heightCache.set(lineIndex, measuredHeight);
      }
    }
    if (hasLineHeightChange || this.virtualizer.config.resizeDebugging) this.computeApproximateSize();
  }
  onRender = (dirty) => {
    if (this.fileContainer == null) return false;
    if (dirty) this.top = this.virtualizer.getOffsetInScrollContainer(this.fileContainer);
    return this.render();
  };
  cleanUp() {
    if (this.fileContainer != null) this.virtualizer.disconnect(this.fileContainer);
    super.cleanUp();
  }
  expandHunk(hunkIndex, direction) {
    this.hunksRenderer.expandHunk(hunkIndex, direction);
    this.computeApproximateSize();
    this.renderRange = void 0;
    this.virtualizer.instanceChanged(this);
  }
  expandHunkFully(hunkIndex) {
    this.hunksRenderer.expandHunkFully(hunkIndex);
    this.computeApproximateSize();
    this.renderRange = void 0;
    this.virtualizer.instanceChanged(this);
  }
  setVisibility(visible) {
    if (this.fileContainer == null) return;
    this.renderRange = void 0;
    if (visible && !this.isVisible) {
      this.top = this.virtualizer.getOffsetInScrollContainer(this.fileContainer);
      this.isVisible = true;
    } else if (!visible && this.isVisible) {
      this.isVisible = false;
      this.rerender();
    }
  }
  computeApproximateSize() {
    const isFirstCompute = this.height === 0;
    this.height = 0;
    if (this.fileDiff == null) return;
    const { disableFileHeader = false, expandUnchanged = false, collapsed = false, collapsedContextThreshold = DEFAULT_COLLAPSED_CONTEXT_THRESHOLD, hunkSeparators = "line-info" } = this.options;
    const { diffHeaderHeight, fileGap, hunkSeparatorHeight } = this.metrics;
    const diffStyle = this.getDiffStyle();
    const separatorGap = hunkSeparators !== "simple" && hunkSeparators !== "metadata" && hunkSeparators !== "line-info-basic" ? fileGap : 0;
    if (!disableFileHeader) this.height += diffHeaderHeight;
    else if (hunkSeparators !== "simple" && hunkSeparators !== "metadata") this.height += fileGap;
    if (collapsed) return;
    iterateOverDiff({
      diff: this.fileDiff,
      diffStyle,
      expandedHunks: expandUnchanged ? true : this.hunksRenderer.getExpandedHunksMap(),
      collapsedContextThreshold,
      callback: ({ hunkIndex, collapsedBefore, collapsedAfter, deletionLine, additionLine }) => {
        const splitLineIndex = additionLine != null ? additionLine.splitLineIndex : deletionLine.splitLineIndex;
        const unifiedLineIndex = additionLine != null ? additionLine.unifiedLineIndex : deletionLine.unifiedLineIndex;
        const hasMetadata = (additionLine?.noEOFCR ?? false) || (deletionLine?.noEOFCR ?? false);
        if (collapsedBefore > 0) {
          if (hunkIndex > 0) this.height += separatorGap;
          this.height += hunkSeparatorHeight + separatorGap;
        }
        this.height += this.getLineHeight(diffStyle === "split" ? splitLineIndex : unifiedLineIndex, hasMetadata);
        if (collapsedAfter > 0 && hunkSeparators !== "simple") this.height += separatorGap + hunkSeparatorHeight;
      }
    });
    if (this.fileDiff.hunks.length > 0) this.height += fileGap;
    if (this.fileContainer != null && this.virtualizer.config.resizeDebugging && !isFirstCompute) {
      const rect = this.fileContainer.getBoundingClientRect();
      if (rect.height !== this.height) console.log("VirtualizedFileDiff.computeApproximateSize: computed height doesnt match", {
        name: this.fileDiff.name,
        elementHeight: rect.height,
        computedHeight: this.height
      });
      else console.log("VirtualizedFileDiff.computeApproximateSize: computed height IS CORRECT");
    }
  }
  render({ fileContainer, oldFile, newFile, fileDiff, ...props } = {}) {
    const isFirstRender = this.fileContainer == null;
    this.fileDiff ??= fileDiff ?? (oldFile != null && newFile != null ? parseDiffFromFile(oldFile, newFile) : void 0);
    fileContainer = this.getOrCreateFileContainer(fileContainer);
    if (this.fileDiff == null) {
      console.error("VirtualizedFileDiff.render: attempting to virtually render when we dont have the correct data");
      return false;
    }
    if (isFirstRender) {
      this.computeApproximateSize();
      this.virtualizer.connect(fileContainer, this);
      this.top ??= this.virtualizer.getOffsetInScrollContainer(fileContainer);
      this.isVisible = this.virtualizer.isInstanceVisible(this.top, this.height);
    } else this.top ??= this.virtualizer.getOffsetInScrollContainer(fileContainer);
    if (!this.isVisible) return this.renderPlaceholder(this.height);
    const windowSpecs = this.virtualizer.getWindowSpecs();
    const renderRange = this.computeRenderRangeFromWindow(this.fileDiff, this.top, windowSpecs);
    return super.render({
      fileDiff: this.fileDiff,
      fileContainer,
      renderRange,
      oldFile,
      newFile,
      ...props
    });
  }
  getDiffStyle() {
    return this.options.diffStyle ?? "split";
  }
  getExpandedRegion(isPartial, hunkIndex, rangeSize) {
    if (rangeSize <= 0 || isPartial) return {
      fromStart: 0,
      fromEnd: 0,
      collapsedLines: Math.max(rangeSize, 0),
      renderAll: false
    };
    const { expandUnchanged = false, collapsedContextThreshold = DEFAULT_COLLAPSED_CONTEXT_THRESHOLD } = this.options;
    if (expandUnchanged || rangeSize <= collapsedContextThreshold) return {
      fromStart: rangeSize,
      fromEnd: 0,
      collapsedLines: 0,
      renderAll: true
    };
    const region = this.hunksRenderer.getExpandedHunk(hunkIndex);
    const fromStart = Math.min(Math.max(region.fromStart, 0), rangeSize);
    const fromEnd = Math.min(Math.max(region.fromEnd, 0), rangeSize);
    const expandedCount = fromStart + fromEnd;
    const renderAll = expandedCount >= rangeSize;
    return {
      fromStart,
      fromEnd,
      collapsedLines: Math.max(rangeSize - expandedCount, 0),
      renderAll
    };
  }
  getExpandedLineCount(fileDiff, diffStyle) {
    let count = 0;
    if (fileDiff.isPartial) {
      for (const hunk of fileDiff.hunks) count += diffStyle === "split" ? hunk.splitLineCount : hunk.unifiedLineCount;
      return count;
    }
    for (const [hunkIndex, hunk] of fileDiff.hunks.entries()) {
      const hunkCount = diffStyle === "split" ? hunk.splitLineCount : hunk.unifiedLineCount;
      count += hunkCount;
      const collapsedBefore = Math.max(hunk.collapsedBefore, 0);
      const { fromStart, fromEnd, renderAll } = this.getExpandedRegion(fileDiff.isPartial, hunkIndex, collapsedBefore);
      if (collapsedBefore > 0) count += renderAll ? collapsedBefore : fromStart + fromEnd;
    }
    const lastHunk = fileDiff.hunks.at(-1);
    if (lastHunk != null && hasFinalHunk(fileDiff)) {
      const additionRemaining = fileDiff.additionLines.length - (lastHunk.additionLineIndex + lastHunk.additionCount);
      const deletionRemaining = fileDiff.deletionLines.length - (lastHunk.deletionLineIndex + lastHunk.deletionCount);
      if (lastHunk != null && additionRemaining !== deletionRemaining) throw new Error(`VirtualizedFileDiff: trailing context mismatch (additions=${additionRemaining}, deletions=${deletionRemaining}) for ${fileDiff.name}`);
      const trailingRangeSize = Math.min(additionRemaining, deletionRemaining);
      if (lastHunk != null && trailingRangeSize > 0) {
        const { fromStart, renderAll } = this.getExpandedRegion(fileDiff.isPartial, fileDiff.hunks.length, trailingRangeSize);
        count += renderAll ? trailingRangeSize : fromStart;
      }
    }
    return count;
  }
  computeRenderRangeFromWindow(fileDiff, fileTop, { top, bottom }) {
    const { disableFileHeader = false, expandUnchanged = false, collapsedContextThreshold = DEFAULT_COLLAPSED_CONTEXT_THRESHOLD, hunkSeparators = "line-info" } = this.options;
    const { diffHeaderHeight, fileGap, hunkLineCount, hunkSeparatorHeight, lineHeight } = this.metrics;
    const diffStyle = this.getDiffStyle();
    const fileHeight = this.height;
    const lineCount = this.getExpandedLineCount(fileDiff, diffStyle);
    const headerRegion = disableFileHeader ? fileGap : diffHeaderHeight;
    if (fileTop < top - fileHeight || fileTop > bottom) return {
      startingLine: 0,
      totalLines: 0,
      bufferBefore: 0,
      bufferAfter: fileHeight - headerRegion - fileGap
    };
    if (lineCount <= hunkLineCount || fileDiff.hunks.length === 0) return {
      startingLine: 0,
      totalLines: hunkLineCount,
      bufferBefore: 0,
      bufferAfter: 0
    };
    const estimatedTargetLines = Math.ceil(Math.max(bottom - top, 0) / lineHeight);
    const totalLines = Math.ceil(estimatedTargetLines / hunkLineCount) * hunkLineCount + hunkLineCount;
    const totalHunks = totalLines / hunkLineCount;
    const overflowHunks = totalHunks;
    const hunkOffsets = [];
    const viewportCenter = (top + bottom) / 2;
    const separatorGap = hunkSeparators === "simple" || hunkSeparators === "metadata" || hunkSeparators === "line-info-basic" ? 0 : fileGap;
    let absoluteLineTop = fileTop + headerRegion;
    let currentLine = 0;
    let firstVisibleHunk;
    let centerHunk;
    let overflowCounter;
    iterateOverDiff({
      diff: fileDiff,
      diffStyle,
      expandedHunks: expandUnchanged ? true : this.hunksRenderer.getExpandedHunksMap(),
      collapsedContextThreshold,
      callback: ({ hunkIndex, collapsedBefore, collapsedAfter, deletionLine, additionLine }) => {
        const splitLineIndex = additionLine != null ? additionLine.splitLineIndex : deletionLine.splitLineIndex;
        const unifiedLineIndex = additionLine != null ? additionLine.unifiedLineIndex : deletionLine.unifiedLineIndex;
        const hasMetadata = (additionLine?.noEOFCR ?? false) || (deletionLine?.noEOFCR ?? false);
        let gapAdjustment = collapsedBefore > 0 ? hunkSeparatorHeight + separatorGap + (hunkIndex > 0 ? separatorGap : 0) : 0;
        if (hunkIndex === 0 && hunkSeparators === "simple") gapAdjustment = 0;
        absoluteLineTop += gapAdjustment;
        const isAtHunkBoundary = currentLine % hunkLineCount === 0;
        if (isAtHunkBoundary) {
          hunkOffsets.push(absoluteLineTop - (fileTop + headerRegion + gapAdjustment));
          if (overflowCounter != null) {
            if (overflowCounter <= 0) return true;
            overflowCounter--;
          }
        }
        const lineHeight$1 = this.getLineHeight(diffStyle === "split" ? splitLineIndex : unifiedLineIndex, hasMetadata);
        const currentHunk = Math.floor(currentLine / hunkLineCount);
        if (absoluteLineTop > top - lineHeight$1 && absoluteLineTop < bottom) firstVisibleHunk ??= currentHunk;
        if (centerHunk == null && absoluteLineTop + lineHeight$1 > viewportCenter) centerHunk = currentHunk;
        if (overflowCounter == null && absoluteLineTop >= bottom && isAtHunkBoundary) overflowCounter = overflowHunks;
        currentLine++;
        absoluteLineTop += lineHeight$1;
        if (collapsedAfter > 0 && hunkSeparators !== "simple") absoluteLineTop += hunkSeparatorHeight + separatorGap;
        return false;
      }
    });
    if (firstVisibleHunk == null) return {
      startingLine: 0,
      totalLines: 0,
      bufferBefore: 0,
      bufferAfter: fileHeight - headerRegion - fileGap
    };
    const collectedHunks = hunkOffsets.length;
    centerHunk ??= firstVisibleHunk;
    const idealStartHunk = Math.round(centerHunk - totalHunks / 2);
    const maxStartHunk = Math.max(0, collectedHunks - totalHunks);
    const startHunk = Math.max(0, Math.min(idealStartHunk, maxStartHunk));
    const startingLine = startHunk * hunkLineCount;
    const clampedTotalLines = idealStartHunk < 0 ? totalLines + idealStartHunk * hunkLineCount : totalLines;
    const bufferBefore = hunkOffsets[startHunk] ?? 0;
    const finalHunkIndex = startHunk + clampedTotalLines / hunkLineCount;
    return {
      startingLine,
      totalLines: clampedTotalLines,
      bufferBefore,
      bufferAfter: finalHunkIndex < hunkOffsets.length ? fileHeight - headerRegion - hunkOffsets[finalHunkIndex] - fileGap : fileHeight - (absoluteLineTop - fileTop) - fileGap
    };
  }
};
function hasFinalHunk(fileDiff) {
  const lastHunk = fileDiff.hunks.at(-1);
  if (lastHunk == null || fileDiff.isPartial || fileDiff.additionLines.length === 0 || fileDiff.deletionLines.length === 0) return false;
  return lastHunk.additionLineIndex + lastHunk.additionCount < fileDiff.additionLines.length || lastHunk.deletionLineIndex + lastHunk.deletionCount < fileDiff.deletionLines.length;
}
function parseLineIndex(lineIndexAttr, diffStyle) {
  const [unifiedIndex, splitIndex] = lineIndexAttr.split(",").map(Number);
  return diffStyle === "split" ? splitIndex : unifiedIndex;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/areVirtualWindowSpecsEqual.js
function areVirtualWindowSpecsEqual(windowSpecsA, windowSpecsB) {
  if (windowSpecsA == null || windowSpecsB == null) return windowSpecsA === windowSpecsB;
  return windowSpecsA.top === windowSpecsB.top && windowSpecsA.bottom === windowSpecsB.bottom;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/createWindowFromScrollPosition.js
function createWindowFromScrollPosition({ scrollTop, scrollHeight, height, containerOffset = 0, fitPerfectly, overscrollSize }) {
  const windowHeight = height + overscrollSize * 2;
  const effectiveHeight = fitPerfectly ? height : windowHeight;
  scrollHeight = Math.max(scrollHeight, effectiveHeight);
  if (windowHeight >= scrollHeight || fitPerfectly) {
    const top$1 = Math.max(scrollTop - containerOffset, 0);
    const bottom$1 = Math.min(scrollTop + effectiveHeight, scrollHeight) - containerOffset;
    return {
      top: top$1,
      bottom: Math.max(bottom$1, top$1)
    };
  }
  let top = scrollTop + height / 2 - windowHeight / 2;
  let bottom = top + windowHeight;
  if (top < 0) top = 0;
  if (bottom > scrollHeight) bottom = scrollHeight;
  top = Math.floor(Math.max(top - containerOffset, 0));
  return {
    top,
    bottom: Math.ceil(Math.max(Math.min(bottom, scrollHeight) - containerOffset, top))
  };
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/components/Virtualizer.js
var DEFAULT_OVERSCROLL_SIZE = 1e3;
var INTERSECTION_OBSERVER_MARGIN = DEFAULT_OVERSCROLL_SIZE * 4;
var INTERSECTION_OBSERVER_THRESHOLD = [
  0,
  1e-6,
  0.99999,
  1
];
var DEFAULT_VIRTUALIZER_CONFIG = {
  overscrollSize: DEFAULT_OVERSCROLL_SIZE,
  intersectionObserverMargin: INTERSECTION_OBSERVER_MARGIN,
  resizeDebugging: false
};
var lastSize = 0;
var instance = -1;
var Virtualizer = class Virtualizer2 {
  static __STOP = false;
  static __lastScrollPosition = 0;
  __id = `virtualizer-${++instance}`;
  config;
  type = "basic";
  intersectionObserver;
  scrollTop = 0;
  height = 0;
  scrollHeight = 0;
  windowSpecs = {
    top: 0,
    bottom: 0
  };
  root;
  contentContainer;
  resizeObserver;
  observers = /* @__PURE__ */ new Map();
  visibleInstances = /* @__PURE__ */ new Map();
  visibleInstancesDirty = false;
  instancesChanged = /* @__PURE__ */ new Set();
  scrollDirty = true;
  heightDirty = true;
  scrollHeightDirty = true;
  renderedObservers = 0;
  connectQueue = /* @__PURE__ */ new Map();
  constructor(config) {
    this.config = {
      ...DEFAULT_VIRTUALIZER_CONFIG,
      ...config
    };
  }
  setup(root, contentContainer) {
    if (this.root != null) return;
    this.root = root;
    this.resizeObserver = new ResizeObserver(this.handleContainerResize);
    this.intersectionObserver = new IntersectionObserver(this.handleIntersectionChange, {
      root: this.root,
      threshold: INTERSECTION_OBSERVER_THRESHOLD,
      rootMargin: `${this.config.intersectionObserverMargin}px 0px ${this.config.intersectionObserverMargin}px 0px`
    });
    if (root instanceof Document) this.setupWindow();
    else this.setupElement(contentContainer);
    window.__INSTANCE = this;
    window.__TOGGLE = () => {
      if (Virtualizer2.__STOP) {
        Virtualizer2.__STOP = false;
        (this.getScrollContainerElement() ?? window).scrollTo({ top: Virtualizer2.__lastScrollPosition });
        queueRender(this.computeRenderRangeAndEmit);
      } else {
        Virtualizer2.__lastScrollPosition = this.getScrollTop();
        Virtualizer2.__STOP = true;
      }
    };
    for (const [container, instance$1] of this.connectQueue.entries()) this.connect(container, instance$1);
    this.connectQueue.clear();
    this.markDOMDirty();
    queueRender(this.computeRenderRangeAndEmit);
  }
  instanceChanged(instance$1) {
    this.instancesChanged.add(instance$1);
    this.markDOMDirty();
    queueRender(this.computeRenderRangeAndEmit);
  }
  getWindowSpecs() {
    if (this.windowSpecs.top === 0 && this.windowSpecs.bottom === 0) this.windowSpecs = createWindowFromScrollPosition({
      scrollTop: this.getScrollTop(),
      height: this.getHeight(),
      scrollHeight: this.getScrollHeight(),
      fitPerfectly: false,
      overscrollSize: this.config.overscrollSize
    });
    return this.windowSpecs;
  }
  isInstanceVisible(elementTop, elementHeight) {
    const scrollTop = this.getScrollTop();
    const height = this.getHeight();
    const margin = this.config.intersectionObserverMargin;
    const top = scrollTop - margin;
    const bottom = scrollTop + height + margin;
    return !(elementTop < top - elementHeight || elementTop > bottom);
  }
  handleContainerResize = (entries) => {
    if (this.root == null) return;
    let shouldQueueUpdate = false;
    for (const entry of entries) {
      const blockSize = entry.borderBoxSize[0].blockSize;
      if (this.root instanceof Document) {
        if (blockSize !== this.scrollHeight) {
          this.scrollHeightDirty = true;
          shouldQueueUpdate = true;
          if (this.config.resizeDebugging) {
            console.log("Virtualizer: content size change", this.__id, {
              sizeChange: blockSize - lastSize,
              newSize: blockSize
            });
            lastSize = blockSize;
          }
        }
      } else if (entry.target === this.root) {
        if (blockSize !== this.height) {
          this.heightDirty = true;
          shouldQueueUpdate = true;
        }
      } else if (entry.target === this.contentContainer) {
        this.scrollHeightDirty = true;
        shouldQueueUpdate = true;
        if (this.config.resizeDebugging) {
          console.log("Virtualizer: scroller size change", this.__id, {
            sizeChange: blockSize - lastSize,
            newSize: blockSize
          });
          lastSize = blockSize;
        }
      }
    }
    if (shouldQueueUpdate) queueRender(this.computeRenderRangeAndEmit);
  };
  setupWindow() {
    if (this.root == null || !(this.root instanceof Document)) throw new Error("Virtualizer.setupWindow: Invalid setup method");
    window.addEventListener("scroll", this.handleWindowScroll, { passive: true });
    window.addEventListener("resize", this.handleWindowResize, { passive: true });
    this.resizeObserver?.observe(this.root.documentElement);
  }
  setupElement(contentContainer) {
    if (this.root == null || this.root instanceof Document) throw new Error("Virtualizer.setupElement: Invalid setup method");
    this.root.addEventListener("scroll", this.handleElementScroll, { passive: true });
    this.resizeObserver?.observe(this.root);
    contentContainer ??= this.root.firstElementChild ?? void 0;
    if (contentContainer instanceof HTMLElement) {
      this.contentContainer = contentContainer;
      this.resizeObserver?.observe(contentContainer);
    }
  }
  cleanUp() {
    this.resizeObserver?.disconnect();
    this.resizeObserver = void 0;
    this.intersectionObserver?.disconnect();
    this.intersectionObserver = void 0;
    this.root?.removeEventListener("scroll", this.handleElementScroll);
    window.removeEventListener("scroll", this.handleWindowScroll);
    window.removeEventListener("resize", this.handleWindowResize);
    this.root = void 0;
    this.contentContainer = void 0;
    this.observers.clear();
    this.visibleInstances.clear();
    this.instancesChanged.clear();
    this.connectQueue.clear();
    this.visibleInstancesDirty = false;
    this.windowSpecs = {
      top: 0,
      bottom: 0
    };
    this.scrollTop = 0;
    this.height = 0;
    this.scrollHeight = 0;
  }
  getOffsetInScrollContainer(element) {
    return this.getScrollTop() + getRelativeBoundingTop(element, this.getScrollContainerElement());
  }
  connect(container, instance$1) {
    if (this.observers.has(container)) throw new Error("Virtualizer.connect: instance is already connected...");
    if (this.intersectionObserver == null) this.connectQueue.set(container, instance$1);
    else {
      this.intersectionObserver.observe(container);
      this.observers.set(container, instance$1);
      this.instancesChanged.add(instance$1);
      this.markDOMDirty();
      queueRender(this.computeRenderRangeAndEmit);
    }
    return () => this.disconnect(container);
  }
  disconnect(container) {
    const instance$1 = this.observers.get(container);
    this.connectQueue.delete(container);
    if (instance$1 == null) return;
    this.intersectionObserver?.unobserve(container);
    this.observers.delete(container);
    if (this.visibleInstances.delete(container)) this.visibleInstancesDirty = true;
    this.markDOMDirty();
    queueRender(this.computeRenderRangeAndEmit);
  }
  handleWindowResize = () => {
    if (Virtualizer2.__STOP || window.innerHeight === this.height) return;
    this.heightDirty = true;
    queueRender(this.computeRenderRangeAndEmit);
  };
  handleWindowScroll = () => {
    if (Virtualizer2.__STOP || this.root == null || !(this.root instanceof Document)) return;
    this.scrollDirty = true;
    queueRender(this.computeRenderRangeAndEmit);
  };
  handleElementScroll = () => {
    if (Virtualizer2.__STOP || this.root == null || this.root instanceof Document) return;
    this.scrollDirty = true;
    queueRender(this.computeRenderRangeAndEmit);
  };
  computeRenderRangeAndEmit = () => {
    if (Virtualizer2.__STOP) return;
    const wrapperDirty = this.heightDirty || this.scrollHeightDirty;
    if (!this.scrollDirty && !this.scrollHeightDirty && !this.heightDirty && this.renderedObservers === this.observers.size && !this.visibleInstancesDirty && this.instancesChanged.size === 0) return;
    if (this.instancesChanged.size === 0) {
      const windowSpecs = createWindowFromScrollPosition({
        scrollTop: this.getScrollTop(),
        height: this.getHeight(),
        scrollHeight: this.getScrollHeight(),
        fitPerfectly: false,
        overscrollSize: this.config.overscrollSize
      });
      if (areVirtualWindowSpecsEqual(this.windowSpecs, windowSpecs) && this.renderedObservers === this.observers.size && !this.visibleInstancesDirty && this.instancesChanged.size === 0) return;
      this.windowSpecs = windowSpecs;
    }
    this.visibleInstancesDirty = false;
    this.renderedObservers = this.observers.size;
    const anchor = this.getScrollAnchor(this.height);
    const updatedInstances = /* @__PURE__ */ new Set();
    for (const instance$1 of wrapperDirty ? this.observers.values() : this.visibleInstances.values()) if (instance$1.onRender(wrapperDirty)) updatedInstances.add(instance$1);
    for (const instance$1 of this.instancesChanged) {
      if (updatedInstances.has(instance$1)) continue;
      if (instance$1.onRender(wrapperDirty)) updatedInstances.add(instance$1);
    }
    this.scrollFix(anchor);
    if (this.instancesChanged.size > 0) this.markDOMDirty();
    for (const instance$1 of updatedInstances) instance$1.reconcileHeights();
    if (this.instancesChanged.size > 0 || wrapperDirty) queueRender(this.computeRenderRangeAndEmit);
    updatedInstances.clear();
    this.instancesChanged.clear();
  };
  scrollFix(anchor) {
    if (anchor == null) return;
    const scrollContainer = this.getScrollContainerElement();
    const { lineIndex, lineOffset, fileElement, fileOffset, fileTypeOffset } = anchor;
    if (lineIndex != null && lineOffset != null) {
      const element = fileElement.shadowRoot?.querySelector(`[data-line][data-line-index="${lineIndex}"]`);
      if (element instanceof HTMLElement) {
        const top$1 = getRelativeBoundingTop(element, scrollContainer);
        if (top$1 !== lineOffset) {
          const scrollOffset = top$1 - lineOffset;
          this.applyScrollFix(scrollOffset);
        }
        return;
      }
    }
    const top = getRelativeBoundingTop(fileElement, scrollContainer);
    if (fileTypeOffset === "top") {
      if (top !== fileOffset) this.applyScrollFix(top - fileOffset);
    } else {
      const bottom = top + fileElement.getBoundingClientRect().height;
      if (bottom !== fileOffset) this.applyScrollFix(bottom - fileOffset);
    }
  }
  applyScrollFix(scrollOffset) {
    if (this.root == null || this.root instanceof Document) window.scrollTo({
      top: window.scrollY + scrollOffset,
      behavior: "instant"
    });
    else this.root.scrollTo({
      top: this.root.scrollTop + scrollOffset,
      behavior: "instant"
    });
    this.markDOMDirty();
  }
  getScrollAnchor(viewportHeight) {
    const scrollContainer = this.getScrollContainerElement();
    let bestAnchor;
    for (const [fileElement] of this.visibleInstances.entries()) {
      const fileTop = getRelativeBoundingTop(fileElement, scrollContainer);
      const fileBottom = fileTop + fileElement.offsetHeight;
      let fileOffset;
      let fileTypeOffset;
      if (fileBottom <= 0) {
        fileOffset = fileBottom;
        fileTypeOffset = "bottom";
      } else {
        fileOffset = fileTop;
        fileTypeOffset = "top";
      }
      let bestLineIndex;
      let bestLineOffset;
      if (fileBottom > 0 && fileTop < viewportHeight) for (const line of fileElement.shadowRoot?.querySelectorAll("[data-line][data-line-index]") ?? []) {
        if (!(line instanceof HTMLElement)) continue;
        const lineIndex = line.dataset.lineIndex;
        if (lineIndex == null) continue;
        const lineOffset = getRelativeBoundingTop(line, scrollContainer);
        if (lineOffset < 0) continue;
        bestLineIndex = lineIndex;
        bestLineOffset = lineOffset;
        break;
      }
      if (bestAnchor?.lineOffset != null && bestLineOffset == null) continue;
      let shouldReplace = false;
      if (bestAnchor == null) shouldReplace = true;
      else if (bestLineOffset != null && (bestAnchor.lineOffset == null || bestLineOffset < bestAnchor.lineOffset)) shouldReplace = true;
      else if (bestLineOffset == null && bestAnchor.lineOffset == null) {
        if (fileOffset >= 0 && (bestAnchor.fileOffset < 0 || fileOffset < bestAnchor.fileOffset)) shouldReplace = true;
        else if (fileOffset < 0 && bestAnchor.fileOffset < 0 && fileOffset > bestAnchor.fileOffset) shouldReplace = true;
      }
      if (shouldReplace) bestAnchor = {
        fileElement,
        fileTypeOffset,
        fileOffset,
        lineIndex: bestLineIndex,
        lineOffset: bestLineOffset
      };
    }
    return bestAnchor;
  }
  handleIntersectionChange = (entries) => {
    this.scrollDirty = true;
    for (const { target, isIntersecting } of entries) {
      if (!(target instanceof HTMLElement)) throw new Error("Virtualizer.handleIntersectionChange: target not an HTMLElement");
      const instance$1 = this.observers.get(target);
      if (instance$1 == null) throw new Error("Virtualizer.handleIntersectionChange: no instance for target");
      if (isIntersecting && !this.visibleInstances.has(target)) {
        instance$1.setVisibility(true);
        this.visibleInstances.set(target, instance$1);
        this.visibleInstancesDirty = true;
      } else if (!isIntersecting && this.visibleInstances.has(target)) {
        instance$1.setVisibility(false);
        this.visibleInstances.delete(target);
        this.visibleInstancesDirty = true;
      }
    }
    if (this.visibleInstancesDirty) queueRender(this.computeRenderRangeAndEmit);
  };
  getScrollTop() {
    if (!this.scrollDirty) return this.scrollTop;
    this.scrollDirty = false;
    let scrollTop = (() => {
      if (this.root == null) return 0;
      if (this.root instanceof Document) return window.scrollY;
      return this.root.scrollTop;
    })();
    scrollTop = Math.max(0, Math.min(scrollTop, this.getScrollHeight() - this.getHeight()));
    this.scrollTop = scrollTop;
    return scrollTop;
  }
  getScrollHeight() {
    if (!this.scrollHeightDirty) return this.scrollHeight;
    this.scrollHeightDirty = false;
    this.scrollHeight = (() => {
      if (this.root == null) return 0;
      if (this.root instanceof Document) return this.root.documentElement.scrollHeight;
      return this.root.scrollHeight;
    })();
    return this.scrollHeight;
  }
  getHeight() {
    if (!this.heightDirty) return this.height;
    this.heightDirty = false;
    this.height = (() => {
      if (this.root == null) return 0;
      if (this.root instanceof Document) return globalThis.innerHeight;
      return this.root.getBoundingClientRect().height;
    })();
    return this.height;
  }
  markDOMDirty() {
    this.scrollDirty = true;
    this.scrollHeightDirty = true;
    this.heightDirty = true;
  }
  getScrollContainerElement() {
    return this.root == null || this.root instanceof Document ? void 0 : this.root;
  }
};
function getRelativeBoundingTop(element, scrollContainer) {
  const rect = element.getBoundingClientRect();
  const scrollContainerTop = scrollContainer?.getBoundingClientRect().top ?? 0;
  return rect.top - scrollContainerTop;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/languages/registerCustomLanguage.js
function registerCustomLanguage(lang, loader, extensionsOrFilenames = []) {
  if (lang === "text" || lang === "ansi") throw new Error("registerCustomLanguage: 'text' and 'ansi' are reserved language names");
  if (RegisteredCustomLanguages.has(lang)) {
    console.error(`registerCustomLanguage: lang: ${lang} is already registered`);
    return;
  }
  RegisteredCustomLanguages.set(lang, loader);
  for (const extension of extensionsOrFilenames) CUSTOM_EXTENSION_TO_FILE_FORMAT.set(extension, lang);
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/highlighter/themes/registerCustomCSSVariableTheme.js
function registerCustomCSSVariableTheme(name, variableDefaults, fontStyle = false) {
  const theme = createCssVariablesTheme({
    name,
    variablePrefix: formatCSSVariablePrefix("global"),
    variableDefaults,
    fontStyle
  });
  registerCustomTheme(name, () => Promise.resolve(theme));
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/areObjectsEqual.js
function areObjectsEqual(objA, objB, omitKeys) {
  if (objA === objB || objA == null || objB == null) return objA === objB;
  const omitSet = new Set(omitKeys);
  const keysA = Object.keys(objA);
  const keysBSet = new Set(Object.keys(objB));
  for (const key of keysA) {
    keysBSet.delete(key);
    if (omitSet.has(key)) continue;
    if (!(key in objB) || objA[key] !== objB[key]) return false;
  }
  for (const key of Array.from(keysBSet)) if (!omitSet.has(key)) return false;
  return true;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/areOptionsEqual.js
function areOptionsEqual(optionsA, optionsB) {
  return areThemesEqual(optionsA?.theme ?? DEFAULT_THEMES, optionsB?.theme ?? DEFAULT_THEMES) && areObjectsEqual(optionsA, optionsB, ["theme"]);
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/areWorkerStatsEqual.js
function areWorkerStatsEqual(statsA, statsB) {
  if (statsA == null || statsB == null) return statsA === statsB;
  return statsA.busyWorkers === statsB.busyWorkers && statsA.diffCacheSize === statsB.diffCacheSize && statsA.fileCacheSize === statsB.fileCacheSize && statsA.managerState === statsB.managerState && statsA.pendingTasks === statsB.pendingTasks && statsA.queuedTasks === statsB.queuedTasks && statsA.themeSubscribers === statsB.themeSubscribers && statsA.totalWorkers === statsB.totalWorkers && statsA.workersFailed === statsB.workersFailed;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/createRowNodes.js
function createRowNodes(line) {
  const row = document.createElement("div");
  row.dataset.line = `${line}`;
  const lineColumn = document.createElement("div");
  lineColumn.dataset.columnNumber = "";
  lineColumn.textContent = `${line}`;
  const content = document.createElement("div");
  content.dataset.columnContent = "";
  row.appendChild(lineColumn);
  row.appendChild(content);
  return {
    row,
    content
  };
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/createStyleElement.js
function createStyleElement(content, isCoreCSS = false) {
  return createHastElement({
    tagName: "style",
    children: [createTextNodeElement(isCoreCSS ? wrapCoreCSS(content) : wrapUnsafeCSS(content))],
    properties: {
      [CORE_CSS_ATTRIBUTE]: isCoreCSS ? "" : void 0,
      [UNSAFE_CSS_ATTRIBUTE]: !isCoreCSS ? "" : void 0
    }
  });
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/diffAcceptRejectHunk.js
function diffAcceptRejectHunk(diff, hunkIndex, type) {
  diff = {
    ...diff,
    hunks: [...diff.hunks],
    deletionLines: type === "accept" ? [...diff.deletionLines] : diff.deletionLines,
    additionLines: type === "reject" ? [...diff.additionLines] : diff.additionLines,
    cacheKey: diff.cacheKey != null ? `${diff.cacheKey}:${type[0]}-${hunkIndex}` : void 0
  };
  const { additionLines, deletionLines } = diff;
  if (additionLines != null && deletionLines != null) {
    const hunk = diff.hunks[hunkIndex];
    if (hunk == null) {
      console.error({
        diff,
        hunkIndex
      });
      throw new Error(`diffResolveRejectHunk: Invalid hunk index: ${hunkIndex}`);
    }
    if (type === "reject") additionLines.splice(hunk.additionLineIndex, hunk.additionCount, ...deletionLines.slice(hunk.deletionLineIndex, hunk.deletionLineIndex + hunk.deletionCount));
    else deletionLines.splice(hunk.deletionLineIndex, hunk.deletionCount, ...additionLines.slice(hunk.additionLineIndex, hunk.additionLineIndex + hunk.additionCount));
  }
  let deletionOffset = 0;
  let additionOffset = 0;
  let splitOffset = 0;
  let unifiedOffset = 0;
  for (let i = hunkIndex; i < diff.hunks.length; i++) {
    let hunk = diff.hunks[i];
    if (hunk == null) {
      console.error({
        hunk,
        i,
        hunkIndex,
        diff
      });
      throw new Error("diffResolveRejectHunk: iterating through hunks, hunk doesnt exist...");
    }
    const { noEOFCRAdditions, noEOFCRDeletions } = hunk;
    diff.hunks[i] = hunk = { ...hunk };
    if (i === hunkIndex) {
      hunk.noEOFCRDeletions = false;
      hunk.noEOFCRAdditions = false;
      if (type === "accept" && noEOFCRAdditions || type === "reject" && noEOFCRDeletions) {
        hunk.noEOFCRAdditions = true;
        hunk.noEOFCRDeletions = true;
      }
      const newContent = {
        type: "context",
        lines: 0,
        additionLineIndex: hunk.additionLineIndex,
        deletionLineIndex: hunk.deletionLineIndex
      };
      for (const content of hunk.hunkContent) if (content.type === "context") newContent.lines += content.lines;
      else if (type === "accept") newContent.lines += content.additions;
      else if (type === "reject") newContent.lines += content.deletions;
      const lineCount = newContent.lines;
      hunk.hunkContent = [newContent];
      splitOffset = lineCount - hunk.splitLineCount;
      hunk.splitLineCount = lineCount;
      unifiedOffset = lineCount - hunk.unifiedLineCount;
      hunk.unifiedLineCount = lineCount;
      deletionOffset = lineCount - hunk.deletionCount;
      hunk.deletionCount = lineCount;
      hunk.deletionLines = 0;
      additionOffset = lineCount - hunk.additionCount;
      hunk.additionCount = lineCount;
      hunk.additionLines = 0;
      diff.splitLineCount += splitOffset;
      diff.unifiedLineCount += unifiedOffset;
      if (splitOffset === 0 && unifiedOffset === 0 && additionOffset === 0 && deletionOffset === 0) break;
    } else {
      hunk.splitLineStart += splitOffset;
      hunk.unifiedLineStart += unifiedOffset;
      hunk.additionStart += additionOffset;
      hunk.additionLineIndex += additionOffset;
      hunk.deletionLineIndex += deletionOffset;
      hunk.deletionStart += deletionOffset;
      if (deletionOffset !== 0 || additionOffset !== 0) {
        let i$1 = 0;
        while (i$1 < hunk.hunkContent.length) {
          const content = hunk.hunkContent[i$1];
          hunk.hunkContent[i$1] = {
            ...content,
            additionLineIndex: content.additionLineIndex + additionOffset,
            deletionLineIndex: content.deletionLineIndex + deletionOffset
          };
          i$1++;
        }
      }
    }
  }
  return diff;
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/getLineEndingType.js
function getLineEndingType(content) {
  if (content.includes("\r\n")) return "CRLF";
  if (content.includes("\r")) return "CR";
  if (content.includes("\n")) return "LF";
  return "none";
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/getSingularPatch.js
function getSingularPatch(patch) {
  const parsedPatches = parsePatchFiles(patch);
  if (parsedPatches.length !== 1) {
    console.error(parsedPatches);
    throw new Error("PatchDiff: Provided patch must include only 1 patch, with 1 diff");
  }
  const { files } = parsedPatches[0];
  if (files.length !== 1) {
    console.error(files);
    throw new Error("FileDiff: Provided patch must contain exactly 1 file diff");
  }
  return files[0];
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/setLanguageOverride.js
function setLanguageOverride(fileOrDiff, lang) {
  return {
    ...fileOrDiff,
    lang
  };
}

// ../../node_modules/.bun/@pierre+diffs@1.1.0-beta.18+dde3f20a083be258/node_modules/@pierre/diffs/dist/utils/trimPatchContext.js
function trimPatchContext(patch, contextSize = 10) {
  const lines = [];
  let currentHunk;
  for (const line of patch.split("\n")) {
    const parsedHunkHeader = line.match(HUNK_HEADER);
    if (parsedHunkHeader != null) {
      if (currentHunk != null) {
        if (currentHunk.hunkLines.length > 0) {
          flushContextLines(currentHunk, contextSize);
          flushHunk(currentHunk, lines);
        }
        currentHunk = void 0;
      }
      const additionStart = parseInt(parsedHunkHeader[3]);
      const deletionStart = parseInt(parsedHunkHeader[1]);
      const additionCount = parseInt(parsedHunkHeader[4] ?? "1");
      const deletionCount = parseInt(parsedHunkHeader[2] ?? "1");
      if (isNaN(additionStart) || isNaN(deletionStart) || isNaN(additionCount) || isNaN(deletionCount)) lines.push(line);
      else currentHunk = {
        hunkContextString: parsedHunkHeader[5] ?? "",
        additionStart,
        deletionStart,
        additionCount: 0,
        deletionCount: 0,
        hunkLines: [],
        contextLines: []
      };
      continue;
    }
    if (currentHunk == null) {
      lines.push(line);
      continue;
    }
    if (line.startsWith(" ")) {
      currentHunk.contextLines.push(line);
      if (currentHunk.hunkLines.length > 0 && currentHunk.contextLines.length === contextSize * 2 + 1) {
        const removedItems = currentHunk.contextLines.slice(contextSize);
        flushContextLines(currentHunk, contextSize);
        const { additionCount: emittedAdditionCount, deletionCount: emittedDeletionCount } = currentHunk;
        flushHunk(currentHunk, lines);
        removedItems.shift();
        currentHunk = {
          hunkContextString: "",
          additionStart: currentHunk.additionStart + emittedAdditionCount + 1,
          deletionStart: currentHunk.deletionStart + emittedDeletionCount + 1,
          deletionCount: 0,
          additionCount: 0,
          contextLines: removedItems,
          hunkLines: []
        };
      }
    } else if (line !== "") {
      flushContextLines(currentHunk, contextSize);
      currentHunk.hunkLines.push(line);
      if (line.startsWith("+")) currentHunk.additionCount += 1;
      else if (line.startsWith("-")) currentHunk.deletionCount += 1;
    }
  }
  if (currentHunk != null && currentHunk.hunkLines.length > 0) {
    flushContextLines(currentHunk, contextSize);
    flushHunk(currentHunk, lines);
  }
  return lines.join("\n");
}
function flushContextLines(hunk, contextSize) {
  if (hunk.contextLines.length > contextSize) if (hunk.hunkLines.length === 0) {
    const difference = hunk.contextLines.length - contextSize;
    hunk.contextLines.splice(0, difference);
    hunk.additionStart += difference;
    hunk.deletionStart += difference;
  } else hunk.contextLines.length = contextSize;
  if (hunk.contextLines.length > 0) {
    hunk.hunkLines.push(...hunk.contextLines);
    hunk.additionCount += hunk.contextLines.length;
    hunk.deletionCount += hunk.contextLines.length;
    hunk.contextLines.length = 0;
  }
  return hunk;
}
function flushHunk(hunk, lines) {
  lines.push(`@@ -${formatHunkRange(hunk.deletionStart, hunk.deletionCount)} +${formatHunkRange(hunk.additionStart, hunk.additionCount)} @@${hunk.hunkContextString !== "" ? ` ${hunk.hunkContextString}` : ""}`);
  lines.push(...hunk.hunkLines);
}
function formatHunkRange(start, count) {
  return count === 1 ? `${start}` : `${start},${count}`;
}
export {
  ALTERNATE_FILE_NAMES_GIT,
  AttachedLanguages,
  AttachedThemes,
  COMMIT_METADATA_SPLIT,
  CORE_CSS_ATTRIBUTE,
  CUSTOM_EXTENSION_TO_FILE_FORMAT,
  CodeToTokenTransformStream,
  DEFAULT_COLLAPSED_CONTEXT_THRESHOLD,
  DEFAULT_EXPANDED_REGION,
  DEFAULT_RENDER_RANGE,
  DEFAULT_THEMES,
  DEFAULT_VIRTUAL_FILE_METRICS,
  DIFFS_TAG_NAME,
  DiffHunksRenderer,
  EMPTY_RENDER_RANGE,
  EXTENSION_TO_FILE_FORMAT,
  FILENAME_HEADER_REGEX,
  FILENAME_HEADER_REGEX_GIT,
  FILE_CONTEXT_BLOB,
  File,
  FileDiff,
  FileRenderer,
  FileStream,
  GIT_DIFF_FILE_BREAK_REGEX,
  HEADER_METADATA_SLOT_ID,
  HEADER_PREFIX_SLOT_ID,
  HUNK_HEADER,
  INDEX_LINE_METADATA,
  InteractionManager,
  RegisteredCustomLanguages,
  RegisteredCustomThemes,
  ResizeManager,
  ResolvedLanguages,
  ResolvedThemes,
  ResolvingLanguages,
  ResolvingThemes,
  SPLIT_WITH_NEWLINES,
  SVGSpriteSheet,
  ScrollSyncManager,
  ShikiStreamTokenizer,
  UNIFIED_DIFF_FILE_BREAK_REGEX,
  UNSAFE_CSS_ATTRIBUTE,
  VirtualizedFile,
  VirtualizedFileDiff,
  Virtualizer,
  areDiffLineAnnotationsEqual,
  areFilesEqual,
  areHunkDataEqual,
  areLanguagesAttached,
  areLineAnnotationsEqual,
  areObjectsEqual,
  areOptionsEqual,
  arePrePropertiesEqual,
  areRenderRangesEqual,
  areSelectionsEqual,
  areThemesAttached,
  areThemesEqual,
  areVirtualWindowSpecsEqual,
  areWorkerStatsEqual,
  attachResolvedLanguages,
  attachResolvedThemes,
  cleanLastNewline,
  cleanUpResolvedLanguages,
  cleanUpResolvedThemes,
  codeToHtml,
  createAnnotationElement,
  createAnnotationWrapperNode,
  createCssVariablesTheme as createCSSVariablesTheme,
  createDiffSpanDecoration,
  createEmptyRowBuffer,
  createFileHeaderElement,
  createGutterGap,
  createGutterItem,
  createGutterUtilityContentNode,
  createGutterUtilityElement,
  createGutterWrapper,
  createHastElement,
  createIconElement,
  createNoNewlineElement,
  createPreElement,
  createPreWrapperProperties,
  createRowNodes,
  createSeparator,
  createSpanFromToken,
  createStyleElement,
  createTextNodeElement,
  createTransformerWithState,
  createUnsafeCSSStyleNode,
  createWindowFromScrollPosition,
  diffAcceptRejectHunk,
  disposeHighlighter,
  extendFileFormatMap,
  findCodeElement,
  formatCSSVariablePrefix,
  getFiletypeFromFileName,
  getHighlighterIfLoaded,
  getHighlighterOptions,
  getHighlighterThemeStyles,
  getHunkSeparatorSlotName,
  getIconForType,
  getLineAnnotationName,
  getLineEndingType,
  getLineNodes,
  getOrCreateCodeNode,
  getResolvedLanguages,
  getResolvedOrResolveLanguage,
  getResolvedOrResolveTheme,
  getResolvedThemes,
  getSharedHighlighter,
  getSingularPatch,
  getThemes,
  getTotalLineCountFromHunks,
  hasResolvedLanguages,
  hasResolvedThemes,
  isDefaultRenderRange,
  isHighlighterLoaded,
  isHighlighterLoading,
  isHighlighterNull,
  isWorkerContext,
  parseDiffFromFile,
  parseLineType,
  parsePatchFiles,
  pluckInteractionOptions,
  preloadHighlighter,
  prerenderHTMLIfNecessary,
  processFile,
  processLine,
  processPatch,
  pushOrJoinSpan,
  queueRender,
  registerCustomCSSVariableTheme,
  registerCustomLanguage,
  registerCustomTheme,
  renderDiffWithHighlighter,
  renderFileWithHighlighter,
  resolveLanguage,
  resolveLanguages,
  resolveTheme,
  resolveThemes,
  setLanguageOverride,
  setPreNodeProperties,
  trimPatchContext,
  wrapCoreCSS,
  wrapUnsafeCSS
};
//# sourceMappingURL=@pierre_diffs.js.map
