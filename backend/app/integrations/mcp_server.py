"""
Mission Control MCP Server

Exposes Mission Control data to Claude Code / Claude Agent SDK
via the Model Context Protocol. Add this to your claude_desktop_config.json
or use it with the Claude Agent SDK.

Usage in claude_desktop_config.json:
{
  "mcpServers": {
    "mission-control": {
      "command": "python",
      "args": ["-m", "app.integrations.mcp_server"],
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://missionctl:missionctl@localhost:5432/missioncontrol"
      }
    }
  }
}
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

# MCP protocol is JSON-RPC over stdio
# This is a minimal implementation that Claude Code can consume


async def handle_request(request: dict) -> dict:
    """Handle an MCP JSON-RPC request."""
    method = request.get("method", "")
    params = request.get("params", {})
    request_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mission-control", "version": "0.1.0"},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "mc_list_tasks",
                        "description": "List open tasks from Mission Control",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string", "enum": ["todo", "in_progress", "blocked", "done"]},
                                "limit": {"type": "integer", "default": 20},
                            },
                        },
                    },
                    {
                        "name": "mc_add_task",
                        "description": "Add a new task to Mission Control",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string", "description": "Task description"},
                                "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"], "default": "medium"},
                                "tags": {"type": "array", "items": {"type": "string"}, "default": []},
                            },
                            "required": ["text"],
                        },
                    },
                    {
                        "name": "mc_add_idea",
                        "description": "Capture a new idea in Mission Control",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "tags": {"type": "array", "items": {"type": "string"}, "default": []},
                            },
                            "required": ["text"],
                        },
                    },
                    {
                        "name": "mc_list_projects",
                        "description": "List all projects in Mission Control",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "mc_status",
                        "description": "Get Mission Control status overview",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "mc_list_agents",
                        "description": "List all configured agents and their status",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "mc_run_agent",
                        "description": "Trigger an agent run by name",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "agent_name": {"type": "string"},
                            },
                            "required": ["agent_name"],
                        },
                    },
                    {
                        "name": "mc_list_habits",
                        "description": "List active habits with streak info",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "mc_complete_habit",
                        "description": "Mark a habit as completed for today",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "habit_name": {"type": "string", "description": "Habit name (partial match)"},
                            },
                            "required": ["habit_name"],
                        },
                    },
                    {
                        "name": "mc_list_goals",
                        "description": "List active goals with progress",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "mc_add_goal",
                        "description": "Create a new goal",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string", "description": "Goal title"},
                                "description": {"type": "string", "default": ""},
                                "tags": {"type": "array", "items": {"type": "string"}, "default": []},
                            },
                            "required": ["title"],
                        },
                    },
                    {
                        "name": "mc_add_journal",
                        "description": "Create a journal entry",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string", "description": "Journal entry text"},
                                "mood": {"type": "string", "enum": ["great", "good", "okay", "low", "bad"]},
                                "energy": {"type": "integer", "minimum": 1, "maximum": 5},
                                "wins": {"type": "array", "items": {"type": "string"}, "default": []},
                                "gratitude": {"type": "array", "items": {"type": "string"}, "default": []},
                            },
                            "required": ["content"],
                        },
                    },
                    {
                        "name": "mc_list_journal",
                        "description": "List recent journal entries",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "limit": {"type": "integer", "default": 5},
                            },
                        },
                    },
                    {
                        "name": "mc_list_approvals",
                        "description": "List pending agent approvals that need review",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "mc_approve",
                        "description": "Approve a pending agent action",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "approval_id": {"type": "string", "description": "Approval UUID"},
                            },
                            "required": ["approval_id"],
                        },
                    },
                    {
                        "name": "mc_dry_run_agent",
                        "description": "Preview what an agent will do without executing (dry run)",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "agent_name": {"type": "string", "description": "Agent name or slug"},
                            },
                            "required": ["agent_name"],
                        },
                    },
                    {
                        "name": "mc_search",
                        "description": "Search across all Mission Control entities",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Search query"},
                                "entity_types": {"type": "string", "default": "all", "description": "Comma-separated: tasks,ideas,reading,goals,journal,habits,projects"},
                            },
                            "required": ["query"],
                        },
                    },
                ],
            },
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        result = await execute_tool(tool_name, tool_args)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
            },
        }

    # Notifications (no response needed)
    if method.startswith("notifications/"):
        return None

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


async def execute_tool(name: str, args: dict) -> dict:
    """Execute an MCP tool against the Mission Control API."""
    import httpx

    api_base = os.environ.get("MC_API_BASE", "http://localhost:8000/api")

    async with httpx.AsyncClient(timeout=30) as client:
        if name == "mc_list_tasks":
            params = {}
            if "status" in args:
                params["status"] = args["status"]
            resp = await client.get(f"{api_base}/tasks", params=params)
            tasks = resp.json()
            return {"tasks": tasks[:args.get("limit", 20)], "count": len(tasks)}

        elif name == "mc_add_task":
            resp = await client.post(f"{api_base}/tasks", json=args)
            return resp.json()

        elif name == "mc_add_idea":
            resp = await client.post(f"{api_base}/ideas", json=args)
            return resp.json()

        elif name == "mc_list_projects":
            resp = await client.get(f"{api_base}/projects")
            return {"projects": resp.json()}

        elif name == "mc_status":
            resp = await client.get("/health")
            return resp.json()

        elif name == "mc_list_agents":
            resp = await client.get(f"{api_base}/agents")
            return {"agents": resp.json()}

        elif name == "mc_run_agent":
            # Find agent by name first
            resp = await client.get(f"{api_base}/agents")
            agents = resp.json()
            match = next((a for a in agents if a["slug"] == args["agent_name"] or args["agent_name"].lower() in a["name"].lower()), None)
            if not match:
                return {"error": f"Agent not found: {args['agent_name']}"}
            resp = await client.post(f"{api_base}/agents/{match['id']}/run")
            return resp.json()

        elif name == "mc_list_habits":
            resp = await client.get(f"{api_base}/habits")
            return {"habits": resp.json()}

        elif name == "mc_complete_habit":
            # Find habit by name
            resp = await client.get(f"{api_base}/habits")
            habits = resp.json()
            match = next((h for h in habits if args["habit_name"].lower() in h["name"].lower()), None)
            if not match:
                return {"error": f"Habit not found: {args['habit_name']}"}
            resp = await client.post(f"{api_base}/habits/{match['id']}/complete")
            return resp.json()

        elif name == "mc_list_goals":
            resp = await client.get(f"{api_base}/goals")
            return {"goals": resp.json()}

        elif name == "mc_add_goal":
            resp = await client.post(f"{api_base}/goals", json=args)
            return resp.json()

        elif name == "mc_add_journal":
            resp = await client.post(f"{api_base}/journal", json=args)
            return resp.json()

        elif name == "mc_list_journal":
            limit = args.get("limit", 5)
            resp = await client.get(f"{api_base}/journal?limit={limit}")
            return {"entries": resp.json()}

        elif name == "mc_list_approvals":
            resp = await client.get(f"{api_base}/approvals")
            return {"approvals": resp.json()}

        elif name == "mc_approve":
            resp = await client.post(f"{api_base}/approvals/{args['approval_id']}/approve")
            return resp.json()

        elif name == "mc_dry_run_agent":
            resp = await client.get(f"{api_base}/agents")
            agents = resp.json()
            match = next((a for a in agents if args["agent_name"].lower() in a["slug"].lower() or args["agent_name"].lower() in a["name"].lower()), None)
            if not match:
                return {"error": f"Agent not found: {args['agent_name']}"}
            resp = await client.post(f"{api_base}/agents/{match['id']}/run?dry_run=true")
            return resp.json()

        elif name == "mc_search":
            params = {"q": args["query"]}
            if "entity_types" in args:
                params["entity_types"] = args["entity_types"]
            resp = await client.get(f"{api_base}/search", params=params)
            return resp.json()

    return {"error": f"Unknown tool: {name}"}


async def main():
    """Run MCP server over stdio."""
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout
    )
    writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, asyncio.get_event_loop())

    while True:
        line = await reader.readline()
        if not line:
            break

        try:
            request = json.loads(line.decode().strip())
            response = await handle_request(request)
            if response:
                writer.write((json.dumps(response) + "\n").encode())
                await writer.drain()
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)},
            }
            writer.write((json.dumps(error_response) + "\n").encode())
            await writer.drain()


if __name__ == "__main__":
    asyncio.run(main())
