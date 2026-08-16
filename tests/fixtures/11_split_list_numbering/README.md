# 11_split_list_numbering

**Purpose:** Verify the already-supported split Word-list-numbering case in
isolation.

The RTF physically stores each list number separately from its expression:

```text
1.
Asthma/

2.
wheeze.tw.

3.
1 or 2
```

This fixture should PASS in the current v20-v2 reference implementation.

It intentionally contains no year-leading continuation line; that is tested
separately in fixture 12.
