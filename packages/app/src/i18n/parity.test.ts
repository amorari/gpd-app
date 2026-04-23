import { describe, expect, test } from "bun:test"
import { dict as en } from "./en"
import { dict as ar } from "./ar"
import { dict as br } from "./br"
import { dict as bs } from "./bs"
import { dict as da } from "./da"
import { dict as de } from "./de"
import { dict as es } from "./es"
import { dict as fr } from "./fr"
import { dict as ja } from "./ja"
import { dict as ko } from "./ko"
import { dict as no } from "./no"
import { dict as pl } from "./pl"
import { dict as ru } from "./ru"
import { dict as th } from "./th"
import { dict as tr } from "./tr"
import { dict as zh } from "./zh"
import { dict as zht } from "./zht"

// Full key-set parity between en.ts (source of truth) and every non-English
// locale. Each locale must:
//   (a) contain every key in en — no missing entries that would silently fall
//       back to English at runtime, and
//   (b) contain no keys absent from en — stale / orphaned translations that no
//       longer correspond to any UI string.
//
// Failure messages print the first ~10 offending keys per locale so CI logs
// stay readable even when the delta is large.

const SAMPLE_LIMIT = 10

const enKeys = new Set(Object.keys(en))

const LOCALES: Record<string, Record<string, string>> = {
  ar,
  br,
  bs,
  da,
  de,
  es,
  fr,
  ja,
  ko,
  no,
  pl,
  ru,
  th,
  tr,
  zh,
  zht,
}

for (const [name, dict] of Object.entries(LOCALES)) {
  describe(`i18n parity: ${name}`, () => {
    test(`${name} contains every key from en`, () => {
      const missing = [...enKeys].filter((k) => !(k in dict))
      expect(
        missing.slice(0, SAMPLE_LIMIT),
        `${name} is missing ${missing.length} key(s) from en (showing first ${SAMPLE_LIMIT})`,
      ).toEqual([])
    })

    test(`${name} has no keys absent from en`, () => {
      const extra = Object.keys(dict).filter((k) => !enKeys.has(k))
      expect(
        extra.slice(0, SAMPLE_LIMIT),
        `${name} has ${extra.length} key(s) not present in en (showing first ${SAMPLE_LIMIT})`,
      ).toEqual([])
    })
  })
}

// Sibling check: the two "unseen session" keys previously spot-checked must
// actually be translated (i.e. not byte-identical to the English source). This
// catches the narrower regression mode where the key exists but was copied
// verbatim from en, which the superset test above cannot detect.
describe("i18n parity: targeted translation check", () => {
  const targetedKeys = [
    "command.session.previous.unseen",
    "command.session.next.unseen",
  ] as const

  for (const [name, dict] of Object.entries(LOCALES)) {
    test(`${name} translates unseen session keys (not copied from en)`, () => {
      for (const key of targetedKeys) {
        expect(dict[key], `${name}.${key} is missing`).toBeDefined()
        expect(
          dict[key],
          `${name}.${key} is byte-identical to en — likely untranslated`,
        ).not.toBe(en[key])
      }
    })
  }
})
