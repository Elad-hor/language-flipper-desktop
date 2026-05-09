# Bug Analysis: Hebrew/English Layout Flip — Multi-Position Keys

## 1. Data Dump — The Multi-Position Keys

Full relevant JSON entries:

```json
{ "en": ",",  "he": "ת" },   // unshifted  -- both produce ת
{ "en": "<",  "he": "ת" },   // shifted    --

{ "en": ".",  "he": "ץ" },   // unshifted  -- both produce ץ
{ "en": ">",  "he": "ץ" },   // shifted    --

{ "en": ";",  "he": "ף" },   // only one entry, no collision
{ "en": "'",  "he": "'" },   // handled by explicit _HE2EN overrides below
{ "en": "\"", "he": "״" },
{ "en": "/",  "he": "." },   // only one entry for /
                               // "?" (shift+/) has NO entry at all
```

Not in JSON at all: `:` (shift+;), `?` (shift+/)

---

## 2. Logic Dump — The Relevant Code

```python
# _load() — builds both dicts from the JSON
for row in pairs:
    en = str(row.get("en", "")).lower()
    he = str(row.get("he", ""))
    _EN2HE[en] = he          # en -> he
    he_low = he.lower()
    _HE2EN[he_low] = en      # he -> en   <- last write wins, no guard

# Post-loop explicit overrides (handles geresh/gershayim variants)
_HE2EN["'"]      = "w"
_HE2EN["׳"] = "w"
_HE2EN["״"] = '"'
# ...etc

# flip_text() — direction detection then map lookup
layout = detect_layout(text)          # "en_us" or "he_il"
forward = layout == "en_us"
mapping = _EN2HE if forward else _HE2EN

for raw in text:
    low = _NORMALIZE.get(raw, raw).lower()
    mapped = mapping.get(low)          # single dict lookup
```

---

## 3. Root Cause

**Pure data/build bug in `_load()` — no guard on `_HE2EN` writes.**

When two JSON entries share the same Hebrew `he` value, the second one silently
overwrites the first in `_HE2EN`. The loop processes the JSON in order, so:

1. `{ "en": ".", "he": "ץ" }` -> `_HE2EN["ץ"] = "."`
2. `{ "en": ">", "he": "ץ" }` -> `_HE2EN["ץ"] = ">"` — **overwrites step 1**

Final result: `_HE2EN["ץ"] == ">"`, not `"."`

Same for ת:
1. `{ "en": ",", "he": "ת" }` -> `_HE2EN["ת"] = ","`
2. `{ "en": "<", "he": "ת" }` -> `_HE2EN["ת"] = "<"` — **overwrites step 1**

The `_EN2HE` dict has NO collision — `,` and `<` are different keys, both correctly
pointing to ת. The bug is **only in `_HE2EN`**.

---

## 4. Full Impact List

| Hebrew char | Expected en->he | Actual en->he | Expected he->en | Actual he->en |
|-------------|-----------------|---------------|-----------------|---------------|
| ץ           | `.` -> ץ        | correct ✓     | ץ -> `.`        | ץ -> `>` ✗   |
| ת           | `,` -> ת        | correct ✓     | ת -> `,`        | ת -> `<` ✗   |

Only **ץ and ת** are affected. All other Hebrew characters appear exactly once
as a `he` value in the JSON, so there is no overwrite.

**Clarifying note on the concrete example in the bug report:**
The code shows that `.` -> ץ (en->he) is actually **correct**.
The bug manifests in the **reverse direction**: ץ -> `>` (he->en) instead of `.`.
The reported symptom ("`.` flips to `>`") likely describes a two-step scenario
or a direction mismatch in the report, but the root cause is the same.

---

## 5. Platform Scope

**Both Mac and Windows are affected equally.**
The bug is entirely in `flipper.py` (`_load()` and `flip_text()`), which is
platform-agnostic. `text_bridge.py` has nothing to do with this — it only handles
getting/setting text from the OS clipboard; the character mapping happens before
it's involved.

---

## 6. Proposed Fix

In `_load()`, when building `_HE2EN`, add a **first-write-wins guard**: only write
to `_HE2EN[he_low]` if that key does not already exist.

This means the unshifted variant (`,` and `.`) wins over the shifted variant
(`<` and `>`), which is the correct natural behavior.

The `<` and `>` entries stay in the JSON and continue to work correctly for en->he
flipping (a user who accidentally typed `>` when they meant ץ will still get ץ).
They just no longer poison the reverse direction.

No changes needed to the JSON itself.

---

## 7. Risk Assessment

**Low risk.** The fix only affects `_HE2EN` and only for ץ and ת.

- en->he direction: **unaffected** — `_EN2HE` is not touched
- he->en for ץ: changes `>` -> `.` — the correct and expected result
- he->en for ת: changes `<` -> `,` — the correct and expected result
- Existing explicit `_HE2EN` overrides for geresh/quotes at the bottom of `_load()`
  run after the loop, so they continue to work as before. Those overrides are
  post-loop unconditional writes and must remain that way — they should NOT be
  subject to the first-write-wins guard.
- No ambiguous cases: ץ and ת each have one clearly correct English target
  (`.` and `,`)

---

Ready to implement on your approval.
