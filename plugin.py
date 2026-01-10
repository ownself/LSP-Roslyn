from __future__ import annotations

import os
import shutil
import sublime
import sublime_plugin

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Callable, Optional

from urllib.request import urlretrieve
from zipfile import ZipFile

from LSP.plugin import AbstractPlugin
from LSP.plugin import ClientConfig
from LSP.plugin import Notification
from LSP.plugin import register_plugin
from LSP.plugin import Request
from LSP.plugin import unregister_plugin
from LSP.plugin import WorkspaceFolder

try:
    from LSP.plugin.core.url import filename_to_uri  # type: ignore
except Exception:
    filename_to_uri = None  # type: ignore

# Roslyn language server version - matches VSCode C# extension
ROSLYN_VERSION = "5.3.0-1.25517.107"

# Azure DevOps NuGet feed URL for Roslyn language server
# Note: These packages are available at:
# https://dev.azure.com/azure-public/vside/_artifacts/feed/vs-impl/NuGet/Microsoft.CodeAnalysis.LanguageServer.<platform>
# However, direct download requires authentication or using the NuGet CLI
#
# For production use, consider:
# 1. Hosting the binaries on GitHub releases
# 2. Using the NuGet CLI to download: nuget install Microsoft.CodeAnalysis.LanguageServer.<platform> -Source https://pkgs.dev.azure.com/azure-public/vside/_packaging/vs-impl/nuget/v3/index.json
# 3. Extracting from the VSCode C# extension
AZURE_NUGET_FEED = "https://pkgs.dev.azure.com/azure-public/vside/_packaging/vs-impl/nuget/v3/index.json"


def _platform_str() -> str:
    """Returns platform-specific identifier for Roslyn language server."""
    platform_map = {
        "osx": {
            "arm64": "osx-arm64",
            "x64": "osx-x64",
        },
        "linux": {
            "arm64": "linux-arm64",
            "x64": "linux-x64",
        },
        "windows": {
            "arm64": "win-arm64",
            "x64": "win-x64",
        },
    }
    return platform_map[sublime.platform()][sublime.arch()]


def _get_package_name() -> str:
    """Returns the full package name for the current platform."""
    return "Microsoft.CodeAnalysis.LanguageServer.{}".format(_platform_str())


def _path_to_uri(path: str) -> str:
    if filename_to_uri:
        return filename_to_uri(path)
    return Path(path).absolute().as_uri()


class Roslyn(AbstractPlugin):
    @classmethod
    def name(cls) -> str:
        return cls.__name__

    @classmethod
    def _plugin_setting(cls, key: str, default: Any = None) -> Any:
        """Read a setting from the LSP server configuration.

        LSP server config files store user settings under the top-level "settings" key.
        """
        settings = cls.get_settings()
        nested = settings.get("settings")
        if isinstance(nested, dict) and key in nested:
            return nested.get(key, default)
        return settings.get(key, default)

    @classmethod
    def _debug_enabled(cls) -> bool:
        enabled = bool(cls._plugin_setting("roslyn.debug")) or bool(cls._plugin_setting("roslyn.debugMode"))
        if not enabled:
            server_level = str(cls._plugin_setting("roslyn.loggingLevel") or "").lower()
            enabled = server_level in {"debug", "trace"}
        return enabled

    @classmethod
    def _debug_static(cls, fmt: str, *args: Any) -> None:
        if not cls._debug_enabled():
            return
        message = fmt.format(*args) if args else fmt
        print("[LSP-Roslyn] {}".format(message))

    @classmethod
    def get_settings(cls) -> sublime.Settings:
        return sublime.load_settings("LSP-{}.sublime-settings".format(cls.name()))

    @classmethod
    def version_str(cls) -> str:
        return ROSLYN_VERSION

    @classmethod
    def installed_version_str(cls) -> str:
        try:
            with open(cls.basedir() / "VERSION", "r") as f:
                return f.readline().strip()
        except Exception:
            return ""

    @classmethod
    def basedir(cls) -> Path:
        """Get the base directory for the Roslyn server.

        We use the packages path instead of storage_path to allow
        users to simply extract the NuGet package into the plugin directory.
        """
        # Use packages_path() to return the plugin's own directory
        return Path(__file__).parent

    @classmethod
    def binary_path(cls) -> Path:
        """Get the path to the Roslyn language server binary.

        We check multiple possible locations in order:
        1. Microsoft.CodeAnalysis.LanguageServer/content/LanguageServer/{platform}/ (organized structure)
        2. content/LanguageServer/{platform}/ (direct NuGet extraction)
        3. Root directory (for custom installations)
        """
        basedir = cls.basedir()
        platform = _platform_str()

        # Define binary name based on platform
        if sublime.platform() == "windows":
            binary_name = "Microsoft.CodeAnalysis.LanguageServer.exe"
        else:
            binary_name = "Microsoft.CodeAnalysis.LanguageServer"

        # Check paths in order of preference
        search_paths = [
            # Organized structure: Microsoft.CodeAnalysis.LanguageServer/content/LanguageServer/{platform}/
            basedir / "Microsoft.CodeAnalysis.LanguageServer" / "content" / "LanguageServer" / platform / binary_name,
            # Direct NuGet extraction: content/LanguageServer/{platform}/
            basedir / "content" / "LanguageServer" / platform / binary_name,
            # Root directory: Microsoft.CodeAnalysis.LanguageServer.exe
            basedir / binary_name,
        ]

        # Return the first path that exists
        for path in search_paths:
            if path.exists():
                return path

        # If none exist, return the first path (for error messages)
        return search_paths[0]

    @classmethod
    def get_command(cls) -> list[str]:
        """Get the command to start the Roslyn language server."""
        settings = cls.get_settings()
        cmd = settings.get("command")
        if isinstance(cmd, list):
            return cmd

        log_level = cls._plugin_setting("roslyn.loggingLevel")
        if not isinstance(log_level, str) or not log_level:
            log_level = "Information"

        # Roslyn server requires these arguments
        return [
            str(cls.binary_path()),
            "--logLevel={}".format(log_level),
            "--extensionLogDirectory={}".format(cls.basedir() / "logs"),
            "--stdio",
        ]

    @classmethod
    def needs_update_or_installation(cls) -> bool:
        """Check if the Roslyn server needs to be installed or updated."""
        # First check if the binary exists
        binary = cls.binary_path()
        if not binary.exists():
            return True

        # If binary exists, check version
        try:
            version_file = cls.basedir() / "VERSION"
            if version_file.exists():
                installed_version = version_file.read_text().strip()
                if cls.version_str() == installed_version:
                    return False
        except Exception:
            pass

        # If we have a binary but no version file, assume it's installed correctly
        # (user manually installed)
        return False

    @classmethod
    def install_or_update(cls) -> None:
        """Download and install the Roslyn language server from GitHub releases."""
        import zipfile
        import io
        import time
        import ssl
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError, URLError

        basedir = cls.basedir()
        platform = _platform_str()
        version = cls.version_str()

        # GitHub repository for releases
        github_repo = "ownself/LSP-Roslyn"

        # Create SSL context
        ssl_context = ssl.create_default_context()

        def fetch_with_retry(url: str, headers: dict, timeout: int = 30, max_retries: int = 3) -> bytes:
            """Fetch URL with retry logic."""
            last_error = None
            for attempt in range(max_retries):
                try:
                    request = Request(url, headers=headers)
                    with urlopen(request, timeout=timeout, context=ssl_context) as response:
                        return response.read()
                except (HTTPError, URLError, ssl.SSLError) as e:
                    last_error = e
                    if isinstance(e, HTTPError) and e.code == 404:
                        raise  # Don't retry 404 errors
                    if attempt < max_retries - 1:
                        time.sleep(2**attempt)  # Exponential backoff
                    continue
            raise last_error  # type: ignore

        try:
            headers = {"User-Agent": "LSP-Roslyn-Sublime-Plugin/1.0"}

            # Construct direct download URL (bypasses API rate limits)
            # Format: https://github.com/{repo}/releases/download/{tag}/{asset_name}
            roslyn_tag = "roslyn-{}".format(version)

            # Try multiple asset name formats
            asset_names = [
                "Microsoft.CodeAnalysis.LanguageServer.{}.{}.zip".format(platform, version),
                "roslyn-{}.zip".format(platform),
            ]

            content = None
            last_error = None

            for asset_name in asset_names:
                download_url = "https://github.com/{}/releases/download/{}/{}".format(
                    github_repo, roslyn_tag, asset_name
                )
                cls._debug_static("Trying download URL: {}", download_url)

                try:
                    content_bytes = fetch_with_retry(download_url, headers, timeout=300)
                    content = io.BytesIO(content_bytes)
                    cls._debug_static("Download successful: {}", asset_name)
                    break
                except HTTPError as e:
                    last_error = e
                    if e.code == 404:
                        cls._debug_static("Asset not found: {}", asset_name)
                        continue
                    raise

            if content is None:
                raise Exception("No matching asset found. Last error: {}".format(last_error))

            # Extract
            # Remove old installation
            target_dir = basedir / "Microsoft.CodeAnalysis.LanguageServer"
            if target_dir.exists():
                shutil.rmtree(target_dir)

            target_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(content) as z:
                z.extractall(target_dir)

            # Set permissions (Unix/macOS)
            if sublime.platform() != "windows":
                binary_path = (
                    target_dir / "content" / "LanguageServer" / platform / "Microsoft.CodeAnalysis.LanguageServer"
                )
                if binary_path.exists():
                    os.chmod(binary_path, 0o755)

            # Create logs directory
            (basedir / "logs").mkdir(exist_ok=True)

            # Write version file
            version_file = basedir / "VERSION"
            version_file.write_text(version)

            cls._debug_static("Installation complete")

        except Exception as e:
            error_msg = (
                "Failed to install Roslyn language server: {}\n\n"
                "Manual installation:\n"
                "1. Visit: https://github.com/{}/releases/tag/roslyn-{}\n"
                "2. Download: Microsoft.CodeAnalysis.LanguageServer.{}.{}.zip\n"
                "3. Extract to: {}/Microsoft.CodeAnalysis.LanguageServer/\n"
                "4. Restart Sublime Text"
            ).format(e, github_repo, version, platform, version, basedir)
            sublime.error_message(error_msg)
            raise

    @classmethod
    def on_pre_start(
        cls,
        window: sublime.Window,
        initiating_view: sublime.View,
        workspace_folders: list[WorkspaceFolder],
        configuration: ClientConfig,
    ) -> Optional[str]:
        """Called before starting the language server."""
        configuration.command = cls.get_command()

        cls._debug_static("on_pre_start workspace_folders: {}", [wf.path for wf in workspace_folders])
        try:
            cls._debug_static("on_pre_start initiating_view: {}", initiating_view.file_name())
        except Exception:
            pass
        cls._debug_static("on_pre_start command: {}", configuration.command)

        # Set environment variables
        if not configuration.env:
            configuration.env = {}
        configuration.env["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"

        return None

    def on_workspace_configuration(self, params: Any, configuration: Any) -> Any:
        """Handle workspace/configuration requests from the server.

        The LSP package calls this method for each ConfigurationItem in the
        workspace/configuration request. The `params` dict contains:
          - section: The configuration section requested
          - scopeUri: Optional URI scope for the configuration

        Roslyn requests configuration sections in these formats:
          - Per-language: "{lang}|{group}.{option}" e.g. "csharp|code_lens.dotnet_enable_references_code_lens"
          - Global: "{group}.{option}" e.g. "projects.dotnet_binary_log_path"

        The `configuration` parameter is the pre-resolved value from LSP settings,
        or None if not found.

        We return None/null for options we don't want to set, allowing Roslyn
        to use its defaults.
        """
        # Log the first configuration request for debugging
        if not getattr(self, "_did_log_first_config", False):
            setattr(self, "_did_log_first_config", True)
            self._debug("workspace/configuration first request - params: {}", params)
            self._debug("workspace/configuration first request - configuration: {}", configuration)

        settings = self.get_settings()
        roslyn_settings = settings.get("roslyn")
        if not isinstance(roslyn_settings, dict):
            roslyn_settings = {}

        # Get the section being requested
        section = params.get("section", "") if isinstance(params, dict) else ""

        # Log all unique sections requested (for debugging)
        if not hasattr(self, "_requested_sections"):
            self._requested_sections: set[str] = set()
        if section and section not in self._requested_sections:
            self._requested_sections.add(section)
            self._debug("workspace/configuration section requested: {}", section)

        # Trigger workspace opening on first configuration request
        # This is more reliable than on_ready across LSP package versions
        sublime.set_timeout_async(self._open_workspace_if_needed, 0)

        # Extract the base section (without language prefix) and group/option parts
        # Format: "csharp|group.option" or "group.option"
        base_section = section
        language_prefix = None
        if "|" in section:
            language_prefix, base_section = section.split("|", 1)

        # Split into group and option name: "code_lens.dotnet_enable_references_code_lens"
        if "." not in base_section:
            # No group, just return the original configuration
            return configuration

        group, option_name = base_section.split(".", 1)

        # Look up the setting value in our roslyn settings
        # Settings structure: roslyn.{group}.{option_name}
        # e.g., roslyn.code_lens.dotnet_enable_references_code_lens
        if group in roslyn_settings:
            group_settings = roslyn_settings[group]
            if isinstance(group_settings, dict) and option_name in group_settings:
                value = group_settings[option_name]
                self._debug("workspace/configuration returning {} = {}", section, value)
                return value

        # Return original configuration to let Roslyn use defaults
        return configuration

    def on_ready(self, client_config: ClientConfig) -> None:
        """Called when the language server is ready (sync hook)."""
        self._debug("on_ready called")
        self._open_workspace_if_needed()

    async def on_ready_async(self, client_config: ClientConfig) -> None:
        """Called when the language server is ready (async hook)."""
        self._debug("on_ready_async called")
        self._open_workspace_if_needed()

    def _open_workspace_if_needed(self) -> None:
        if getattr(self, "_did_open_workspace", False):
            return
        setattr(self, "_did_open_workspace", True)

        if self._plugin_setting("roslyn.forceProjectOpen"):
            self._debug("roslyn.forceProjectOpen enabled")

        session = self.weaksession()
        if not session:
            self._debug("No session in _open_workspace_if_needed")
            return

        workspace_folders = session.get_workspace_folders()
        self._debug("workspace_folders: {}", [wf.path for wf in workspace_folders])
        if not workspace_folders:
            self._debug("No workspace folders")
            return

        root_path = workspace_folders[0].path
        self._debug("workspace root_path: {}", root_path)

        # Check for Unity project first
        unity_main_projects = self._find_unity_main_projects(root_path)
        if unity_main_projects:
            self._debug("Unity main projects detected: {}", unity_main_projects)
            self._open_projects(unity_main_projects)
            return

        # For regular .NET projects, try to use .sln to discover all projects
        solution_file = self._find_solution_file(root_path)
        if solution_file:
            # Parse .sln to get project list, then open as individual .csproj files
            # This ensures proper project association while loading all dependencies
            projects_from_sln = self._parse_solution_projects(solution_file)
            if projects_from_sln:
                self._debug("Parsed {} projects from solution", len(projects_from_sln))
                self._open_projects(projects_from_sln)
                return
            else:
                # Fallback: open solution directly if parsing failed
                self._debug("Could not parse solution, opening directly")
                self._open_solution(solution_file)
                return

        # Last resort: find and open individual .csproj files
        project_files = self._find_project_files(root_path)
        self._debug("Found {} csproj(s)", len(project_files))
        if project_files:
            self._open_projects(project_files)

    def _open_solution(self, solution_path: str) -> None:
        """Send solution/open notification to the server."""
        session = self.weaksession()
        if not session:
            self._debug("No session in _open_solution")
            return

        uri = _path_to_uri(solution_path)
        notification = Notification("solution/open", {"solution": uri})
        session.send_notification(notification)

        self._print(False, "Opened solution: {}".format(Path(solution_path).name))
        self._debug("Sent solution/open: {}", solution_path)

    def _open_projects(self, project_paths: list[str]) -> None:
        """Send project/open notification to the server."""
        session = self.weaksession()
        if not session:
            self._debug("No session in _open_projects")
            return

        uris = [_path_to_uri(p) for p in project_paths]
        notification = Notification("project/open", {"projects": uris})
        session.send_notification(notification)

        self._print(False, "Opened {} project(s)".format(len(project_paths)))
        self._debug("Sent project/open: {}", project_paths)

    def _find_solution_file(self, root_path: str) -> Optional[str]:
        """Find a solution file (.sln, .slnx, .slnf) in the workspace."""
        settings = self.get_settings()
        default_solution = self._plugin_setting("roslyn.defaultLaunchSolution")

        extensions = [".sln", ".slnx", ".slnf"]
        solutions: list[str] = []

        for ext in extensions:
            for file in Path(root_path).rglob("*{}".format(ext)):
                solutions.append(str(file))

        if not solutions:
            self._debug("No solution file found under: {}", root_path)
            return None

        self._debug("Found solutions: {}", len(solutions))
        if len(solutions) <= 5:
            self._debug("Solutions: {}", solutions)

        # If a default solution is specified, use it
        if default_solution:
            for solution in solutions:
                if Path(solution).name == default_solution:
                    self._debug("Using defaultLaunchSolution: {}", solution)
                    return solution
            self._debug("defaultLaunchSolution not found: {}", default_solution)

        # Otherwise, return the first solution found (alphabetically)
        solutions.sort()
        self._debug("Using first solution alphabetically: {}", solutions[0])
        return solutions[0]

    def _parse_solution_projects(self, solution_path: str) -> list[str]:
        """Parse a .sln file and return all .csproj paths it contains.

        This allows us to discover all projects in a solution and open them
        via project/open instead of solution/open, which provides better
        project association and reference resolution.
        """
        import re
        sln_dir = Path(solution_path).parent
        projects = []

        try:
            content = Path(solution_path).read_text(encoding="utf-8-sig")

            # Match: Project("{...}") = "ProjectName", "path\to\project.csproj", "{...}"
            # The pattern captures the relative path to the project file
            pattern = r'Project\("[^"]*"\)\s*=\s*"[^"]*",\s*"([^"]+\.csproj)"'

            for match in re.finditer(pattern, content, re.IGNORECASE):
                rel_path = match.group(1)
                # Convert Windows path separators
                rel_path = rel_path.replace("\\", "/")
                # Resolve to absolute path
                abs_path = (sln_dir / rel_path).resolve()
                if abs_path.exists():
                    projects.append(str(abs_path))

            self._debug("Parsed {} projects from {}", len(projects), Path(solution_path).name)

        except Exception as e:
            self._debug("Error parsing solution {}: {}", solution_path, e)

        return projects

    def _find_project_files(self, root_path: str) -> list[str]:
        """Find .csproj files in the workspace."""
        projects: list[str] = []
        for file in Path(root_path).rglob("*.csproj"):
            parts = set(file.parts)
            # Skip Unity/SDK generated folders and build outputs
            if parts.intersection({"obj", "bin", "Library", "Temp", "Logs", "Packages"}):
                continue
            projects.append(str(file))
        self._debug("Found projects: {}", len(projects))
        if len(projects) <= 10:
            self._debug("Projects: {}", projects)
        return projects

    def _find_unity_main_projects(self, root_path: str) -> list[str]:
        """Detect Unity project roots and return the primary csproj(s) and their dependencies.

        Unity projects are typically identified by the presence of Assets/ and ProjectSettings/.
        We open Assembly-CSharp*.csproj files and automatically discover all ProjectReference
        dependencies to ensure all references are properly resolved.
        """
        root = Path(root_path)
        if not (root / "Assets").exists() or not (root / "ProjectSettings").exists():
            return []

        # Main project files to load
        main_projects = [
            "Assembly-CSharp.csproj",
            "Assembly-CSharp-Editor.csproj",
            "Assembly-CSharp.Player.csproj",
        ]

        candidates = []
        discovered_refs = set()

        # Add main projects and discover their ProjectReferences
        for name in main_projects:
            p = root / name
            if p.exists():
                candidates.append(str(p))
                # Parse ProjectReferences from this csproj
                refs = self._parse_project_references(p)
                discovered_refs.update(refs)

        # Add discovered ProjectReferences
        for ref_name in discovered_refs:
            ref_path = root / ref_name
            if ref_path.exists() and str(ref_path) not in candidates:
                candidates.append(str(ref_path))

        self._debug("Unity projects: {} main + {} dependencies",
                    len([c for c in candidates if any(m in c for m in main_projects)]),
                    len(candidates) - len([c for c in candidates if any(m in c for m in main_projects)]))

        return candidates

    def _parse_project_references(self, csproj_path: Path) -> set[str]:
        """Parse ProjectReference elements from a csproj file.

        Returns a set of referenced project file names (e.g., 'UnityEngine.UI.csproj').
        """
        refs = set()
        try:
            import re
            content = csproj_path.read_text(encoding="utf-8-sig")
            # Match: <ProjectReference Include="SomeProject.csproj">
            pattern = r'<ProjectReference\s+Include="([^"]+)"'
            for match in re.finditer(pattern, content):
                ref = match.group(1)
                # Get just the filename (in case it's a relative path)
                ref_name = Path(ref).name
                refs.add(ref_name)
        except Exception as e:
            self._debug("Error parsing ProjectReferences from {}: {}", csproj_path, e)
        return refs

    def _print(self, sticky: bool, fmt: str, *args: Any) -> None:
        """Print a message to the status bar."""
        session = self.weaksession()
        if session:
            message = fmt.format(*args) if args else fmt
            if sticky:
                session.set_config_status_async(message)
            else:
                session.set_config_status_async("")
                session.window.status_message(message)

    def _debug(self, fmt: str, *args: Any) -> None:
        enabled = bool(self._plugin_setting("roslyn.debug")) or bool(self._plugin_setting("roslyn.debugMode"))
        if not enabled:
            # Also enable debug if user set server logging to Debug/Trace.
            server_level = str(self._plugin_setting("roslyn.loggingLevel") or "").lower()
            enabled = server_level in {"debug", "trace"}
        if not enabled:
            return

        message = fmt.format(*args) if args else fmt
        print("[LSP-Roslyn] {}".format(message))

    # --- Roslyn-specific notification handlers -------------------------------
    #
    # Note: Roslyn uses non-standard notification methods. The LSP plugin dispatches
    # notifications to methods named `m_{method}` where `/` is replaced with `_`.
    # Examples:
    #   workspace/projectInitializationComplete -> m_workspace_projectInitializationComplete
    #   workspace/_roslyn_projectNeedsRestore -> m_workspace__roslyn_projectNeedsRestore

    def on_server_notification_async(self, notification: Notification) -> None:
        """Handle server notifications using the new async hook.

        This provides a more reliable way to handle Roslyn-specific notifications.
        Note: workspace/_roslyn_projectNeedsRestore is a REQUEST, not a notification,
        so it's handled via m_workspace__roslyn_projectNeedsRestore instead.
        """
        method = notification.method
        params = notification.params

        if method == "workspace/projectInitializationComplete":
            self._on_project_initialization_complete(params)
        elif method == "workspace/refreshSourceGeneratedDocument":
            self._on_refresh_source_generated_document(params)

    def _on_project_initialization_complete(self, params: Any) -> None:
        """Handle workspace/projectInitializationComplete notification."""
        self._debug("workspace/projectInitializationComplete received")
        self._print(False, "Roslyn project initialization complete")

        # Mark that project is initialized
        setattr(self, "_project_initialized", True)

        # Trigger diagnostic refresh for all open views
        # Wait for solution/projects to be fully loaded (loading .sln takes longer)
        sublime.set_timeout_async(self._refresh_all_diagnostics, 3000)

    def _on_project_needs_restore(self, params: Any, request_id: Any = None) -> None:
        """Handle workspace/_roslyn_projectNeedsRestore request.

        Note: This is actually a REQUEST, not a notification. Roslyn expects a response.
        """
        self._debug("workspace/_roslyn_projectNeedsRestore: {}", params)
        self._print(True, "Project needs restore - run 'dotnet restore'")

        # If this is a request (has request_id), we need to send a response
        if request_id is not None:
            session = self.weaksession()
            if session:
                # Send empty response to acknowledge the request
                from LSP.plugin import Response
                session.send_response(Response(request_id, None))

    def _on_refresh_source_generated_document(self, params: Any) -> None:
        """Handle workspace/refreshSourceGeneratedDocument notification."""
        self._debug("workspace/refreshSourceGeneratedDocument: {}", params)
        # TODO: Implement source-generated file refresh

    def _refresh_all_diagnostics(self) -> None:
        """Request diagnostics for all open C# views.

        Since we disabled the LSP plugin's built-in pull diagnostics (which crashes
        on Roslyn's null responses), we manually request diagnostics and convert
        them to push format.
        """
        session = self.weaksession()
        if not session:
            self._debug("No session in _refresh_all_diagnostics")
            return

        self._debug("Refreshing diagnostics for all open views")

        # Get all open C# views in this window
        window = session.window
        for view in window.views():
            if view.match_selector(0, "source.cs"):
                file_name = view.file_name()
                if file_name:
                    self._request_diagnostics_for_uri(_path_to_uri(file_name))

    def _request_diagnostics_for_uri(self, uri: str) -> None:
        """Request diagnostics for a specific URI and publish them.

        Sends textDocument/diagnostic request to Roslyn and converts the response
        to textDocument/publishDiagnostics format for the LSP plugin to display.
        """
        session = self.weaksession()
        if not session:
            return

        if not getattr(self, "_project_initialized", False):
            self._debug("Skipping diagnostic request - project not initialized: {}", uri)
            return

        self._debug("Requesting diagnostics for: {}", uri)

        # Build the diagnostic request
        request = Request("textDocument/diagnostic", {
            "textDocument": {"uri": uri}
        })

        def on_result(response: Any) -> None:
            if response is None:
                self._debug("Diagnostic response is None for: {}", uri)
                return

            # Extract diagnostics from response
            # Response format: { kind: "full" | "unchanged", items?: Diagnostic[], resultId?: string }
            kind = response.get("kind", "full") if isinstance(response, dict) else "full"
            items = response.get("items", []) if isinstance(response, dict) else []

            self._debug("Received {} diagnostics for: {} (kind={})", len(items), uri, kind)

            # Debug: print diagnostic codes to see what we're getting
            if items:
                codes = []
                for diag in items[:5]:  # First 5 diagnostics
                    code = diag.get("code", "?")
                    msg = diag.get("message", "")[:50]
                    severity = diag.get("severity", "?")
                    codes.append("{}(sev={}): {}".format(code, severity, msg))
                self._debug("Sample diagnostics: {}", codes)

            if kind == "unchanged":
                # No changes, don't update
                return

            # Convert to publishDiagnostics format and inject into LSP plugin
            self._publish_diagnostics(uri, items)

        def on_error(error: Any) -> None:
            self._debug("Diagnostic request error for {}: {}", uri, error)

        session.send_request_async(request, on_result, on_error)

    def _publish_diagnostics(self, uri: str, diagnostics: list) -> None:
        """Publish diagnostics using the LSP plugin's push diagnostics handler.

        This converts pull diagnostics to push format so the LSP plugin can display them.
        """
        session = self.weaksession()
        if not session:
            return

        # Build PublishDiagnosticsParams
        params = {
            "uri": uri,
            "diagnostics": diagnostics
        }

        self._debug("Publishing {} diagnostics for: {}", len(diagnostics), uri)

        # Call the LSP plugin's push diagnostics handler directly
        # This is the standard LSP notification handler
        session.m_textDocument_publishDiagnostics(params)

    # Legacy handlers (kept for compatibility with older LSP plugin versions)
    def m_workspace_projectInitializationComplete(self, params: Any) -> None:
        """Legacy handler for workspace/projectInitializationComplete."""
        self._on_project_initialization_complete(params)

    def m_workspace__roslyn_projectNeedsRestore(self, params: Any, request_id: Any) -> None:
        """Legacy handler for workspace/_roslyn_projectNeedsRestore (request)."""
        self._on_project_needs_restore(params, request_id)


class RoslynEventListener(sublime_plugin.EventListener):
    """Event listener for triggering diagnostic refresh on file save and modification."""

    def on_post_save_async(self, view: sublime.View) -> None:
        """Trigger diagnostic refresh after saving a C# file."""
        self._request_diagnostics(view)

    def on_modified_async(self, view: sublime.View) -> None:
        """Trigger diagnostic refresh after modifying a C# file (debounced).

        We use a debounce to:
        1. Avoid sending too many requests while typing
        2. Ensure textDocument/didChange is processed by Roslyn before we request diagnostics
        """
        # Check if this is a C# file (early exit for performance)
        if not view.match_selector(0, "source.cs"):
            return

        # Use a debounce with version tracking to cancel stale requests
        import time
        key = "roslyn_diag_{}".format(view.id())
        current_time = time.time()

        pending = getattr(self, "_pending_diagnostics", {})
        pending[key] = current_time
        setattr(self, "_pending_diagnostics", pending)

        # Debounce: wait 1.5 seconds after last modification
        # This gives time for:
        # 1. User to finish typing
        # 2. LSP plugin to send textDocument/didChange
        # 3. Roslyn to process the change and update semantic model
        def delayed_request() -> None:
            current_pending = getattr(self, "_pending_diagnostics", {})
            # Only proceed if this is still the latest request for this view
            if current_pending.get(key) == current_time:
                del current_pending[key]
                self._request_diagnostics(view)

        sublime.set_timeout_async(delayed_request, 1500)

    def _request_diagnostics(self, view: sublime.View) -> None:
        """Request diagnostics for a view via the Roslyn plugin."""
        # Check if this is a C# file
        if not view.match_selector(0, "source.cs"):
            return

        file_name = view.file_name()
        if not file_name:
            return

        # Try to trigger diagnostic refresh via the plugin
        try:
            from LSP.plugin.core.registry import windows
            from LSP.plugin.core.sessions import get_plugin

            window = view.window()
            if not window:
                return

            wm = windows.lookup(window)
            if not wm:
                return

            # Find the Roslyn session for this view
            for session in wm.sessions(view):
                if session.config.name == "Roslyn":
                    # Get the plugin instance and request diagnostics
                    if session._plugin:
                        uri = _path_to_uri(file_name)
                        session._plugin._request_diagnostics_for_uri(uri)
                    break
        except Exception:
            # Silently fail if LSP internals change
            pass


def plugin_loaded() -> None:
    register_plugin(Roslyn)


def plugin_unloaded() -> None:
    unregister_plugin(Roslyn)
