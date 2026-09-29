"""Validated personal-library backups; no executable paths are imported."""
from game_info import validate_profile

def ids(value):
    if not isinstance(value, list) or len(value) > 20000: raise ValueError('Invalid game list')
    if any(not isinstance(v, str) or len(v) > 120 for v in value): raise ValueError('Invalid game identifier')
    return list(dict.fromkeys(value))

def personal_settings(settings):
    return {k:settings[k] for k in ('favorites','profiles','queue','hidden','theme','coverSize') if k in settings}

def merge_backup(current, document):
    if not isinstance(document, dict) or document.get('format') != 'orbit-personal-library' or document.get('version') != 1:
        raise ValueError('Choose an Orbit personal-library backup (version 1).')
    incoming = document.get('settings')
    if not isinstance(incoming, dict): raise ValueError('Invalid backup settings')
    result = dict(current)
    for key in ('favorites','queue','hidden'):
        if key in incoming: result[key] = ids(list(current.get(key, [])) + ids(incoming[key]))
    if 'profiles' in incoming:
        profiles = incoming['profiles']
        if not isinstance(profiles, dict) or len(profiles)>20000: raise ValueError('Invalid game profiles')
        result['profiles'] = dict(current.get('profiles', {}))
        for key, value in profiles.items():
            ids([key])
            result['profiles'][key] = validate_profile(value)
    if 'theme' in incoming:
        if incoming['theme'] not in ('orbit','ocean','violet','ember'): raise ValueError('Invalid theme')
        result['theme'] = incoming['theme']
    if 'coverSize' in incoming:
        if incoming['coverSize'] not in ('small','medium','large'): raise ValueError('Invalid cover size')
        result['coverSize'] = incoming['coverSize']
    return result
