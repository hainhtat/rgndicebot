import sys

filename = 'game/game_logic.py'

with open(filename, 'r') as f:
    lines = f.readlines()

# Indent lines 198 to 391 (1-indexed, so indices 197 to 390)
for i in range(197, 391):
    if i < len(lines):
        lines[i] = '    ' + lines[i]

with open(filename, 'w') as f:
    f.writelines(lines)
print('Indentation fixed.')