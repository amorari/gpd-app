import "./chunk-G3PMV62Z.js";

// ../../node_modules/.bun/marked-shiki@1.2.1+3ec8384d7116adf9/node_modules/marked-shiki/dist/index.js
function p(i = {}) {
  const { highlight: e, container: n } = i;
  return {
    async: true,
    async walkTokens(t) {
      var s;
      if (t.type !== "code" || typeof e != "function") return;
      const [a = "text", ...l] = ((s = t.lang) == null ? void 0 : s.split(" ")) ?? [], { text: c } = t, r = await e(c, a, l), o = n ? n.replace("%l", String(a).toUpperCase()).replace("%s", r).replace("%t", c) : r;
      Object.assign(t, {
        type: "html",
        block: true,
        text: `${o}
`
      });
    }
  };
}
export {
  p as default
};
//# sourceMappingURL=marked-shiki.js.map
