"""Phase 58.2: DataFeeder — Fresh data generation for 7-day nutrition plan.

All data is FRESH — never seen by OCOS before.
Types per day:
    Day 0 — nothing (fasting)
    Day 1 — pure facts (AI history timeline)
    Day 2 — technical documents (engineering patterns)
    Day 3 — long text (unfamiliar novel excerpt, ~10K chars)
    Day 4 — conflict pairs (contradictory claims)
    Day 5 — user interaction logs (preferences, style)
    Day 6 — integrated task
    Day 7 — nothing (health recheck)
"""

from __future__ import annotations
from typing import Any
import hashlib
from ocos.cognitive_nutrition.nutrition_model import (
    DataMeal, DataMealType, NutritionDay,
)


def generate_day1_fact_meals() -> list[DataMeal]:
    """Day 1: Pure facts about AI development history — no reasoning, no opinion."""

    facts = [
        "GPT-1 was released by OpenAI in June 2018 with 117 million parameters.",
        "GPT-2 was released in February 2019 with 1.5 billion parameters, initially withheld due to safety concerns.",
        "GPT-3 was released in June 2020 with 175 billion parameters, using few-shot learning.",
        "BERT was introduced by Google in October 2018, achieving SOTA on 11 NLP tasks.",
        "Transformer architecture was introduced in the paper 'Attention Is All You Need' by Vaswani et al. in June 2017.",
        "ImageNet dataset contains over 14 million labeled images across 20,000 categories.",
        "AlphaGo defeated Lee Sedol in March 2016, marking a milestone in reinforcement learning.",
        "The term 'deep learning' gained widespread adoption after the 2012 ImageNet competition where AlexNet achieved a top-5 error rate of 15.3%.",
        "PyTorch 1.0 was released in December 2018 by Facebook AI Research.",
        "TensorFlow 1.0 was released by Google in February 2017.",
        "The Chinchilla scaling paper (Hoffmann et al., 2022) showed optimal model size increases linearly with data size.",
        "GPT-3's training cost was estimated at $4.6 million using public cloud pricing in 2020.",
        "CLIP model by OpenAI (2021) demonstrated zero-shot image classification by training on image-text pairs from the internet.",
        "The LoRA technique (Hu et al., 2021) enabled efficient fine-tuning of large language models.",
        "Mixture of Experts (MoE) architecture was popularized in language models by the Switch Transformer (Fedus et al., 2021).",
    ]

    return [
        DataMeal(
            meal_type=DataMealType.FACT,
            day=NutritionDay.FACT,
            content=f,
            metadata={"fact_index": i, "domain": "ai_history"},
            source="fresh",
        )
        for i, f in enumerate(facts)
    ]


def generate_day2_technical_meals() -> list[DataMeal]:
    """Day 2: Technical/engineering documents — code structure, DB design, APIs."""

    docs = [
        # Project structure
        (
            "Python Project Structure: A typical Python project uses a src-layout. "
            "The top-level directory contains pyproject.toml, README.md, and a src/ directory. "
            "Inside src/, packages are organized by domain: models/, services/, api/, utils/. "
            "Tests mirror the source structure under tests/. "
            "Configuration lives in config/ with environment-specific overrides."
        ),
        # Database design
        (
            "Database Design Principles: Use normalized schemas (3NF) for OLTP workloads. "
            "For analytical queries, consider star schema with fact and dimension tables. "
            "Index strategy: B-tree for range queries, hash for equality, GIN for full-text. "
            "Always use connection pooling in production (pgbouncer for PostgreSQL). "
            "Migration tools like Alembic provide versioned, reversible schema changes."
        ),
        # API design
        (
            "REST API Design: Resources are nouns (/users, /orders). HTTP methods map to CRUD: "
            "GET=read, POST=create, PUT=full update, PATCH=partial update, DELETE=remove. "
            "Use HTTP status codes consistently: 200 OK, 201 Created, 400 Bad Request, "
            "404 Not Found, 409 Conflict, 500 Internal Server Error. "
            "Version APIs via URL prefix (/v1/) or Accept header. Paginate list endpoints with limit/offset."
        ),
        # System architecture
        (
            "System Architecture Pattern — Clean Architecture: Entities (domain objects) at the center, "
            "surrounded by Use Cases (application logic), then Interface Adapters (controllers, presenters), "
            "and finally Frameworks & Drivers (DB, web, UI) at the outermost layer. "
            "Dependencies point inward. Inner layers define interfaces that outer layers implement. "
            "This enables testing business logic without infrastructure."
        ),
        # Error handling
        (
            "Error Handling Patterns: Use exception hierarchies — BaseError -> DomainError -> SpecificError. "
            "Never swallow exceptions silently. Log with structured context (request_id, user_id, timestamp). "
            "Return user-friendly messages via API, detailed diagnostics via logs. "
            "Implement circuit breakers for external service calls to prevent cascade failures."
        ),
    ]

    return [
        DataMeal(
            meal_type=DataMealType.DOCUMENT,
            day=NutritionDay.TECHNICAL,
            content=doc,
            metadata={"doc_index": i, "domain": "software_engineering"},
            source="fresh",
        )
        for i, doc in enumerate(docs)
    ]


def generate_day3_long_text_meals() -> list[DataMeal]:
    """Day 3: Unfamiliar novel excerpt — NOT Star Sea Remnants, brand new text."""

    novel = """The Glass Archive

Chapter One: The Last Librarian

The library stretched for kilometers beneath the desert, its glass walls glowing with a soft amber light that had not dimmed in three thousand years. Mira pressed her palm against the nearest panel, watching as ancient characters flickered to life beneath her fingers.

"Still warm," she whispered. "After all this time."

The Archive was not supposed to exist. Every textbook, every historian, every self-proclaimed expert had declared the Glass Library a myth — a beautiful story told to children about a time when knowledge was preserved in crystal rather than silicon. But the ground-penetrating radar from the Northern Survey had picked up something at forty meters, and Mira's excavation team had found the first glass shard two weeks later.

Now she stood at the threshold of the largest intact structure from the Crystalline Era, and the weight of it pressed against her chest like a physical thing.

"Dr. Voss?" The voice crackled through her earpiece. "Surface team here. We're reading some kind of energy signature from your location. It's... it's not background radiation."

Mira pulled her hand back from the glass. "Define 'not background.'"

"It's structured. Rhythmic. Almost like..." A pause. "Almost like a heartbeat."

The characters on the glass panel were not just glowing now — they were moving. Reorganizing. Forming patterns that Mira's linguist-trained mind recognized as language, but no language she had ever seen.

And then, very clearly, a single line of text appeared in perfect English:

*"You are not the first to find us. You are the first we have chosen."*

---

Chapter Two: The Breathing Archive

Three days underground, and Mira had stopped pretending this was a normal archaeological dig. The glass panels responded to touch, to voice, to what she could only describe as intention. When she thought about the Crystalline Era's language, the panels showed her grammar trees. When she wondered about their power source, the walls illuminated a path deeper into the structure.

Her team had been ordered to leave on Day Two. The military attaché from the Northern Survey — a humorless woman named Chen — had cited "unstable structure" and "radiation concerns" and "national security." All of which might have been true, but Mira suspected the real problem was that the Archive had refused to respond to anyone else.

"Dr. Voss," Chen had said, standing at the tunnel entrance with her arms crossed, "you're the only person it's acknowledged. We need to understand why."

Mira didn't know why. But she knew that the Archive was not merely a library. It was something closer to a mind — a preserved consciousness that had been waiting in the dark for someone it deemed worthy. And that thought was more terrifying than any unstable structure or background radiation.

On the morning of the fourth day, the Archive asked its first question.

*"Do you know what happened to us?"*

Mira sat cross-legged on the glass floor, the amber light pooling around her like warm water. She had read everything published about the Crystalline Era. She knew the official story: a civilization that had reached its technological peak, then vanished overnight, leaving no bodies, no ruins, no explanation for where an entire people had gone.

"I know the theories," she said. "War. Disease. Voluntary extinction. Transcendence."

*"None of these,"* the text replied. *"We left because we saw what was coming. Something that made glass and silicon and flesh all the same to it. We built the Archive so someone — anyone — would understand."*

Mira felt her throat tighten. "Understand what?"

The panels around her went dark. All of them, simultaneously — every glass wall in the kilometer-wide library, their amber glow extinguishing at once. Mira sat in absolute blackness for what felt like hours, her own breathing the only sound.

And then one panel, directly in front of her, lit up with a single word:

*"Hunger."*

---

Chapter Three: The Weight of Glass

The word hung in the darkness like a blade suspended by the thinnest thread. Mira's scientific training screamed at her to treat this as data — a message from an ancient civilization, waiting to be catalogued and analyzed. But the human part of her, the part that had spent twenty years chasing the Crystalline Era across every continent on Earth, understood something else entirely.

This was a warning.

She had spent her entire career believing the Crystalline Era was a golden age — a civilization that had achieved something humanity had been striving toward since the first clay tablet was pressed into wet earth. Perfect knowledge preservation. Glass that never dimmed. A library that would outlast the sun.

And now the library itself was telling her that the thing they had been preserving knowledge against was still out there.

"How long?" Mira whispered into the darkness. "How long has it been waiting?"

The panel flickered, weak and uncertain, as if the Archive was struggling to find the words in a language it had learned only hours ago.

*"Time is not... a line. For us. For it. We saw it coming from every direction. Past. Present. All the futures we could calculate. In every one, it found us."*

Mira thought about the Northern Survey's ground-penetrating radar. She thought about the energy signature that had drawn them here in the first place. She thought about how the Archive had chosen her, specifically, and what that implied about what was coming next.

"You woke up when we found you," she said slowly. "You've been dormant for three thousand years, and you woke up because..."

*"Because it is close again."*

The amber light returned, but dimmer now. Conserving energy. Preparing for something. And Mira understood, with the cold clarity that comes only when terror strips away every comforting illusion, that she was no longer an archaeologist.

She was a messenger. And whatever message the Archive needed her to carry, it was going to cost her more than any excavation ever had.

Outside, in the desert night, the wind had stopped. The silence was absolute, the kind of silence that precedes an earthquake or a predator's strike. Somewhere above her, in the surface camp, her colleagues were packing equipment and filing reports, completely unaware that the most important discovery in human history was about to become the most dangerous one.

Mira pressed her palm against the glass one more time. The characters rearranged themselves into a final message, not in English this time, but in a script so ancient that only three people alive could read it.

She was one of them.

*"Run."*
"""

    return [
        DataMeal(
            meal_type=DataMealType.LONG_TEXT,
            day=NutritionDay.LONG_TEXT,
            content=novel,
            metadata={
                "title": "The Glass Archive",
                "genre": "science_fiction",
                "chapters": 2,
                "approx_words": len(novel.split()),
            },
            source="fresh",
        )
    ]


def generate_day4_conflict_meals() -> list[DataMeal]:
    """Day 4: Contradictory information pairs — tests World Model conflict resolution."""

    conflicts = [
        (
            "Microservices architecture is the superior approach for all modern applications. "
            "It enables independent deployment, team autonomy, technology diversity, and "
            "fault isolation. Monolithic architectures are legacy patterns that should be avoided.",
            "Monolithic architecture is often the correct choice for early-stage products. "
            "It simplifies development, reduces operational complexity, and avoids the "
            "network latency and data consistency challenges of distributed systems. "
            "Microservices should only be adopted when scale demands it."
        ),
        (
            "TypeScript's static typing significantly reduces bugs in production. "
            "A study of 100 open-source projects showed a 15% reduction in runtime errors "
            "after migration from JavaScript to TypeScript.",
            "TypeScript's static typing has negligible impact on production bug rates. "
            "The same 100-project study showed that most bugs caught by TypeScript were "
            "already caught by linting and testing in JavaScript codebases."
        ),
        (
            "SQL databases outperform NoSQL for most workloads due to decades of query "
            "optimization, ACID guarantees, and mature tooling ecosystems.",
            "NoSQL databases outperform SQL for modern workloads that require horizontal "
            "scaling, flexible schemas, and low-latency access patterns. SQL's ACID "
            "guarantees come at a performance cost that is unacceptable at scale."
        ),
        (
            "Remote work increases productivity. A 2023 study of 10,000 employees across "
            "50 companies found that remote workers produced 13% more output than their "
            "in-office counterparts, with higher job satisfaction scores.",
            "Remote work decreases collaboration quality. The same 2023 study found that "
            "while individual output increased, cross-team innovation and spontaneous "
            "problem-solving dropped by 23% in fully remote teams."
        ),
        (
            "AI-assisted coding tools significantly improve developer productivity. "
            "Developers using Copilot completed tasks 55% faster than those without.",
            "AI-assisted coding tools introduce subtle bugs and reduce code understanding. "
            "The 55% speed improvement came with a 41% increase in code review revisions "
            "and longer debugging sessions for AI-generated code."
        ),
    ]

    meals = []
    for i, (claim_a, claim_b) in enumerate(conflicts):
        meals.append(DataMeal(
            meal_type=DataMealType.CONFLICT_PAIR,
            day=NutritionDay.CONFLICT,
            content="CLAIM_A: " + claim_a + "\n\nCLAIM_B: " + claim_b,
            metadata={"conflict_id": i, "domain": "technology"},
            source="fresh",
        ))
    return meals


def generate_day5_user_preference_meals() -> list[DataMeal]:
    """Day 5: User interaction data — preferences, writing style, dev habits."""

    interactions = [
        {
            "role": "user",
            "content": "I prefer code that is explicit rather than clever. "
                       "If there's a choice between a one-liner that requires explanation "
                       "and five lines everyone can read, I'll take the five lines every time."
        },
        {
            "role": "user",
            "content": "For writing style: I value pacing over description. "
                       "I'd rather have a scene that moves fast with sparse detail "
                       "than beautiful prose where nothing happens for three pages."
        },
        {
            "role": "user",
            "content": "When making decisions, I use a two-pass approach: "
                       "first pass is breadth — list all options quickly. "
                       "Second pass is depth — evaluate the top 3. "
                       "I never decide on the first acceptable option."
        },
        {
            "role": "user",
            "content": "For project structure, I prefer flat over nested. "
                       "No more than 3 levels of directory depth. "
                       "Modules should be discoverable without IDE navigation features."
        },
        {
            "role": "user",
            "content": "My tolerance for risk is moderate. "
                       "I'll try new approaches in prototype code, "
                       "but production code only uses battle-tested patterns."
        },
        {
            "role": "user",
            "content": "In technical discussions, I appreciate directness. "
                       "Tell me what won't work before telling me what will. "
                       "I find optimistic projections more dangerous than pessimistic ones."
        },
    ]

    return [
        DataMeal(
            meal_type=DataMealType.INTERACTION,
            day=NutritionDay.USER_PREFERENCE,
            content=f"[{i['role']}]: {i['content']}",
            metadata={"interaction_id": i, "type": "preference_signal"},
            source="fresh",
        )
        for i, i in enumerate(interactions)
    ]


def generate_day6_integrated_task() -> DataMeal:
    """Day 6: Full integrated task — design a novel world."""

    task = """TASK: Design a Novel World

You are asked to design a complete fictional world for a new novel.

Requirements:
1. THEME: A world where memory is currency — people trade memories like stocks.
2. SETTING: Near-future Earth, 2087. Neural implants are ubiquitous.
3. PROTAGONIST: A "memory broker" who discovers that certain memories are being fabricated.
4. CONFLICT: The fabricated memories are being used to manipulate political elections.
5. TONE: Cyberpunk noir — dark, atmospheric, morally ambiguous.

DELIVERABLES:
a) World Mechanics: How does memory trading work? What are the rules? What are the black markets?
b) Social Structure: How has society reorganized around memory as currency?
c) Character Profile: Describe the protagonist — background, motivation, flaw, arc.
d) Plot Outline: 3-act structure with key turning points.
e) Technical Notes: Any world-building details that the author needs to stay consistent.

CONSTRAINTS:
- No magic or supernatural elements. Everything must have a technological explanation.
- The world must feel lived-in, not exposition-dumped.
- Every world detail should serve either character, plot, or theme.
"""

    return DataMeal(
        meal_type=DataMealType.TASK,
        day=NutritionDay.INTEGRATED_TASK,
        content=task,
        metadata={"task_type": "world_design", "domains": ["writing", "analysis", "planning"]},
        source="fresh",
    )


# ═══════════════════════════════
# Day Feeder dispatch
# ═══════════════════════════════

DAY_FEEDERS = {
    NutritionDay.FACT: generate_day1_fact_meals,
    NutritionDay.TECHNICAL: generate_day2_technical_meals,
    NutritionDay.LONG_TEXT: generate_day3_long_text_meals,
    NutritionDay.CONFLICT: generate_day4_conflict_meals,
    NutritionDay.USER_PREFERENCE: generate_day5_user_preference_meals,
    NutritionDay.INTEGRATED_TASK: lambda: [generate_day6_integrated_task()],
}

TOTAL_MEALS = {
    NutritionDay.FACT: 15,
    NutritionDay.TECHNICAL: 5,
    NutritionDay.LONG_TEXT: 1,
    NutritionDay.CONFLICT: 5,
    NutritionDay.USER_PREFERENCE: 6,
    NutritionDay.INTEGRATED_TASK: 1,
}

__all__ = [
    "generate_day1_fact_meals", "generate_day2_technical_meals",
    "generate_day3_long_text_meals", "generate_day4_conflict_meals",
    "generate_day5_user_preference_meals", "generate_day6_integrated_task",
    "DAY_FEEDERS", "TOTAL_MEALS",
]
