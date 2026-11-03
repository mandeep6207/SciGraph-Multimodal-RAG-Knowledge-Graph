import re
from pathlib import Path

path = Path("frontend/landing.html")
content = path.read_text(encoding="utf-8")

# 1. Update font link to include Space Grotesk
old_font = '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">'
new_font = '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">'
if old_font in content:
    content = content.replace(old_font, new_font)

# 2. Update :root CSS variables
old_root = """:root {
  --bg-primary: #060608;
  --bg-secondary: #0d0e14;
  --bg-card: rgba(18, 20, 29, 0.75);
  --bg-card-hover: rgba(26, 30, 44, 0.85);
  --accent-cyan: #00e5ff;
  --accent-cyan-glow: rgba(0, 229, 255, 0.25);
  --accent-purple: #8b5cf6;
  --accent-green: #10b981;
  --accent-amber: #f59e0b;
  --text-main: #f1f5f9;
  --text-muted: #94a3b8;
  --text-dim: #64748b;
  --border-color: rgba(255, 255, 255, 0.08);
  --border-cyan: rgba(0, 229, 255, 0.35);
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}"""

new_root = """:root {
  --bg-primary: #090C0A;
  --bg-secondary: #0B0F0D;
  --bg-card: rgba(16, 22, 18, 0.88);
  --bg-card-hover: rgba(21, 29, 24, 0.95);
  --accent-cyan: #B5F36B;
  --accent-cyan-glow: rgba(181, 243, 107, 0.25);
  --accent-purple: #6EAA85;
  --accent-green: #B5F36B;
  --accent-amber: #D9A65A;
  --text-main: #E9E8DF;
  --text-muted: #929B91;
  --text-dim: #687367;
  --border-color: rgba(190, 220, 190, 0.12);
  --border-cyan: rgba(181, 243, 107, 0.35);
  --font-heading: 'Space Grotesk', -apple-system, sans-serif;
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}"""
content = content.replace(old_root, new_root)

# 3. Update background gradients
content = content.replace(
    "radial-gradient(circle at 50% 0%, rgba(0, 229, 255, 0.08) 0%, transparent 60%),\n    radial-gradient(circle at 85% 30%, rgba(139, 92, 246, 0.06) 0%, transparent 50%),\n    radial-gradient(circle at 15% 70%, rgba(16, 185, 129, 0.05) 0%, transparent 50%);",
    "radial-gradient(circle at 50% 0%, rgba(181, 243, 107, 0.08) 0%, transparent 60%),\n    radial-gradient(circle at 85% 30%, rgba(110, 170, 133, 0.06) 0%, transparent 50%),\n    radial-gradient(circle at 15% 70%, rgba(181, 243, 107, 0.04) 0%, transparent 50%);"
)
content = content.replace(
    "radial-gradient(circle at 50% 0%, rgba(0, 229, 255, 0.08) 0%, transparent 60%),\r\n    radial-gradient(circle at 85% 30%, rgba(139, 92, 246, 0.06) 0%, transparent 50%),\r\n    radial-gradient(circle at 15% 70%, rgba(16, 185, 129, 0.05) 0%, transparent 50%);",
    "radial-gradient(circle at 50% 0%, rgba(181, 243, 107, 0.08) 0%, transparent 60%),\r\n    radial-gradient(circle at 85% 30%, rgba(110, 170, 133, 0.06) 0%, transparent 50%),\r\n    radial-gradient(circle at 15% 70%, rgba(181, 243, 107, 0.04) 0%, transparent 50%);"
)

# 4. Header background
content = content.replace("background: rgba(6, 6, 8, 0.8);", "background: rgba(9, 12, 10, 0.88);")

# 5. Heading typography
content = re.sub(
    r"\.hero-title\s*\{[^}]*\}",
    """.hero-title {
  font-family: var(--font-heading);
  font-size: clamp(38px, 5.2vw, 68px);
  font-weight: 700;
  line-height: 1.08;
  letter-spacing: -0.03em;
  color: #fff;
  margin-bottom: 24px;
}""",
    content
)

# 6. Button Primary styling (make it signature emerald #B5F36B with dark text)
content = re.sub(
    r"\.btn-primary\s*\{[^}]*\}",
    """.btn-primary {
  background: var(--accent-cyan);
  color: #090C0A !important;
  font-weight: 600;
  border: 1px solid var(--accent-cyan);
  box-shadow: 0 0 16px rgba(181, 243, 107, 0.35);
}
.btn-primary:hover {
  background: #c5f884;
  box-shadow: 0 0 24px rgba(181, 243, 107, 0.55);
  transform: translateY(-2px);
}""",
    content
)

# 7. Canvas colors: Replace cyan particle connection colors
content = content.replace(
    "`rgba(0, 229, 255, ${0.15 * (1 - dist / 130)})`",
    "`rgba(181, 243, 107, ${0.18 * (1 - dist / 130)})`"
)
content = content.replace(
    "`rgba(0, 229, 255, ${Math.max(0, sw.opacity)})`",
    "`rgba(181, 243, 107, ${Math.max(0, sw.opacity)})`"
)
content = content.replace(
    "'rgba(0, 229, 255, 0.35)'",
    "'rgba(181, 243, 107, 0.35)'"
)
content = content.replace(
    "ctx.fillStyle = '#00e5ff';",
    "ctx.fillStyle = '#B5F36B';"
)

path.write_text(content, encoding="utf-8")
print("Re-themed landing.html successfully to Obsidian design system.")
