# LSP-Roslyn Quick Start Guide

Get up and running with LSP-Roslyn in 5 minutes.

## Prerequisites Check

Before starting, verify you have:

```bash
# Check Sublime Text version (should be 4075+)
# Help → About Sublime Text

# Check .NET SDK (should be 8.0+)
dotnet --version

# Check if LSP package is installed
# Tools → Command Palette → "Package Control: List Packages"
# Look for "LSP" in the list
```

If any are missing, install them first:
- Sublime Text 4: https://www.sublimetext.com/download
- .NET SDK: https://dotnet.microsoft.com/download
- LSP Package: Package Control → Install Package → "LSP"

## Quick Install

### 1. Install the Plugin

```bash
# Choose your platform:

# macOS
cd ~/Library/Application\ Support/Sublime\ Text/Packages
git clone https://github.com/yourusername/LSP-Roslyn.git

# Windows (PowerShell)
cd $env:APPDATA\Sublime Text\Packages
git clone https://github.com/yourusername/LSP-Roslyn.git

# Linux
cd ~/.config/sublime-text/Packages
git clone https://github.com/yourusername/LSP-Roslyn.git
```

### 2. Install Roslyn Server (Choose One Method)

**Easiest: Using dotnet tool**

```bash
# Get the install path first:
# macOS: ~/Library/Application Support/Sublime Text/Package Storage/LSP-Roslyn
# Windows: %APPDATA%\Sublime Text\Package Storage\LSP-Roslyn
# Linux: ~/.config/sublime-text/Package Storage/LSP-Roslyn

# Then run:
dotnet tool install --tool-path "<your-path-here>" Microsoft.CodeAnalysis.LanguageServer
```

**Alternative: Using the script**

```bash
# Unix/macOS
cd LSP-Roslyn
./install_roslyn.sh

# Windows
cd LSP-Roslyn
.\install_roslyn.ps1
```

### 3. Test It

1. Restart Sublime Text
2. Open any `.cs` file (or create a new one with C# syntax)
3. Start typing - you should see completions!
4. Check status bar - should show "LSP: Roslyn"

## Example Test File

Create a file `test.cs`:

```csharp
using System;

namespace HelloWorld
{
    class Program
    {
        static void Main(string[] args)
        {
            Console.WriteLine("Hello, World!");
            // Try typing: Console. (you should see completions)
        }
    }
}
```

If you see completions when typing `Console.`, it's working! 🎉

## Troubleshooting

### Server Not Starting?

1. **Check LSP logs**:
   - Tools → LSP → Troubleshoot Server Configuration

2. **Verify installation**:
   ```bash
   # Check if binary exists
   ls "$HOME/Library/Application Support/Sublime Text/Package Storage/LSP-Roslyn/"
   ```

3. **Check permissions** (Unix/macOS):
   ```bash
   chmod +x "$HOME/Library/Application Support/Sublime Text/Package Storage/LSP-Roslyn/Microsoft.CodeAnalysis.LanguageServer"
   ```

### No Completions?

1. Make sure you have a `.csproj` or `.sln` file in your workspace
2. Wait a few seconds for the server to initialize
3. Check status bar shows "LSP: Roslyn" (not "LSP: idle")

### "dotnet not found"?

Make sure .NET SDK is in your PATH:
```bash
# Test
dotnet --version

# If not found, add to PATH:
# Windows: Add to System Environment Variables
# macOS/Linux: Add to ~/.bashrc or ~/.zshrc
export PATH="$PATH:/usr/local/share/dotnet"
```

## Next Steps

Now that it's working, explore these features:

1. **Go to Definition**: Right-click → "LSP: Goto Definition" or `F12`
2. **Find References**: Right-click → "LSP: Find References"
3. **Rename Symbol**: Right-click → "LSP: Rename"
4. **Code Actions**: Click the lightbulb icon or use the command palette
5. **Format Document**: Right-click → "LSP: Format Document"

## Customize Settings

Open settings: Command Palette → "Preferences: LSP-Roslyn Settings"

Popular settings to enable:

```json
{
    "settings": {
        "roslyn.inlayHints": {
            "csharp_enable_inlay_hints_for_implicit_variable_types": true,
            "dotnet_enable_inlay_hints_for_parameters": true
        },
        "roslyn.codeLens": {
            "dotnet_enable_references_code_lens": true
        }
    }
}
```

## Need More Help?

- **Full Documentation**: See [README.md](README.md)
- **Detailed Installation**: See [INSTALLATION.md](INSTALLATION.md)
- **Report Issues**: https://github.com/yourusername/LSP-Roslyn/issues

Happy coding with C# in Sublime Text! 🚀
