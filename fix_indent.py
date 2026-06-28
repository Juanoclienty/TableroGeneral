with open(r'C:\Users\rjuan\dashboard\pages\4_Trazabilidad.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    lineno = i + 1  # 1-indexed

    if 1344 <= lineno <= 1776:
        stripped = lines[i].rstrip('\n')
        if stripped.startswith('    '):
            stripped = stripped[4:]
        new_lines.append(stripped + '\n')
        i += 1

    elif lineno == 1778:
        # Replace lines 1778-1782 with properly structured tab_sol/tab_fer blocks
        new_lines.append('    tab_sol, tab_fer = st.tabs(["Perfo Sol", "Perfo Fer"])\n')
        new_lines.append('    with tab_sol:\n')
        new_lines.append('        try:\n')
        new_lines.append('            _df_sol = _cargar_bbdd_sol()\n')
        new_lines.append('            _render_perfo_cc(_df_sol, "Sol")\n')
        new_lines.append('        except Exception as _e_sol:\n')
        new_lines.append('            st.error(f"Error cargando datos de Sol: {_e_sol}")\n')
        i += 1  # skip line 1778

    elif 1779 <= lineno <= 1782:
        i += 1  # skip (replaced above)

    elif lineno == 1784:
        i += 1  # skip duplicate _ID_FER

    else:
        new_lines.append(lines[i])
        i += 1

with open(r'C:\Users\rjuan\dashboard\pages\4_Trazabilidad.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Done. Total lines:", len(new_lines))
