# Network Operations Agent Web Interface

A web interface for querying the Network Operations AgentCore agent with real-time streaming responses.

## Features

- Real-time streaming responses from the agent
- Example queries from the demo scenarios in the sidebar
- Session management for conversation context
- Error handling and loading states

## Setup

1. Install dependencies:
```bash
uv pip install flask==3.1.3 boto3==1.43.54
```

2. Ensure your AWS credentials are configured:
```bash
aws configure
```

3. Set the AWS region (defaults to us-east-1):
```bash
export AWS_REGION=us-east-1
```

## Running the Application

```bash
AWS_REGION=us-east-1 uv run python app.py
```

The application will be available at: http://localhost:5000

## Usage

1. Open your browser to http://localhost:5000
2. Click an example query from the sidebar, or type your own question
3. Press Enter or click "Send"
4. Watch the agent's response stream in real-time

## Architecture

- **Backend**: Flask server with Server-Sent Events (SSE) for streaming
- **Frontend**: Vanilla JavaScript with EventSource API
- **AWS Integration**: Boto3 client for Bedrock AgentCore
- **Agent**: Network Operations Agent deployed to AgentCore Runtime
