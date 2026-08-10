import os
import json
import logging
import boto3
from flask import Flask, render_template, request, Response, stream_with_context

app = Flask(__name__)
logger = logging.getLogger(__name__)

# Initialize the Bedrock AgentCore clients
REGION = os.environ.get('AWS_REGION', 'us-east-1')
agent_core_client = boto3.client('bedrock-agentcore', region_name=REGION)
agent_core_control_client = boto3.client(
    'bedrock-agentcore-control',
    region_name=REGION,
)

def get_agent_arn():
    """Get the Network Operations agent ARN"""
    try:
        next_token = None
        while True:
            request_params = {}
            if next_token:
                request_params['nextToken'] = next_token

            response = agent_core_control_client.list_agent_runtimes(
                **request_params
            )
            for runtime in response.get('agentRuntimes', []):
                arn = runtime.get('agentRuntimeArn', '')
                if 'network_operations_agent' in arn.lower():
                    return arn

            next_token = response.get('nextToken')
            if not next_token:
                break
    except Exception:
        logger.exception("Unable to list AgentCore runtimes")
    return None

AGENT_ARN = get_agent_arn()
DEFAULT_SESSION_ID = "netops-web-session-12345678901234567891"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/query', methods=['POST'])
def query_agent():
    """Stream responses from the agent"""
    data = request.get_json(silent=True) or {}
    prompt = data.get('prompt', '').strip()
    session_id = data.get('session_id', DEFAULT_SESSION_ID)

    if not prompt:
        return Response(json.dumps({'error': 'No prompt provided'}), status=400)

    if not AGENT_ARN:
        return Response(json.dumps({'error': 'Agent is unavailable'}), status=503)

    def generate():
        try:
            payload = json.dumps({"prompt": prompt}).encode()

            response = agent_core_client.invoke_agent_runtime(
                agentRuntimeArn=AGENT_ARN,
                runtimeSessionId=session_id,
                payload=payload
            )

            # Get the streaming body
            response_data = response.get("response")

            if hasattr(response_data, 'read'):
                # Read the full response and parse SSE lines
                raw = b""
                while True:
                    chunk = response_data.read(4096)
                    if not chunk:
                        break
                    raw += chunk

                content = raw.decode('utf-8', errors='replace')

                # The response is SSE-formatted: multiple "data: <json>\n" lines
                # Parse each line and extract the final 'response' field
                final_response = None
                for line in content.split('\n'):
                    line = line.strip()
                    if not line.startswith('data:'):
                        continue
                    json_str = line[len('data:'):].strip().strip('"')
                    # Unescape the JSON string (it's double-encoded)
                    try:
                        json_str = json_str.encode().decode('unicode_escape')
                    except Exception:
                        pass
                    try:
                        msg = json.loads(json_str)
                    except json.JSONDecodeError:
                        continue

                    # The completed message has the full 'response' field
                    if msg.get('status') == 'completed' and 'response' in msg:
                        final_response = msg['response']

                if final_response:
                    yield f"data: {json.dumps({'text': final_response})}\n\n"
                else:
                    yield f"data: {json.dumps({'error': 'No response received from agent'})}\n\n"

            yield "data: [DONE]\n\n"

        except Exception:
            logger.exception("Agent query failed")
            yield f"data: {json.dumps({'error': 'Unable to process your request'})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

if __name__ == '__main__':
    if not AGENT_ARN:
        logger.warning("Could not find Network Operations agent ARN")
    else:
        logger.info("Found Network Operations agent ARN")

    logger.info("Using region: %s", REGION)
    logger.info("Starting local server on http://localhost:5000")
    app.run(debug=False, host='127.0.0.1', port=5000)
