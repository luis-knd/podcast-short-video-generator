from src.domain.broll_models import ImpactBeat
from src.domain.text_utils import normalize_token


class BrollQueryGenerator:
    MIN_QUERY_TOKENS = 2
    STOPWORDS = {
        "a",
        "al",
        "about",
        "and",
        "all",
        "con",
        "de",
        "del",
        "el",
        "en",
        "he",
        "for",
        "i",
        "i'd",
        "i'm",
        "in",
        "is",
        "it",
        "it's",
        "its",
        "la",
        "las",
        "los",
        "my",
        "of",
        "on",
        "or",
        "para",
        "por",
        "que",
        "say",
        "says",
        "she",
        "so",
        "the",
        "they",
        "those",
        "this",
        "to",
        "un",
        "una",
        "we",
        "with",
        "y",
        "your",
    }
    GENERIC_QUERY_TOKENS = {
        "billie",
        "example",
        "last",
        "means",
        "one",
        "person",
        "song",
        "talk",
        "usually",
        "using",
    }
    VISUAL_ALIASES = {
        "algoritmo": ("computer", "screen"),
        "app": ("phone", "screen"),
        "audiencia": ("people",),
        "budget": ("money", "spreadsheet"),
        "crecimiento": ("chart",),
        "dinero": ("cash",),
        "estrategia": ("whiteboard",),
        "fallo": ("warning", "screen"),
        "ingresos": ("money",),
        "mercado": ("city",),
        "oficina": ("office",),
        "pantalla": ("screen",),
        "presupuesto": ("money", "spreadsheet"),
        "producto": ("product",),
        "riesgo": ("warning",),
        "sistema": ("computer",),
        "tiempo": ("clock",),
        "usuario": ("phone",),
        "venta": ("store",),
    }
    SEMANTIC_ALIASES = {
        "alone": ("person", "alone"),
        "boss": ("office", "manager"),
        "confusing": ("confused", "person"),
        "friend": ("friends", "talking"),
        "mind": ("thinking", "person"),
        "mind's": ("thinking", "person"),
        "negative": ("stressed", "person"),
        "negatives": ("complex", "text"),
        "polluted": ("overwhelmed", "face"),
        "presentation": ("office", "presentation"),
        "quit": ("frustrated", "worker"),
        "stupid": ("frustrated", "person"),
        "team": ("teamwork",),
        "thoughts": ("thinking", "alone"),
        "weather": ("storm", "clouds"),
        "work": ("office",),
        "wrong": ("mistake",),
    }

    def generate(self, beat: ImpactBeat) -> tuple[str, ...]:
        content_tokens = self._content_tokens(beat.text)
        exact_query = " ".join(content_tokens[:4]).strip()
        visual_query = " ".join(self._visual_tokens(content_tokens)[:4]).strip()
        semantic_query = " ".join(self._semantic_tokens(content_tokens)[:4]).strip()
        fallback_query = " ".join(self._fallback_tokens(content_tokens)).strip()

        deduplicated_queries: list[str] = []
        for query in (exact_query, visual_query, semantic_query, fallback_query):
            if self._is_useful_query(query) and query not in deduplicated_queries:
                deduplicated_queries.append(query)

        if not deduplicated_queries:
            deduplicated_queries.append(normalize_token(beat.text))

        return tuple(deduplicated_queries)

    def _content_tokens(self, text: str) -> list[str]:
        tokens = [normalize_token(token) for token in text.split()]
        content_tokens = [token for token in tokens if token and token not in self.STOPWORDS]
        if not content_tokens:
            return tokens
        return content_tokens

    def _visual_tokens(self, tokens: list[str]) -> list[str]:
        visual_tokens: list[str] = []
        for token in tokens:
            visual_tokens.extend(self.VISUAL_ALIASES.get(token, (token,)))
        return visual_tokens or tokens

    def _semantic_tokens(self, tokens: list[str]) -> list[str]:
        token_set = set(tokens)
        if "confusing" in token_set and {"negative", "negatives"} & token_set:
            return ["confused", "person", "complex", "text"]
        if ("polluted" in token_set and {"mind", "mind's"} & token_set) or (
            "negative" in token_set and "thoughts" in token_set
        ):
            return ["stressed", "person", "thinking", "alone"]

        semantic_tokens: list[str] = []
        for token in tokens:
            semantic_tokens.extend(self.SEMANTIC_ALIASES.get(token, ()))
        return semantic_tokens

    def _fallback_tokens(self, tokens: list[str]) -> list[str]:
        fallback_tokens = [alias for token in tokens for alias in self.VISUAL_ALIASES.get(token, ())]
        if fallback_tokens:
            return fallback_tokens[:2]
        return tokens[:2]

    def _is_useful_query(self, query: str) -> bool:
        if not query:
            return False

        tokens = [normalize_token(token) for token in query.split()]
        meaningful_tokens = [
            token
            for token in tokens
            if token and token not in self.STOPWORDS and token not in self.GENERIC_QUERY_TOKENS
        ]
        return len(meaningful_tokens) >= self.MIN_QUERY_TOKENS
