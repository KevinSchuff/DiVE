import csv
import networkx as nx
import io
import unicodedata
import re

def normalize_key(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    # transliteration first, preserves german specific umlauts
    s = (s.replace("ä","ae").replace("ö","oe").replace("ü","ue")
           .replace("Ä","Ae").replace("Ö","Oe").replace("Ü","Ue")
           .replace("ß","ss"))
    # strip diacritics, for other languages
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    # keep alnum only, collapse to underscores
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "col"

def _unique_key_map(fieldnames):
    """Map raw headers -> unique safe keys."""
    key_map = {}
    seen = {}
    for name in fieldnames or []:
        base = normalize_key(name)
        safe = base
        i = 2
        while safe in seen:
            safe = f"{base}_{i}"
            i += 1
        key_map[name] = safe
        seen[safe] = True
    return key_map

def load_graph_from_csv(csv_path_or_buffer, node_id_col=None):
    """
    Load a graph from CSV. Each row becomes a node with attributes from columns.
    Column headers are normalized to safe keys (stored in G.graph['key_map']).
    """
    G = nx.Graph()

    # Open file or buffer (keep your latin-1 choice)
    if isinstance(csv_path_or_buffer, str):
        csvfile = open(csv_path_or_buffer, newline='', encoding='latin-1')
    else:
        csvfile = io.StringIO(csv_path_or_buffer.decode('latin-1'))

    reader = csv.DictReader(csvfile)
    fieldnames = reader.fieldnames or []
    key_map = _unique_key_map(fieldnames)                       # raw -> safe
    inv_map = {v: k for k, v in key_map.items()}                # safe -> raw

    # Work out which column is the node id (accept raw or safe)
    if node_id_col is None and fieldnames:
        node_raw = fieldnames[0]
    else:
        node_raw = node_id_col if node_id_col in fieldnames else inv_map.get(node_id_col, node_id_col)
    node_safe = key_map.get(node_raw, normalize_key(node_raw or "id"))

    for idx, row in enumerate(reader, start=1):
        # Build a safe-keyed row
        safe_row = { key_map.get(k, normalize_key(k)): v for k, v in row.items() }
        # Node id: prefer original raw key value if present, else safe
        node_id = row.get(node_raw) or safe_row.get(node_safe) or str(idx)
        G.add_node(str(node_id), **safe_row)

    csvfile.close()

    # Stash mappings for the UI
    G.graph['key_map'] = key_map
    G.graph['inv_key_map'] = inv_map
    return G
