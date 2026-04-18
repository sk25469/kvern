# VS Code Development & Debugging Setup

This directory contains VS Code configuration for debugging and development workflow in the KVern project.

## 🚀 Quick Start

1. **Open the project** in VS Code
2. **Select the Python interpreter**: `Ctrl+Shift+P` → "Python: Select Interpreter" → Choose `./venv/bin/python`
3. **Start debugging**: Press `F5` or go to Run & Debug panel

## 📁 Configuration Files

### `launch.json` - Debug Configurations

| Configuration | Purpose | How to Use |
|--------------|---------|------------|
| 🚀 **Run Proxy Server** | Start the main KVern proxy | `F5` or Debug panel |
| 🧪 **Debug Current Test File** | Debug the currently opened test file | Open a test file, then `F5` |
| 🧪 **Debug All Tests** | Run all tests with debugging | Select from debug dropdown |
| 🧪 **Debug Trie Tests** | Focus on trie functionality | Select from debug dropdown |
| 🧪 **Debug Tokenizer Tests** | Focus on tokenizer functionality | Select from debug dropdown |
| 📊 **Run Dashboard** | Start Streamlit dashboard | Select from debug dropdown |
| 🔍 **Debug Python Module** | Debug any Python file | Open any `.py` file, then `F5` |
| 🧪 **Debug Specific Test** | Run a specific test by name | Enter test name when prompted |
| ⚡ **FastAPI with Auto-reload** | Development server with hot reload | Select from debug dropdown |

### `tasks.json` - Build & Run Tasks

| Task | Shortcut | Purpose |
|------|----------|---------|
| 🧪 **Run All Tests** | `Ctrl+Shift+P` → "Run Task" | Execute all test suites |
| 🧪 **Run Current Test File** | | Test only the current file |
| 🚀 **Start Proxy Server** | `Ctrl+Shift+B` | Background server process |
| 📊 **Start Dashboard** | | Background dashboard process |
| 🔧 **Install Dependencies** | | Update Python packages |
| 🧹 **Clean Cache** | | Remove `__pycache__` directories |
| 🎨 **Format Code** | | Run Black code formatter |
| 🔍 **Type Check** | | Run MyPy type checking |

### `settings.json` - Workspace Settings

Automatically configures:
- ✅ Python interpreter path
- ✅ Testing with pytest
- ✅ Code formatting with Black
- ✅ Import path resolution
- ✅ File exclusions for clean workspace

## 🐛 Debugging Workflow

### Set Breakpoints
- **Single click** in the gutter (left of line numbers)
- **Conditional breakpoints**: Right-click → "Add Conditional Breakpoint"
- **Logpoints**: Right-click → "Add Logpoint" (log without stopping)

### Debug Controls
- **F5**: Start/Continue debugging
- **F10**: Step Over (execute current line)
- **F11**: Step Into (enter function calls)
- **Shift+F11**: Step Out (exit current function)
- **Ctrl+Shift+F5**: Restart debugging
- **Shift+F5**: Stop debugging

### Debug a Specific Test
1. Open the test file
2. Set breakpoints where needed
3. Press `F5` or use "Debug Current Test File"
4. Or use "Debug Specific Test" and enter the test name like `test_lookup_on_empty_trie`

### Debug the Proxy Server
1. Set breakpoints in `src/proxy/main.py` or related files
2. Use "🚀 Run Proxy Server" configuration
3. Make HTTP requests to trigger breakpoints
4. Use tools like `curl` or Postman to send requests

## 🏃‍♂️ Running Without Debugging

### Via Command Palette (`Ctrl+Shift+P`)
- Type "Run Task" and select from available tasks
- Type "Python: Run Python File in Terminal"

### Via Integrated Terminal
```bash
# Run tests
./venv/bin/python -m pytest tests/test_trie.py -v

# Start proxy server  
./venv/bin/python run_proxy.py

# Start dashboard
./venv/bin/python -m streamlit run src/dashboard/app.py

# Format code
./venv/bin/python -m black src/ tests/ --line-length 100
```

## 🔧 Environment Setup

### Environment Variables
1. Copy `.env.example` to `.env`
2. Customize values for your setup
3. VS Code will automatically load these variables

### Python Path Issues
If imports fail, the configurations automatically set `PYTHONPATH` to the workspace root. This allows imports like:
```python
from src.trie.node import TrieNode  # ✅ Works
from src.tokenizer.pipeline import TokenizerPipeline  # ✅ Works
```

## 🔍 Testing Integration

### Discover Tests
VS Code will automatically discover tests. Look for the test tube icon in:
- **Activity Bar**: Click the test icon
- **File Explorer**: Tests are marked with special icons
- **Status Bar**: Shows test count and status

### Run Tests Via UI
1. Open Testing panel (`Ctrl+;`)
2. Click ▶️ next to individual tests or test classes
3. Click 🐛 to debug specific tests

### Test Output
- **Test Results**: Appear in the Test Results panel
- **Debug Console**: Shows detailed debugging output
- **Terminal**: Shows pytest output and logs

## 🚨 Troubleshooting

### "Module not found" Errors
- Verify Python interpreter is set to `./venv/bin/python`
- Check that `PYTHONPATH` includes the workspace folder
- Ensure all imports use `src.` prefix: `from src.trie.node import TrieNode`

### Debugger Not Stopping at Breakpoints
- Ensure "justMyCode" is set to `false` in launch.json
- Check that the code path is actually being executed
- Verify breakpoints are on executable lines (not comments or empty lines)

### Performance Issues
- Use "Debug Console" instead of print statements for better performance
- Disable unnecessary breakpoints
- Use conditional breakpoints to reduce noise

### Port Already in Use
If you see "Address already in use" errors:
```bash
# Find process using port 8080
lsof -i :8080

# Kill the process
kill -9 <PID>
```

## 🎯 Pro Tips

1. **Use Conditional Breakpoints** for loops:
   ```python
   # Right-click breakpoint → "Edit Breakpoint" → "Expression"
   i > 10  # Only break when i > 10
   ```

2. **Logpoints for Quick Debug**:
   ```python
   # Right-click → "Add Logpoint"
   token_ids: {token_ids}, depth: {depth}
   ```

3. **Debug Console Commands**:
   ```python
   # Evaluate expressions in debug console
   len(token_ids)
   manager.node_count("llama3")
   ```

4. **Watch Variables**:
   - Add variables to "Watch" panel
   - Automatically updates as you step through code

5. **Call Stack Navigation**:
   - Click different stack frames to see variables at each level
   - Useful for understanding complex async operations

## 📚 Additional Resources

- [VS Code Python Debugging](https://code.visualstudio.com/docs/python/debugging)
- [Pytest in VS Code](https://code.visualstudio.com/docs/python/testing)
- [VS Code Tasks](https://code.visualstudio.com/docs/editor/tasks)