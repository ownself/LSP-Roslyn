from __future__ import annotations

import os
import shutil
import sublime

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

    def on_workspace_configuration(
        self, params: dict[str, Any], configuration: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Handle workspace/configuration requests from the server."""
        # Initialize configuration if None
        if configuration is None:
            configuration = {}

        settings = self.get_settings()
        nested = settings.get("settings")
        if not isinstance(nested, dict):
            nested = {}

        # Map Sublime settings to Roslyn configuration
        roslyn_config: dict[str, Any] = {}

        # Background analysis settings
        if "roslyn.backgroundAnalysis" in nested:
            roslyn_config["csharp|background_analysis"] = nested.get("roslyn.backgroundAnalysis")

        # Code lens settings
        if "roslyn.codeLens" in nested:
            roslyn_config["csharp|code_lens"] = nested.get("roslyn.codeLens")

        # Completion settings
        if "roslyn.completion" in nested:
            roslyn_config["csharp|completion"] = nested.get("roslyn.completion")

        # Inlay hints settings
        if "roslyn.inlayHints" in nested:
            roslyn_config["csharp|inlay_hints"] = nested.get("roslyn.inlayHints")

        # Symbol search settings
        if "roslyn.symbolSearch" in nested:
            roslyn_config["csharp|symbol_search"] = nested.get("roslyn.symbolSearch")

        # Formatting settings
        if "roslyn.formatting" in nested:
            roslyn_config["csharp|formatting"] = nested.get("roslyn.formatting")

        # Project system settings - explicitly disable binlog generation by default
        # This prevents .binlog files from being created in project directories
        binlog_path = nested.get("projects.dotnet_binary_log_path")
        roslyn_config["projects.dotnet_binary_log_path"] = binlog_path  # null by default

        if not getattr(self, "_did_log_config_keys", False):
            setattr(self, "_did_log_config_keys", True)
            self._debug("workspace/configuration settings keys: {}", sorted(list(nested.keys())))

        configuration.update(roslyn_config)

        # `on_ready`/`on_ready_async` are not reliably called across LSP package versions.
        # `workspace/configuration` is requested after initialization, so it's a safe and
        # stable signal to open the workspace.
        sublime.set_timeout_async(self._open_workspace_if_needed, 0)

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

        unity_main_projects = self._find_unity_main_projects(root_path)
        if unity_main_projects:
            self._debug("Unity main projects detected: {}", unity_main_projects)
            self._open_projects(unity_main_projects)
            return

        if not self._plugin_setting("roslyn.forceProjectOpen"):
            solution_file = self._find_solution_file(root_path)
            if solution_file:
                self._open_solution(solution_file)
                return

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
        """Detect Unity project roots and return the primary csproj(s).

        Unity projects are typically identified by the presence of Assets/ and ProjectSettings/.
        When detected, prefer opening `Assembly-CSharp*.csproj` to avoid loading a huge solution.
        """
        root = Path(root_path)
        if not (root / "Assets").exists() or not (root / "ProjectSettings").exists():
            return []

        candidates = []
        for name in ("Assembly-CSharp.csproj", "Assembly-CSharp-Editor.csproj", "Assembly-CSharp.Player.csproj"):
            p = root / name
            if p.exists():
                candidates.append(str(p))

        return candidates

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

    def m_workspace__projectInitializationComplete(self, params: Any) -> None:
        """Handle workspace/projectInitializationComplete notification."""
        self._print(False, "Roslyn project initialization complete")

    def m_workspace__refreshSourceGeneratedDocument(self, params: Any) -> None:
        """Handle workspace/refreshSourceGeneratedDocument notification."""
        # TODO: Implement source-generated file refresh
        pass

    def m_workspace___roslyn_projectNeedsRestore(self, params: Any) -> None:
        """Handle workspace/_roslyn_projectNeedsRestore notification."""
        self._debug("workspace/_roslyn_projectNeedsRestore: {}", params)
        self._print(True, "Project needs restore - run 'dotnet restore'")


def plugin_loaded() -> None:
    register_plugin(Roslyn)


def plugin_unloaded() -> None:
    unregister_plugin(Roslyn)
