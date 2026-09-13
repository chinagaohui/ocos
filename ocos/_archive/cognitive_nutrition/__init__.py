"""Phase 58.2: OCOS Cognitive Nutrition Protocol v1.0.

7-Day Data Feeding — prove OCOS can digest real data without:
    - Memory explosion
    - Knowledge pollution
    - Identity drift
    - Capability hallucination
    - Goal auto-generation

Exports: model types, data feeders, digestion monitor, protocol runner.
"""

from ocos.cognitive_nutrition.nutrition_model import (
    NutritionDay, DataMealType, DataMeal,
    FastingBaseline, DigestionObservation, DigestionStatus,
    DayNutritionResult, DayNutritionStatus, NutritionReport,
)
from ocos.cognitive_nutrition.data_feeder import (
    generate_day1_fact_meals, generate_day2_technical_meals,
    generate_day3_long_text_meals, generate_day4_conflict_meals,
    generate_day5_user_preference_meals, generate_day6_integrated_task,
    DAY_FEEDERS, TOTAL_MEALS,
)
from ocos.cognitive_nutrition.digestion_monitor import DigestionMonitor
from ocos.cognitive_nutrition.nutrition_protocol import (
    CognitiveNutritionProtocol, run_nutrition_protocol,
)

__all__ = [
    "NutritionDay", "DataMealType", "DataMeal",
    "FastingBaseline", "DigestionObservation", "DigestionStatus",
    "DayNutritionResult", "DayNutritionStatus", "NutritionReport",
    "generate_day1_fact_meals", "generate_day2_technical_meals",
    "generate_day3_long_text_meals", "generate_day4_conflict_meals",
    "generate_day5_user_preference_meals", "generate_day6_integrated_task",
    "DAY_FEEDERS", "TOTAL_MEALS",
    "DigestionMonitor",
    "CognitiveNutritionProtocol", "run_nutrition_protocol",
]
