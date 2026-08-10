"""Unit tests for the Neptune Analytics openCypher query examples."""

import io
import json
import unittest
from unittest.mock import Mock

from query_examples import (
    NeptuneAnalyticsQueryHelper,
    query_high_load_secondary_substations,
    query_path_gsp_to_property,
    query_properties_by_city,
    query_properties_by_postcode_prefix,
    query_properties_by_secondary_substation,
)


class TestNeptuneAnalyticsQueryHelper(unittest.TestCase):
    """Verify the data-plane API invocation and payload decoding."""

    def setUp(self) -> None:
        self.client = Mock()
        self.client.execute_query.return_value = {
            "payload": io.BytesIO(json.dumps({"results": [{"count": 1}]}).encode())
        }
        self.helper = NeptuneAnalyticsQueryHelper(
            graph_id="g-0123456789",
            region="us-east-1",
            client=self.client,
        )

    def test_execute_query_uses_open_cypher_and_structured_parameters(self) -> None:
        results = self.helper.execute_query(
            "MATCH (p:Property) WHERE p.address_city = $city RETURN p",
            parameters={"city": "Manchester"},
            description="test query",
        )

        self.assertEqual(results, [{"count": 1}])
        self.client.execute_query.assert_called_once_with(
            graphIdentifier="g-0123456789",
            queryString="MATCH (p:Property) WHERE p.address_city = $city RETURN p",
            language="OPEN_CYPHER",
            parameters={"city": "Manchester"},
            planCache="AUTO",
            queryTimeoutMilliseconds=10_000,
        )

    def test_decode_payload_accepts_a_top_level_list(self) -> None:
        self.client.execute_query.return_value = {
            "payload": io.BytesIO(b'[{"id": "SS001"}]')
        }

        results = self.helper.execute_query("MATCH (n) RETURN n")

        self.assertEqual(results, [{"id": "SS001"}])

    def test_empty_graph_identifier_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            NeptuneAnalyticsQueryHelper(graph_id="", client=self.client)

    def test_excessive_query_timeout_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            NeptuneAnalyticsQueryHelper(
                graph_id="g-0123456789",
                client=self.client,
                query_timeout_milliseconds=30_001,
            )


class TestOpenCypherExamples(unittest.TestCase):
    """Verify examples bind user values as parameters rather than query text."""

    def setUp(self) -> None:
        self.helper = Mock()
        self.helper.execute_query.return_value = []

    def test_city_query_uses_city_and_limit_parameters(self) -> None:
        query_properties_by_city(self.helper, "Manchester", limit=20)

        query = self.helper.execute_query.call_args.args[0]
        parameters = self.helper.execute_query.call_args.kwargs["parameters"]
        self.assertIn("$city", query)
        self.assertNotIn("Manchester", query)
        self.assertEqual(parameters, {"city": "Manchester", "limit": 20})

    def test_postcode_prefix_is_normalized_and_parameterized(self) -> None:
        query_properties_by_postcode_prefix(self.helper, "m1", limit=10)

        query = self.helper.execute_query.call_args.args[0]
        parameters = self.helper.execute_query.call_args.kwargs["parameters"]
        self.assertIn("$postcode_prefix", query)
        self.assertEqual(parameters, {"postcode_prefix": "M1", "limit": 10})

    def test_substation_query_uses_parameters(self) -> None:
        query_properties_by_secondary_substation(self.helper, "SS001", limit=5)

        query = self.helper.execute_query.call_args.args[0]
        parameters = self.helper.execute_query.call_args.kwargs["parameters"]
        self.assertIn("$substation_id", query)
        self.assertEqual(parameters, {"substation_id": "SS001", "limit": 5})

    def test_high_load_query_validates_limit(self) -> None:
        with self.assertRaises(ValueError):
            query_high_load_secondary_substations(self.helper, limit=0)

    def test_path_query_uses_parameters(self) -> None:
        query_path_gsp_to_property(self.helper, "GSP001", "100012345678")

        query = self.helper.execute_query.call_args.args[0]
        parameters = self.helper.execute_query.call_args.kwargs["parameters"]
        self.assertIn("$gsp_id", query)
        self.assertIn("$uprn", query)
        self.assertEqual(
            parameters,
            {"gsp_id": "GSP001", "uprn": "100012345678"},
        )


if __name__ == "__main__":
    unittest.main()
