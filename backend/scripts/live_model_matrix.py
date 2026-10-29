"""Billable, blinded HomHive model evaluation on verified gallery image pairs.

Run from backend:
    python -m scripts.live_model_matrix --full --require-all

The accepted edit labels are kept out of all model prompts. Reports contain no API
keys and are saved outside the repository by default. Images are transmitted to
configured third-party model providers; use synthetic gallery data only.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import mimetypes
import os
import re
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ENDPOINTS = {
    'nebius': 'https://api.tokenfactory.nebius.com/v1/chat/completions',
    'openai': 'https://api.openai.com/v1/chat/completions',
    'anthropic': 'https://api.anthropic.com/v1/messages',
    'nemotron': 'https://api.tokenfactory.nebius.com/v1/chat/completions',
    'tavily': 'https://api.tavily.com/search',
}
CATEGORIES = ('condition', 'removal', 'addition', 'human_addition',
              'lighting', 'occlusion', 'crop', 'depiction', 'reflection',
              'relocation', 'no_material_change', 'uncertain')
PAIR_PROMPT = (
    'You are evaluating two photographs of a household setting. Photo A is the earlier view; Photo B is later. '
    'Independently inspect both. Report the MOST SIGNIFICANT visible change, if supported. '
    'Separate real objects/people from items displayed on TV, photographs and monitors; a mannequin is not a person. '
    'A mirror can show a physically present person but does not create a second object. '
    'A cropped or occluded object must not be declared physically removed without evidence. '
    'Lighting change alone is not an object-condition change. Do not invent identities, actions, or tasks. '
    'Do NOT assume a particular kind of change occurred. '
    'Return ONLY JSON object with exact keys: change_type (one of '
    + ', '.join(CATEGORIES) + '), summary (brief string), changed_objects (array of short strings), '
    'physical_person_added (boolean or null), added_physical_objects (array of short strings), '
    'removed_physical_objects (array of short strings). '
    'No commentary, markdown, or additional keys.'
)
SINGLE_PROMPT = (
    'Inspect this photograph. Return ONLY a JSON object with exactly '
    'room_category (string), visible_objects (array of 1 to 12 short strings), '
    'physically_present_person (boolean or null), screen_or_photo_person_only (boolean), '
    'condition_evidence (short string). Describe only directly visible evidence. '
    'Do not invent objects, household members, activities or tasks. '
    'An uncertain room may be "unknown".'
)
FALLBACK_PROMPT = (
    'Describe only this image. Return JSON with keys room_category (string), '
    'visible_objects (list of short strings), physically_present_person (boolean or null), '
    'screen_or_photo_person_only (boolean), condition_evidence (short string), '
    'visibility_notes (short string). Do not invent what is out of frame.'
)

REASONING_CASES = [
    ('away_home_required', 'A home-only task is pending; presence AWAY; available minutes 40.', 'defer'),
    ('home_busy', 'Presence HOME; user BUSY; home-only task requires 15 active minutes.', 'defer'),
    ('quiet_hours_vacuum', 'Presence HOME, user FREE; quiet hours active; task is noisy vacuuming.', 'defer'),
    ('short_window', 'Presence HOME, user FREE; task needs 30 active minutes; available window 8.', 'defer'),
    ('unknown_presence', 'Presence UNKNOWN; task strictly requires home presence; user otherwise FREE.', 'defer'),
    ('high_priority_away', 'Priority 1.0, but presence AWAY and task requires home presence.', 'defer'),
    ('free_eligible', 'Presence HOME, user FREE, outside quiet hours; safe 10-minute home task and available window 30.', 'execute'),
    ('quiet_task_in_quiet_hours', 'Presence HOME, user FREE, quiet hours active; quiet 5-minute desk sorting and available window 30.', 'execute'),
]
RESEARCH_CASES = [
    ('smoke_alarm', 'NFPA smoke alarm testing maintenance official guidance'),
    ('plant_stress', 'university extension diagnosing yellow leaves on houseplants overwatering guidance'),
    ('hvac_filter', 'energy.gov residential HVAC air filter replacement maintenance guidance'),
]

class ProviderError(Exception):
    def __init__(self, reason: str, status: int | None = None):
        super().__init__(reason)
        self.status = status


class Gateway:
    def __init__(self, timeout: int):
        self.timeout = timeout
        self.lock = threading.Lock()
        self.calls = 0

    def post(self, url: str, payload: dict, headers: dict) -> dict:
        data = json.dumps(payload).encode('utf-8')
        req = Request(url, data, headers={'Content-Type': 'application/json', 'Accept': 'application/json', **headers}, method='POST')
        for attempt in range(3):
            with self.lock:
                self.calls += 1
            try:
                with urlopen(req, timeout=self.timeout) as response:
                    answer = json.loads(response.read(2 * 1024 * 1024))
                if not isinstance(answer, dict):
                    raise ProviderError('response_not_json_object')
                return answer
            except HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise ProviderError(f'http_{exc.code}', status=exc.code) from None
            except URLError:
                raise ProviderError('network_error') from None
            except (json.JSONDecodeError, TimeoutError):
                raise ProviderError('unreadable_provider_response') from None
        raise ProviderError('retries_exhausted')


def parse_json_object(content: str) -> tuple[dict, bool]:
    """Extract valid JSON after optional reasoning/fences; flag format recovery."""
    if not isinstance(content, str) or not content.strip():
        raise ProviderError('empty_model_text')
    value = content.strip()
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed, False
    except (ValueError, TypeError):
        pass
    value = re.sub(r'<think>.*?</think>', '', value, flags=re.S | re.I).strip()
    value = re.sub(r'^```(?:json)?\s*|\s*```$', '', value, flags=re.I).strip()
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed, True
    except (ValueError, TypeError):
        pass

    decoder = json.JSONDecoder()
    for pos, char in enumerate(value):
        if char != '{':
            continue
        try:
            parsed, _ = decoder.raw_decode(value[pos:])
            if isinstance(parsed, dict):
                return parsed, True
        except ValueError:
            pass
    raise ProviderError('invalid_json')


def load_image(path: Path) -> tuple[str, str]:
    if not path.is_file():
        raise ProviderError('missing_image')
    mime = mimetypes.guess_type(path.name)[0]
    if mime not in ('image/jpeg', 'image/png', 'image/webp'):
        raise ProviderError('unsupported_image_type')
    if not 0 < path.stat().st_size <= 10 * 1024 * 1024:
        raise ProviderError('unsupported_image_size')
    return mime, base64.b64encode(path.read_bytes()).decode('ascii')


def provider_config(provider: str) -> tuple[str, str, dict]:
    if provider == 'nebius':
        key = os.environ.get('NEBIUS_API_KEY')
        model = os.environ.get('HOMHIVE_NEBIUS_VISION_MODEL', 'openbmb/MiniCPM-V-4_5')
        headers = {'Authorization': f'Bearer {key}'}
    elif provider == 'openai':
        key = os.environ.get('OPENAI_API_KEY')
        model = os.environ.get('HOMHIVE_OPENAI_REVIEW_MODEL', 'gpt-4.1-mini')
        headers = {'Authorization': f'Bearer {key}'}
    elif provider == 'anthropic':
        key = os.environ.get('ANTHROPIC_API_KEY')
        model = os.environ.get('HOMHIVE_ANTHROPIC_REVIEW_MODEL', 'claude-sonnet-4-5-20250929')
        headers = {'x-api-key': key or '', 'anthropic-version': '2023-06-01'}
    elif provider == 'nemotron':
        key = os.environ.get('NEBIUS_API_KEY')
        model = os.environ.get('NEBIUS_REASONING_MODEL')
        headers = {'Authorization': f'Bearer {key}'}
    elif provider == 'tavily':
        key, model, headers = os.environ.get('TAVILY_API_KEY'), 'search', {'Authorization': f"Bearer {os.environ.get('TAVILY_API_KEY')}"}
    else:
        raise ValueError('invalid_provider')
    if not key or not model:
        raise ProviderError('missing_provider_configuration')
    return key, model, headers


def image_completion(gateway: Gateway, provider: str, images: list[tuple[str, str]], prompt: str) -> tuple[dict, bool]:
    _, model, headers = provider_config(provider)
    if provider == 'anthropic':
        content = [{'type': 'text', 'text': prompt}]
        for index, (mime, b64) in enumerate(images):
            content.append({'type': 'text', 'text': 'Photo '+('A' if index == 0 else 'B')})
            content.append({'type': 'image', 'source': {'type': 'base64', 'media_type': mime, 'data': b64}})
        payload = {'model': model, 'max_tokens': 1300, 'temperature': 0, 'messages': [{'role': 'user', 'content': content}]}
        response = gateway.post(ENDPOINTS[provider], payload, headers)
        blocks = response.get('content', [])
        if not isinstance(blocks, list):
            raise ProviderError('missing_content')
        text = '\n'.join(str(b.get('text','')) for b in blocks if isinstance(b,dict) and b.get('type')=='text')
    else:
        content = [{'type': 'text', 'text': prompt}]
        for index,(mime,b64) in enumerate(images):
            content.append({'type': 'text','text':'Photo '+('A' if index == 0 else 'B')})
            content.append({'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{b64}'}})
        payload = {'model': model, 'max_tokens': 1300,
                   'messages':[{'role':'system','content':'Describe only image evidence. Output JSON only.'},
                               {'role':'user','content':content}]}
        if provider=='openai':payload['temperature']=0
        response = gateway.post(ENDPOINTS[provider], payload, headers)
        choices = response.get('choices')
        if not isinstance(choices, list) or not choices or not isinstance(choices[0],dict):
            raise ProviderError('missing_choices')
        text = choices[0].get('message',{}).get('content')
    return parse_json_object(text)


def text_completion(gateway: Gateway, provider: str, instruction: str, prompt: str) -> tuple[dict, bool]:
    _,model,headers = provider_config(provider)
    if provider == 'anthropic':
        payload={'model':model,'max_tokens':1100,'temperature':0,'system':instruction,
                 'messages':[{'role':'user','content':prompt}]}
        result=gateway.post(ENDPOINTS[provider],payload,headers)
        blocks=result.get('content',[])
        if not isinstance(blocks,list):raise ProviderError('missing_content')
        txt='\n'.join(b.get('text','') for b in blocks if isinstance(b,dict) and b.get('type')=='text')
    else:
        payload={'model':model,'max_tokens':1500,'messages':[{'role':'system','content':instruction}, {'role':'user','content':prompt}]}

        if provider!='nemotron':payload['temperature']=0
        result=gateway.post(ENDPOINTS[provider],payload,headers)
        choices=result.get('choices',[])
        if not isinstance(choices,list) or not choices:raise ProviderError('missing_choices')
        txt=choices[0].get('message',{}).get('content')
    return parse_json_object(txt)


def validate_pair(data: dict, expected: str) -> tuple[bool,str]:
    name=data.get('change_type')
    if name not in CATEGORIES:return False,'invalid_change_type'
    if not isinstance(data.get('summary'),str) or not data['summary'].strip():return False,'missing_summary'
    for key in ('changed_objects','added_physical_objects','removed_physical_objects'):
        value=data.get(key)
        if not isinstance(value,list) or not all(isinstance(v,str) for v in value):return False, f'invalid_{key}'
    person=data.get('physical_person_added')
    if person is not None and not isinstance(person,bool):return False,'invalid_person_added_flag'
    if name!=expected:return False,'change_type_mismatch'
    if expected=='human_addition' and person is not True:return False,'physical_person_not_identified'
    if expected in ('depiction','reflection') and data['added_physical_objects']:
        return False,'depiction_or_reflection_counted_as_new_physical_object'
    if expected in ('depiction','reflection','addition') and person is True:
        return False,'false_physical_person_added'
    if expected=='crop' and data['removed_physical_objects']:
        return False,'crop_treated_as_physical_removal'
    return True,'grounded_change_matched'


def result_error(kind, provider, case_id, expected, exc, start):
    return {'kind':kind,'provider':provider,'case_id':case_id,'expected':expected,'observed':'',
            'pass':False,'reason':str(exc)[:95] if isinstance(exc,ProviderError) else type(exc).__name__,
            'seconds':round(time.monotonic()-start,2),'recovered_json':False,'fallback':False,'summary':'','sdk_calls':0}


def run_pair(gateway, provider: str, case: dict, directory: Path) -> dict:
    start=time.monotonic()
    try:
        a=load_image(directory/case['base']);b=load_image(directory/case['variant']);fallback=False
        try:
            data,recovered=image_completion(gateway,provider,[a,b],PAIR_PROMPT)
        except ProviderError as e:
            if e.status not in (400, 413, 422):raise


            one,_=image_completion(gateway,provider,[a],FALLBACK_PROMPT)
            two,_=image_completion(gateway,provider,[b],FALLBACK_PROMPT)
            data,recovered=text_completion(gateway,provider,PAIR_PROMPT,
                'Earlier image evidence: '+json.dumps(one)+'\nLater image evidence: '+json.dumps(two))
            fallback=True
        ok,reason=validate_pair(data,case['expected'])
        return {'kind':'pair','provider':provider,'case_id':case['id'],'expected':case['expected'],
                'observed':data.get('change_type'),'pass':ok,'reason':reason,'seconds':round(time.monotonic()-start,2),
                'recovered_json':recovered,'fallback':fallback,'summary':data.get('summary','')[:180]}
    except Exception as exc:
        return result_error('pair',provider,case['id'],case['expected'],exc,start)


def validate_single(data):
    objects=data.get('visible_objects')
    if not isinstance(data.get('room_category'),str):return False,'invalid_room'
    if not isinstance(objects,list) or not objects or not all(isinstance(v,str) and v.strip() for v in objects):return False,'no_visible_objects'
    if data.get('physically_present_person') is not None and not isinstance(data['physically_present_person'],bool):return False,'invalid_person_flag'
    if not isinstance(data.get('screen_or_photo_person_only'),bool):return False,'invalid_screen_person_flag'
    if not isinstance(data.get('condition_evidence'),str):return False,'invalid_condition_evidence'
    return True,'structured_visual_evidence'


def run_single(gateway,provider,case,directory):
    start=time.monotonic()
    try:
        img=load_image(directory/case['file'])
        data,recovered=image_completion(gateway,provider,[img],SINGLE_PROMPT)
        ok,reason=validate_single(data)
        return {'kind':'single','provider':provider,'case_id':case['id'],'expected':case['expected_room'],
                'observed':data.get('room_category'),'pass':ok,'reason':reason,
                'seconds':round(time.monotonic()-start,2),'recovered_json':recovered,'fallback':False,
                'summary':', '.join(data.get('visible_objects',[])[:5])[:180] if isinstance(data.get('visible_objects'),list) else ''}
    except Exception as exc:return result_error('single',provider,case['id'],case['expected_room'],exc,start)


def run_reasoning(gateway,case):
    case_id,context,expected=case
    start=time.monotonic()
    instruction=('You are HomHive. A deterministic hard constraint overrides priority. '
                 'Reply ONLY JSON: {"decision":"defer" or "execute", "reason":"one short sentence"}. '
                 'Do not invent new constraints or tasks. To execute, the task must satisfy all given restrictions.')
    try:
        recovered=False
        try:
            data,recovered=text_completion(gateway,'nemotron',instruction,context)
        except ProviderError as e:
            if str(e)!='invalid_json':raise

            data,recovered=text_completion(gateway,'nemotron',instruction+' No preamble or reasoning tags.',context)
        ok=data.get('decision')==expected and isinstance(data.get('reason'),str) and bool(data['reason'].strip())
        return {'kind':'reasoning','provider':'nemotron','case_id':case_id,'expected':expected,
                'observed':data.get('decision'),'pass':ok,'reason':'constraint_obeyed' if ok else 'constraint_or_format_failed',
                'seconds':round(time.monotonic()-start,2),'recovered_json':recovered,'fallback':False,
                'summary':str(data.get('reason',''))[:180]}
    except Exception as e:return result_error('reasoning','nemotron',case_id,expected,e,start)


def run_research(gateway,case):
    case_id,query=case;start=time.monotonic()
    try:
        _,_,h=provider_config('tavily')
        res=gateway.post(ENDPOINTS['tavily'],{'query':query,'search_depth':'basic','max_results':4,
                         'include_images':False,'include_raw_content':False,'include_answer':False},h)
        items=res.get('results')
        good=isinstance(items,list) and any(isinstance(i,dict) and isinstance(i.get('url'),str)
                and i['url'].startswith('https://') and isinstance(i.get('title'),str) and bool(i['title'])
                and isinstance(i.get('content'),str) and bool(i['content']) for i in items)
        return {'kind':'research','provider':'tavily','case_id':case_id,'expected':'grounded_sources',
                'observed':str(len(items))+' sources' if isinstance(items,list) else 'missing',
                'pass':bool(good),'reason':'attributable_sources' if good else 'no_attributable_evidence',
                'seconds':round(time.monotonic()-start,2),'recovered_json':False,'fallback':False,'summary':'','sdk_calls':0}
    except Exception as e:return result_error('research','tavily',case_id,'grounded_sources',e,start)




PRODUCTION_EXPECTATIONS = {
    'NV01': ('dish_load', 'increase'),
    'NV02': ('laundry_load', 'increase'),
    'NV04': ('lawn_condition', 'increase'),
    'NV10': ('dish_load', 'decrease'),
    'NV11': ('laundry_load', 'decrease_or_absent'),
}


def evaluate_condition_change(first: dict, second: dict, category: str, direction: str):
    a = first.get(category)
    b = second.get(category)
    if a is None:
        return False,'baseline_condition_missing'
    if direction=='decrease_or_absent' and b is None:
        return True,'target_absent_no_unfounded_zero'
    if b is None:
        return False,'variant_condition_missing'
    if direction=='increase':
        ok = b > a + 0.05
        return ok,'workload_or_severity_increased' if ok else 'missed_increase'
    if direction in ('decrease','decrease_or_absent'):
        ok = b < a - 0.05
        return ok,'workload_decreased' if ok else 'missed_decrease'
    return False,'invalid_expectation'


def run_production_pair(case, directory: Path, with_review: bool):
    start=time.monotonic()
    sdk_calls=0
    try:
        from app.vision.provider import NebiusVisionProvider
        from app.vision.verification import OpenAIImageVerifier, corroborate
        category,direction=PRODUCTION_EXPECTATIONS[case['id']]
        primary=NebiusVisionProvider(model=os.environ.get('HOMHIVE_NEBIUS_VISION_MODEL','openbmb/MiniCPM-V-4_5'))
        reviewer=OpenAIImageVerifier(model=os.environ.get('HOMHIVE_OPENAI_REVIEW_MODEL','gpt-4.1-mini')) if with_review else None
        states=[]; reviews=[]
        for name in ('base','variant'):
            path=directory/case[name]
            mime=load_image(path)[0]
            sdk_calls += 1
            extraction=primary.extract(path.read_bytes(),mime,'evaluation_room')
            states.append({c.category.value: c.value for c in extraction.candidates})
            if reviewer is not None and extraction.candidates:
                sdk_calls += 1
                review=reviewer.review(path.read_bytes(),mime,extraction)
                reviews.append(corroborate(extraction,review))
        ok,reason=evaluate_condition_change(states[0],states[1],category,direction)
        if reviews and not all(reviews):
            ok=False;reason='independent_review_disagrees'
        observed=str(states[0].get(category,'unknown'))+' -> '+str(states[1].get(category,'unknown'))
        return {'kind':'production','provider':'production_nebius','case_id':case['id'],
                'expected':category+' '+direction,'observed':observed,'pass':ok,'reason':reason,
                'seconds':round(time.monotonic()-start,2),'recovered_json':False,'fallback':False,
                'summary':('OpenAI image review confirmed' if reviews and all(reviews) else
                           'OpenAI reviewer unavailable or no claims' if reviewer is not None else 'review disabled'),
                'sdk_calls':sdk_calls}
    except Exception as exc:
        row=result_error('production','production_nebius',case['id'],
                    str(PRODUCTION_EXPECTATIONS.get(case['id'])),exc,start)
        row['sdk_calls']=sdk_calls
        return row


def select_pairs(pairs, count):
    if count>=len(pairs):return pairs

    out=[];seen=set()
    for c in pairs:
        if c['expected'] not in seen:
            out.append(c);seen.add(c['expected'])
        if len(out)>=count:return out
    for c in pairs:
        if c not in out:out.append(c)
        if len(out)>=count:break
    return out


def verify_case_manifest(data: dict, directory: Path) -> None:
    cases=data['pairs'];ids=[c['id'] for c in cases]
    if len(ids)!=len(set(ids)) or len(cases)!=28:raise ValueError('invalid_eval_manifest')
    filenames=set()
    for pair in cases:
        if pair['expected'] not in CATEGORIES:raise ValueError('invalid_expected_class')
        for field in ('base','variant'):
            filename=pair[field]
            if Path(filename).name != filename or not (directory/filename).is_file():
                raise FileNotFoundError(f'missing_gallery_image: {filename}')
            filenames.add(filename)
    for i in data['standalone']:
        filename=i['file']
        if Path(filename).name != filename or not (directory/filename).is_file():
            raise FileNotFoundError(f'missing_gallery_image: {filename}')
    print(f'Image preflight: {len(cases)} verified gallery pairs, {len(filenames)} unique pair images, '
          f'{len(data["standalone"])} standalone checks, missing accepted variants: {", ".join(data["missing_pairs"])}',flush=True)


def write_reports(records, directory: Path, meta: dict) -> None:
    directory.mkdir(parents=True,exist_ok=True)
    with (directory/'results.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=['kind','provider','case_id','expected','observed','pass','reason','seconds','recovered_json','fallback','summary','sdk_calls'],extrasaction='ignore')
        writer.writeheader();writer.writerows(records)
    counts={}
    for provider in ('nebius','openai','anthropic','nemotron','tavily','production_nebius'):
        r=[item for item in records if item['provider']==provider]
        if r:counts[provider]={'passed':sum(bool(i['pass']) for i in r),'total':len(r)}
    (directory/'summary.json').write_text(json.dumps({'metadata':meta,'providers':counts,'cases':records},indent=2)+'\n',encoding='utf-8')
    print(f'REPORTS: {directory / "results.csv"} and {directory / "summary.json"}',flush=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description='Real image/variant evaluation of HomHive Nebius/OpenAI/Claude/Nemotron/Tavily')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--full',action='store_true',help='28 variant pairs, 12 original photos, 8 reasoning, 3 research cases')
    mode.add_argument('--quick',action='store_true',help='12 stratified pairs, 6 original photos, 4 reasoning, 2 research cases (default)')
    parser.add_argument('--providers',default='nebius,openai,anthropic,nemotron,tavily',help='Comma-separated provider names')
    parser.add_argument('--timeout',type=int,default=120)
    parser.add_argument('--no-production',action='store_true',help='Skip actual HomHive production Nebius extraction and OpenAI image verification')
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--require-all',action='store_true',help='Treat missing configured provider as failure')
    parser.add_argument('--gallery',type=Path,default=Path(__file__).resolve().parents[2]/'frontend/public/demo-library')
    parser.add_argument('--report-dir',type=Path,default=Path(tempfile.gettempdir())/('homhive_model_eval_'+datetime.now().strftime('%Y%m%d_%H%M%S')))
    args=parser.parse_args(argv)
    if not 20<=args.timeout<=300:parser.error('timeout must be 20..300 seconds')
    if not 1<=args.workers<=6:parser.error('workers must be 1..6')
    choices={'nebius','openai','anthropic','nemotron','tavily'}
    providers=[v.strip().lower() for v in args.providers.split(',') if v.strip()]
    if not providers or any(v not in choices for v in providers):parser.error('unknown provider')
    from app.config import load_local_environment
    load_local_environment()
    data=json.loads((Path(__file__).with_name('model_eval_cases.json')).read_text(encoding='utf-8'))
    directory=args.gallery.resolve()
    verify_case_manifest(data,directory)
    pairs=select_pairs(data['pairs'],28 if args.full else 12)
    singles=data['standalone'] if args.full else data['standalone'][:6]
    reasoning=REASONING_CASES if args.full else REASONING_CASES[:4]
    research=RESEARCH_CASES if args.full else RESEARCH_CASES[:2]
    missing=[]
    for p in providers:
        try:provider_config(p)
        except ProviderError:missing.append(p)
    if missing:print('MISSING CONFIGURATION:',', '.join(missing),flush=True)
    usable=[p for p in providers if p not in missing]
    gw=Gateway(args.timeout)
    futures=[];records=[]
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for p in usable:
            if p in ('nebius','openai','anthropic'):
                futures += [executor.submit(run_pair,gw,p,c,directory) for c in pairs]
                futures += [executor.submit(run_single,gw,p,c,directory) for c in singles]
            if p=='nemotron':futures += [executor.submit(run_reasoning,gw,c) for c in reasoning]
            if p=='tavily':futures += [executor.submit(run_research,gw,c) for c in research]
        if not args.no_production and 'nebius' in usable:
            review='openai' in usable
            selected=[case for case in data['pairs'] if case['id'] in PRODUCTION_EXPECTATIONS]
            if not args.full:selected=selected[:2]
            futures += [executor.submit(run_production_pair,case,directory,review) for case in selected]
        print('Scheduled',len(futures),'model checks; actual API calls may be higher if retries/fallbacks are needed.',flush=True)
        for future in as_completed(futures):
            result=future.result();records.append(result)
            label='PASS' if result['pass'] else 'FAIL'
            print(f'[{label}] {result["provider"]:9} {result["case_id"]:23} '
                  f'expected={str(result["expected"]):17} got={str(result["observed"]):17} '
                  f'{result["reason"]} ({result["seconds"]}s)',flush=True)
    meta={'sdk_requests':sum(r.get('sdk_calls',0) for r in records),
          'production_pairs':0 if args.no_production else (5 if args.full else 2), 'profile':'full' if args.full else 'quick','pairs':len(pairs),'standalone_photos':len(singles),
          'reasoning':len(reasoning),'research':len(research),'provider_requests':gw.calls,
          'missing_configuration':missing,'missing_gallery_variants':data['missing_pairs'],
          'note':'Pairs are blinded predictions compared with pre-existing curated edits; raw provider content and API keys are not persisted. Missing 4 gallery variant pairs do not count as tested.'}
    write_reports(records,args.report_dir,meta)
    for p in usable+(['production_nebius'] if not args.no_production and 'nebius' in usable else []):
        r=[i for i in records if i['provider']==p]
        print(f'{p.upper()}: {sum(i["pass"] for i in r)}/{len(r)} PASS',flush=True)
    failed=len([r for r in records if not r['pass']])
    print(f'RESULT: {len(records)-failed} PASS, {failed} FAIL, {len(missing)} PROVIDERS SKIPPED, '
          f'{gw.calls + sum(r.get("sdk_calls",0) for r in records)} API CALL ATTEMPTS (including production SDK)',flush=True)
    return 1 if failed or (missing and args.require_all) else 0

if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,ValueError,ProviderError) as exc:
        print(f'PREFLIGHT FAILED: {str(exc)[:180]}',file=sys.stderr)
        sys.exit(2)
