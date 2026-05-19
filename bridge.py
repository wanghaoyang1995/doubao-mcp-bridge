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
    lines.append('MCP_CALL_JSON: {"server":"服务器名","tool":"工具名","arguments":{}}')
    lines.append("")
    lines.append("调用规则：")
    lines.append("1. 只有确实需要本地工具时才输出 MCP_CALL_JSON。")
    lines.append("2. 输出 MCP_CALL_JSON 时，只输出这一行，不要附加任何自然语言。")
    lines.append("3. 等用户返回 MCP_RESULT_JSON 后，再根据结果自然语言回答。")
    lines.append("4. 不要伪造工具结果。")
    lines.append("5. 一次只允许调用一个工具。")
    lines.append("6. 必须严格输出 MCP_CALL_JSON: 开头，后面紧跟合法JSON，不允许省略前缀。")
    lines.append("7. arguments 必须严格符合对应工具的 inputSchema。")
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


async def call_mcp_tool(config: dict[str, Any], tool_name: str, arguments: dict[str, Any]) -> Any:
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
            result = await session.call_tool(tool_name, arguments)
            return result


async def command_call() -> None:
    # 1. 从剪贴板读取 MCP_CALL_JSON
    clipboard_content = pyperclip.paste()
    # 立即清空剪贴板，若后续异常退出，外层AHK可判断
    pyperclip.copy("")

    prefix = "MCP_CALL_JSON:"
    prefix_idx = clipboard_content.find(prefix)

    if prefix_idx == -1:
        raise ValueError("剪贴板中未找到 MCP_CALL_JSON")

    mcp_call_json = clipboard_content[prefix_idx + len(prefix):].strip()

    # 2. 解析 JSON
    try:
        mcp_call = json.loads(mcp_call_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"MCP_CALL JSON 解析失败: {e}")

    server_name = mcp_call.get("server")
    tool_name = mcp_call.get("tool")
    arguments = mcp_call.get("arguments", {})

    if not server_name or not tool_name:
        raise ValueError("MCP_CALL 必须包含 server 和 tool 字段")

    # 3. 根据 server/tool 路由到对应 MCP server
    servers = load_servers_config()
    if server_name not in servers:
        raise ValueError(f"未找到服务器配置: {server_name}")

    config = servers[server_name]

    # 4. call_tool()
    try:
        result = await call_mcp_tool(config, tool_name, arguments)
    except Exception as e:
        result = {"error": str(e)}

    # 5. 将 MCP_RESULT_JSON 写回剪贴板
    result_str = json.dumps(result.content[0].text, ensure_ascii=False)
    mcp_result = f"MCP_RESULT_JSON: {result_str}"
    pyperclip.copy(mcp_result)
    # print("MCP_RESULT 已写入剪贴板。")


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
