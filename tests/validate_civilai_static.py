from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def extract_registry_tools() -> list[str]:
    return re.findall(r'new\("([A-Za-z0-9_]+)"', read("src/CivilAI.Core/Tools/ToolRegistry.cs"))


def extract_executor_tools() -> list[str]:
    return re.findall(r'"([A-Za-z0-9_]+)"\s*=>', read("src/CivilAI.Plugin/Services/AutodeskCadToolExecutor.cs"))


def extract_readme_tools() -> set[str]:
    tools: set[str] = set()
    for line in read("README.md").splitlines():
        match = re.match(r"- `([A-Za-z0-9_]+)`", line.strip())
        if match:
            tools.add(match.group(1))
    return tools


def main() -> int:
    registry_tools = extract_registry_tools()
    executor_tools = extract_executor_tools()
    readme_tools = extract_readme_tools()

    require(len(registry_tools) == len(set(registry_tools)), "Duplicate tools found in ToolRegistry.")
    require(set(registry_tools) == set(executor_tools), "ToolRegistry and AutodeskCadToolExecutor are out of sync.")
    require(set(registry_tools).issubset(readme_tools), "README tool list does not cover all registered tools.")

    for xaml in (ROOT / "src/CivilAI.Plugin/UI").rglob("*.xaml"):
        ET.parse(xaml)

    execution_models = read("src/CivilAI.Core/Models/ExecutionModels.cs")
    require("EnableNativeCommandBridge" in execution_models, "AssistantSettings lacks EnableNativeCommandBridge.")
    require("AllowUncatalogedNativeCommands" in execution_models, "AssistantSettings lacks AllowUncatalogedNativeCommands.")

    view_model = read("src/CivilAI.Plugin/UI/ViewModels/AssistantViewModel.cs")
    require("EnableNativeCommandBridge" in view_model, "AssistantViewModel does not expose native command bridge settings.")
    require("AllowUncatalogedNativeCommands" in view_model, "AssistantViewModel does not expose uncataloged command settings.")

    settings_window = read("src/CivilAI.Plugin/UI/Windows/SettingsWindow.xaml")
    require("Enable native command bridge" in settings_window, "SettingsWindow is missing native command bridge toggle.")
    require("Allow uncataloged commands" in settings_window, "SettingsWindow is missing uncataloged command toggle.")

    interface_code = read("src/CivilAI.Core/Contracts/ICadToolExecutor.cs")
    orchestrator_code = read("src/CivilAI.Core/Runtime/AssistantOrchestrator.cs")
    for method_name in ["BeginExecutionScopeAsync", "CompleteExecutionScopeAsync", "AbortExecutionScopeAsync"]:
        require(method_name in interface_code, f"ICadToolExecutor missing {method_name}.")
        require(method_name in orchestrator_code, f"AssistantOrchestrator missing {method_name} handling.")

    native_catalog = read("src/CivilAI.Plugin/Services/NativeCommandCatalogService.cs")
    require("ALIGNMENTCREATE" in native_catalog and "CORRIDORCREATE" in native_catalog, "Native command catalog is missing expected Civil 3D commands.")

    print("CivilAI static validation passed.")
    print(f"Validated {len(registry_tools)} registered tools, {len(list((ROOT / 'src/CivilAI.Plugin/UI').rglob('*.xaml')))} XAML files, and command-bridge settings wiring.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"Static validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
