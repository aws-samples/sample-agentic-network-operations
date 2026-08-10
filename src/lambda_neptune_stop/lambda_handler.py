import boto3
import logging
import os

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

neptune = boto3.client("neptune-graph")


def lambda_handler(event, context):
    graph_id = os.environ["GRAPH_ID"]

    # Check current graph status
    graph = neptune.get_graph(graphIdentifier=graph_id)
    status = graph["status"]
    logger.info(f"Graph {graph_id} current status: {status}")

    if status == "STOPPED":
        logger.info("Graph is already stopped - no action needed")
        return {"status": "already_stopped", "graphId": graph_id}

    if status != "AVAILABLE":
        logger.warning(f"Graph is in unexpected state '{status}' - skipping stop")
        return {"status": "skipped", "graphId": graph_id, "reason": status}

    neptune.stop_graph(graphIdentifier=graph_id)
    logger.info(f"Stop request sent for graph {graph_id}")
    return {"status": "stop_requested", "graphId": graph_id}
