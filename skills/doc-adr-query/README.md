# doc-adr-query (deprecated)

`/sdd:doc-adr-query` is a deprecated alias of [`/sdd:ask`](../ask/README.md) `type:adr`.

`/sdd:ask` searches all four registries (ADRs included), loads only the documents that
match the question within a budget, and grounds every answer in `raw/`. Add `type:adr`
to restrict it to ADRs.
