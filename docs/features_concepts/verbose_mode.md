# Verbose Mode Feature

## Übersicht

Der Verbose Mode zeigt alle Tool-Aufrufe detailliert an, sodass der User sieht, was bassi im Hintergrund macht.

## Features

### 1. Command "/" - Befehls-Liste anzeigen
Wenn der User nur "/" tippt, werden alle verfügbaren Befehle angezeigt:
- `/` - Zeige diese Befehlsliste
- `/help` - Detaillierte Hilfe mit Beispielen
- `/config` - Konfiguration anzeigen
- `/alles_anzeigen` - Verbose Mode ein/aus
- `/reset` - Konversation zurücksetzen
- `/quit` - bassi beenden

### 2. Command "/alles_anzeigen" - Verbose Mode Toggle
Ein Befehl zum Ein-/Ausschalten des Verbose Mode:
- Toggle zwischen AN und AUS
- Zeigt Status nach Toggle: "✅ Verbose Modus AN" oder "Verbose Modus AUS"
- Persistent während der Session

### 3. Verbose Output für Tools
Wenn Verbose Mode aktiv ist, zeigt bassi:

#### Bash Kommandos
Zeigt in einem grünen Panel:
- Exit Code
- Success Status
- STDOUT (gelb)
- STDERR (rot)

#### File Search
Zeigt in einem grünen Panel:
- Anzahl gefundene Dateien
- Liste der Matches (max 20)
- Ob limitiert wurde

#### Andere Tools
Zeigt Input und Output als JSON in Syntax-highlighted Panels.

## Implementierung

### Agent (bassi/agent.py)
- `self.verbose` Flag (bool)
- `toggle_verbose()` → bool
- `set_verbose(value: bool)` → None
- `_show_tool_input()` - Zeigt Tool-Input
- `_show_tool_output()` - Zeigt Tool-Output
- `_show_bash_output()` - Speziell für Bash
- `_show_file_search_output()` - Speziell für File Search

### Main (bassi/main.py)
- `print_commands()` - Zeigt alle Commands
- Command Handler für "/"
- Command Handler für "/alles_anzeigen"

## Verwendung

```bash
# Starte bassi
uv run bassi

# Zeige alle Commands
> /

# Aktiviere Verbose Mode
> /alles_anzeigen
✅ Verbose Modus AN - Zeige alle Tool-Aufrufe

# Jetzt werden alle Tool-Aufrufe angezeigt
> find all python files
🔧 Tool: file_search
{
  "pattern": "python",
  "search_content": false
}

📁 File Search Result
Found: 15 files
Matches:
  • /path/to/file1.py
  • /path/to/file2.py
  ...

# Deaktiviere Verbose Mode
> /alles_anzeigen
Verbose Modus AUS
```

## Tests

Tests in `tests/test_verbose.py`:
- `test_verbose_toggle()` - Toggle funktioniert
- `test_set_verbose()` - Direkt setzen
- `test_verbose_mode_exists()` - Attribute existieren

## Zukunft

Mögliche Erweiterungen:
- Verbose Level (1, 2, 3) statt nur ein/aus
- Log-File für Verbose Output
- Farbschema anpassbar
- Timestamp bei jedem Tool-Aufruf
