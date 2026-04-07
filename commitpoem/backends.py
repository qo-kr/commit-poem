from __future__ import annotations

import random
from typing import Protocol

from anthropic import Anthropic
from openai import OpenAI

# fmt: off
# 한국 시인 100명 (Korean poets)
_KOREAN_POETS: list[str] = [
    # 근현대 대표 시인
    "김소월 (Kim So-wol)", "서정주 (Seo Jeong-ju)", "정지용 (Jeong Ji-yong)",
    "김수영 (Kim Su-yeong)", "백석 (Baek Seok)", "한용운 (Han Yong-un)",
    "김춘수 (Kim Chun-su)", "이상 (Yi Sang)", "박목월 (Park Mok-wol)",
    "윤동주 (Yun Dong-ju)", "김영랑 (Kim Yeong-nang)", "이육사 (Yi Yuk-sa)",
    "박인환 (Park In-hwan)", "김광균 (Kim Gwang-gyun)", "김현승 (Kim Hyeon-seung)",
    "노천명 (No Cheon-myeong)", "고은 (Ko Un)", "신경림 (Shin Gyeong-nim)",
    "김남조 (Kim Nam-jo)", "김지하 (Kim Ji-ha)", "신동엽 (Shin Dong-yeop)",
    "박재삼 (Park Jae-sam)", "조지훈 (Jo Ji-hun)", "박두진 (Park Du-jin)",
    "정호승 (Jeong Ho-seung)", "안도현 (An Do-hyeon)", "김용택 (Kim Yong-taek)",
    "도종환 (Do Jong-hwan)", "나태주 (Na Tae-ju)", "문정희 (Moon Jeong-hee)",
    # 현대 시인
    "황동규 (Hwang Dong-gyu)", "기형도 (Ki Hyung-do)", "정현종 (Jung Hyun-jong)",
    "오규원 (O Gyu-won)", "이성복 (Lee Seong-bok)", "황지우 (Hwang Ji-wu)",
    "최승자 (Choi Seung-ja)", "구상 (Ku Sang)", "허영자 (Heo Yeong-ja)",
    "이근배 (Lee Geun-bae)", "김종해 (Kim Jong-hae)", "이건청 (Lee Geon-cheong)",
    "오세영 (O Se-yeong)", "신달자 (Shin Dal-ja)", "최동호 (Choi Dong-ho)",
    "유자효 (Yu Ja-hyo)", "유안진 (Yu An-jin)", "김광규 (Kim Kwang-gyu)",
    "마종기 (Ma Jong-gi)", "오상순 (O Sang-sun)", "김동환 (Kim Dong-hwan)",
    "김종삼 (Kim Jong-sam)", "김혜순 (Kim Hye-soon)", "황인숙 (Hwang In-suk)",
    "강은교 (Kang Eun-gyo)", "곽재구 (Kwak Jae-gu)", "이성부 (Lee Seong-bu)",
    "천양희 (Cheon Yang-hui)", "허수경 (Heo Su-gyeong)", "나희덕 (Na Hee-deok)",
    "최영미 (Choi Yeong-mi)", "이문재 (Lee Mun-jae)", "문태준 (Moon Tae-jun)",
    "손택수 (Son Taek-su)", "김기택 (Kim Ki-taek)", "이승훈 (Lee Seung-hun)",
    "김종길 (Kim Jong-gil)", "송찬호 (Song Chan-ho)", "문인수 (Moon In-su)",
    "하종오 (Ha Jong-o)", "이재무 (Lee Jae-mu)", "심보선 (Shim Bo-seon)",
    "김소연 (Kim So-yeon)", "김경주 (Kim Gyeong-ju)", "이병률 (Lee Byeong-ryul)",
    "박형준 (Park Hyeong-jun)", "장석남 (Jang Seok-nam)", "김상용 (Kim Sang-yong)",
    "주요한 (Ju Yo-han)", "김동명 (Kim Dong-myeong)", "조병화 (Jo Byeong-hwa)",
    "박남수 (Park Nam-su)", "김달진 (Kim Dal-jin)", "이형기 (Lee Hyeong-gi)",
    # 고전 시인
    "정철 (Jeong Cheol)", "윤선도 (Yun Seon-do)", "황진이 (Hwang Jin-i)",
    "허난설헌 (Heo Nan-seol-heon)", "박인로 (Park In-no)", "송순 (Song Sun)",
    "이황 (Yi Hwang)", "이이 (Yi I)", "정몽주 (Jeong Mong-ju)",
    "김삿갓 (Kim Sat-gat)", "정약용 (Jeong Yak-yong)", "이색 (Yi Saek)",
    "김천택 (Kim Cheon-taek)", "성삼문 (Seong Sam-mun)", "김시습 (Kim Si-seup)",
    "윤석산 (Yun Seok-san)",
]

# 외국 시인 100명 (International poets)
_INTL_POETS: list[str] = [
    # 영미권
    "William Shakespeare", "Emily Dickinson", "Robert Frost", "Walt Whitman",
    "Edgar Allan Poe", "Maya Angelou", "Langston Hughes", "Sylvia Plath",
    "T.S. Eliot", "E.E. Cummings", "Wallace Stevens", "Allen Ginsberg",
    "Ezra Pound", "Carl Sandburg", "Mary Oliver", "Anne Sexton",
    "Edna St. Vincent Millay", "Henry Wadsworth Longfellow", "Ralph Waldo Emerson",
    "Shel Silverstein", "Oscar Wilde",
    # 영국/아일랜드
    "William Butler Yeats", "John Keats", "William Blake", "William Wordsworth",
    "John Milton", "Geoffrey Chaucer", "Percy Bysshe Shelley", "Lord Byron",
    "Samuel Taylor Coleridge", "Alfred Lord Tennyson", "Rudyard Kipling",
    "Dylan Thomas", "John Donne", "Gerard Manley Hopkins", "Philip Larkin",
    "Ted Hughes", "Robert Burns", "Robert Browning", "Elizabeth Barrett Browning",
    "Christina Rossetti", "W.H. Auden", "Seamus Heaney", "Amy Lowell",
    # 독일/오스트리아
    "Johann Wolfgang von Goethe", "Rainer Maria Rilke", "Paul Celan",
    # 프랑스
    "Charles Baudelaire", "Arthur Rimbaud", "Paul Verlaine", "Victor Hugo",
    "Stephane Mallarme", "Paul Valery",
    # 이탈리아
    "Dante Alighieri", "Petrarch", "Giuseppe Ungaretti", "Eugenio Montale",
    "Giacomo Leopardi",
    # 스페인/포르투갈
    "Federico Garcia Lorca", "Fernando Pessoa",
    # 러시아
    "Alexander Pushkin", "Anna Akhmatova", "Marina Tsvetaeva",
    "Boris Pasternak", "Osip Mandelstam",
    # 중남미
    "Pablo Neruda", "Octavio Paz", "Gabriela Mistral", "Cesar Vallejo",
    # 그리스/로마 고전
    "Homer", "Sappho", "Virgil", "Ovid", "Catullus", "Lucretius", "Pindar", "Horace",
    # 페르시아/아랍
    "Rumi", "Omar Khayyam", "Hafiz", "Al-Mutanabbi", "Mahmoud Darwish", "Nizar Qabbani",
    # 인도
    "Rabindranath Tagore", "Kalidasa",
    # 동아시아
    "Matsuo Basho", "Li Bai", "Du Fu", "Wang Wei", "Bai Juyi",
    # 아프리카/카리브
    "Wole Soyinka", "Leopold Sedar Senghor", "Derek Walcott", "Aime Cesaire",
    # 폴란드
    "Wislawa Szymborska", "Czeslaw Milosz",
    # 스웨덴
    "Tomas Transtromer",
    # 이스라엘
    "Yehuda Amichai",
    # 중국 현대
    "Bei Dao",
    # 조지아
    "Nikoloz Baratashvili",
]
# fmt: on

_POETS: list[str] = _KOREAN_POETS + _INTL_POETS


class LLMBackend(Protocol):
    """Structural protocol all LLM backend classes must satisfy."""

    def generate_poem(self, commits: list[str], model: str) -> str:
        """Generate a poem from a list of commit messages using the given model."""
        ...


def _build_prompt(commits: list[str]) -> str:
    """Format a list of commit message strings into a single prompt string."""
    if not commits:
        commits_text = "(no commits)"
    else:
        commits_text = "\n".join(f"- {c}" for c in commits)
    from datetime import date

    today = date.today()
    day_seed = today.year * 1000 + today.timetuple().tm_yday  # unique per day
    rng = random.Random(day_seed)
    poet = rng.choice(_POETS)
    return (
        f"You are a poet writing in the style of {poet}.\n"
        "Below are today's git commit messages from a software project.\n\n"
        f"{commits_text}\n\n"
        "First, identify 1-3 *specific* and *interesting* details from these commits "
        "(e.g. a function name, a bug that was fixed, a clever trick, a refactor, "
        "a surprising change, a meaningful variable name, a deleted file, etc.). "
        "Then weave those concrete details directly into the poems — "
        "name them, allude to them, let the reader almost feel what changed.\n\n"
        "Write TWO short poems (4-8 lines each):\n"
        "1. First poem: in English\n"
        "2. Second poem: in Korean (한국어) — 영어 기술 용어(함수명, 파일명 등)는 그대로 섞어서 (영한 혼용)\n\n"
        f"Write in the distinctive style of {poet}. "
        f"End each poem with: \"— in the style of {poet}\"\n"
        "Label them with 🇺🇸 and 🇰🇷 headers.\n"
        "Do NOT be vague or generic. The poem should feel like it's about *this* code, *this* day."
    )


class AnthropicBackend:
    """LLM backend that uses the Anthropic API to generate poems."""

    def __init__(self, api_key: str) -> None:
        """Initialise with the given Anthropic API key."""
        self._api_key = api_key

    def generate_poem(self, commits: list[str], model: str) -> str:
        """Generate a poem from commit messages using the specified Anthropic model."""
        prompt = _build_prompt(commits)
        client = Anthropic(api_key=self._api_key)
        resp = client.messages.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        return resp.content[0].text


class OpenAIBackend:
    """LLM backend that uses the OpenAI API to generate poems."""

    def __init__(self, api_key: str) -> None:
        """Initialise with the given OpenAI API key."""
        self._api_key = api_key

    def generate_poem(self, commits: list[str], model: str) -> str:
        """Generate a poem from commit messages using the specified OpenAI model."""
        prompt = _build_prompt(commits)
        client = OpenAI(api_key=self._api_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content


_BACKENDS: dict[str, type] = {
    "anthropic": AnthropicBackend,
    "openai": OpenAIBackend,
}


def get_backend(name: str, api_key: str) -> LLMBackend:
    """Return an LLMBackend instance for the given backend name and API key.

    Raises:
        ValueError: If *name* is not a supported backend name.
    """
    if name not in _BACKENDS:
        supported = ", ".join(sorted(_BACKENDS.keys()))
        raise ValueError(
            f"Unsupported backend {name!r}. Supported backends: {supported}"
        )
    backend_cls = _BACKENDS[name]
    return backend_cls(api_key=api_key)
