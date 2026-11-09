# ADR 0004: borrowed terms stay behind stand-in labels

Status: accepted.

Context: vendor, product and model family names in prose age fast and tie the lab to one supplier.

Decision: an identifier the code must use to call a public library API (an import name, a class or function the library exports, a config key the library requires) is not a borrowed term and stays. A vendor, product or model family name in prose, a string literal, a comment, a docstring, a log line or a file name is a borrowed term and goes behind a stand-in label such as `model-a`, with the real id only in the untracked local config. `docs/TERMS.tsv` names the stand-in for each term (or `none`), and `tests/test_qa_pins.py::test_no_vendor_words_in_src` enforces the rule by scanning strings, comments, docstrings and own identifiers while skipping import lines and imported names.

Alternative: ban the words everywhere, including imports. Rejected: it would make the library classes uncallable.
