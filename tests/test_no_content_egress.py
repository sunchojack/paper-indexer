"""Document content must never be sent to third parties.

pdf2doi ships with websearch=True, which googles the first 1000 characters of
any PDF it cannot identify locally. A downloads folder holds contracts, payslips
and private drafts, so that default has to stay off. Only a DOI -- an identifier
the document volunteered about itself -- may go out over the network.
"""

import pytest

from paper_indexer.metadata import _configure_no_content_egress

pdf2doi = pytest.importorskip("pdf2doi")


def test_websearch_is_disabled():
    pdf2doi.config.set("websearch", True)  # simulate a fresh import / user override
    _configure_no_content_egress()
    assert pdf2doi.config.get("websearch") is False


def test_doi_validation_stays_enabled():
    """webvalidation sends only the resolved DOI, so it must keep working.

    Without it there is no metadata to index at all.
    """
    _configure_no_content_egress()
    assert pdf2doi.config.get("webvalidation") is True


def test_configure_is_idempotent():
    _configure_no_content_egress()
    _configure_no_content_egress()
    assert pdf2doi.config.get("websearch") is False
