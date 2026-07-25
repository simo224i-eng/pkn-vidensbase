import tempfile
from pathlib import Path
import unittest

import pandas as pd

from ejnar.evaluation.metrics import EvaluationCase
from ejnar.evaluation.run_retrieval import (
    _metrics_input,
    discover_data_files,
    retrieve_case,
    write_jsonl,
)


class _Plan:
    intent = type("Intent", (), {"value": "exact_content_search"})()
    use_hyde = False
    expand_query = False
    use_auto_filters = False
    prioritize_lexical = True
    top_retrieve = 20
    top_final = 10


class _Shared:
    def __init__(self):
        self.expansion_calls = 0
        self.rerank_calls = 0

    def udvid_query(self, query):
        self.expansion_calls += 1
        return query + " udvidet"

    def hybrid_retrieval(self, query, df, vec, mat, embeds, sub_idx, top_retrieve, top_final):
        self.last_query = query
        return [1, 0]

    def llm_rerank(self, query, candidates, top_n):
        self.rerank_calls += 1
        return list(reversed(candidates))[:top_n]


class EvaluationRunnerTests(unittest.TestCase):
    def setUp(self):
        self.case = EvaluationCase(
            question_id="EJ-T1",
            query='Find kendelser hvor der står "undertaget er ikke ført sammen over kip"',
            intent="exact_content_search",
            expected_decision_ids=(),
            expected_terms=("undertag", "kip"),
            expected_phrase="undertaget er ikke ført sammen over kip",
        )
        self.frame = pd.DataFrame(
            [
                {
                    "Dato": pd.Timestamp("2024-01-01"),
                    "Titel": "A",
                    "Link": "https://example.test/a",
                    "Tekst": "første",
                    "Excerpt": "første",
                    "Sagsnummer": "1",
                    "Selskab": "X",
                    "Udfald": "Ikke medhold",
                    "Mangeltype": "Tag",
                },
                {
                    "Dato": pd.Timestamp("2025-01-01"),
                    "Titel": "B",
                    "Link": "https://example.test/b",
                    "Tekst": "undertaget er ikke ført sammen over kip",
                    "Excerpt": "undertaget er ikke ført sammen over kip",
                    "Sagsnummer": "2",
                    "Selskab": "Y",
                    "Udfald": "Medhold",
                    "Mangeltype": "Tag",
                },
            ]
        )

    def test_exact_query_is_not_expanded(self):
        shared = _Shared()
        payload = retrieve_case(self.case, self.frame, object(), object(), shared, top_k=2)
        self.assertEqual(shared.expansion_calls, 0)
        self.assertEqual(shared.last_query, self.case.query)
        self.assertEqual(payload["results"][0]["Sagsnummer"], "2")
        self.assertEqual(payload["detected_intent"], "exact_content_search")

    def test_rerank_is_opt_in(self):
        shared = _Shared()
        payload = retrieve_case(
            self.case, self.frame, object(), object(), shared, top_k=2, rerank=True
        )
        self.assertEqual(shared.rerank_calls, 1)
        self.assertEqual(payload["results"][0]["Sagsnummer"], "1")

    def test_metrics_input_keeps_question_ids(self):
        data = _metrics_input([
            {"question_id": "EJ-1", "results": [{"Sagsnummer": "10"}]},
            {"question_id": "EJ-2", "results": []},
        ])
        self.assertEqual(list(data), ["EJ-1", "EJ-2"])
        self.assertEqual(data["EJ-1"][0]["Sagsnummer"], "10")

    def test_write_jsonl_roundtrip_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.jsonl"
            write_jsonl(path, [{"question_id": "EJ-1", "results": []}])
            self.assertEqual(
                path.read_text(encoding="utf-8").strip(),
                '{"question_id": "EJ-1", "results": []}',
            )

    def test_discover_data_files_prefers_plain_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "ejnar_test.csv"
            expected.write_text("Dato,Titel\n", encoding="utf-8")
            self.assertEqual(discover_data_files(root), [expected])


if __name__ == "__main__":
    unittest.main()
