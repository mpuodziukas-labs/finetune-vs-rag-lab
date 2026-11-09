from ftlab.retrieve import BM25


def test_rare_term_wins() -> None:
    docs = ["my card has not arrived", "exchange rate for euros", "top up failed again"]
    bm = BM25(docs)
    assert bm.top_k("what is the exchange rate", 1) == [1]
    assert bm.top_k("card arrived late", 1) == [0]


def test_k_larger_than_corpus_and_ties_deterministic() -> None:
    bm = BM25(["a b", "a b", "c"])
    assert bm.top_k("a", 10) == [0, 1, 2]
    assert bm.top_k("zzz", 2) == [0, 1]
