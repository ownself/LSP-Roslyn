# LSP-Roslyn (For Sublime Text)

中文 | [English](README.md)

这是一个用于Sublime Text的C# LSP插件，不同于LSP-OmniSharp，LSP-Roslyn直接使用了微软的Roslyn作为后端，即当前Visual Studio Code C#扩展和C# Dev Kit所使用的相同后端

对比OmniSharp方案，具有更现代的功能设计和性能表现

## 配置需求

- Sublime Text 4 (Build 4107 or later)
	- Build 4107 : 20 May 2021
- **[LSP](https://packagecontrol.io/packages/LSP)** Package Installed via Package Control
- **[.NET SDK 8.0 or higher](https://dotnet.microsoft.com/download)** installed

## 插件安装方法

### 1. 通过Package Control (Coming Soon)

1. 首先需要确保Sublime Text已安装了LSP插件
2. 通过Package Control安装LSP-Rosly插件

### 2. 手动安装

将插件工程克隆到Sublime Text的Packages目录下：

```bash
# macOS
cd "~/Library/Application Support/Sublime Text/Packages"
# Windows (PowerShell)
cd "$env:APPDATA\Sublime Text\Packages"
# Linux
cd "~/.config/sublime-text/Packages"
# Install by git
git clone https://github.com/ownself/LSP-Roslyn.git
```

# Roslyn安装方法

### 1. 自动下载

正常情况下，当你使用Sublime Text打开.cs文件时，会自动搜索定位.sln, .csproj文件并启用LSP-Roslyn

首次启用的时候，插件会根据用户所使用的操作系统尝试自动下载对应的Roslyn的可执行程序，并解压在插件目录下

因此，只需要稍等片刻，完成下载后会自动解压并启动Roslyn，并使得Sublime Text的C#的LSP功能自动开始生效

当前自动下载的Roslyn版本号：

- Pre-Release : 5.3.0-1.25517.107

自动下载所支持的系统平台：

- win-x86
- win-x64
- win-arm64
- osx-x64
- osx-arm64
- linux-x64
- linux-arm64

### 2. 手动下载

如果自动下载未能生效，或者所使用的平台未在插件默认支持的列表中，可能需要用户自行下载Roslyn后，并解压缩至Sublime Text的Packages下插件所在的目录中的Microsoft.CodeAnalysis.LanguageServer目录下

关于下载Roslyn的可执行文件的更多信息，请查阅[roslyn-packages](https://github.com/dotnet/roslyn/blob/main/docs/wiki/NuGet-packages.md)

# 配置

可以通过Command Palette中的`Preferences: LSP-Roslyn Settings`来进行设置：

```json
{
    "settings": {
        // Specify default solution if multiple .sln files exist
        "roslyn.defaultLaunchSolution": "MyProject.sln",
		// Background analysis
        "roslyn.backgroundAnalysis": {
            "dotnet_analyzer_diagnostics_scope": "openFiles",  // or "fullSolution", "none"
            "dotnet_compiler_diagnostics_scope": "openFiles"
        },
		// Inlay Hints
        "roslyn.inlayHints": {
            "csharp_enable_inlay_hints_for_implicit_variable_types": true,
            "dotnet_enable_inlay_hints_for_parameters": true
        },
		// Code Lens
	    "roslyn.codeLens": {
            "dotnet_enable_references_code_lens": true,
            "dotnet_enable_tests_code_lens": true
        },
		// better performance for large solution
		"roslyn.loadProjectsOnDemand": true,
    }
}
```

# 功能

**核心功能**

- **Code Completion** - 智能感知及自动完成建议
- **Signature Help** - 方法的参数信息
- **Hover Information** - 文档与类型信息
- **Go to Definition** - 函数定义跳转
- **Find References** - 汇列所有引用
- **Rename** - 跨工程重命名

**高级功能**

- **Code Actions** - 快速修复及重构
- **Code Lens** - 行内引用数提示
- **Inlay Hints** - 类型与参数提示
- **Diagnostics** - 实时错误与警告提示
- **Formatting** - 代码自动格式化
- **Symbol Search** - 工程范围内函数定义搜索
- **Source Generators** - 源文件生成支持

**Roslyn分析器**

- **Built-in Analyzers** - 代码质量及风格分析
- **Custom Analyzers** - 支持第三方分析器
- **EditorConfig** - 支持.editorconfig设定

# 命令

Command Palette中支持的命令：

- **LSP-Roslyn: Restart Server** - 重启LSP-Roslyn
- **LSP-Roslyn: Select Solution** - 切换工程
- **Preferences: LSP-Roslyn Settings** - 打开LSP-Roslyn配置

# License

MIT License. 更多请查看详情[LICENSE](LICENSE)

# 鸣谢

从Sublime Text2开始我就非常喜爱这款简洁典雅、性能卓越的代码编辑器，甚至有3、4年的时间它还是我在工作中的主力编辑器，虽然现在我日常工作中已经替换为了Neovim和Rider等更现代的编辑器，但是当处理一些Json或者文本类的数据时，Sublime Text依然是我的好帮手，能够为这个社区做一些贡献，一直是我的心愿

插件编写灵感来源于[LSP-OmniSharp](https://github.com/sublimelsp/LSP-OmniSharp)

我编写的另一个款Sublime Text的插件：[CursorWordHighlighter](https://github.com/ownself/CursorWordHighlighter)
