import unittest

from app import app, build_recommendations


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.products = [
            {"id": 1, "name": "A", "category": "home", "tags": "clean, home"},
            {"id": 2, "name": "B", "category": "home", "tags": "clean"},
            {"id": 3, "name": "C", "category": "food", "tags": "meal"},
            {"id": 4, "name": "D", "category": "other", "tags": ""},
        ]
        self.transactions = [{1, 2}] * 3 + [{1, 3}] * 2 + [{3, 4}]

    def test_combines_association_content_and_popularity(self):
        recommendations = build_recommendations(
            self.products, self.transactions, viewed=[1]
        )

        self.assertNotIn(1, [rec["product"]["id"] for rec in recommendations])
        self.assertEqual(recommendations[0]["product"]["id"], 2)
        self.assertEqual(
            recommendations[0]["reason"],
            "Купують разом · Схожий товар",
        )

    def test_without_history_uses_purchase_popularity(self):
        recommendations = build_recommendations(
            self.products, self.transactions
        )

        self.assertEqual(recommendations[0]["product"]["id"], 1)
        self.assertEqual(recommendations[0]["reason"], "Популярне")

    def test_product_page_shows_description(self):
        client = app.test_client()
        response = client.get("/view/1")

        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Швидкий виїзд на дом", page)
        self.assertIn("До каталогу", page)

    def test_homepage_uses_one_combined_recommendation_section(self):
        response = app.test_client().get("/")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(page.count("<h2>Рекомендації для вас</h2>"), 1)
        self.assertIn("class=\"recommend-item\"", page)

    def test_missing_product_does_not_enter_view_history(self):
        client = app.test_client()
        response = client.get("/view/999999")

        self.assertEqual(response.status_code, 404)
        with client.session_transaction() as session:
            self.assertNotIn("viewed", session)


if __name__ == "__main__":
    unittest.main()
