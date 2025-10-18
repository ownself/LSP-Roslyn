# LSP-Roslyn

This is a helper package that provides C# language support for Sublime Text using the modern [Roslyn Language Server](https://github.com/dotnet/roslyn). This is the same language server used by the Visual Studio Code C# Extension and C# Dev Kit.

## Why LSP-Roslyn instead of LSP-OmniSharp?

The OmniSharp language server has been discontinued in favor of the newer Roslyn language server. LSP-Roslyn provides:

- **Active Development**: Regularly updated with new features and bug fixes
- **Better Performance**: Improved memory usage and responsiveness
- **Modern Features**: Support for latest C# language features
- **Source Generators**: Full support for source-generated files
- **Better Code Actions**: More comprehensive refactoring and quick fixes

## Requirements

To use this package, you must have:

- **Sublime Text 4** (Build 4075 or later)
- **[LSP](https://packagecontrol.io/packages/LSP)** package installed via Package Control
- **[.NET SDK 8.0 or higher](https://dotnet.microsoft.com/download)** installed
- (Optional but recommended) **[LSP-file-watcher-chokidar](https://github.com/sublimelsp/LSP-file-watcher-chokidar)** for file watching support

## Applicable Selectors

This language server operates on views with the `source.cs` or `source.cake` base scope.

## Installation

### Via Package Control (Coming Soon)

1. Install the LSP package if not already installed
2. Install LSP-Roslyn via Package Control

### Manual Installation

#### Step 1: Install the Plugin

Clone this repository into your Sublime Text Packages directory:

```bash
# macOS
cd "~/Library/Application Support/Sublime Text/Packages"
git clone https://github.com/yourusername/LSP-Roslyn.git

# Windows (PowerShell)
cd "$env:APPDATA\Sublime Text\Packages"
git clone https://github.com/yourusername/LSP-Roslyn.git

# Linux
cd "~/.config/sublime-text/Packages"
git clone https://github.com/yourusername/LSP-Roslyn.git
```

#### Step 2: Install the Roslyn Language Server

The Roslyn language server is hosted on Azure DevOps and requires manual installation. Choose one of the following methods:

**Method A: Using the Installation Scripts (Recommended)**

```bash
# Unix/Linux/macOS
cd LSP-Roslyn
chmod +x install_roslyn.sh
./install_roslyn.sh

# Windows (PowerShell as Administrator)
cd LSP-Roslyn
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install_roslyn.ps1
```

**Method B: Using dotnet CLI**

```bash
# Get your Sublime Text Package Storage path:
# macOS: ~/Library/Application Support/Sublime Text/Package Storage/LSP-Roslyn
# Windows: %APPDATA%\Sublime Text\Package Storage\LSP-Roslyn
# Linux: ~/.config/sublime-text/Package Storage/LSP-Roslyn

# Install using dotnet tool (neutral version)
dotnet tool install --tool-path "<path-to-package-storage>/LSP-Roslyn" \
    Microsoft.CodeAnalysis.LanguageServer
```

**Method C: Manual Download**

1. Visit the Azure DevOps NuGet feed:
   - Windows x64: https://dev.azure.com/azure-public/vside/_artifacts/feed/vs-impl/NuGet/Microsoft.CodeAnalysis.LanguageServer.win-x64
   - macOS x64: https://dev.azure.com/azure-public/vside/_artifacts/feed/vs-impl/NuGet/Microsoft.CodeAnalysis.LanguageServer.osx-x64
   - macOS ARM64: https://dev.azure.com/azure-public/vside/_artifacts/feed/vs-impl/NuGet/Microsoft.CodeAnalysis.LanguageServer.osx-arm64
   - Linux x64: https://dev.azure.com/azure-public/vside/_artifacts/feed/vs-impl/NuGet/Microsoft.CodeAnalysis.LanguageServer.linux-x64

2. Download the latest version (e.g., `4.14.0-3.24630.3`)

3. Rename the `.nupkg` file to `.zip` and extract it

4. Copy the contents to `<Package Storage>/LSP-Roslyn/`

5. Make the binary executable (Unix/macOS):
   ```bash
   chmod +x "<Package Storage>/LSP-Roslyn/Microsoft.CodeAnalysis.LanguageServer"
   ```

**Method D: Use Custom Command**

If you have the Roslyn server installed elsewhere, specify a custom command in your settings:

```json
{
    "command": [
        "/path/to/Microsoft.CodeAnalysis.LanguageServer",
        "--logLevel=Information",
        "--extensionLogDirectory=/tmp/roslyn-logs",
        "--stdio"
    ]
}
```

#### Step 3: Verify Installation

1. Open a C# file in Sublime Text
2. Check the status bar - it should show "LSP: Roslyn"
3. If there are issues, check: Tools → LSP → Troubleshoot Server Configuration

## Installation Location

The Roslyn language server is installed **in the same directory as the plugin code**:

- **macOS**: `~/Library/Application Support/Sublime Text/Packages/LSP-Roslyn/`
- **Windows**: `%APPDATA%\Sublime Text\Packages\LSP-Roslyn\`
- **Linux**: `~/.config/sublime-text/Packages/LSP-Roslyn/`

The server binary can be in any of these locations (checked in order):

1. **Organized structure** (recommended):
   `Packages/LSP-Roslyn/Microsoft.CodeAnalysis.LanguageServer/content/LanguageServer/{platform}/`
2. **Direct extraction**:
   `Packages/LSP-Roslyn/content/LanguageServer/{platform}/`
3. **Custom location**:
   `Packages/LSP-Roslyn/`

Where `{platform}` is `win-x64`, `osx-x64`, `osx-arm64`, `linux-x64`, etc.

The plugin automatically detects the server location from these paths.

## Configuration

Configure LSP-Roslyn by running `Preferences: LSP-Roslyn Settings` from the Command Palette.

### Key Settings

#### Solution Selection

```json
{
    "settings": {
        // Specify default solution if multiple .sln files exist
        "roslyn.defaultLaunchSolution": "MyProject.sln"
    }
}
```

#### Background Analysis

Control the scope of diagnostics analysis:

```json
{
    "settings": {
        "roslyn.backgroundAnalysis": {
            "dotnet_analyzer_diagnostics_scope": "openFiles",  // or "fullSolution", "none"
            "dotnet_compiler_diagnostics_scope": "openFiles"
        }
    }
}
```

#### Inlay Hints

Enable inline type and parameter hints:

```json
{
    "settings": {
        "roslyn.inlayHints": {
            "csharp_enable_inlay_hints_for_implicit_variable_types": true,
            "dotnet_enable_inlay_hints_for_parameters": true
        }
    }
}
```

#### Code Lens

Show references and test indicators:

```json
{
    "settings": {
        "roslyn.codeLens": {
            "dotnet_enable_references_code_lens": true,
            "dotnet_enable_tests_code_lens": true
        }
    }
}
```

## Capabilities

LSP-Roslyn provides comprehensive C# language support:

### Core Features
- **Code Completion** - IntelliSense with automatic import suggestions
- **Signature Help** - Parameter information for methods
- **Hover Information** - Documentation and type information
- **Go to Definition** - Navigate to symbol definitions
- **Find References** - Find all usages of symbols
- **Rename** - Rename symbols across the solution

### Advanced Features
- **Code Actions** - Quick fixes and refactorings
- **Code Lens** - Inline references and test indicators
- **Inlay Hints** - Type and parameter hints
- **Diagnostics** - Real-time error and warning detection
- **Formatting** - Code formatting support
- **Symbol Search** - Workspace-wide symbol search
- **Source Generators** - Support for source-generated files

### Roslyn Analyzers
- **Built-in Analyzers** - Code quality and style analyzers
- **Custom Analyzers** - Support for third-party analyzer packages
- **EditorConfig** - Respects .editorconfig settings

## Commands

Available commands from the Command Palette:

- **LSP-Roslyn: Restart Server** - Restart the language server
- **LSP-Roslyn: Select Solution** - Choose a different solution file
- **Preferences: LSP-Roslyn Settings** - Open settings file

## Multiple Solutions

If your workspace contains multiple solution files, LSP-Roslyn will:

1. Check for `roslyn.defaultLaunchSolution` setting
2. If not set, use the first solution file (alphabetically)
3. Use the `LSP-Roslyn: Select Solution` command to switch between solutions

## Project Structure Support

LSP-Roslyn supports:

- **Solution files**: `.sln`, `.slnx`, `.slnf`
- **Project files**: `.csproj` (standalone projects without solution)
- **Multiple projects**: Full solution support with project references

## Troubleshooting

### Server Not Starting

1. Verify .NET SDK is installed: `dotnet --version`
2. Check LSP logs: Tools → LSP → Troubleshoot Server
3. Try restarting the server: Command Palette → LSP-Roslyn: Restart Server

### Solution Not Loading

1. Ensure solution file is valid: `dotnet build YourSolution.sln`
2. Run `dotnet restore` in the solution directory
3. Set `roslyn.defaultLaunchSolution` if multiple solutions exist

### Performance Issues

For large solutions:

```json
{
    "settings": {
        "roslyn.loadProjectsOnDemand": true,
        "roslyn.backgroundAnalysis": {
            "dotnet_analyzer_diagnostics_scope": "openFiles"
        }
    }
}
```

### Viewing Logs

Server logs are stored in:
`$DATA/Package Storage/LSP-Roslyn/logs/`

## Differences from OmniSharp

| Feature | LSP-OmniSharp | LSP-Roslyn |
|---------|---------------|------------|
| Server | OmniSharp (discontinued) | Roslyn (active) |
| .NET Version | .NET 6+ | .NET 8+ |
| Source Generators | Limited | Full support |
| Performance | Good | Better |
| Latest C# Features | Delayed | Immediate |
| Maintenance | Discontinued | Active |

## Contributing

Issues and pull requests are welcome! Please visit the [GitHub repository](https://github.com/yourusername/LSP-Roslyn).

## License

This package is released under the MIT License. See [LICENSE](LICENSE) for details.

## Acknowledgments

- Based on the [LSP-OmniSharp](https://github.com/sublimelsp/LSP-OmniSharp) package structure
- Uses the [Roslyn Language Server](https://github.com/dotnet/roslyn) from Microsoft
- Built on the [LSP](https://github.com/sublimelsp/LSP) package for Sublime Text
