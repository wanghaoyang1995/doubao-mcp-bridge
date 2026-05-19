# bridge.py
import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import pyperclip
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


BASE_DIR = Path(__file__).resolve().parent
SERVERS_CONFIG = BASE_DIR / "servers.json"


def load_servers_config() -> dict[str, Any]:
    if not SERVERS_CONFIG.exists():
        raise FileNotFoundError(f"找不到配置文件: {SERVERS_CONFIG}")

    with SERVERS_CONFIG.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
        raise ValueError("servers.json 必须包含 mcpServers 对象")

    return data["mcpServers"]


async def list_tools_for_server(server_name: str, config: dict[str, Any]) -> dict[str, Any]:
    command = config["command"]
    args = config.get("args", [])
    env = config.get("env")

    server_params = StdioServerParameters(
        command=command,
        args=args,
        env=env
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()

    return {
        "server": server_name,
        "tools": tools_result.tools,
    }


async def collect_all_tools() -> list[dict[str, Any]]:
    servers = load_servers_config()
    results = []

    for server_name, config in servers.items():
        try:
            info = await list_tools_for_server(server_name, config)
            results.append(info)
        except Exception as e:
            results.append({
                "server": server_name,
                "error": str(e),
                "tools": [],
            })

    return results


def schema_to_compact_text(schema: Any) -> str:
    try:
        return json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return str(schema)


def build_prompt(tools_info: list[dict[str, Any]]) -> str:
    lines: list[str] = []

    lines.append("你现在具有“虚拟 MCP 工具调用”能力。")
    lines.append("")
    lines.append("当你判断需要调用本地工具时，必须只输出以下格式，不要输出任何解释、寒暄、Markdown 或代码块：")
    lines.append("")
    lines.append('<MCP_CALL>{"server":"服务器名","tool":"工具名","arguments":{}}</MCP_CALL>')
    lines.append("")
    lines.append("调用规则：")
    lines.append("1. 只有确实需要本地工具时才输出 MCP_CALL。")
    lines.append("2. 输出 MCP_CALL 时，只输出这一段，不要附加任何自然语言。")
    lines.append("3. 等用户返回 <MCP_RESULT> 后，再根据结果自然语言回答。")
    lines.append("4. 不要伪造工具结果。")
    lines.append("5. 一次只允许调用一个工具。")
    lines.append("6. arguments 必须严格符合对应工具的 inputSchema。")
    lines.append("")
    lines.append("当前可用 MCP 工具如下：")
    lines.append("")

    for server in tools_info:
        server_name = server["server"]
        lines.append(f"[server: {server_name}]")

        if server.get("error"):
            lines.append(f"- 无法读取该 server 的工具信息，错误：{server['error']}")
            lines.append("")
            continue

        tools = server.get("tools", [])
        if not tools:
            lines.append("- 暂无可用工具")
            lines.append("")
            continue

        for tool in tools:
            name = getattr(tool, "name", "")
            description = getattr(tool, "description", "") or ""
            input_schema = getattr(tool, "inputSchema", None)

            lines.append(f"- tool: {name}")
            if description:
                lines.append(f"  description: {description}")
            if input_schema is not None:
                lines.append(f"  inputSchema: {schema_to_compact_text(input_schema)}")

        lines.append("")

    return "\n".join(lines)


async def command_prompt() -> None:
    tools_info = await collect_all_tools()
    prompt = build_prompt(tools_info)
    pyperclip.copy(prompt)
    print("Prompt 已写入剪贴板。")


async def command_call() -> None:
    # TODO:
    # 1. 从剪贴板读取 <MCP_CALL>...</MCP_CALL>
    # 2. 解析 JSON
    # 3. 根据 server/tool 路由到对应 MCP server
    # 4. call_tool()
    # 5. 将 <MCP_RESULT>...</MCP_RESULT> 写回剪贴板
    raise NotImplementedError("call 功能尚未实现。")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["prompt", "call"],
        help="prompt: 生成工具说明提示词；call: 执行 MCP_CALL",
    )
    args = parser.parse_args()

    if args.command == "prompt":
        await command_prompt()
    elif args.command == "call":
        await command_call()


if __name__ == "__main__":
    asyncio.run(main())
