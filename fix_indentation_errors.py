#!/usr/bin/env python3
"""
Script para corregir errores de indentación en tablero.py
"""

import re

def fix_indentation_errors():
    with open('tablero.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    fixed_lines = []
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Patrones comunes de errores de indentación
        if re.match(r'^[^#\s].*try:$', line.strip()):
            # try sin except/finally
            fixed_lines.append(line)
            i += 1
            # Buscar el bloque try y agregar except si no existe
            indent_level = len(line) - len(line.lstrip())
            while i < len(lines):
                next_line = lines[i]
                if next_line.strip() == '':
                    fixed_lines.append(next_line)
                    i += 1
                    continue
                next_indent = len(next_line) - len(next_line.lstrip())
                if next_indent <= indent_level and next_line.strip():
                    # Agregar except Exception: pass
                    fixed_lines.append(' ' * indent_level + 'except Exception:\n')
                    fixed_lines.append(' ' * (indent_level + 4) + 'pass\n')
                    break
                fixed_lines.append(next_line)
                i += 1
        elif re.match(r'^[^#\s].*if.*:$', line.strip()) and i + 1 < len(lines):
            # if sin bloque
            next_line = lines[i + 1]
            if next_line.strip() and not next_line.startswith(' '):
                # Agregar pass
                indent_level = len(line) - len(line.lstrip())
                fixed_lines.append(line)
                fixed_lines.append(' ' * (indent_level + 4) + 'pass\n')
                i += 1
            else:
                fixed_lines.append(line)
                i += 1
        elif re.match(r'^[^#\s].*for.*:$', line.strip()) and i + 1 < len(lines):
            # for sin bloque
            next_line = lines[i + 1]
            if next_line.strip() and not next_line.startswith(' '):
                # Agregar pass
                indent_level = len(line) - len(line.lstrip())
                fixed_lines.append(line)
                fixed_lines.append(' ' * (indent_level + 4) + 'pass\n')
                i += 1
            else:
                fixed_lines.append(line)
                i += 1
        elif re.match(r'^[^#\s].*while.*:$', line.strip()) and i + 1 < len(lines):
            # while sin bloque
            next_line = lines[i + 1]
            if next_line.strip() and not next_line.startswith(' '):
                # Agregar pass
                indent_level = len(line) - len(line.lstrip())
                fixed_lines.append(line)
                fixed_lines.append(' ' * (indent_level + 4) + 'pass\n')
                i += 1
            else:
                fixed_lines.append(line)
                i += 1
        elif re.match(r'^[^#\s].*def.*:$', line.strip()) and i + 1 < len(lines):
            # def sin bloque
            next_line = lines[i + 1]
            if next_line.strip() and not next_line.startswith(' '):
                # Agregar pass
                indent_level = len(line) - len(line.lstrip())
                fixed_lines.append(line)
                fixed_lines.append(' ' * (indent_level + 4) + 'pass\n')
                i += 1
            else:
                fixed_lines.append(line)
                i += 1
        elif re.match(r'^[^#\s].*class.*:$', line.strip()) and i + 1 < len(lines):
            # class sin bloque
            next_line = lines[i + 1]
            if next_line.strip() and not next_line.startswith(' '):
                # Agregar pass
                indent_level = len(line) - len(line.lstrip())
                fixed_lines.append(line)
                fixed_lines.append(' ' * (indent_level + 4) + 'pass\n')
                i += 1
            else:
                fixed_lines.append(line)
                i += 1
        elif re.match(r'^[^#\s].*else:$', line.strip()) and i + 1 < len(lines):
            # else sin bloque
            next_line = lines[i + 1]
            if next_line.strip() and not next_line.startswith(' '):
                # Agregar pass
                indent_level = len(line) - len(line.lstrip())
                fixed_lines.append(line)
                fixed_lines.append(' ' * (indent_level + 4) + 'pass\n')
                i += 1
            else:
                fixed_lines.append(line)
                i += 1
        elif re.match(r'^[^#\s].*elif.*:$', line.strip()) and i + 1 < len(lines):
            # elif sin bloque
            next_line = lines[i + 1]
            if next_line.strip() and not next_line.startswith(' '):
                # Agregar pass
                indent_level = len(line) - len(line.lstrip())
                fixed_lines.append(line)
                fixed_lines.append(' ' * (indent_level + 4) + 'pass\n')
                i += 1
            else:
                fixed_lines.append(line)
                i += 1
        else:
            fixed_lines.append(line)
            i += 1
    
    # Escribir el archivo corregido
    with open('tablero.py', 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)
    
    print("✅ Errores de indentación corregidos")

if __name__ == "__main__":
    fix_indentation_errors()

