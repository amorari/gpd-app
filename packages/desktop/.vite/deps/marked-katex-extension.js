import {
  katex
} from "./chunk-BDS4IMCO.js";
import "./chunk-G3PMV62Z.js";

// ../../node_modules/.bun/marked-katex-extension@5.1.6+e40ca5f9ce40dfbe/node_modules/marked-katex-extension/src/index.js
var inlineRule = /^(\${1,2})(?!\$)((?:\\.|[^\\\n])*?(?:\\.|[^\\\n\$]))\1(?=[\s?!\.,:？！。，：]|$)/;
var inlineRuleNonStandard = /^(\${1,2})(?!\$)((?:\\.|[^\\\n])*?(?:\\.|[^\\\n\$]))\1/;
var blockRule = /^(\${1,2})\n((?:\\[^]|[^\\])+?)\n\1(?:\n|$)/;
function src_default(options = {}) {
  return {
    extensions: [
      inlineKatex(options, createRenderer(options, false)),
      blockKatex(options, createRenderer(options, true))
    ]
  };
}
function createRenderer(options, newlineAfter) {
  return (token) => katex.renderToString(token.text, { ...options, displayMode: token.displayMode }) + (newlineAfter ? "\n" : "");
}
function inlineKatex(options, renderer) {
  const nonStandard = options && options.nonStandard;
  const ruleReg = nonStandard ? inlineRuleNonStandard : inlineRule;
  return {
    name: "inlineKatex",
    level: "inline",
    start(src) {
      let index;
      let indexSrc = src;
      while (indexSrc) {
        index = indexSrc.indexOf("$");
        if (index === -1) {
          return;
        }
        const f = nonStandard ? index > -1 : index === 0 || indexSrc.charAt(index - 1) === " ";
        if (f) {
          const possibleKatex = indexSrc.substring(index);
          if (possibleKatex.match(ruleReg)) {
            return index;
          }
        }
        indexSrc = indexSrc.substring(index + 1).replace(/^\$+/, "");
      }
    },
    tokenizer(src, tokens) {
      const match = src.match(ruleReg);
      if (match) {
        return {
          type: "inlineKatex",
          raw: match[0],
          text: match[2].trim(),
          displayMode: match[1].length === 2
        };
      }
    },
    renderer
  };
}
function blockKatex(options, renderer) {
  return {
    name: "blockKatex",
    level: "block",
    tokenizer(src, tokens) {
      const match = src.match(blockRule);
      if (match) {
        return {
          type: "blockKatex",
          raw: match[0],
          text: match[2].trim(),
          displayMode: match[1].length === 2
        };
      }
    },
    renderer
  };
}
export {
  src_default as default
};
//# sourceMappingURL=marked-katex-extension.js.map
