"""
This module handles all interaction with the uploaded csv, which includes building a coin graph based on csv.
"""

import csv
import networkx as nx
import io
import unicodedata
import re

from proxy import proxify


def normalize_key(key):
    """
    function normalizes a string.

    Parameters
    ----------
    key : str
        input string to normalize, which may contain accents, umlauts, spaces..

    Returns
    -------
    str
        An ASCII-only, lowercase identifier using underscores. or 'col' if normalization steps resulted in empty string
    """

    if key is None:
        return ""
    key = str(key).strip()
    key = (key.replace("ä","ae").replace("ö","oe").replace("ü","ue")
           .replace("Ä","Ae").replace("Ö","Oe").replace("Ü","Ue")
           .replace("ß","ss"))
    # strip diacritics, for other languages
    key = unicodedata.normalize("NFKD", key)
    key = "".join(ch for ch in key if not unicodedata.combining(ch))
    # keep alnum only, collapse to underscores
    key = re.sub(r"[^a-zA-Z0-9]+", "_", key)
    # collapse multiple underscores from ends
    key = re.sub(r"_+", "_", key).strip("_")
    return key or "col"   # fallback if string becomes empty


def _unique_key_map(fieldnames):
    """
    Map raw headers to unique safe keys.

    Parameters
    ----------
    fieldnames : list of str
        contains raw header names.

    Returns
    -------
    dict of str to str
        Mapping from original header names, ASCII-only keys. Also adds suffixes when normalization resulted in duplicates.
    """

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
    Load a graph from CSV. Each row with it's columns becomes a node with attributes.
    Column headers are normalized to safe keys and stored in G.graph['key_map'].

    Parameters
    ----------
    csv_path_or_buffer : str or bytes
        Path to csv file or bytes object containing the csv data.
    node_id_col : str or None
        name of id column, ir not specified just assumes id column is the first column

    Returns
    -------
    networkX.Graph
        Graph containing all converter rows to nodes. This graph does not have edges yet. 
        Also graph attributes have the mapping from raw to safe keys and vice versa.
    """

    G = nx.Graph()

    # Open file or buffer
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


def is_url(potential_url):
    """
    Function checks if string looks like url.

    Parameters
    ----------
    potential_url : str
        String that needs be checked.

    Returns
    -------
    bool
        True if string looks like url or data URI. False otherwise.
    """

    return bool(re.match(r'^[a-zA-Z][a-zA-Z0-9+.\-]*://', potential_url)) or potential_url.startswith("data:")


def norm_path(path):
    """
    Function normalizes file path string, by converting backslashes to forward and remove leading dots and slashes.

    Parameters
    ----------
    path : str
        String that contains a file path.

    Returns
    -------
    str
        String that contains the normalized file path.
    """

    return path.replace("\\", "/").lstrip("./")


def bg_url_from_csv_value(raw_val):
    """
    Converts a csv value into a usuable url for background-image in a cytoscape instance.
    If it's a url it will route through a proxy, else it should be a relative path in assets folder.

    Parameters
    ----------
    raw_val : str
        Raw value from a csv cell. Should be a url, relative file path or empty.

    Returns
    -------
    str
        A proxy route if raw_val was url, modified relative path if it was a relative path or None if it was empty string.
    """
    
    if not raw_val:
        return None
    path = str(raw_val).strip()
    if not path:
        return None
    if is_url(path):
        return proxify(path)               # external URL through Proxy
    return "/assets/" + norm_path(path)    # relative paths in assets