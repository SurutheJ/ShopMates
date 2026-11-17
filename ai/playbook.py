"""
Retrieval over the playbook: TF-IDF with cosine similarity, in plain Python.

Why not embeddings or a vector database: the playbook is a few dozen short
passages, so classic TF-IDF is accurate enough, runs in microseconds, needs no
model download (free hosting has 512 MB of disk) and works offline. The index is
built once per process.

Retrieved passages are used two ways: shown to the owner with their sources, and
passed to the LLM as grounding for drafts and answers.
"""

import math
import re
from collections import Counter
from functools import lru_cache

from .playbook_data import PASSAGES

_WORD = re.compile(r"[a-z']+")
_STOPWORDS = frozenset("""
a an and are as at be but by for from has have how i in is it its of on or our so that the their
them then there these they this to was we what when which who will with you your should would can do
does into than too very out up about over more most some any each both either
""".split())


# Query/document expansion: map everyday words to the term the playbook uses.
# Added after evaluation showed vocabulary mismatch was the main retrieval failure
# (see docs/EVALUATION.md, improvement 1).
SYNONYMS = {
    'gym': 'fitness', 'yoga': 'fitness', 'studio': 'fitness', 'workout': 'fitness', 'class': 'fitness',
    'coffee': 'cafe', 'smoothie': 'cafe', 'latte': 'cafe',
    'florist': 'flower', 'bouquet': 'flower',
    'allow': 'cap', 'limit': 'cap', 'maximum': 'cap', 'budget': 'cap',
    'fairness': 'fair', 'unfair': 'fair', 'balanced': 'fair', 'equal': 'fair',
    'price': 'spend', 'pricing': 'spend', 'expensive': 'spend', 'cheap': 'spend',
    'staff': 'staff', 'employee': 'staff', 'cashier': 'staff', 'counter': 'staff',
}


def _stem(word):
    for suffix in ('ing', 'es', 's', 'ed'):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def tokenize(text, expand=True):
    tokens = [_stem(w) for w in _WORD.findall(text.lower()) if w not in _STOPWORDS and len(w) > 1]
    if expand:
        tokens = [SYNONYMS.get(t, t) for t in tokens]
    return tokens


class Index:
    def __init__(self, passages, expand=True):
        self.passages = passages
        self.expand = expand
        docs = [tokenize(f"{p['title']} {p['title']} {' '.join(p['tags'])} {p['text']}", expand) for p in passages]
        n = len(docs)
        df = Counter(term for doc in docs for term in set(doc))
        self.idf = {term: math.log((1 + n) / (1 + count)) + 1 for term, count in df.items()}
        self.vectors = [self._vector(doc) for doc in docs]

    def _vector(self, tokens):
        tf = Counter(tokens)
        vec = {t: (1 + math.log(c)) * self.idf.get(t, 0) for t, c in tf.items() if t in self.idf}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def search(self, query, k=3, min_score=0.05):
        q = self._vector(tokenize(query, self.expand))
        scored = []
        for passage, vec in zip(self.passages, self.vectors):
            score = sum(w * vec.get(t, 0) for t, w in q.items())
            if score >= min_score:
                scored.append((score, passage))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [{**passage, 'score': round(score, 3)} for score, passage in scored[:k]]


@lru_cache(maxsize=1)
def _index():
    return Index(PASSAGES)


def search(query, k=3):
    """Top-k passages for a free-text question. Each has id, title, text, score."""
    if not (query or '').strip():
        return []
    return _index().search(query, k=k)


def passages_for_pair(proposer, recipient, k=3):
    """Passages relevant to a pair of shops, used to ground an AI draft."""
    query = (f'{proposer.get_category_display()} {recipient.get_category_display()} '
             f'{proposer.category} {recipient.category} deal discount cap')
    return _index().search(query, k=k)
