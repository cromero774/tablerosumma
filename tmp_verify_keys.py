import sqlite3

conn = sqlite3.connect('data/tablero_completo.db')
cursor = conn.cursor()

# Verificar las claves específicas
keys_to_check = ['TAL-3748', 'TAL-3757', 'TAL-3769', 'TAL-3102', 'TAL-2788']

for key in keys_to_check:
    # Buscar la issue
    cursor.execute("""
        SELECT key, issuetype, story_points, assignee_id, project
        FROM issues
        WHERE key = ?
    """, (key,))
    row = cursor.fetchone()
    
    if row:
        print(f"\n{key}:")
        print(f"  Type: {row[1]}")
        print(f"  Points: {row[2]}")
        print(f"  Assignee: {row[3]}")
        print(f"  Project: {row[4]}")
        
        # Buscar transiciones de testing
        cursor.execute("""
            SELECT to_status, transition_date
            FROM issue_transitions
            WHERE issue_key = ? AND is_testing = 1
            ORDER BY transition_date ASC
        """, (key,))
        transitions = cursor.fetchall()
        
        if transitions:
            print(f"  Transiciones a testing: {len(transitions)}")
            for trans in transitions:
                print(f"    {trans}")
        else:
            print(f"  ⚠️ NO tiene transiciones a testing")
    else:
        print(f"\n{key}: NO encontrada en la base de datos")

conn.close()




