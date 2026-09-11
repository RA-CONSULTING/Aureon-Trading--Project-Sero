from __future__ import annotations

from array import array
import copy
import json
from pathlib import Path
import sys

import pytest

from aureon.queen.research_corpus_index import (
    CACHE_VERSION,
    ResearchCorpusIndex,
    _decode_posting_values,
    _encode_posting_values,
)


def test_path_fragment_exclusions_are_platform_neutral(
    tmp_path: Path,
) -> None:
    included = tmp_path / "src" / "included.py"
    excluded = tmp_path / "data" / "research" / "grants" / "excluded.py"
    included.parent.mkdir(parents=True)
    excluded.parent.mkdir(parents=True)
    included.write_text("def included():\n    return 'indexed'\n", encoding="utf-8")
    excluded.write_text("def excluded():\n    return 'not indexed'\n", encoding="utf-8")

    index = ResearchCorpusIndex(
        root=str(tmp_path),
        cache_path=None,
        exclude=("data/research/grants",),
        ingest_exts=(".py",),
    )

    relative = {
        Path(path).relative_to(tmp_path).as_posix()
        for path in index._iter_source_files()
    }
    assert relative == {"src/included.py"}


def test_compact_postings_preserve_tf_and_cache_roundtrip(
    tmp_path: Path,
) -> None:
    source = tmp_path / "research.md"
    cache = tmp_path / "index.json"
    source.write_text(
        "# Compact index\n\n"
        "resonance resonance resonance appears in this paragraph.\n\n"
        "resonance appears once in this second paragraph.",
        encoding="utf-8",
    )
    cold = ResearchCorpusIndex(
        root=str(tmp_path),
        cache_path=str(cache),
        ingest_exts=(".md",),
    )
    cold.ensure_built()

    values = cold._postings["resonance"]
    assert isinstance(values, array) and values.typecode == "I" and values.itemsize == 4
    assert sorted(values[2::3]) == [1, 3]
    cold_hits = cold.search("resonance", top_k=2)
    assert cold_hits[0].paragraph_idx == 0

    payload = json.loads(cache.read_text(encoding="utf-8"))
    assert payload["version"] == CACHE_VERSION
    cached_values = payload["postings"]["resonance"]
    assert isinstance(cached_values, str)
    assert payload["posting_value_count"] == sum(
        len(postings) for postings in cold._postings.values()
    )

    warm = ResearchCorpusIndex(
        root=str(tmp_path),
        cache_path=str(cache),
        ingest_exts=(".md",),
    )
    warm.ensure_built()
    assert all(isinstance(values, array) and values.typecode == "I" for values in warm._postings.values())
    warm_hits = warm.search("resonance", top_k=2)
    assert [hit.to_dict() for hit in warm_hits] == [
        hit.to_dict() for hit in cold_hits
    ]


def test_legacy_cache_is_rejected_before_full_json_parse(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cache = tmp_path / "legacy.json"
    cache.write_text(
        '{"version":1,"root":"legacy","docs":this-is-not-valid-json',
        encoding="utf-8",
    )
    index = ResearchCorpusIndex(root=str(tmp_path), cache_path=str(cache))

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("legacy cache should fail prefix preflight")

    monkeypatch.setattr(json, "load", fail_if_called)
    assert index._try_load_cache() is False


def test_unindexable_source_does_not_force_warm_rebuild(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "empty.md").write_text("", encoding="utf-8")
    (tmp_path / "indexed.md").write_text(
        "A searchable research paragraph with enough text to retain.",
        encoding="utf-8",
    )
    cache = tmp_path / "index.json"
    cold = ResearchCorpusIndex(
        root=str(tmp_path),
        cache_path=str(cache),
        ingest_exts=(".md",),
    )
    cold.ensure_built()
    assert len(cold._source_mtimes) == 2
    assert cold.doc_count() == 1

    warm = ResearchCorpusIndex(
        root=str(tmp_path),
        cache_path=str(cache),
        ingest_exts=(".md",),
    )

    def fail_if_rebuilt(*_args, **_kwargs):
        raise AssertionError("valid warm cache should not rebuild")

    monkeypatch.setattr(warm, "build", fail_if_rebuilt)
    warm.ensure_built()
    assert warm.doc_count() == 1


@pytest.mark.parametrize("query", ["resonance", "coherence frequency", "resonance resonance", "absenttoken", ""])
def test_uint32_storage_preserves_exact_list_backed_search_and_ranking(tmp_path, query):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "alpha.md").write_text(
        "# Alpha\n\nResonance resonance resonance supports coherence across the measured frequency band.\n\n"
        "Coherence remains a separate measurement in this paragraph.", encoding="utf-8",
    )
    (corpus / "beta.md").write_text(
        "# Beta\n\nFrequency frequency frequency and resonance appear in this observation.\n\n"
        "A second resonance observation has its own frequency measurement.", encoding="utf-8",
    )
    cache = tmp_path / "cache.json"
    compact = ResearchCorpusIndex(root=str(corpus), cache_path=str(cache), ingest_exts=(".md",))
    compact.ensure_built()
    # The unchanged ranking algorithm must behave identically over its former
    # list-backed representation, including scores, ties and result truncation.
    list_backed = copy.copy(compact)
    list_backed._postings = {token: list(values) for token, values in compact._postings.items()}
    warm = ResearchCorpusIndex(root=str(corpus), cache_path=str(cache), ingest_exts=(".md",))
    assert warm._try_load_cache() is True
    warm._built = True
    for top_k in (0, 1, 3, 20):
        expected = list_backed.search(query, top_k)
        assert compact.search(query, top_k) == expected
        assert warm.search(query, top_k) == expected


def test_uint32_posting_codec_retains_existing_cache_bytes_and_boundaries():
    values = [0, 1, 255, 256, 65535, 2**32 - 1]
    compact = array("I", values)
    assert _encode_posting_values(compact) == _encode_posting_values(values)
    restored = _decode_posting_values(_encode_posting_values(values))
    assert isinstance(restored, array) and restored.typecode == "I"
    assert list(restored) == values
    assert _decode_posting_values("not-valid-base64") is None


def test_uint32_postings_reduce_retained_storage_even_with_shared_small_integers():
    documents = list(range(1000))
    paragraphs = list(range(100))
    counts = list(range(1, 8))
    values = [value for index in range(100_000) for value in (
        documents[index // 100], paragraphs[index % 100], counts[index % 7],
    )]
    compact = array("I", values)
    # Count each referenced integer object once; this avoids exaggerating the
    # baseline footprint when repeated triples share the same integer objects.
    unique_integers = {id(value): value for value in values}
    list_bytes = sys.getsizeof(values) + sum(sys.getsizeof(value) for value in unique_integers.values())
    compact_bytes = sys.getsizeof(compact)
    assert list(compact) == values
    assert compact.itemsize == 4
    assert compact_bytes < list_bytes * 0.6
