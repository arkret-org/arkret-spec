"""Derive closed current-result values from registered cell projections."""
from pathlib import Path
import json
import sys
import re

root=Path(__file__).resolve().parents[1]/'spec/v1/artifacts'
catalog=json.loads((root/'registry/contract-registry.json').read_text(encoding='utf-8'))
payloads={r['event_kind']:r['payload_schema_ref'] for r in catalog['event_kind_registry']['event_kinds'] if 'payload_schema_ref' in r}
cache={}
def load(file):
    if file not in cache:cache[file]=json.loads((root/file).read_text(encoding='utf-8'))
    return cache[file]
def deref(ref,base=''):
    file,_,pointer=ref.partition('#')
    if file.startswith('https://arkret.org/v1/'):file=file.removeprefix('https://arkret.org/v1/')
    elif file:file=(Path(base).parent/file).as_posix() if base else file
    else:file=base
    file=str(Path(file)).replace('\\','/')
    value=load(file)
    for part in pointer.strip('/').split('/') if pointer else []:value=value[int(part)] if isinstance(value,list) else value[part.replace('~1','/').replace('~0','~')]
    return value,file,pointer
def locate(ref,parts,base=''):
    value,file,pointer=deref(ref,base)
    if not parts:return [{'ref':file+'#'+pointer}]
    def walk(value,pointer,parts):
        if '$ref' in value:
            result=locate(value['$ref'],parts,file)
            if result:return result
        if parts[0] in value.get('properties',{}):
            return locate(file+'#'+pointer+'/properties/'+parts[0],parts[1:])
        result=[]
        for key in ['oneOf','anyOf','allOf']:
            for i,branch in enumerate(value.get(key,[])):
                result+=walk(branch,pointer+'/'+key+'/'+str(i),parts)
        return result
    return walk(value,pointer,parts)
def field(kind,path):
    if path=='payload':return [{'ref':payloads[kind]}]
    return locate(payloads[kind],path.removeprefix('payload.').split('.'))
def source(kind,spec,write):
    if 'field' in spec:
        values=field(kind,spec['field'])
        if not values:raise ValueError((kind,spec['field']))
        return values
    if 'const' in spec:return [{'const':spec['const']}]
    if 'object_without_fields' in spec:return field(kind,spec['object_without_fields']['field'])
    if 'envelope_field' in spec:return [{'ref':'schemas/event-envelope.schema.json#/properties/'+spec['envelope_field']}]
    if spec.get('projected_value'):
        return [{'projected':write['value_projection']}]
    raise ValueError((kind,spec))
families={}
errors=[]
for kind,contract in catalog['event_kind_registry']['cell_contracts'].items():
    for write in contract['cell_writes']:
        family=write.get('cell_family')
        if family is None or write.get('value_shape')=='log':continue
        row=families.setdefault(family,{'state_model':write['state_model'],'values':[],'writers':[]})
        row['writers'].append(kind)
        effect=write['effect_projection'];op=effect['kind']
        try:
            if op in ['set','or_set_add']:row['values']+=source(kind,effect['value'],write)
            elif op in ['transition','transition_to']:row['values']+=source(kind,effect['to'],write)
            elif op=='or_set_delta':
                for branch in effect['branches'].values():
                    if branch['op']=='add':row['values']+=source(kind,branch['value'],write)
        except ValueError as e:errors.append(str(e))
if errors: raise SystemExit(str(errors))

def schema_ref(ref):
    return {'$ref':'./'+ref.removeprefix('schemas/')}
def atom(kind,spec):
    if 'field' in spec:
        matches=field(kind,spec['field']);assert matches,(kind,spec)
        values=[schema_ref(x['ref']) for x in matches]
        return values[0] if len(values)==1 else {'anyOf':values}
    if 'literal' in spec:return {'const':spec['literal']}
    if 'normalized_string_set' in spec:return atom(kind,{'field':spec['normalized_string_set']['field']})
    if 'envelope_field' in spec:return schema_ref('schemas/event-envelope.schema.json#/properties/'+spec['envelope_field'])
    if 'derivation' in spec:return schema_ref('schemas/event-envelope.schema.json#/$defs/digest')
    raise ValueError(spec)
object_schemas={'strand.object':'strand','space.metadata':'space','morph':'morph','view':'view','relation':'relation','profile.create':'actor-profile','circle.metadata':'circle'}
bindings={row['cell_family']:row for row in catalog['current_result_registry']['families']}
if set(bindings)!=set(families):raise SystemExit('Current-result family coverage differs from registered non-log cells')
def projected_object(schema_name,omissions):
    original=load('schemas/'+schema_name+'.schema.json')
    value=json.loads(json.dumps(original))
    for key in ['$id','$schema','$defs','title']:value.pop(key,None)
    def rewrite_refs(node):
        if isinstance(node,dict):
            for key,item in list(node.items()):
                if key=='$ref' and item.startswith('#'):node[key]='./'+schema_name+'.schema.json'+item
                else:rewrite_refs(item)
        elif isinstance(node,list):
            for item in node:rewrite_refs(item)
    rewrite_refs(value)
    def omit(node):
        if not isinstance(node,dict):return
        for name in omissions:node.get('properties',{}).pop(name,None)
        if 'required' in node:node['required']=[key for key in node['required'] if key not in omissions]
        for key in ['allOf','anyOf','oneOf']:
            for branch in node.get(key,[]):omit(branch)
        for key in ['if','then','else']:omit(node.get(key))
        if isinstance(node.get('not'),dict) and set(node['not'].get('required',[])) and set(node['not']['required']).issubset(omissions):node.pop('not')
    omit(value)
    required=set(value.get('required',[])+['id'])
    value['required']=[key for key in value.get('properties',{}) if key in required]
    return value
value_defs={}
for family,row in families.items():
    if bindings[family]['delivery']=='dedicated_channel':continue
    suffix=family.removeprefix('ak.component.').removesuffix('.v1');name='value_'+suffix.replace('.','_')
    if bindings[family].get('result_projection_schema_ref'):
        value=schema_ref(bindings[family]['result_projection_schema_ref'])
    elif suffix in object_schemas:
        value=projected_object(object_schemas[suffix],bindings[family]['projection_omitted_fields'])
    elif suffix=='mls.epoch':value=schema_ref('schemas/mls-governance-proof-bundle.schema.json#/$defs/mls_epoch_head')
    elif suffix=='identity.resolution':value=schema_ref('schemas/identity-resolution.schema.json#/$defs/resolution_projection')
    else:
        variants=[]
        for kind in set(row['writers']):
            for write in catalog['event_kind_registry']['cell_contracts'][kind]['cell_writes']:
                if write.get('cell_family')!=family:continue
                effect=write['effect_projection'];op=effect['kind']
                values=[]
                if op in ['set','or_set_add']:values=source(kind,effect['value'],write)
                elif op in ['transition','transition_to']:values=source(kind,effect['to'],write)
                elif op=='or_set_delta':
                    for branch in effect['branches'].values():
                        if branch['op']=='add':values+=source(kind,branch['value'],write)
                for val in values:
                    if 'ref' in val:variants.append(schema_ref(val['ref']))
                    elif 'const' in val:variants.append(val)
                    else:
                        members=val['projected']['members'];props={m['name']:atom(kind,m) for m in members}
                        if suffix=='realm.authority_root':
                            for key in ['controller_epoch','authority_generation']:props[key]={'type':'integer','minimum':0,'maximum':9007199254740991}
                        variants.append({'type':'object','required':[m['name'] for m in members if not m.get('optional')],'properties':props,'additionalProperties':False})
        dedup={json.dumps(v,sort_keys=True):v for v in variants};variants=[dedup[k] for k in sorted(dedup)]
        value=variants[0] if len(variants)==1 else {'anyOf':variants}
    if bindings[family]['value_shape']=='set' and bindings[family]['result_projection']=='joined_value':value={'type':'array','uniqueItems':True,'items':value}
    elif row['state_model']=='sequenced_state' and bindings[family]['value_shape']=='register':
        value={'anyOf':[{'type':'null'},value]}
    value_defs[name]=value

genesis_epoch=next(write for write in catalog['event_kind_registry']['cell_contracts']['ak.mls.genesis']['cell_writes'] if write.get('cell_family')=='ak.component.mls.epoch.v1')
if next(member for member in genesis_epoch['value_projection']['members'] if member['name']=='previous_epoch').get('literal')!=0:
    raise SystemExit('MLS Genesis current epoch requires the unique (0,0) head')

for family,row in families.items():
    binding=bindings[family]
    if binding['state_model']!=row['state_model'] or binding['source_event_kinds']!=sorted(set(row['writers'])):
        raise SystemExit('Current-result source contract drift: '+family)
path=root/'schemas/account-current-result.schema.json'
actual=json.loads(path.read_text(encoding='utf-8'))
expected=json.loads(json.dumps(actual))
expected['$defs']={key:value for key,value in expected['$defs'].items() if not key.startswith('value_')}
expected['$defs']={**value_defs,**expected['$defs']}
expected['$defs']['result']={
    'oneOf':[
        {
            'type':'object',
            'properties':{
                'status':{'const':'value'},
                'value':{'anyOf':[]},
                'source':{
                    'type':'object',
                    'required':['event_id','depth'],
                    'properties':{
                        'event_id':{'$ref':'./common-ids.schema.json#/$defs/event_id'},
                        'depth':{'type':'integer','minimum':0,'maximum':9007199254740991},
                    },
                    'additionalProperties':False,
                },
            },
            'required':['status','value'],
            'additionalProperties':False,
        },
        actual['$defs']['result']['oneOf'][-2],
        {
            'type':'object',
            'properties':{
                'status':{'const':'unavailable'},
                'reason':{'enum':['dependency_missing','limit_exceeded']},
            },
            'required':['status','reason'],
            'additionalProperties':False,
        },
    ]
}
# Derive selector dispatch from the same registry as concrete value schemas.
subject_tail=r"(?:[A-Za-z0-9._~=-]|%[0-9A-Fa-f]{2})*(?::(?:[A-Za-z0-9._~=-]|%[0-9A-Fa-f]{2})+)*$"
conditions=[]
patterns=[]
for family,binding in bindings.items():
    if binding['delivery']=='dedicated_channel':continue
    pattern='^ak:cell:'+re.escape(family)+':'+subject_tail
    patterns.append(pattern)
    targets={'object':['realm','strand','event'],'pin_scope':['realm','strand']}.get(binding['target_class'],[binding['target_class']])
    value={'$ref':'./'+binding['value_schema_ref'].removeprefix('schemas/')}
    result={'status':{'enum':['value','removed','unavailable']},'value':value}
    result_constraint={'properties':result}
    if binding['state_model']=='causal_register':result_constraint['required']=['source']
    else:result['source']=False
    conditions.append({'if':{'properties':{'selector':{'properties':{'cell_id':{'pattern':pattern}}}}},'then':{'properties':{'target':{'properties':{'kind':{'enum':targets}}},'result':result_constraint}}})
conditions.append({'if':{'properties':{'selector':{'properties':{'cell_id':{'$ref':'./event-envelope.schema.json#/$defs/cell_ref','not':{'anyOf':[{'pattern':p} for p in patterns]}}}}}},'then':{'properties':{'result':{'properties':{'status':{'enum':['removed','unavailable']}}}}}})
expected['$defs']['entry']['allOf']=conditions
expected['$defs']['result']['oneOf'][0]['properties']['value']['anyOf']=[{'$ref':'#/$defs/'+name} for name in value_defs]

if '--check' in sys.argv:
    if expected!=actual:raise SystemExit('Current-result value schema drift; run generate_current_result_values.py')
    print(f'Current-result values: {len(value_defs)} closed family mappings match')
else:
    path.write_text(json.dumps(expected,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(f'Generated {len(value_defs)} closed current-result value mappings')
