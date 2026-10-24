"""Bind derived enum annotations to the exact generated declaration owner."""
from __future__ import annotations

import json
import re


def owned_projection(node, file_name: str, pointer: str):
    result = json.loads(json.dumps(node))

    def walk(value, here):
        if isinstance(value,dict):
            for key,child in list(value.items()):
                if key != 'x-arkret-value-ownership':
                    walk(child,here+'/'+key.replace('~','~0').replace('/','~1'))
            if 'enum' in value or 'const' in value:
                values=value.get('enum',[value.get('const')]);non_null=[v for v in values if v is not None]
                previous=value.get('x-arkret-value-ownership')
                owner=file_name+'#'+here
                if isinstance(previous,dict):
                    kind,authority=previous['class'],previous['authority']
                    if previous.get('authority')==previous.get('owner'):authority=owner
                elif all(isinstance(v,(bool,int,float)) for v in non_null):kind,authority='numeric',owner
                elif all(isinstance(v,str) and re.fullmatch(r'[a-z][a-z0-9]*(?:_[a-z0-9]+)*',v) for v in non_null):kind,authority='owned_symbol',owner
                elif all(isinstance(v,str) and re.fullmatch(r'ak\.[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*',v) for v in non_null):kind,authority='namespaced_symbol',owner
                elif all(isinstance(v,str) and re.fullmatch(r'0|[1-9][0-9]*',v) for v in non_null):kind,authority='decimal_text',owner
                else:raise ValueError(f'generated enum requires an explicit source authority: {owner}')
                value['x-arkret-value-ownership']={'class':kind,'authority':authority,'owner':owner,'values':values}
        elif isinstance(value,list):
            for index,child in enumerate(value):walk(child,here+'/'+str(index))
    walk(result,pointer)
    return result
