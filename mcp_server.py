#!/usr/bin/env python3
"""
MCP Server for FE Compliance Service.
Exposes invoice validation and reference data tools via Model Context Protocol.

Modes:
  - stdio (default): python mcp_server.py
  - SSE (remote):    python mcp_server.py --sse --port 8001
                     or: uvicorn mcp_server:app --host 0.0.0.0 --port 8001
"""
import sys
import json
import base64
import argparse
from pathlib import Path
from typing import Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.xsd_validator import XSDValidator
from app.services import rules_engine
from app.routers import reference

DATA_DIR = Path(__file__).parent / "data"
XSD_DIR = DATA_DIR / "xsd"

server = Server("fe-compliance")


def extract_facturx_xml(pdf_bytes: bytes) -> bytes:
    """Extract embedded XML from Factur-X PDF."""
    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("Payload is not a PDF (missing %PDF header)")
    start = pdf_bytes.find(b"<?xml")
    if start == -1:
        raise ValueError("No embedded XML found in Factur-X payload")
    end = -1
    for marker in [b"</rsm:CrossIndustryInvoice>", b"</Invoice>"]:
        idx = pdf_bytes.find(marker, start)
        if idx != -1:
            end = idx + len(marker)
            break
    if end == -1:
        end = len(pdf_bytes)
    return pdf_bytes[start:end]


@server.list_tools()
async def list_tools():
    """List available MCP tools."""
    return [
        Tool(
            name="validate_invoice",
            description="Validate an electronic invoice (UBL, CII, Factur-X, CDV, e-reporting, annuaire). Returns syntax errors, business rule violations, and codelist issues.",
            inputSchema={
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "description": "Invoice format: ubl, cii, facturx, cdv, ereporting, annuaire",
                        "enum": ["ubl", "cii", "facturx", "cdv", "ereporting", "annuaire"]
                    },
                    "payload": {
                        "type": "string",
                        "description": "XML content as string or base64-encoded"
                    },
                    "flow": {
                        "type": "string",
                        "description": "Flow type: f1, f6, f10, f13, f14",
                        "enum": ["f1", "f6", "f10", "f13", "f14"]
                    },
                    "profile": {
                        "type": "string",
                        "description": "Profile: base or full",
                        "enum": ["base", "full"]
                    }
                },
                "required": ["format", "payload"]
            }
        ),
        Tool(
            name="get_codelist",
            description="Get a codelist by name (e.g., UNTDID1001, CDV_REFUS, ISO4217, ISO3166, CADRES)",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Codelist name"
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="get_required_fields",
            description="Get mandatory fields (BT codes) for a given profile and flow",
            inputSchema={
                "type": "object",
                "properties": {
                    "profile": {
                        "type": "string",
                        "description": "Profile: base or full",
                        "enum": ["base", "full"]
                    },
                    "flow": {
                        "type": "string",
                        "description": "Flow: f1, f10, f13, f14",
                        "enum": ["f1", "f10", "f13", "f14"]
                    }
                },
                "required": ["profile", "flow"]
            }
        ),
        Tool(
            name="get_rule",
            description="Get details of a business rule by ID (e.g., G1.01, G1.05)",
            inputSchema={
                "type": "object",
                "properties": {
                    "rule_id": {
                        "type": "string",
                        "description": "Rule identifier"
                    }
                },
                "required": ["rule_id"]
            }
        ),
        Tool(
            name="get_refusal_codes",
            description="Get all CDV refusal codes with their labels",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_next_status",
            description="Get allowed next CDV statuses from a given current status",
            inputSchema={
                "type": "object",
                "properties": {
                    "current": {
                        "type": "string",
                        "description": "Current CDV status (e.g., CDV-200, CDV-202). Omit for initial status."
                    }
                }
            }
        ),
        Tool(
            name="audit_capabilities",
            description="Audit platform capabilities against FE requirements. Returns missing formats, profiles, CDV statuses, and cadres.",
            inputSchema={
                "type": "object",
                "properties": {
                    "formats": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Supported formats (e.g., ['ubl', 'cii'])"
                    },
                    "profiles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Supported profiles (e.g., ['base', 'full'])"
                    },
                    "cdv_statuses": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Supported CDV statuses"
                    },
                    "cadres": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Supported cadres de facturation"
                    },
                    "annuaire": {
                        "type": "boolean",
                        "description": "Supports annuaire (F13/F14)"
                    },
                    "facturx": {
                        "type": "boolean",
                        "description": "Supports Factur-X"
                    }
                }
            }
        ),
        Tool(
            name="list_available_codelists",
            description="List all available codelist names",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool invocations."""

    if name == "validate_invoice":
        fmt = arguments.get("format", "ubl")
        payload = arguments.get("payload", "")
        flow = arguments.get("flow")
        profile = arguments.get("profile")

        # Decode payload
        try:
            stripped = payload.strip()
            if stripped.startswith("<") or stripped.startswith("\ufeff<"):
                xml_bytes = stripped.encode("utf-8")
            else:
                xml_bytes = base64.b64decode(payload)
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": f"Invalid payload encoding: {e}"}))]

        fmt_for_schema = fmt
        fmt_for_rules = fmt

        # Handle Factur-X
        if fmt.lower() == "facturx":
            try:
                xml_bytes = extract_facturx_xml(xml_bytes)
                fmt_for_schema = "cii"
                fmt_for_rules = "cii"
            except Exception as e:
                return [TextContent(type="text", text=json.dumps({"error": f"Failed to extract Factur-X XML: {e}"}))]

        # XSD validation
        validator = XSDValidator(base_dir=XSD_DIR)
        syntax_errors = validator.validate(xml_bytes, fmt_for_schema, flow, profile)

        # Business rules
        rule_issues, codelist_issues = rules_engine.evaluate(xml_bytes, fmt_for_rules, flow)

        result = {
            "syntax": syntax_errors,
            "rules": [{"ruleId": r.ruleId, "severity": r.severity, "xpath": r.xpath, "message": r.message} for r in rule_issues],
            "codelists": [{"ruleId": r.ruleId, "severity": r.severity, "xpath": r.xpath, "message": r.message} for r in codelist_issues]
        }
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "get_codelist":
        codelist_name = arguments.get("name", "")
        if codelist_name not in reference.CODELISTS:
            return [TextContent(type="text", text=json.dumps({"error": f"Codelist '{codelist_name}' not found"}))]
        return [TextContent(type="text", text=json.dumps(reference.CODELISTS[codelist_name], ensure_ascii=False, indent=2))]

    elif name == "get_required_fields":
        profile = arguments.get("profile", "base")
        flow = arguments.get("flow", "f1")
        key = (profile, flow)
        if key not in reference.REQUIRED_FIELDS:
            return [TextContent(type="text", text=json.dumps({"error": f"No required fields for profile={profile}, flow={flow}"}))]
        return [TextContent(type="text", text=json.dumps(reference.REQUIRED_FIELDS[key], indent=2))]

    elif name == "get_rule":
        rule_id = arguments.get("rule_id", "")
        if rule_id not in reference.RULES:
            return [TextContent(type="text", text=json.dumps({"error": f"Rule '{rule_id}' not found"}))]
        rule = reference.RULES[rule_id]
        return [TextContent(type="text", text=json.dumps({"id": rule_id, **rule}, ensure_ascii=False, indent=2))]

    elif name == "get_refusal_codes":
        codes = reference.CODELISTS.get("CDV_REFUS", [])
        return [TextContent(type="text", text=json.dumps(codes, ensure_ascii=False, indent=2))]

    elif name == "get_next_status":
        current = arguments.get("current")
        allowed = reference.NEXT_STATUS_MAP.get(current, [])
        return [TextContent(type="text", text=json.dumps({"current": current, "allowed": allowed}))]

    elif name == "audit_capabilities":
        formats = set(arguments.get("formats", []))
        profiles = set(arguments.get("profiles", []))
        cdv_statuses = set(arguments.get("cdv_statuses", []))
        cadres = set(arguments.get("cadres", []))
        annuaire = arguments.get("annuaire", False)
        facturx = arguments.get("facturx", False)

        required_formats = {"ubl", "cii"}
        required_profiles = {"base", "full"}
        required_cdv = {"CDV-200", "CDV-202", "CDV-203", "CDV-205", "CDV-207", "CDV-211", "CDV-212", "CDV-213", "CDV-220"}
        required_cadres = set(reference.CODELISTS.get("CADRES", []))

        result = {
            "missingFormats": list(required_formats - formats),
            "missingProfiles": list(required_profiles - profiles),
            "missingCDV": list(required_cdv - cdv_statuses),
            "missingCadres": list(required_cadres - cadres),
            "notes": []
        }

        if not annuaire:
            result["notes"].append("Annuaire (F13/F14) non supporté")
        if not facturx:
            result["notes"].append("Factur-X non supporté")

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "list_available_codelists":
        return [TextContent(type="text", text=json.dumps(list(reference.CODELISTS.keys()), indent=2))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


# =============================================================================
# SSE Transport (for remote access)
# =============================================================================

def create_sse_app():
    """Create Starlette app with SSE transport for remote MCP access."""
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    from starlette.responses import JSONResponse

    sse = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())

    async def handle_messages(request):
        return await sse.handle_post_message(request.scope, request.receive, request._send)

    async def health(request):
        return JSONResponse({"status": "ok", "server": "fe-compliance", "mode": "sse"})

    return Starlette(
        debug=True,
        routes=[
            Route("/", endpoint=health),
            Route("/sse", endpoint=handle_sse),
            Route("/messages/", endpoint=handle_messages, methods=["POST"]),
        ]
    )


# ASGI app for uvicorn
app = create_sse_app()


# =============================================================================
# CLI Entry Point
# =============================================================================

async def run_stdio():
    """Run MCP server in stdio mode (local)."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


async def run_sse(host: str, port: int):
    """Run MCP server in SSE mode (remote)."""
    import uvicorn
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    srv = uvicorn.Server(config)
    await srv.serve()


def main():
    parser = argparse.ArgumentParser(description="MCP FE Compliance Server")
    parser.add_argument("--sse", action="store_true", help="Run in SSE mode (remote access)")
    parser.add_argument("--host", default="0.0.0.0", help="Host for SSE mode (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8001, help="Port for SSE mode (default: 8001)")
    args = parser.parse_args()

    import asyncio

    if args.sse:
        print(f"Starting MCP server in SSE mode on {args.host}:{args.port}")
        print(f"  - Health check: http://{args.host}:{args.port}/")
        print(f"  - SSE endpoint: http://{args.host}:{args.port}/sse")
        asyncio.run(run_sse(args.host, args.port))
    else:
        asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
