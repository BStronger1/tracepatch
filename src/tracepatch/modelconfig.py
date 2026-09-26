"""Select versioned model and quote without changing the provider or budget."""
from copy import deepcopy
import math


def select_profile(config, profiles, name='default'):
    result = deepcopy(config)
    if name == 'default':
        return result
    if name not in profiles:
        raise ValueError('Unknown model profile')
    profile = profiles[name]
    if set(profile) != {'model', 'pricing'} or not isinstance(profile['model'], str) or not profile['model'].strip():
        raise ValueError('Profile may override only model and pricing')
    pricing = profile['pricing']
    if pricing.get('currency') != 'CNY' or pricing.get('unit_tokens') != 1000000 or not pricing.get('source'):
        raise ValueError('Pricing requires CNY per million tokens and a source')
    for key in ('input', 'output'):
        value = pricing.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('Invalid model price')
    result.update(deepcopy(profile))
    return result
