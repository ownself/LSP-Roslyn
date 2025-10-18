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

# Roslyn language server version - matches VSCode C# extension
VERSION = "4.14.0-3.24630.3"

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
        }
    }
    return platform_map[sublime.platform()][sublime.arch()]


def _get_package_name() -> str:
    """Returns the full package name for the current platform."""
    return f"Microsoft.CodeAnalysis.LanguageServer.{_platform_str()}"


class Roslyn(AbstractPlugin):
    @classmethod
    def name(cls) -> str:
        return cls.__name__

    @classmethod
    def get_settings(cls) -> sublime.Settings:
        return sublime.load_settings(f"LSP-{cls.name()}.sublime-settings")

    @classmethod
    def version_str(cls) -> str:
        return VERSION

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

        # Roslyn server requires these arguments
        return [
            str(cls.binary_path()),
            "--logLevel=Information",
            f"--extensionLogDirectory={cls.basedir() / 'logs'}",
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
        """Download and install the Roslyn language server using dotnet tool."""
        basedir = cls.basedir()
        shutil.rmtree(basedir, ignore_errors=True)
        basedir.mkdir(parents=True, exist_ok=True)

        # Create logs directory
        (basedir / "logs").mkdir(exist_ok=True)

        platform = _platform_str()
        version = cls.version_str()
        package_name = _get_package_name()

        try:
            import subprocess

            # Try to download using dotnet/nuget CLI
            # Method 1: Use nuget.exe (Windows) or mono nuget.exe (Unix)
            nuget_install_dir = basedir / "nuget_temp"
            nuget_install_dir.mkdir(exist_ok=True)

            # Check if dotnet is available
            dotnet_available = False
            try:
                result = subprocess.run(
                    ["dotnet", "--version"],
                    capture_output=True,
                    timeout=5
                )
                dotnet_available = result.returncode == 0
            except Exception:
                pass

            if dotnet_available:
                # Use dotnet to add the NuGet source and install the package
                # Add the Azure DevOps NuGet feed
                subprocess.run(
                    [
                        "dotnet", "nuget", "add", "source",
                        AZURE_NUGET_FEED,
                        "--name", "vs-impl",
                    ],
                    capture_output=True,
                    timeout=30,
                    check=False  # Don't fail if source already exists
                )

                # Install the package using dotnet tool
                # Note: This requires the package to be available as a .NET tool
                # Alternative: Use nuget.exe or manually download the .nupkg file

                sublime.message_dialog(
                    "LSP-Roslyn: Manual Installation Required\n\n"
                    f"Please manually install the Roslyn language server:\n\n"
                    f"1. Download the package from:\n"
                    f"   https://dev.azure.com/azure-public/vside/_artifacts/feed/vs-impl/NuGet/{package_name}\n\n"
                    f"2. Extract the .nupkg file (it's a zip file) to:\n"
                    f"   {basedir}\n\n"
                    f"3. Ensure the server binary is executable\n\n"
                    f"Or use the neutral version and dotnet:\n"
                    f"   dotnet tool install --tool-path {basedir} Microsoft.CodeAnalysis.LanguageServer"
                )
                raise Exception("Manual installation required - see dialog for instructions")
            else:
                raise Exception("dotnet CLI not found - please install .NET SDK")

        except Exception as e:
            # If automatic installation fails, provide instructions
            error_msg = (
                f"Failed to automatically install Roslyn language server: {e}\n\n"
                f"Manual installation instructions:\n"
                f"1. Ensure .NET SDK 8.0+ is installed\n"
                f"2. Download {package_name} version {version} from:\n"
                f"   https://dev.azure.com/azure-public/vside/_artifacts/feed/vs-impl\n"
                f"3. Extract to: {basedir}\n"
                f"4. Make the binary executable (Unix/macOS)\n\n"
                f"Alternative: Use 'dotnet tool install' with the neutral package:\n"
                f"   dotnet tool install --tool-path \"{basedir}\" Microsoft.CodeAnalysis.LanguageServer\n\n"
                f"Or specify a custom command in LSP-Roslyn settings."
            )
            sublime.error_message(error_msg)
            raise

    @classmethod
    def on_pre_start(
        cls,
        window: sublime.Window,
        initiating_view: sublime.View,
        workspace_folders: list[WorkspaceFolder],
        configuration: ClientConfig
    ) -> Optional[str]:
        """Called before starting the language server."""
        configuration.command = cls.get_command()

        # Set environment variables
        if not configuration.env:
            configuration.env = {}
        configuration.env["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"

        return None

    def on_workspace_configuration(
        self,
        params: dict[str, Any],
        configuration: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Handle workspace/configuration requests from the server."""
        # Initialize configuration if None
        if configuration is None:
            configuration = {}

        settings = self.get_settings()

        # Map Sublime settings to Roslyn configuration
        roslyn_config = {}

        # Background analysis settings
        if settings.has("roslyn.backgroundAnalysis"):
            roslyn_config["csharp|background_analysis"] = settings.get("roslyn.backgroundAnalysis")

        # Code lens settings
        if settings.has("roslyn.codeLens"):
            roslyn_config["csharp|code_lens"] = settings.get("roslyn.codeLens")

        # Completion settings
        if settings.has("roslyn.completion"):
            roslyn_config["csharp|completion"] = settings.get("roslyn.completion")

        # Inlay hints settings
        if settings.has("roslyn.inlayHints"):
            roslyn_config["csharp|inlay_hints"] = settings.get("roslyn.inlayHints")

        # Symbol search settings
        if settings.has("roslyn.symbolSearch"):
            roslyn_config["csharp|symbol_search"] = settings.get("roslyn.symbolSearch")

        # Formatting settings
        if settings.has("roslyn.formatting"):
            roslyn_config["csharp|formatting"] = settings.get("roslyn.formatting")

        configuration.update(roslyn_config)
        return configuration

    async def on_ready_async(self, client_config: ClientConfig) -> None:
        """Called when the language server is ready."""
        session = self.weaksession()
        if not session:
            return

        # Find solution or project files in workspace
        window = session.window
        workspace_folders = session.get_workspace_folders()

        if not workspace_folders:
            return

        root_path = workspace_folders[0].path
        solution_file = self._find_solution_file(root_path)

        if solution_file:
            # Open solution
            await self._open_solution(solution_file)
        else:
            # Try to find .csproj files
            project_files = self._find_project_files(root_path)
            if project_files:
                await self._open_projects(project_files)

    async def _open_solution(self, solution_path: str) -> None:
        """Send solution/open notification to the server."""
        session = self.weaksession()
        if not session:
            return

        uri = sublime.filename_to_uri(solution_path)
        notification = Notification("solution/open", {"solution": uri})

        session.send_notification(notification)
        self._print(False, f"Opened solution: {Path(solution_path).name}")

    async def _open_projects(self, project_paths: list[str]) -> None:
        """Send project/open notification to the server."""
        session = self.weaksession()
        if not session:
            return

        uris = [sublime.filename_to_uri(p) for p in project_paths]
        notification = Notification("project/open", {"projects": uris})

        session.send_notification(notification)
        self._print(False, f"Opened {len(project_paths)} project(s)")

    def _find_solution_file(self, root_path: str) -> Optional[str]:
        """Find a solution file (.sln, .slnx, .slnf) in the workspace."""
        settings = self.get_settings()
        default_solution = settings.get("roslyn.defaultLaunchSolution")

        extensions = [".sln", ".slnx", ".slnf"]
        solutions = []

        for ext in extensions:
            for file in Path(root_path).rglob(f"*{ext}"):
                solutions.append(str(file))

        if not solutions:
            return None

        # If a default solution is specified, use it
        if default_solution:
            for solution in solutions:
                if Path(solution).name == default_solution:
                    return solution

        # Otherwise, return the first solution found (alphabetically)
        solutions.sort()
        return solutions[0]

    def _find_project_files(self, root_path: str) -> list[str]:
        """Find .csproj files in the workspace."""
        projects = []
        for file in Path(root_path).rglob("*.csproj"):
            # Skip obj and bin directories
            if "obj" not in file.parts and "bin" not in file.parts:
                projects.append(str(file))
        return projects

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
        # TODO: Implement project restore handling
        self._print(True, "Project needs restore - run 'dotnet restore'")


def plugin_loaded() -> None:
    register_plugin(Roslyn)


def plugin_unloaded() -> None:
    unregister_plugin(Roslyn)
