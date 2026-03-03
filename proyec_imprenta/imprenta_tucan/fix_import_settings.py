filepath = r"usuarios/views.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

old = "from settings_custom import MESSAGES, USER_STATES\n"
new = ""

if old in content:
    content = content.replace(old, new)
    print("Import eliminado OK")
else:
    print("ERROR: linea no encontrada")

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)
