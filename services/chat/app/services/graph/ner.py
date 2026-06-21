"""
Entity extractor using spaCy NER.
Fast, runs locally, no API cost.
"""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

LABEL_MAP = {
    "PERSON":      "Person",
    "ORG":         "Organisation",
    "GPE":         "Location",
    "LOC":         "Location",
    "FAC":         "Location",
    "PRODUCT":     "Product",
    "EVENT":       "Event",
    "WORK_OF_ART": "Work",
    "LAW":         "Law",
    "DATE":        "Date",
    "MONEY":       "Money",
    "NORP":        "Group",
}

_nlp = None


def get_nlp():
    global _nlp
    if _nlp is None:
        import spacy
        try:
            _nlp = spacy.load("en_core_web_trf")
        except OSError:
            logger.warning("en_core_web_trf not found, falling back to en_core_web_sm")
            _nlp = spacy.load("en_core_web_sm")
    return _nlp


@dataclass
class Entity:
    text: str
    normalized: str
    type: str
    start_char: int
    end_char: int
    confidence: float = 1.0


@dataclass
class ChunkEntities:
    chunk_id: str
    entities: list[Entity] = field(default_factory=list)


def extract_entities(chunk_id: str, text: str) -> ChunkEntities:
    """Extract named entities from a single chunk using spaCy."""
    nlp = get_nlp()
    doc = nlp(text)
    entities = []
    seen = set()

    for ent in doc.ents:
        entity_type = LABEL_MAP.get(ent.label_)
        if not entity_type:
            continue
        normalized = ent.text.strip().lower()
        if len(normalized) < 2:
            continue
        key = (normalized, entity_type)
        if key in seen:
            continue
        seen.add(key)
        entities.append(Entity(
            text=ent.text.strip(),
            normalized=normalized,
            type=entity_type,
            start_char=ent.start_char,
            end_char=ent.end_char,
        ))

    return ChunkEntities(chunk_id=chunk_id, entities=entities)


def extract_entities_batch(chunks: list[tuple[str, str]]) -> list[ChunkEntities]:
    """
    Batch extract entities from multiple (chunk_id, text) pairs.
    Uses spaCy pipe() for efficiency.
    """
    nlp = get_nlp()
    texts = [text for _, text in chunks]
    chunk_ids = [cid for cid, _ in chunks]

    results = []
    for i, doc in enumerate(nlp.pipe(texts, batch_size=32)):
        chunk_id = chunk_ids[i]
        entities = []
        seen = set()

        for ent in doc.ents:
            entity_type = LABEL_MAP.get(ent.label_)
            if not entity_type:
                continue
            normalized = ent.text.strip().lower()
            if len(normalized) < 2:
                continue
            key = (normalized, entity_type)
            if key in seen:
                continue
            seen.add(key)
            entities.append(Entity(
                text=ent.text.strip(),
                normalized=normalized,
                type=entity_type,
                start_char=ent.start_char,
                end_char=ent.end_char,
            ))

        results.append(ChunkEntities(chunk_id=chunk_id, entities=entities))

    return results
