# 12_year_leading_continuation

**Purpose:** Isolate the documented year-leading continuation defect.

The RTF source physically contains:

```text
1. asthma.tw.
2. (2019 publication or
2020 publication).tw.
3. 1 or 2
```

The line beginning `2020 publication...` is a continuation of row 2. It must
not become a new strategy row numbered 2020.

**Current reference implementation:** KNOWN_FAIL.

Do not weaken this fixture. Correct the parser.
