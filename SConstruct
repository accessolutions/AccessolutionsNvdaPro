"""Construction reproductible de l’extension Accessolutions NVDA Pro.

Le script ne dépend pas des outils internes du dépôt NVDA : il compile les
catalogues PO en catalogues MO, puis crée directement le paquet NVDA avec les
fichiers sources et les traductions compilées.
"""

import ast
import hashlib
import json
import os
import re
import struct
import zipfile
from pathlib import Path

from SCons.Script import ARGUMENTS, Action, Alias, Default, Dir, Environment

import buildVars


ROOT = Path(Dir("#").abspath)
BUILD_DIR = ROOT / "build"
PACKAGE_DIR = ROOT / "package"
MANIFEST_PATH = ROOT / "manifest.ini"
VERSION_PATTERN = re.compile(r"^[0-9]{4}(?:\.[0-9]+){2,5}$")


def _read_manifest_value(key):
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    match = re.search(rf"^\s*{re.escape(key)}\s*=\s*(.*?)\s*$", text, re.MULTILINE)
    if not match:
        raise ValueError(f"La clé {key!r} est absente de manifest.ini")
    return match.group(1).strip().strip("\"'")


VERSION = ARGUMENTS.get("version", _read_manifest_value("version"))
if not VERSION_PATTERN.fullmatch(VERSION):
    raise ValueError(
        "La version doit respecter le format YYYY.N.N (ou YYYY.N.N.N...)."
    )


def _expand_python_sources():
    files = []
    for pattern in buildVars.python_sources:
        files.extend(Path(ROOT).glob(pattern))
    return sorted({path for path in files if path.is_file()})


def _expand_package_sources():
    files = []
    for directory in buildVars.source_directories:
        directory_path = ROOT / directory
        if directory_path.is_dir():
            files.extend(path for path in directory_path.rglob("*") if _is_packagable(path))
    return sorted(set(files))


def _po_files():
    locale_root = ROOT / "locale"
    if not locale_root.is_dir():
        return []
    return sorted(locale_root.glob("*/LC_MESSAGES/nvda.po"))


def _node_path(node):
    return Path(node.abspath)


def _write_manifest(target, source, env):
    del env
    target_path = _node_path(target[0])
    source_path = _node_path(source[0])
    text = source_path.read_text(encoding="utf-8")
    text, replacements = re.subn(
        r"(?m)^\s*version\s*=\s*.*$",
        f"version = {VERSION}",
        text,
        count=1,
    )
    if replacements != 1:
        raise ValueError("La version est absente de manifest.ini")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(text, encoding="utf-8", newline="")


def _po_string(value):
    return json.dumps(value, ensure_ascii=False)


def _parse_po(path):
    """Lit les entrées PO nécessaires à la génération d’un fichier MO."""
    entries = []
    current = {}
    active_field = None
    fuzzy = False

    def flush():
        nonlocal current, active_field, fuzzy
        msgid = current.get("msgid", "")
        msgstr = current.get("msgstr", "")
        if msgstr and not fuzzy:
            entries.append((msgid, msgstr))
        current = {}
        active_field = None
        fuzzy = False

    field_pattern = re.compile(r"^(msgid|msgstr(?:\[\d+\])?)\s+(.*)$")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            flush()
            continue
        if line.startswith("#, ") or line.startswith("#,"):
            fuzzy = fuzzy or "fuzzy" in line[2:].split(",")
            continue
        if line.startswith("#"):
            continue
        match = field_pattern.match(line)
        if match:
            field = match.group(1)
            if field != "msgstr":
                # Les catalogues de cette extension n’utilisent pas les pluriels.
                if field != "msgid":
                    active_field = None
                    continue
            active_field = field
            current[field] = ast.literal_eval(match.group(2))
            continue
        if line.startswith('"') and active_field:
            current[active_field] += ast.literal_eval(line)
            continue
        raise ValueError(f"Ligne PO invalide dans {path}: {raw_line}")
    flush()
    return entries


def _compile_po(target, source, env):
    del env
    source_path = _node_path(source[0])
    target_path = _node_path(target[0])
    messages = {}
    for msgid, msgstr in _parse_po(source_path):
        previous = messages.setdefault(msgid, msgstr)
        if previous != msgstr:
            raise ValueError(f"Traduction contradictoire pour {msgid!r} dans {source_path}")

    ordered = sorted(messages.items())
    original_table = []
    translated_table = []
    payload = bytearray()
    string_offset = 28 + (16 * len(ordered))

    for msgid, _ in ordered:
        encoded = msgid.encode("utf-8")
        original_table.append((len(encoded), string_offset + len(payload)))
        payload.extend(encoded)
        payload.append(0)
    for _, msgstr in ordered:
        encoded = msgstr.encode("utf-8")
        translated_table.append((len(encoded), string_offset + len(payload)))
        payload.extend(encoded)
        payload.append(0)

    data = bytearray(
        struct.pack(
            "<7I",
            0x950412DE,
            0,
            len(ordered),
            28,
            28 + (8 * len(ordered)),
            0,
            0,
        )
    )
    for length, offset in original_table + translated_table:
        data.extend(struct.pack("<2I", length, offset))
    data.extend(payload)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(data)


def _extract_pot(target, source, env):
    del env
    messages = set()
    for source_node in source:
        source_path = _node_path(source_node)
        if source_path.suffix != ".py":
            continue
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id != "_" or not node.args:
                continue
            argument = node.args[0]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                messages.add(argument.value)

    lines = [
        "# Catalogue généré par SCons; ne pas modifier directement.",
        "",
        'msgid ""',
        'msgstr ""',
        '"Project-Id-Version: Accessolutions NVDA Pro\\n"',
        '"Content-Type: text/plain; charset=UTF-8\\n"',
        "",
    ]
    for message in sorted(messages):
        lines.extend([f"msgid {_po_string(message)}", 'msgstr ""', ""])
    target_path = _node_path(target[0])
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _is_packagable(path):
    if any(part in buildVars.excluded_directories for part in path.parts):
        return False
    return path.suffix not in buildVars.excluded_suffixes and path.is_file()


def _package(target, source, env):
    del env
    addon_path = _node_path(target[0])
    checksum_path = _node_path(target[1])
    manifest_source = _node_path(source[0])
    compiled_locales = {
        _node_path(node)
        for node in source[1:]
        if _node_path(node).suffix == ".mo"
    }

    addon_path.parent.mkdir(parents=True, exist_ok=True)
    if addon_path.exists():
        addon_path.unlink()
    with zipfile.ZipFile(addon_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(manifest_source, "manifest.ini")
        for directory in buildVars.source_directories:
            directory_path = ROOT / directory
            if not directory_path.is_dir():
                continue
            for path in sorted(directory_path.rglob("*")):
                if _is_packagable(path):
                    archive.write(path, path.relative_to(ROOT).as_posix())
        for locale_path in sorted(compiled_locales):
            relative = locale_path.relative_to(BUILD_DIR).as_posix()
            archive.write(locale_path, relative)

    digest = hashlib.sha256(addon_path.read_bytes()).hexdigest()
    checksum_path.write_text(f"{digest}  {addon_path.name}\n", encoding="ascii", newline="\n")
    print(f"Built {addon_path.name}")


# The custom actions keep the build usable on Windows without requiring the
# NVDA source tree or its SCons site tools to be installed.
env = Environment(ENV=os.environ)
manifest_target = env.Command(
    str(BUILD_DIR / "manifest.ini"),
    str(MANIFEST_PATH),
    Action(_write_manifest, "Generating manifest.ini"),
)

python_source_paths = _expand_python_sources()
python_source_nodes = [env.File(str(path)) for path in python_source_paths]
package_source_paths = _expand_package_sources()
package_source_nodes = [env.File(str(path)) for path in package_source_paths]
po_nodes = [env.File(str(path)) for path in _po_files()]
mo_targets = []
for po_node in po_nodes:
    po_path = Path(str(po_node))
    language = po_path.parent.parent.name
    mo_path = BUILD_DIR / "locale" / language / "LC_MESSAGES" / "nvda.mo"
    mo_targets.append(
        env.Command(
            str(mo_path),
            po_node,
            Action(_compile_po, f"Compiling {language} translation"),
        )
    )

package_name = f"{buildVars.addon_name}-{VERSION}.nvda-addon"
addon_target = PACKAGE_DIR / package_name
checksum_target = PACKAGE_DIR / f"{package_name}.sha256"
package_dependencies = [
    manifest_target,
    *mo_targets,
    *package_source_nodes,
    env.File("buildVars.py"),
]
package_command = env.Command(
    [str(addon_target), str(checksum_target)],
    package_dependencies,
    Action(_package, "Creating NVDA add-on package"),
)

pot_target = env.Command(
    str(BUILD_DIR / f"{buildVars.addon_name}.pot"),
    [*python_source_nodes, env.File("buildVars.py")],
    Action(_extract_pot, "Extracting translation messages"),
)

Alias("package", package_command)
Alias("pot", pot_target)
Default(package_command)
env.Clean(package_command, [str(BUILD_DIR), str(PACKAGE_DIR)])
