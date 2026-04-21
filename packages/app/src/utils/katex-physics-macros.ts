// Shared KaTeX macros for physics notation. Used by the chat equation editor's
// physics shortcut bar so the preview glyphs on the buttons match how the same
// notation renders when sent into the chat markdown pipeline.
//
// These approximate the most common forms from the LaTeX `physics` package.
// Overloaded/starred variants are not supported by KaTeX's macro system.

export const PHYSICS_MACROS: Record<string, string> = {
  "\\hbar": "\\hslash",

  "\\dd": "\\mathrm{d}",

  "\\dv": "\\frac{\\mathrm{d} #1}{\\mathrm{d} #2}",
  "\\pdv": "\\frac{\\partial #1}{\\partial #2}",
  "\\fdv": "\\frac{\\delta #1}{\\delta #2}",

  "\\grad": "\\nabla",
  "\\curl": "\\nabla \\times",
  "\\divergence": "\\nabla \\cdot",
  "\\div": "\\nabla \\cdot",
  "\\laplacian": "\\nabla^2",

  "\\bra": "\\langle #1 |",
  "\\ket": "| #1 \\rangle",
  "\\braket": "\\langle #1 | #2 \\rangle",
  "\\ip": "\\langle #1 , #2 \\rangle",
  "\\op": "| #1 \\rangle\\!\\langle #2 |",
  "\\expval": "\\langle #1 \\rangle",
  "\\ev": "\\langle #1 \\rangle",

  "\\comm": "\\left[ #1 , #2 \\right]",
  "\\acomm": "\\left\\{ #1 , #2 \\right\\}",
  "\\pb": "\\left\\{ #1 , #2 \\right\\}",

  "\\Tr": "\\operatorname{Tr}",
  "\\tr": "\\operatorname{tr}",
  "\\rank": "\\operatorname{rank}",
  "\\erf": "\\operatorname{erf}",
  "\\Res": "\\operatorname{Res}",
  "\\pv": "\\operatorname{P.V.}",
  "\\Re": "\\operatorname{Re}",
  "\\Im": "\\operatorname{Im}",

  "\\label": "\\htmlClass{katex-label}{}",
  "\\ref": "\\text{(#1)}",
  "\\eqref": "\\text{(#1)}",
  "\\cite": "\\text{[#1]}",
  "\\nonumber": "",
  "\\notag": "",
}
