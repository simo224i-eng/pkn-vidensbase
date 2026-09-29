import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["EJNAR_API_EAGER_LOAD"] = "0"

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover - API-afhængigheder er valgfri
    TestClient = None

if TestClient is not None:
    import api
    import engine
    import shared
    from test_engine import rows

KEY = {"X-API-Key": "test-key"}


@unittest.skipIf(TestClient is None, "fastapi er ikke installeret")
class APITests(unittest.TestCase):
    def setUp(self):
        api.RATE.hits.clear()
        df = engine.prepare_frame(rows())
        vec, mat = engine.build_index(df)
        api.STATE.corpus = engine.Corpus(df=df, vec=vec, mat=mat, options=engine.filter_options(df))
        api.STATE.error = ""
        self.env = mock.patch.dict(os.environ, {"EJNAR_API_KEYS": "other,test-key"})
        self.env.start()
        self.client = TestClient(api.app)

    def tearDown(self):
        self.env.stop()
        api.STATE.corpus = None

    def test_health_is_public(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["decisions"], 3)

    def test_auth_required(self):
        self.assertEqual(self.client.get("/v1/meta").status_code, 401)
        self.assertEqual(self.client.get("/v1/meta", headers={"X-API-Key": "bad"}).status_code, 401)
        r = self.client.get("/v1/meta", headers={"Authorization": "Bearer test-key"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["outcome_counts"]["Afvist"], 1)

    def test_loading_returns_503(self):
        api.STATE.corpus = None
        api.STATE.started = 1.0
        r = self.client.get("/v1/meta", headers=KEY)
        self.assertEqual(r.status_code, 503)
        api.STATE.started = 0.0

    def test_exact_and_keyword_search_with_filters(self):
        r = self.client.post("/v1/search", headers=KEY, json={"query": "undertag", "mode": "exact"})
        body = r.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["results"][0]["outcome"], "Delvis medhold")
        self.assertIn("ndertag", body["results"][0]["snippet"])

        r = self.client.post("/v1/search", headers=KEY, json={
            "query": "", "mode": "exact", "filters": {"companies": ["Tryg"], "year_from": 2015}})
        self.assertEqual([d["case_number"] for d in r.json()["results"]], ["93497"])

        r = self.client.post("/v1/search", headers=KEY, json={"query": "kloak", "mode": "keyword"})
        self.assertEqual(r.status_code, 200)

    def test_get_decision(self):
        r = self.client.get("/v1/decisions/60767", headers=KEY)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Rotter", r.json()["text"])
        self.assertEqual(self.client.get("/v1/decisions/xyz", headers=KEY).status_code, 404)

    def _patched_answer(self):
        c = api.STATE.corpus
        kilder = c.df.iloc[[0, 1]].to_dict("records")
        return (
            mock.patch.object(engine, "smart_retrieval", return_value=("q", kilder)),
            mock.patch.object(shared, "llm_tilgaengelig", return_value=True),
            mock.patch.object(shared, "_llm", return_value="Praksis er fast [Kilde 2]."),
        )

    def test_answer_json(self):
        p1, p2, p3 = self._patched_answer()
        with p1, p2, p3:
            r = self.client.post("/v1/answer", headers=KEY, json={"question": "Dækkes skimmel?"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["answer"], "Praksis er fast [Kilde 2].")
        self.assertEqual([s["cited"] for s in body["sources"]], [False, True])
        self.assertEqual(body["sources"][1]["n"], 2)

    def test_answer_stream(self):
        def fake_stream(prompt, max_tokens=2000, placeholder=None):
            placeholder.markdown("Hej ▌")
            placeholder.markdown("Hej [Kilde 1]▌")
            placeholder.markdown("Hej [Kilde 1]")
            return "Hej [Kilde 1]"

        p1, p2, _ = self._patched_answer()
        with p1, p2, mock.patch.object(shared, "_llm_stream", side_effect=fake_stream):
            r = self.client.post("/v1/answer", headers=KEY, json={"question": "Dækkes skimmel?", "stream": True})
        text = r.text
        self.assertTrue(text.startswith("event: sources"))
        self.assertIn('event: delta\ndata: {"text": "Hej "}', text)
        self.assertIn('"cited": [1]', text)
        self.assertTrue(text.rstrip().split("\n")[-2].startswith("event: done"))

    def test_stats(self):
        r = self.client.post("/v1/stats", headers=KEY, json={"filters": {"companies": ["Tryg"]}})
        body = r.json()
        self.assertEqual(body["total"], 2)
        self.assertEqual([y["label"] for y in body["by_year"]], ["2010", "2021"])
        self.assertEqual(body["by_company"], [{"label": "Tryg", "total": 2, "counts": {"Ikke medhold": 1, "Afvist": 1}}])
        r = self.client.post("/v1/stats", headers=KEY, json={"query": "undertag"})
        self.assertEqual(r.json()["total"], 1)

    def test_llm_rate_limit(self):
        api.RATE.hits.clear()
        with mock.patch.dict(os.environ, {"EJNAR_LLM_RATE_PER_MIN": "1"}), \
             mock.patch.object(shared, "llm_tilgaengelig", return_value=True), \
             mock.patch.object(shared, "_llm", return_value="Resumé"):
            self.assertEqual(self.client.post("/v1/decisions/60767/summary", headers=KEY).status_code, 200)
            r = self.client.post("/v1/decisions/60767/summary", headers=KEY)
        self.assertEqual(r.status_code, 429)
        self.assertIn("Retry-After", r.headers)
        api.RATE.hits.clear()

    def test_answer_requires_llm(self):
        with mock.patch.object(shared, "llm_tilgaengelig", return_value=False):
            r = self.client.post("/v1/answer", headers=KEY, json={"question": "Hvad?"})
        self.assertEqual(r.status_code, 503)


if __name__ == "__main__":
    unittest.main()
