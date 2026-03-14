from dataclasses import replace

from src.domain.broll_models import BeatScoreBreakdown, ImpactBeat
from src.domain.subtitle_models import ProjectedCue, ProjectedWord, SubtitleTimeline
from src.domain.text_utils import normalize_token


class ImpactBeatDetector:
    DEFAULT_MINIMUM_SCORE = 0.68
    DEFAULT_MINIMUM_VISUALIZABILITY = 0.35
    DEFAULT_MINIMUM_TIMING_CONFIDENCE = 0.55
    DEFAULT_MIN_DURATION_MS = 700
    DEFAULT_MAX_DURATION_MS = 3000
    DEFAULT_FALLBACK_MINIMUM_SCORE = 0.58
    DEFAULT_FALLBACK_MINIMUM_SEMANTIC_SALIENCE = 0.55
    DEFAULT_MINIMUM_TIMELINE_QUALITY_FOR_FALLBACK = 0.85

    STOPWORDS = {
        "a",
        "al",
        "an",
        "and",
        "as",
        "at",
        "by",
        "con",
        "de",
        "del",
        "el",
        "en",
        "es",
        "esto",
        "for",
        "from",
        "in",
        "la",
        "las",
        "lo",
        "los",
        "of",
        "on",
        "or",
        "para",
        "por",
        "que",
        "se",
        "the",
        "to",
        "un",
        "una",
        "y",
    }
    GENERIC_TERMS = {"algo", "cosa", "cosas", "eso", "esta", "este", "esto", "tema", "thing", "things"}
    SEMANTIC_SALIENCE_TERMS = {
        "alone",
        "boss",
        "city",
        "close",
        "comment",
        "comments",
        "compliment",
        "compliments",
        "confusing",
        "course",
        "friend",
        "mind",
        "mind's",
        "negative",
        "negatives",
        "office",
        "polluted",
        "presentation",
        "quit",
        "rude",
        "stupid",
        "team",
        "thoughts",
        "weather",
        "work",
        "wrong",
    }
    SEMANTIC_PATTERNS = (
        (frozenset({"confusing", "negative"}), 0.40),
        (frozenset({"confusing", "negatives"}), 0.40),
        (frozenset({"negative", "thoughts"}), 0.40),
        (frozenset({"mind", "polluted"}), 0.40),
        (frozenset({"mind's", "polluted"}), 0.40),
        (frozenset({"boss", "presentation"}), 0.22),
        (frozenset({"team", "work"}), 0.22),
        (frozenset({"friend", "wrong"}), 0.18),
    )
    VISUAL_TERMS = {
        "accidente",
        "animal",
        "app",
        "avion",
        "beach",
        "budget",
        "cafe",
        "camera",
        "camion",
        "car",
        "cash",
        "celular",
        "city",
        "clock",
        "coche",
        "coffee",
        "computer",
        "dinero",
        "doctor",
        "dog",
        "dollar",
        "email",
        "escuela",
        "factura",
        "factory",
        "food",
        "gato",
        "grafico",
        "hospital",
        "house",
        "image",
        "kitchen",
        "laptop",
        "lluvia",
        "mapa",
        "market",
        "money",
        "mountain",
        "negocio",
        "notebook",
        "oficina",
        "paper",
        "pantalla",
        "persona",
        "phone",
        "playa",
        "product",
        "road",
        "screen",
        "ship",
        "smartphone",
        "spreadsheet",
        "store",
        "street",
        "table",
        "taxi",
        "tienda",
        "train",
        "truck",
        "video",
        "window",
    }
    ABSTRACT_TO_VISUAL = {
        "algoritmo": "computer",
        "audiencia": "people",
        "budget": "money",
        "crecimiento": "chart",
        "dinero": "cash",
        "estrategia": "whiteboard",
        "ingresos": "money",
        "mercado": "city",
        "presupuesto": "money",
        "producto": "product",
        "riesgo": "warning",
        "sistema": "computer",
        "tiempo": "clock",
        "usuario": "phone",
        "venta": "store",
    }
    EMOTIONAL_TERMS = {
        "brutal",
        "cambio",
        "crash",
        "danger",
        "dramatico",
        "fallo",
        "failed",
        "fuerte",
        "gigante",
        "confusing",
        "impacto",
        "imposible",
        "increible",
        "increíble",
        "miedo",
        "never",
        "nunca",
        "panic",
        "problema",
        "riesgo",
        "negative",
        "negatives",
        "polluted",
        "shock",
        "stupid",
        "thoughts",
        "urgent",
        "urgente",
        "wow",
        "wrong",
    }
    CONTRAST_MARKERS = {"aunque", "but", "excepto", "however", "instead", "pero", "yet"}
    NARRATIVE_MARKERS = {"entonces", "finally", "luego", "momento", "problem", "resulta", "suddenly", "then"}
    ACTION_TERMS = {
        "abrir",
        "buy",
        "caer",
        "change",
        "cerrar",
        "comprar",
        "crear",
        "fall",
        "ganar",
        "grow",
        "lanzar",
        "launch",
        "lose",
        "mostrar",
        "open",
        "romper",
        "run",
        "sell",
        "subir",
        "vender",
        "win",
    }

    def __init__(
        self,
        minimum_score: float | None = None,
        minimum_visualizability: float | None = None,
        minimum_timing_confidence: float | None = None,
        min_duration_ms: int | None = None,
        max_duration_ms: int | None = None,
        fallback_minimum_score: float | None = None,
        fallback_minimum_semantic_salience: float | None = None,
        minimum_timeline_quality_for_fallback: float | None = None,
    ):
        self.minimum_score = self.DEFAULT_MINIMUM_SCORE if minimum_score is None else minimum_score
        self.minimum_visualizability = (
            self.DEFAULT_MINIMUM_VISUALIZABILITY if minimum_visualizability is None else minimum_visualizability
        )
        self.minimum_timing_confidence = (
            self.DEFAULT_MINIMUM_TIMING_CONFIDENCE if minimum_timing_confidence is None else minimum_timing_confidence
        )
        self.min_duration_ms = self.DEFAULT_MIN_DURATION_MS if min_duration_ms is None else min_duration_ms
        self.max_duration_ms = self.DEFAULT_MAX_DURATION_MS if max_duration_ms is None else max_duration_ms
        self.fallback_minimum_score = (
            self.DEFAULT_FALLBACK_MINIMUM_SCORE if fallback_minimum_score is None else fallback_minimum_score
        )
        self.fallback_minimum_semantic_salience = (
            self.DEFAULT_FALLBACK_MINIMUM_SEMANTIC_SALIENCE
            if fallback_minimum_semantic_salience is None
            else fallback_minimum_semantic_salience
        )
        self.minimum_timeline_quality_for_fallback = (
            self.DEFAULT_MINIMUM_TIMELINE_QUALITY_FOR_FALLBACK
            if minimum_timeline_quality_for_fallback is None
            else minimum_timeline_quality_for_fallback
        )

    def detect(self, timeline: SubtitleTimeline) -> list[ImpactBeat]:
        ranked_beats = self.detect_candidates(timeline)
        accepted_beats = [beat for beat in ranked_beats if beat.scores.total >= self.minimum_score]
        if not accepted_beats:
            accepted_beats = [beat for beat in ranked_beats if "promoted near-miss high-salience beat" in beat.reasons]

        return self._assign_beat_ids(accepted_beats)

    def detect_candidates(self, timeline: SubtitleTimeline) -> list[ImpactBeat]:
        scored_beats: list[ImpactBeat] = []
        for cue in timeline.cues:
            for window in self._build_windows(cue):
                beat = self._score_impact_beat(window, cue)
                if beat is not None:
                    scored_beats.append(beat)

        ranked_beats = sorted(scored_beats, key=lambda beat: beat.scores.total, reverse=True)
        promoted_near_miss = self._promote_near_miss_beats(ranked_beats, timeline)
        if not promoted_near_miss:
            return self._assign_beat_ids(ranked_beats)

        promoted_beat = promoted_near_miss[0]
        enriched_beats: list[ImpactBeat] = []
        for beat in ranked_beats:
            if (
                beat.start_ms == promoted_beat.start_ms
                and beat.end_ms == promoted_beat.end_ms
                and beat.text == promoted_beat.text
            ):
                enriched_beats.append(promoted_beat)
            else:
                enriched_beats.append(beat)

        return self._assign_beat_ids(enriched_beats)

    @staticmethod
    def _assign_beat_ids(beats: list[ImpactBeat]) -> list[ImpactBeat]:
        return [
            ImpactBeat(
                beat_id=f"beat-{index:04d}",
                text=beat.text,
                start_ms=beat.start_ms,
                end_ms=beat.end_ms,
                duration_ms=beat.duration_ms,
                timing_mode=beat.timing_mode,
                word_confidence_avg=beat.word_confidence_avg,
                cue_quality_score=beat.cue_quality_score,
                scores=beat.scores,
                reasons=beat.reasons,
            )
            for index, beat in enumerate(beats, start=1)
        ]

    def _build_windows(self, cue: ProjectedCue) -> list[tuple[ProjectedWord, ...]]:
        windows: list[tuple[ProjectedWord, ...]] = []
        current_words: list[ProjectedWord] = []

        for word in cue.words:
            current_words.append(word)
            if self._should_close_window(current_words):
                if len(current_words) >= 2:
                    windows.append(tuple(current_words))
                current_words = []

        if len(current_words) >= 2:
            windows.append(tuple(current_words))

        return windows

    def _should_close_window(self, words: list[ProjectedWord]) -> bool:
        if len(words) >= 8:
            return True

        duration_ms = words[-1].end_ms - words[0].start_ms
        if duration_ms >= 2400:
            return True

        last_token = normalize_token(words[-1].text)
        if any(words[-1].text.endswith(marker) for marker in (".", "!", "?", ";", ":")):
            return True

        return len(words) >= 3 and last_token in self.CONTRAST_MARKERS | self.NARRATIVE_MARKERS

    def _score_impact_beat(
        self,
        words: tuple[ProjectedWord, ...],
        cue: ProjectedCue,
    ) -> ImpactBeat | None:
        normalized_tokens = [normalize_token(word.text) for word in words if normalize_token(word.text)]
        if not normalized_tokens:
            return None

        duration_ms = words[-1].end_ms - words[0].start_ms
        visualizability = self._score_visualizability(words, normalized_tokens)
        semantic_salience = self._score_semantic_salience(normalized_tokens)
        timing_confidence = self._score_timing_confidence(words, cue)
        if (
            duration_ms < self.min_duration_ms
            or duration_ms > self.max_duration_ms
            or max(visualizability, semantic_salience) < self.minimum_visualizability
            or timing_confidence < self.minimum_timing_confidence
        ):
            return None

        emotional_load = self._score_token_hits(normalized_tokens, self.EMOTIONAL_TERMS)
        contrast = self._score_token_hits(normalized_tokens, self.CONTRAST_MARKERS)
        narrative_turn = self._score_token_hits(normalized_tokens, self.NARRATIVE_MARKERS)
        verbal_force = self._score_token_hits(normalized_tokens, self.ACTION_TERMS)
        duration_fit = self._score_duration_fit(duration_ms)
        penalties = self._compute_penalties(normalized_tokens, duration_ms, cue.quality_score)

        total_score = round(
            max(
                0.0,
                min(
                    1.0,
                    (
                        0.20 * visualizability
                        + 0.25 * semantic_salience
                        + 0.18 * emotional_load
                        + 0.08 * contrast
                        + 0.05 * narrative_turn
                        + 0.05 * verbal_force
                        + 0.09 * duration_fit
                        + 0.10 * timing_confidence
                        - penalties
                    ),
                ),
            ),
            4,
        )

        return ImpactBeat(
            beat_id="",
            text=" ".join(word.text for word in words),
            start_ms=words[0].start_ms,
            end_ms=words[-1].end_ms,
            duration_ms=duration_ms,
            timing_mode=cue.timing_mode,
            word_confidence_avg=self._average_word_confidence(words),
            cue_quality_score=cue.quality_score,
            scores=BeatScoreBreakdown(
                total=total_score,
                visualizability=visualizability,
                emotional_load=emotional_load,
                contrast=contrast,
                narrative_turn=narrative_turn,
                verbal_force=verbal_force,
                duration_fit=duration_fit,
                timing_confidence=timing_confidence,
                semantic_salience=semantic_salience,
            ),
            reasons=self._build_reasons(
                normalized_tokens,
                duration_ms,
                visualizability,
                semantic_salience,
                emotional_load,
                contrast,
            ),
        )

    def _promote_near_miss_beats(
        self,
        ranked_beats: list[ImpactBeat],
        timeline: SubtitleTimeline,
    ) -> list[ImpactBeat]:
        try:
            timeline_quality = float(getattr(timeline, "quality_score", 0.0))
        except (TypeError, ValueError):
            return []

        if timeline_quality < self.minimum_timeline_quality_for_fallback:
            return []

        for beat in ranked_beats:
            if not self._is_promotable_near_miss(beat):
                continue

            return [
                replace(
                    beat,
                    reasons=beat.reasons + ("promoted near-miss high-salience beat",),
                )
            ]

        return []

    def _score_visualizability(self, words: tuple[ProjectedWord, ...], tokens: list[str]) -> float:
        concrete_hits = 0
        proper_case_hits = 0
        numeric_hits = 0

        for word, token in zip(words, tokens):
            if token.isdigit() or any(char.isdigit() for char in token):
                numeric_hits += 1
                continue

            if token in self.VISUAL_TERMS or token in self.ABSTRACT_TO_VISUAL:
                concrete_hits += 1
                continue

            if token not in self.STOPWORDS and token not in self.GENERIC_TERMS and len(token) >= 5:
                concrete_hits += 1

            if any(char.isupper() for char in word.text[:1]):
                proper_case_hits += 1

        score = 0.25 * concrete_hits + 0.20 * numeric_hits + 0.10 * proper_case_hits
        return round(min(1.0, score), 4)

    def _score_semantic_salience(self, tokens: list[str]) -> float:
        if not tokens:
            return 0.0

        token_set = set(tokens)
        score = 0.0
        score += 0.22 * sum(1 for token in token_set if token in self.SEMANTIC_SALIENCE_TERMS)
        score += 0.12 * sum(1 for token in token_set if token in self.ABSTRACT_TO_VISUAL)
        score += 0.08 * sum(1 for token in token_set if token in self.VISUAL_TERMS)
        score += 0.10 * sum(1 for token in token_set if token in self.ACTION_TERMS)

        for required_tokens, bonus in self.SEMANTIC_PATTERNS:
            if required_tokens.issubset(token_set):
                score += bonus

        return round(min(1.0, score), 4)

    def _score_timing_confidence(self, words: tuple[ProjectedWord, ...], cue: ProjectedCue) -> float:
        if cue.timing_mode == "approximate":
            return 0.0

        average_confidence = self._average_word_confidence(words)
        score = 0.65 * cue.quality_score + 0.35 * average_confidence
        return round(min(1.0, score), 4)

    @staticmethod
    def _average_word_confidence(words: tuple[ProjectedWord, ...]) -> float:
        positive_confidences = [word.confidence for word in words if word.confidence > 0]
        if not positive_confidences:
            return 0.0

        return round(sum(positive_confidences) / len(positive_confidences), 4)

    @staticmethod
    def _score_duration_fit(duration_ms: int) -> float:
        if 900 <= duration_ms <= 2200:
            return 1.0
        if duration_ms < 900:
            return round(max(0.0, duration_ms / 900), 4)
        return round(max(0.0, 1 - ((duration_ms - 2200) / 1200)), 4)

    def _compute_penalties(self, tokens: list[str], duration_ms: int, cue_quality_score: float) -> float:
        penalty = 0.0
        content_tokens = [token for token in tokens if token not in self.STOPWORDS]
        if not content_tokens:
            penalty += 0.25
        if any(token in self.GENERIC_TERMS for token in content_tokens):
            penalty += 0.12
        if duration_ms < 850 or duration_ms > 2600:
            penalty += 0.10
        if cue_quality_score < 0.70:
            penalty += 0.10
        return penalty

    @staticmethod
    def _score_token_hits(tokens: list[str], lexicon: set[str]) -> float:
        if not tokens:
            return 0.0

        hits = sum(1 for token in tokens if token in lexicon)
        return round(min(1.0, hits / max(1, min(3, len(tokens)))), 4)

    def _is_promotable_near_miss(self, beat: ImpactBeat) -> bool:
        if beat.scores.total < self.fallback_minimum_score:
            return False

        if beat.scores.semantic_salience < self.fallback_minimum_semantic_salience:
            return False

        content_tokens = [
            token
            for token in (normalize_token(part) for part in beat.text.split())
            if token and token not in self.STOPWORDS and token not in self.GENERIC_TERMS
        ]
        return len(content_tokens) >= 2

    def _build_reasons(
        self,
        tokens: list[str],
        duration_ms: int,
        visualizability: float,
        semantic_salience: float,
        emotional_load: float,
        contrast: float,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if visualizability >= 0.60:
            reasons.append("contains concrete or visual anchors")
        if semantic_salience >= 0.60:
            reasons.append("contains abstract but visually reinforceable language")
        if emotional_load >= 0.50:
            reasons.append("contains emotional or urgency language")
        if contrast >= 0.50:
            reasons.append("contains contrast or narrative shift markers")
        if 900 <= duration_ms <= 2200:
            reasons.append("duration within ideal range")
        if any(token.isdigit() or token in self.ABSTRACT_TO_VISUAL for token in tokens):
            reasons.append("has strong queryable anchors")
        return tuple(reasons)
