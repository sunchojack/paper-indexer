from paper_indexer.scan import iter_new_pdfs, sha256_file
from paper_indexer.state import StateStore


def _make_pdf(folder, name, content=b"%PDF-1.4 hello"):
    p = folder / name
    p.write_bytes(content)
    return p


def test_sha256_stable(tmp_path):
    p = _make_pdf(tmp_path, "a.pdf")
    assert sha256_file(p) == sha256_file(p)


def test_iter_finds_new_and_skips_indexed(tmp_path):
    src = tmp_path / "downloads"
    src.mkdir()
    p1 = _make_pdf(src, "one.pdf", b"%PDF one")
    _make_pdf(src, "two.pdf", b"%PDF two")
    _make_pdf(src, "notes.txt", b"ignore me")  # non-pdf

    db = tmp_path / "s.db"
    with StateStore(db) as st:
        found = {c.path.name for c in iter_new_pdfs(src, st)}
        assert found == {"one.pdf", "two.pdf"}

        # Mark one as indexed; it should no longer appear.
        st.upsert(sha256_file(p1), status="indexed", filename="one.pdf")
        found2 = {c.path.name for c in iter_new_pdfs(src, st)}
        assert found2 == {"two.pdf"}


def test_since_filter(tmp_path):
    import os
    import time

    src = tmp_path / "downloads"
    src.mkdir()
    old = _make_pdf(src, "old.pdf", b"%PDF old")
    _make_pdf(src, "new.pdf", b"%PDF new")
    # Make old.pdf appear a week old.
    week_ago = time.time() - 7 * 86400
    os.utime(old, (week_ago, week_ago))

    with StateStore(tmp_path / "s.db") as st:
        recent = {c.path.name for c in iter_new_pdfs(src, st, since=time.time() - 86400)}
        assert recent == {"new.pdf"}
