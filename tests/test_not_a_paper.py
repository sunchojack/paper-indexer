"""The gate that keeps non-papers out of Zotero and Notion.

A downloads folder legitimately contains NDAs, payslips and scanned forms.
These assert the decision is made on looked-up metadata, never on the filename
fallback that paper_from_metadata applies.
"""

from paper_indexer.metadata import has_bibliographic_evidence, paper_from_metadata


def test_empty_metadata_is_not_a_paper():
    # pdf2bib returns {} when it resolves no identifier -- the common non-paper case.
    assert has_bibliographic_evidence({}) is False
    assert has_bibliographic_evidence(None) is False


def test_doi_alone_is_evidence():
    assert has_bibliographic_evidence({"doi": "10.1515/jbnst-2022-0034"}) is True
    assert has_bibliographic_evidence({"DOI": "10.1515/jbnst-2022-0034"}) is True


def test_title_alone_is_evidence():
    assert has_bibliographic_evidence({"title": "Harmonization of Product Classifications"}) is True


def test_filename_fallback_does_not_count_as_evidence():
    """The regression this whole gate exists for.

    paper_from_metadata fills a missing title from the filename, so the Paper
    always has a truthy title. Gating on the Paper would index everything.
    """
    paper = paper_from_metadata({}, "/tmp/Declaration of secrecy (1).pdf")
    assert paper.title == "Declaration of secrecy (1)"  # filename leaked in as title
    assert has_bibliographic_evidence({}) is False  # but the metadata says: not a paper


def test_blank_values_are_not_evidence():
    assert has_bibliographic_evidence({"title": "", "doi": ""}) is False
    assert has_bibliographic_evidence({"doi": None}) is False
