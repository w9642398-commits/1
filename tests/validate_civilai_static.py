from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XAML_NS = "{http://schemas.microsoft.com/winfx/2006/xaml/presentation}"


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


def extract_solution_projects() -> list[str]:
    return re.findall(r'Project\("\{[^\}]+\}"\) = "[^"]+", "([^"]+\.csproj)"', read("CivilAI.sln"))


def parse_bindings(xaml_path: Path) -> set[str]:
    text = xaml_path.read_text(encoding="utf-8")
    return set(re.findall(r'\{Binding\s+([A-Za-z0-9_]+)', text))


def parse_commands(xaml_path: Path) -> set[str]:
    text = xaml_path.read_text(encoding="utf-8")
    return set(re.findall(r'Command="\{Binding\s+([A-Za-z0-9_]+)', text))


def main() -> int:
    registry_tools = extract_registry_tools()
    executor_tools = extract_executor_tools()
    readme_tools = extract_readme_tools()
    project_paths = extract_solution_projects()

    require((ROOT / "CivilAI.sln").exists(), "CivilAI.sln is missing.")
    require(project_paths, "No projects were found in CivilAI.sln.")
    for rel_project in project_paths:
        project_path = ROOT / Path(rel_project.replace("\\", "/"))
        require(project_path.exists(), f"Project from solution is missing: {project_path}")
        project_xml = ET.parse(project_path).getroot()
        require(project_xml.tag.endswith("Project"), f"Invalid project XML: {project_path}")

    require(len(registry_tools) == len(set(registry_tools)), "Duplicate tools found in ToolRegistry.")
    require(set(registry_tools) == set(executor_tools), "ToolRegistry and AutodeskCadToolExecutor are out of sync.")
    require(set(registry_tools).issubset(readme_tools), "README tool list does not cover all registered tools.")

    xaml_files = list((ROOT / "src/CivilAI.Plugin/UI").rglob("*.xaml"))
    require(xaml_files, "No XAML files found in plugin UI.")
    for xaml in xaml_files:
        ET.parse(xaml)
        codebehind = xaml.with_suffix(".xaml.cs")
        require(codebehind.exists(), f"Missing code-behind file for {xaml.relative_to(ROOT)}")

    execution_models = read("src/CivilAI.Core/Models/ExecutionModels.cs")
    require("EnableNativeCommandBridge" in execution_models, "AssistantSettings lacks EnableNativeCommandBridge.")
    require("AllowUncatalogedNativeCommands" in execution_models, "AssistantSettings lacks AllowUncatalogedNativeCommands.")
    require("https://api.openai.com/v1/responses" in execution_models, "Responses API endpoint default is missing.")

    responses_client = read("src/CivilAI.Core/OpenAI/ResponsesApiClient.cs")
    require("Authorization" in responses_client and "Bearer" in responses_client, "ResponsesApiClient does not attach Bearer authorization.")
    require("GetSecretAsync" in responses_client, "ResponsesApiClient is not using the secret store.")

    secret_store = read("src/CivilAI.Plugin/Services/WindowsCredentialManagerSecretStore.cs")
    require("ProtectedData.Protect" in secret_store and "ProtectedData.Unprotect" in secret_store, "Secret store is not using DPAPI protection.")

    composition_root = read("src/CivilAI.Plugin/Composition/PluginCompositionRoot.cs")
    for required_service in ["NativeCommandCatalogService", "AutodeskCadContextProvider", "AutodeskCadToolExecutor", "ResponsesApiClient", "ToolRegistry", "AssistantViewModel"]:
        require(required_service in composition_root, f"CompositionRoot is missing service wiring for {required_service}.")

    interface_code = read("src/CivilAI.Core/Contracts/ICadToolExecutor.cs")
    orchestrator_code = read("src/CivilAI.Core/Runtime/AssistantOrchestrator.cs")
    for method_name in ["BeginExecutionScopeAsync", "CompleteExecutionScopeAsync", "AbortExecutionScopeAsync"]:
        require(method_name in interface_code, f"ICadToolExecutor missing {method_name}.")
        require(method_name in orchestrator_code, f"AssistantOrchestrator missing {method_name} handling.")

    native_catalog = read("src/CivilAI.Plugin/Services/NativeCommandCatalogService.cs")
    for command_name in ["ALIGNMENTCREATE", "PROFILECREATE", "CREATESURFACE", "CORRIDORCREATE"]:
        require(command_name in native_catalog, f"Native command catalog is missing {command_name}.")

    assistant_vm = read("src/CivilAI.Plugin/UI/ViewModels/AssistantViewModel.cs")
    assistant_bindings = parse_bindings(ROOT / "src/CivilAI.Plugin/UI/Controls/AssistantControl.xaml")
    settings_bindings = parse_bindings(ROOT / "src/CivilAI.Plugin/UI/Windows/SettingsWindow.xaml")
    for binding in sorted(assistant_bindings | settings_bindings):
        require(binding in assistant_vm or binding in read("src/CivilAI.Plugin/UI/Windows/SettingsWindow.xaml.cs"), f"Binding '{binding}' is not represented in the ViewModel or settings code-behind.")

    assistant_commands = parse_commands(ROOT / "src/CivilAI.Plugin/UI/Controls/AssistantControl.xaml")
    settings_commands = parse_commands(ROOT / "src/CivilAI.Plugin/UI/Windows/SettingsWindow.xaml")
    for command in sorted(assistant_commands | settings_commands):
        require(command in assistant_vm, f"Command binding '{command}' is not exposed by AssistantViewModel.")

    readme = read("README.md")
    require("python tests/validate_civilai_static.py" in readme, "README does not document the static validation command.")
    require("NETLOAD" in readme and "C3D_2026_SDK" in readme, "README is missing build/deploy instructions.")

    forbidden_secret_patterns = [r"sk-[A-Za-z0-9]{20,}", r"OPENAI_API_KEY\s*=\s*[\"\']"]
    source_blobs = [p.read_text(encoding="utf-8", errors="ignore") for p in ROOT.rglob("*") if p.is_file() and p.suffix in {".cs", ".xaml", ".json", ".md", ".py", ".csproj", ".sln"}]
    for pattern in forbidden_secret_patterns:
        require(not any(re.search(pattern, blob) for blob in source_blobs), f"Potential hardcoded secret pattern found: {pattern}")

    print("CivilAI full static validation passed.")
    print(f"Validated {len(project_paths)} projects, {len(registry_tools)} registered tools, {len(xaml_files)} XAML files, ViewModel bindings, command bridge wiring, and secret-handling safeguards.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"Static validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
