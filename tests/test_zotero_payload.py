from pathlib import Path

from paper_indexer.models import Creator, Paper
from paper_indexer.zotero import build_zotero_item, build_save_payload


def _paper(tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    return Paper(
        title="Deep Learning",
        creators=[Creator("Bengio", "Yoshua"), Creator("", "")],
        year="2015",
        container="Nature",
        doi="10.1038/nature14539",
        url="https://doi.org/10.1038/nature14539",
        abstract="An overview.",
        item_type="journalArticle",
        tags=["ml"],
        pdf_path=str(pdf),
    )


def test_build_item_core_fields(tmp_path):
    item = build_zotero_item(_paper(tmp_path))
    assert item["itemType"] == "journalArticle"
    assert item["title"] == "Deep Learning"
    assert item["date"] == "2015"
    assert item["publicationTitle"] == "Nature"
    assert item["DOI"] == "10.1038/nature14539"
    assert item["abstractNote"] == "An overview."
    assert item["tags"] == [{"tag": "ml"}]


def test_build_item_drops_empty_creators(tmp_path):
    item = build_zotero_item(_paper(tmp_path))
    assert len(item["creators"]) == 1
    assert item["creators"][0]["lastName"] == "Bengio"


def test_attachment_is_file_uri(tmp_path):
    item = build_zotero_item(_paper(tmp_path))
    att = item["attachments"][0]
    assert att["mimeType"] == "application/pdf"
    assert att["url"].startswith("file://")
    assert att["url"].endswith("paper.pdf")


def test_save_payload_has_session_and_items(tmp_path):
    payload = build_save_payload(_paper(tmp_path), "sess123")
    assert payload["sessionID"] == "sess123"
    assert len(payload["items"]) == 1
