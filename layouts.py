def build_layout(name):
    """
    Builds a layout configuration dictionary.
    Different cytoscape layout support different parameters and this function applies some defaults for each.

    Parameters
    ----------
    name : str
        This string contains the name of the selected layout.

    Returns
    -------
    dict
        Dictionary of layout configurations.
    """

    layout = {'name': name,'fit': True,'padding': 30,}
        
    if name == 'concentric':
        layout.update({'minNodeSpacing': 30})

    elif name == 'grid':
        layout.update({'avoidOverlap': True})

    elif name == 'circle':
        layout.update({'avoidOverlap': True})

    elif name == 'cose':
        layout.update({'randomize': False})

    elif name == 'cose-bilkent':
        layout.update({
            'randomize': False,
            'idealEdgeLength': 240,
            'edgeElasticity': 0.45,
            'nodeRepulsion': 12000,
            'nestingFactor': 0.1,
            'gravity': 0.25,
            'numIter': 2500,
            'tile': True,
            'tilingPaddingVertical': 20,
            'tilingPaddingHorizontal': 20,
            'gravityRange': 3.8,
            'gravityCompound': 1.0,
            'gravityRangeCompound': 3.0,
            'animate': False,
        })
        
    elif name == 'dagre':
        layout.update({
            'rankDir': 'LR',          # LR (left→right) or TB (top→bottom)
            'rankSep': 180,           # separation between ranks (rows and columns)
            'nodeSep': 60,            # separation within a rank
            'edgeSep': 20,
            'ranker': 'network-simplex',
            'animate': False,
        })

    elif name == 'klay':
        layout.update({
            'animate': False,
            'klay': {
                'direction': 'RIGHT',        # RIGHT, DOWN, LEFT, UP
                'nodePlacement': 'LINEAR_SEGMENTS',
                'edgeRouting': 'ORTHOGONAL', 
                'spacing': 60,               
                'borderSpacing': 20,
                'crossingMinimization': 'LAYER_SWEEP',
            }
        })

    return layout