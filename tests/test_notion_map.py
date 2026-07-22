from paper_indexer.config import DEFAULT_NOTION_PROPERTIES
from paper_indexer.models import Creator, Paper
from paper_indexer.notion import build_properties


def _paper(**kw):
    base = dict(
        title="A Title",
        creators=[Creator("Doe", "Jane")],
        year="2020",
        container="Nature",
        doi="10.1/x",
        url="https://doi.org/10.1/x",
        abstract="Abs.",
        tags=["ml", "nlp"],
    )
    base.update(kw)
    return Paper(**base)


def test_build_properties_types():
    props = build_properties(_paper(), DEFAULT_NOTION_PROPERTIES)
    assert props["Title"]["title"][0]["text"]["content"] == "A Title"
    assert props["Authors"]["rich_text"][0]["text"]["content"] == "Jane Doe"
    assert props["Year"]["number"] == 2020
    assert props["URL"]["url"] == "https://doi.org/10.1/x"
    assert {o["name"] for o in props["Tags"]["multi_select"]} == {"ml", "nlp"}
    assert "start" in props["Added"]["date"]


def test_custom_property_names():
    pmap = dict(DEFAULT_NOTION_PROPERTIES, title="Name", doi="Identifier")
    props = build_properties(_paper(), pmap)
    assert "Name" in props and "Identifier" in props
    assert "Title" not in props


def test_non_numeric_year_falls_back_to_text():
    props = build_properties(_paper(year="in press"), DEFAULT_NOTION_PROPERTIES)
    assert "rich_text" in props["Year"]


def test_missing_optional_fields_omitted():
    props = build_properties(
        Paper(title="Only Title"), DEFAULT_NOTION_PROPERTIES
    )
    assert "Title" in props and "Added" in props
    assert "Authors" not in props and "DOI" not in props
