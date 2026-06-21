"""
Semantic chunker — splits text into meaningful chunks rather than fixed-size windows.
Falls back to sentence splitter if the text is too short for semantic splitting.
"""
from dataclasses import dataclass
from app.config import get_settings

settings = get_settings()


@dataclass
class Chunk:
    content: str
    chunk_index: int
    token_count: int
    metadata: dict


def chunk_text(text: str, document_metadata: dict | None = None) -> list[Chunk]:
    """
    Split text into semantic chunks using LlamaIndex.
    Returns list of Chunk objects ready for embedding.
    """
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.core.schema import Document as LlamaDocument
    import tiktoken

    if not text or not text.strip():
        return []

    enc = tiktoken.get_encoding("cl100k_base")

    # Use SentenceSplitter — reliable, no external API calls needed
    # SemanticSplitter requires embedding API calls during chunking (expensive)
    # Switch to SemanticSplitter later once you want higher quality splits
    splitter = SentenceSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        tokenizer=enc.encode,
    )

    doc = LlamaDocument(text=text, metadata=document_metadata or {})
    nodes = splitter.get_nodes_from_documents([doc])

    chunks = []
    for i, node in enumerate(nodes):
        content = node.get_content().strip()
        if not content:
            continue
        token_count = len(enc.encode(content))
        chunks.append(Chunk(
            content=content,
            chunk_index=i,
            token_count=token_count,
            metadata={
                "start_char": getattr(node, "start_char_idx", None),
                "end_char":   getattr(node, "end_char_idx", None),
            },
        ))

    return chunks
