from paper_indexer.state import StateStore, normalize_doi


def test_normalize_doi_variants():
    assert normalize_doi("https://doi.org/10.1/AbC") == "10.1/abc"
    assert normalize_doi("doi:10.1/AbC") == "10.1/abc"
    assert normalize_doi("  10.1/AbC ") == "10.1/abc"
    assert normalize_doi(None) is None
    assert normalize_doi("") is None


def test_is_indexed_by_hash(tmp_path):
    with StateStore(tmp_path / "s.db") as st:
        assert not st.is_indexed("abc")
        st.upsert("abc", status="indexed", doi="10.1/x", filename="a.pdf")
        assert st.is_indexed("abc")


def test_is_indexed_by_doi_different_file(tmp_path):
    with StateStore(tmp_path / "s.db") as st:
        st.upsert("hash1", status="indexed", doi="10.1/X")
        # A different file (hash) but same DOI should be considered indexed.
        assert st.is_indexed("hash2", "https://doi.org/10.1/x")


def test_error_status_not_treated_as_indexed(tmp_path):
    with StateStore(tmp_path / "s.db") as st:
        st.upsert("h", status="error", filename="bad.pdf")
        assert not st.is_indexed("h")


def test_upsert_coalesces_fields(tmp_path):
    with StateStore(tmp_path / "s.db") as st:
        st.upsert("h", status="partial", doi="10.1/x", zotero_key="ZK")
        st.upsert("h", status="indexed", notion_id="NID")
        rec = st.get("h")
        assert rec.status == "indexed"
        assert rec.zotero_key == "ZK"  # preserved
        assert rec.notion_id == "NID"  # added
