#!/usr/bin/env python3
"""
Neptune Analytics openCypher query examples.

The sample data is imported into Neptune Analytics. This script uses the
Neptune Analytics data-plane API instead of direct database connections, and
all values supplied to a query are passed as openCypher parameters.

Usage:
    export NEPTUNE_GRAPH_ID="g-0123456789"
    python src/query_examples.py --query properties-by-city --city Manchester
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError


DEFAULT_QUERY_TIMEOUT_MILLISECONDS = 10_000
MAX_RESULT_LIMIT = 100
MAX_QUERY_TIMEOUT_MILLISECONDS = 30_000

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure concise command-line logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


class NeptuneAnalyticsQueryHelper:
    """Execute parameterized openCypher queries through Neptune Analytics."""

    def __init__(
        self,
        graph_id: str,
        region: Optional[str] = None,
        client: Optional[Any] = None,
        query_timeout_milliseconds: int = DEFAULT_QUERY_TIMEOUT_MILLISECONDS,
    ) -> None:
        if not graph_id:
            raise ValueError("A Neptune Analytics graph identifier is required.")
        self.graph_id = graph_id
        self.query_timeout_milliseconds = _validate_timeout(
            query_timeout_milliseconds
        )
        self.client = client or boto3.client("neptune-graph", region_name=region)

    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        description: str = "",
    ) -> List[Dict[str, Any]]:
        """Execute a static openCypher query and decode its JSON payload."""
        if description:
            logger.info("Running query: %s", description)

        start_time = time.monotonic()
        response = self.client.execute_query(
            graphIdentifier=self.graph_id,
            queryString=query,
            language="OPEN_CYPHER",
            parameters=parameters or {},
            planCache="AUTO",
            queryTimeoutMilliseconds=self.query_timeout_milliseconds,
        )
        records = self._decode_payload(response["payload"])
        logger.info(
            "Query completed in %.3fs and returned %d record(s).",
            time.monotonic() - start_time,
            len(records),
        )
        return records

    @staticmethod
    def _decode_payload(payload: Any) -> List[Dict[str, Any]]:
        """Decode the streaming JSON response returned by ExecuteQuery."""
        raw_payload = payload.read() if hasattr(payload, "read") else payload
        if isinstance(raw_payload, bytes):
            raw_payload = raw_payload.decode("utf-8")
        if not raw_payload:
            return []

        decoded = json.loads(raw_payload)
        if isinstance(decoded, list):
            return decoded
        if isinstance(decoded, dict):
            results = decoded.get("results")
            if isinstance(results, list):
                return results
            return [decoded]
        raise ValueError("Neptune Analytics returned an unexpected query payload.")


def _require_text(value: str, name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty.")
    return normalized


def _validate_limit(limit: int) -> int:
    if isinstance(limit, bool) or not 1 <= limit <= MAX_RESULT_LIMIT:
        raise ValueError(f"limit must be an integer between 1 and {MAX_RESULT_LIMIT}.")
    return limit


def _validate_timeout(timeout_milliseconds: int) -> int:
    if (
        isinstance(timeout_milliseconds, bool)
        or not 1 <= timeout_milliseconds <= MAX_QUERY_TIMEOUT_MILLISECONDS
    ):
        raise ValueError(
            "Query timeout must be an integer between 1 and "
            f"{MAX_QUERY_TIMEOUT_MILLISECONDS} milliseconds."
        )
    return timeout_milliseconds


def query_count_properties_by_type(
    helper: NeptuneAnalyticsQueryHelper,
) -> List[Dict[str, Any]]:
    """Count properties by type."""
    return helper.execute_query(
        """
        MATCH (property:Property)
        RETURN property.property_type AS property_type, count(property) AS count
        ORDER BY count DESC
        """,
        description="count properties by type",
    )


def query_properties_by_secondary_substation(
    helper: NeptuneAnalyticsQueryHelper,
    substation_id: str,
    limit: int = 25,
) -> List[Dict[str, Any]]:
    """Find properties connected to a secondary substation."""
    return helper.execute_query(
        """
        MATCH (substation:SecondarySubstation {id: $substation_id})
              <-[:CONNECTS]-(property:Property)
        RETURN property.uprn AS uprn,
               property.address_city AS city,
               property.postcode AS postcode,
               property.peak_demand_kw AS peak_demand_kw
        ORDER BY property.postcode
        LIMIT $limit
        """,
        parameters={
            "substation_id": _require_text(substation_id, "substation_id"),
            "limit": _validate_limit(limit),
        },
        description="find properties connected to a secondary substation",
    )


def query_properties_by_city(
    helper: NeptuneAnalyticsQueryHelper,
    city: str,
    limit: int = 25,
) -> List[Dict[str, Any]]:
    """Find properties in a city."""
    return helper.execute_query(
        """
        MATCH (property:Property)
        WHERE property.address_city = $city
        RETURN property.uprn AS uprn,
               property.address_number AS address_number,
               property.address_street AS address_street,
               property.postcode AS postcode,
               property.property_type AS property_type,
               property.peak_demand_kw AS peak_demand_kw
        ORDER BY property.postcode, property.address_street
        LIMIT $limit
        """,
        parameters={
            "city": _require_text(city, "city"),
            "limit": _validate_limit(limit),
        },
        description="find properties by city",
    )


def query_properties_by_postcode_prefix(
    helper: NeptuneAnalyticsQueryHelper,
    postcode_prefix: str,
    limit: int = 25,
) -> List[Dict[str, Any]]:
    """Find properties whose postcode starts with a supplied prefix."""
    normalized_prefix = _require_text(postcode_prefix, "postcode_prefix").upper()
    if len(normalized_prefix) > 8:
        raise ValueError("postcode_prefix must contain at most 8 characters.")

    return helper.execute_query(
        """
        MATCH (property:Property)
        WHERE property.postcode STARTS WITH $postcode_prefix
        RETURN property.uprn AS uprn,
               property.address_city AS city,
               property.postcode AS postcode,
               property.property_type AS property_type
        ORDER BY property.postcode
        LIMIT $limit
        """,
        parameters={
            "postcode_prefix": normalized_prefix,
            "limit": _validate_limit(limit),
        },
        description="find properties by postcode prefix",
    )


def query_total_load_secondary_substation(
    helper: NeptuneAnalyticsQueryHelper,
    substation_id: str,
) -> List[Dict[str, Any]]:
    """Calculate the total connected load for a secondary substation."""
    return helper.execute_query(
        """
        MATCH (substation:SecondarySubstation {id: $substation_id})
              <-[:CONNECTS]-(property:Property)
        RETURN substation.id AS substation_id,
               substation.name AS substation_name,
               count(property) AS property_count,
               sum(property.peak_demand_kw) AS total_load_kw,
               substation.transformer_capacity_kva AS capacity_kva
        """,
        parameters={"substation_id": _require_text(substation_id, "substation_id")},
        description="calculate total secondary-substation load",
    )


def query_high_load_secondary_substations(
    helper: NeptuneAnalyticsQueryHelper,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Find the secondary substations with the highest connected load."""
    return helper.execute_query(
        """
        MATCH (substation:SecondarySubstation)<-[:CONNECTS]-(property:Property)
        WITH substation,
             sum(property.peak_demand_kw) AS total_load_kw,
             count(property) AS property_count
        RETURN substation.id AS substation_id,
               substation.name AS substation_name,
               substation.location AS location,
               substation.transformer_capacity_kva AS capacity_kva,
               property_count,
               total_load_kw,
               (total_load_kw / substation.transformer_capacity_kva * 100)
                 AS utilization_percent
        ORDER BY total_load_kw DESC
        LIMIT $limit
        """,
        parameters={"limit": _validate_limit(limit)},
        description="find high-load secondary substations",
    )


def query_path_gsp_to_property(
    helper: NeptuneAnalyticsQueryHelper,
    gsp_id: str,
    uprn: str,
) -> List[Dict[str, Any]]:
    """Trace a supply path from a Grid Supply Point to a property."""
    return helper.execute_query(
        """
        MATCH path = (gsp:GridSupplyPoint {id: $gsp_id})
              -[:FEEDS]->(:PrimarySubstation)
              -[:SUPPLIES*1..4]->(:SecondarySubstation)
              <-[:CONNECTS]-(property:Property {uprn: $uprn})
        RETURN path
        LIMIT 1
        """,
        parameters={
            "gsp_id": _require_text(gsp_id, "gsp_id"),
            "uprn": _require_text(uprn, "uprn"),
        },
        description="trace a Grid Supply Point to property path",
    )


def print_results(results: List[Dict[str, Any]]) -> None:
    """Render query records as readable JSON."""
    print(json.dumps(results, indent=2, default=str))


def run_query(args: argparse.Namespace, helper: NeptuneAnalyticsQueryHelper) -> List[Dict[str, Any]]:
    """Run one named, parameterized example."""
    if args.query == "count-properties-by-type":
        return query_count_properties_by_type(helper)
    if args.query == "properties-by-city":
        return query_properties_by_city(helper, args.city, args.limit)
    if args.query == "properties-by-substation":
        return query_properties_by_secondary_substation(
            helper, args.secondary_substation_id, args.limit
        )
    if args.query == "properties-by-postcode-prefix":
        return query_properties_by_postcode_prefix(
            helper, args.postcode_prefix, args.limit
        )
    if args.query == "substation-load":
        return query_total_load_secondary_substation(
            helper, args.secondary_substation_id
        )
    if args.query == "high-load-substations":
        return query_high_load_secondary_substations(helper, args.limit)
    if args.query == "gsp-to-property-path":
        return query_path_gsp_to_property(helper, args.gsp_id, args.uprn)
    raise ValueError(f"Unsupported query example: {args.query}")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""
    parser = argparse.ArgumentParser(
        description="Run parameterized openCypher examples against Neptune Analytics."
    )
    parser.add_argument(
        "--graph-id",
        default=os.environ.get("NEPTUNE_GRAPH_ID"),
        help="Neptune Analytics graph identifier (or set NEPTUNE_GRAPH_ID).",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION")),
        help="AWS Region for the Neptune Analytics graph.",
    )
    parser.add_argument(
        "--query",
        default="count-properties-by-type",
        choices=(
            "count-properties-by-type",
            "properties-by-city",
            "properties-by-substation",
            "properties-by-postcode-prefix",
            "substation-load",
            "high-load-substations",
            "gsp-to-property-path",
        ),
        help="Named example to run.",
    )
    parser.add_argument("--city", default="Manchester")
    parser.add_argument("--secondary-substation-id", default="SS001")
    parser.add_argument("--postcode-prefix", default="M1")
    parser.add_argument("--gsp-id", default="GSP001")
    parser.add_argument("--uprn", default="100012345678")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help=f"Maximum records to return (1-{MAX_RESULT_LIMIT}).",
    )
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=DEFAULT_QUERY_TIMEOUT_MILLISECONDS,
        help=(
            "Neptune Analytics query timeout in milliseconds "
            f"(1-{MAX_QUERY_TIMEOUT_MILLISECONDS})."
        ),
    )
    return parser


def main() -> int:
    """Run the selected example and return a shell status code."""
    configure_logging()
    args = build_parser().parse_args()
    if not args.graph_id:
        logger.error("Set NEPTUNE_GRAPH_ID or provide --graph-id.")
        return 2

    try:
        helper = NeptuneAnalyticsQueryHelper(
            graph_id=args.graph_id,
            region=args.region,
            query_timeout_milliseconds=args.timeout_ms,
        )
        print_results(run_query(args, helper))
    except (BotoCoreError, ClientError):
        logger.error("Neptune Analytics rejected the query request.")
        return 1
    except (ValueError, json.JSONDecodeError) as error:
        logger.error("%s", error)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
