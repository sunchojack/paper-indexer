from paper_indexer.metadata import paper_from_metadata, _creators_from, _year_from


def test_paper_from_crossref_shape():
    meta = {
        "title": ["Attention Is All You Need"],
        "author": [
            {"given": "Ashish", "family": "Vaswani"},
            {"given": "Noam", "family": "Shazeer"},
        ],
        "container-title": ["NeurIPS"],
        "DOI": "10.5555/3295222",
        "type": "proceedings-article",
        "issued": {"date-parts": [[2017, 6]]},
    }
    paper = paper_from_metadata(meta, "/tmp/x.pdf", extra_tags=["auto"])
    assert paper.title == "Attention Is All You Need"
    assert paper.item_type == "conferencePaper"
    assert paper.year == "2017"
    assert paper.container == "NeurIPS"
    assert paper.doi == "10.5555/3295222"
    assert paper.url == "https://doi.org/10.5555/3295222"
    assert paper.author_string() == "Ashish Vaswani; Noam Shazeer"
    assert "auto" in paper.tags


def test_paper_from_bibtex_string_authors():
    meta = {
        "title": "A Study",
        "author": "Doe, Jane and Smith, John",
        "journal": "Nature",
        "year": "2021-05-03",
        "ENTRYTYPE": "article",
    }
    paper = paper_from_metadata(meta, "/tmp/y.pdf")
    assert paper.item_type == "journalArticle"
    assert paper.year == "2021"
    assert [c.last_name for c in paper.creators] == ["Doe", "Smith"]


def test_title_falls_back_to_filename():
    paper = paper_from_metadata({}, "/tmp/some-paper.pdf")
    assert paper.title == "some-paper"


def test_year_extraction_helpers():
    assert _year_from(2020) == "2020"
    assert _year_from("Published 2019 in") == "2019"
    assert _year_from({"date-parts": [[2015, 1, 1]]}) == "2015"
    assert _year_from(None) is None


def test_creators_semicolon_separated_full_names():
    creators = _creators_from("Jane Doe; John Smith")
    assert creators[0].first_name == "Jane" and creators[0].last_name == "Doe"
    assert creators[1].first_name == "John" and creators[1].last_name == "Smith"


def test_creators_bibtex_and_separated():
    creators = _creators_from("Doe, Jane and Smith, John")
    assert [(c.first_name, c.last_name) for c in creators] == [
        ("Jane", "Doe"),
        ("John", "Smith"),
    ]
