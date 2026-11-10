from app.kb import KnowledgeBase, parse_doc, tokenize
from app.org_config import DEFAULT_CONFIG, load


def test_tokenize_drops_stopwords_and_folds_plurals():
    assert tokenize("How do I find my Invoices and passes?") == ["find", "invoice", "passe"]
    assert tokenize("access the class") == ["access", "class"]


def test_sections_get_stable_ids_and_flags(fixture_kb):
    ids = {s.id: s for s in fixture_kb.sections}
    assert set(ids) == {
        "product/export#export-your-data-to-csv",
        "product/export#import-a-csv-file",
        "account/delete#delete-your-account",
        "policies/policy#answer-only-from-the-docs",
    }
    delete = ids["account/delete#delete-your-account"]
    assert delete.human_only and not delete.is_policy
    assert delete.text == "Deletion cannot be undone, so a person verifies every request."
    assert ids["policies/policy#answer-only-from-the-docs"].is_policy


def test_get_finds_a_section_or_none(fixture_kb):
    assert fixture_kb.get("product/export#import-a-csv-file").heading == "Import a CSV file"
    assert fixture_kb.get("nope") is None


def test_search_ranks_and_drops_unrelated(fixture_kb):
    results = fixture_kb.search("export my project data")
    assert results[0].id == "product/export#export-your-data-to-csv"
    assert all(r.score > 0 for r in results)
    assert fixture_kb.search("meaning of life") == []
    assert len(fixture_kb.search("csv export import account delete docs", k=2)) == 2


def test_top_level_doc_and_text_before_first_heading(tmp_path):
    doc = tmp_path / "faq.md"
    doc.write_text("Intro text with no heading.\n\n## Contact us\nEmail support.\n")
    (tmp_path / "README.md").write_text("## Not a doc\nskip me")
    sections = parse_doc(doc, tmp_path)
    assert [(s.id, s.area, s.title) for s in sections] == [("faq#contact-us", "general", "Faq")]
    assert [s.id for s in KnowledgeBase.load(tmp_path).sections] == ["faq#contact-us"]


def test_empty_knowledge_base_returns_nothing():
    assert KnowledgeBase([]).search("anything") == []


def test_the_shipped_docs_load_and_answer_common_questions():
    kb = KnowledgeBase.load(load(DEFAULT_CONFIG).docs_dir)
    assert len(kb.sections) >= 20
    assert any(s.human_only for s in kb.sections)
    assert any(s.is_policy for s in kb.sections)
    assert kb.search("how do I reset my password")[0].id.startswith("account/password-reset")
