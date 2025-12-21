import logging
from types import SimpleNamespace

from src.metadata.chat import MetadataChatSession


def make_session():
    # Bypass __init__ heavy dependencies; set required attrs manually
    session = MetadataChatSession.__new__(MetadataChatSession)
    session.logger = logging.getLogger("MetadataChatSessionTest")
    session.current_metadata = {
        "topic": "old-topic",
        "summary": "old-summary",
        "key_concepts": ["alpha"],
    }
    return session


def test_merge_list_into_string_overwrites():
    session = make_session()
    session._merge_metadata({"topic": ["new-topic"]})
    assert session.current_metadata["topic"] == ["new-topic"]


def test_merge_string_into_list_wraps_string():
    session = make_session()
    session._merge_metadata({"key_concepts": "beta"})
    assert session.current_metadata["key_concepts"] == ["beta"]


def test_merge_list_into_list_deduplicates():
    session = make_session()
    session._merge_metadata({"key_concepts": ["alpha", "gamma"]})
    assert session.current_metadata["key_concepts"] == ["alpha", "gamma"]


def test_merge_string_overwrites_string():
    session = make_session()
    session._merge_metadata({"summary": "new-summary"})
    assert session.current_metadata["summary"] == "new-summary"

