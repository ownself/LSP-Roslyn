# LSP-Roslyn Installation Guide

This guide provides detailed instructions for installing the Roslyn Language Server for use with LSP-Roslyn.

## Prerequisites

Before installing LSP-Roslyn, ensure you have:

1. **Sublime Text 4** (Build 4075 or later)
2. **LSP Package** - Install via Package Control
3. **.NET SDK 8.0+** - Download from https://dotnet.microsoft.com/download

Verify .NET installation:
```bash
dotnet --version
```

## Understanding the Installation

The Roslyn language server is distributed as a NuGet package on Azure DevOps. Unlike OmniSharp, it cannot be directly downloaded via HTTP URL. Instead, you need to use one of the following methods:

## Installation Methods

### Method 1: Automated Script (Recommended)

The easiest way to install is using the provided installation scripts.

#### macOS / Linux

```bash
cd "~/Library/Application Support/Sublime Text/Packages/LSP-Roslyn"  # macOS
# cd "~/.config/sublime-text/Packages/LSP-Roslyn"  # Linux

chmod +x install_roslyn.sh
./install_roslyn.sh
```

#### Windows

Open PowerShell as Administrator:

```powershell
cd "$env:APPDATA\Sublime Text\Packages\LSP-Roslyn"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install_roslyn.ps1
```

### Method 2: Using dotnet tool

The `Microsoft.CodeAnalysis.LanguageServer` package is available as a .NET tool.

#### Step 1: Determine Installation Path

Get your Sublime Text Package Storage path:

- **macOS**: `~/Library/Application Support/Sublime Text/Package Storage/LSP-Roslyn`
- **Windows**: `%APPDATA%\Sublime Text\Package Storage\LSP-Roslyn`
- **Linux**: `~/.config/sublime-text/Package Storage/LSP-Roslyn`

#### Step 2: Install Using dotnet

```bash
# Create the directory if it doesn't exist
mkdir -p "<Package Storage Path>/LSP-Roslyn"

# Install the tool
dotnet tool install \
    --tool-path "<Package Storage Path>/LSP-Roslyn" \
    Microsoft.CodeAnalysis.LanguageServer
```

Example for macOS:
```bash
dotnet tool install \
    --tool-path "$HOME/Library/Application Support/Sublime Text/Package Storage/LSP-Roslyn" \
    Microsoft.CodeAnalysis.LanguageServer
```

Example for Windows:
```powershell
dotnet tool install `
    --tool-path "$env:APPDATA\Sublime Text\Package Storage\LSP-Roslyn" `
    Microsoft.CodeAnalysis.LanguageServer
```

### Method 3: Manual NuGet Package Download

If you need a specific version or the platform-specific package:

#### Step 1: Navigate to Azure DevOps

Visit the NuGet feed based on your platform:

- **Windows x64**: https://dev.azure.com/azure-public/vside/_artifacts/feed/vs-impl/NuGet/Microsoft.CodeAnalysis.LanguageServer.win-x64
- **Windows ARM64**: https://dev.azure.com/azure-public/vside/_artifacts/feed/vs-impl/NuGet/Microsoft.CodeAnalysis.LanguageServer.win-arm64
- **macOS x64**: https://dev.azure.com/azure-public/vside/_artifacts/feed/vs-impl/NuGet/Microsoft.CodeAnalysis.LanguageServer.osx-x64
- **macOS ARM64**: https://dev.azure.com/azure-public/vside/_artifacts/feed/vs-impl/NuGet/Microsoft.CodeAnalysis.LanguageServer.osx-arm64
- **Linux x64**: https://dev.azure.com/azure-public/vside/_artifacts/feed/vs-impl/NuGet/Microsoft.CodeAnalysis.LanguageServer.linux-x64
- **Linux ARM64**: https://dev.azure.com/azure-public/vside/_artifacts/feed/vs-impl/NuGet/Microsoft.CodeAnalysis.LanguageServer.linux-arm64
- **Neutral (all platforms)**: https://dev.azure.com/azure-public/vside/_artifacts/feed/vs-impl/NuGet/Microsoft.CodeAnalysis.LanguageServer

#### Step 2: Download the Package

1. Click on the version you want to download (e.g., `4.14.0-3.24630.3`)
2. Click "Download" button
3. Save the `.nupkg` file

#### Step 3: Extract the Package

NuGet packages are zip files. The package contains the server in a `content/LanguageServer/{platform}/` subdirectory.

```bash
# Rename to .zip
mv Microsoft.CodeAnalysis.LanguageServer.*.nupkg roslyn.zip

# Extract directly to the LSP-Roslyn directory
unzip roslyn.zip -d "$HOME/Library/Application Support/Sublime Text/Package Storage/LSP-Roslyn"
```

On Windows:
```powershell
# Rename the file to .zip in File Explorer (e.g., roslyn.zip)
# Right-click and "Extract All..."
# Extract to: %APPDATA%\Sublime Text\Package Storage\LSP-Roslyn
```

**Expected directory structure after extraction:**
```
Package Storage/LSP-Roslyn/
├── content/
│   └── LanguageServer/
│       └── win-x64/  (or osx-x64, linux-x64, etc.)
│           ├── Microsoft.CodeAnalysis.LanguageServer.exe
│           ├── Microsoft.CodeAnalysis.LanguageServer.dll
│           └── ... (other dependencies)
├── lib/
├── [Content_Types].xml
└── ... (other NuGet metadata)
```

**Note:** The plugin automatically detects the `content/LanguageServer/{platform}/` subdirectory structure, so you can extract the entire NuGet package as-is.

#### Step 4: Set Permissions (Unix/macOS only)

```bash
# Set executable permission on the server binary
chmod +x "$HOME/Library/Application Support/Sublime Text/Package Storage/LSP-Roslyn/content/LanguageServer/osx-x64/Microsoft.CodeAnalysis.LanguageServer"

# For Linux
# chmod +x "$HOME/.config/sublime-text/Package Storage/LSP-Roslyn/content/LanguageServer/linux-x64/Microsoft.CodeAnalysis.LanguageServer"
```

### Method 4: Using Existing Installation

If you already have the Roslyn language server installed (e.g., from VSCode C# extension), you can point LSP-Roslyn to it.

#### Find Existing Installation

**VSCode Extension Path:**
- **macOS**: `~/.vscode/extensions/ms-dotnettools.csharp-*/`
- **Windows**: `%USERPROFILE%\.vscode\extensions\ms-dotnettools.csharp-*\`
- **Linux**: `~/.vscode/extensions/ms-dotnettools.csharp-*/`

Look for the `Microsoft.CodeAnalysis.LanguageServer` binary in the `.roslyn` subdirectory.

#### Configure Custom Command

Edit LSP-Roslyn settings (Preferences → Package Settings → LSP → Servers → LSP-Roslyn Settings):

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

For the neutral package with dotnet:
```json
{
    "command": [
        "dotnet",
        "/path/to/Microsoft.CodeAnalysis.LanguageServer.dll",
        "--logLevel=Information",
        "--extensionLogDirectory=/tmp/roslyn-logs",
        "--stdio"
    ]
}
```

## Verification

After installation, verify it works:

1. Open Sublime Text
2. Open any `.cs` file
3. Check the status bar at the bottom - it should show "LSP: Roslyn"
4. Try typing some C# code - you should see completions

### Troubleshooting

If the server doesn't start:

1. **Check LSP Logs**:
   - Tools → LSP → Troubleshoot Server Configuration
   - Tools → LSP → LSP: Open Language Server Logs

2. **Verify Binary Path**:
   ```bash
   # macOS/Linux
   ls -la "$HOME/Library/Application Support/Sublime Text/Package Storage/LSP-Roslyn/"

   # Windows
   dir "%APPDATA%\Sublime Text\Package Storage\LSP-Roslyn"
   ```

3. **Check Permissions** (Unix/macOS):
   ```bash
   chmod +x "<path>/Microsoft.CodeAnalysis.LanguageServer"
   ```

4. **Test Server Manually**:
   ```bash
   "/path/to/Microsoft.CodeAnalysis.LanguageServer" --version
   ```

5. **Check .NET Installation**:
   ```bash
   dotnet --version
   # Should be 8.0 or higher
   ```

## Updating the Server

To update to a newer version:

### Using dotnet tool:
```bash
dotnet tool update \
    --tool-path "<Package Storage Path>/LSP-Roslyn" \
    Microsoft.CodeAnalysis.LanguageServer
```

### Manual update:
1. Delete the old installation directory
2. Follow the installation steps again with the new version

## Version Compatibility

| Roslyn Server Version | .NET SDK Required | C# Language Version |
|-----------------------|-------------------|---------------------|
| 4.14.0-3.24630.3     | .NET 8.0+         | C# 12               |
| 4.13.0-*             | .NET 8.0+         | C# 12               |
| 4.12.0-*             | .NET 8.0+         | C# 12               |

For the latest version information, check:
- https://github.com/dotnet/roslyn/blob/main/docs/wiki/NuGet-packages.md

## Additional Resources

- **Roslyn Repository**: https://github.com/dotnet/roslyn
- **NuGet Package Versioning**: https://github.com/dotnet/roslyn/blob/main/docs/wiki/NuGet-packages.md
- **VSCode C# Extension**: https://github.com/dotnet/vscode-csharp
- **LSP Package Documentation**: https://lsp.sublimetext.io/

## Getting Help

If you encounter issues:

1. Check the [Troubleshooting section](#troubleshooting) above
2. Review LSP logs in Sublime Text
3. Open an issue on GitHub: https://github.com/yourusername/LSP-Roslyn/issues
4. Include:
   - Sublime Text version
   - .NET SDK version
   - Installation method used
   - Error messages from LSP logs
