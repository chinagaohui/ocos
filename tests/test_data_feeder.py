"""OCOS cognitive_nutrition/data_feeder 测试。"""

import pytest
from ocos.cognitive_nutrition.data_feeder import (
    generate_day1_fact_meals,
    generate_day2_technical_meals,
)


class TestDataFeeder:
    def test_generate_day1_facts(self):
        meals = generate_day1_fact_meals()
        assert len(meals) > 0
        for meal in meals:
            assert meal.meal_type.value == "fact"
            assert len(meal.content) > 0
            assert meal.source == "fresh"

    def test_generate_day2_technical(self):
        meals = generate_day2_technical_meals()
        assert len(meals) > 0
        for meal in meals:
            assert meal.meal_type.value == "document"
            assert len(meal.content) > 0

    def test_fact_meals_have_metadata(self):
        meals = generate_day1_fact_meals()
        for meal in meals:
            assert "fact_index" in meal.metadata
            assert "domain" in meal.metadata