"""Unchanged official scene-B adapter; shared input manifest, no scene-A patching."""
import importlib
import json
from pathlib import Path
from q1_io import PROCESSED, official, verify, sha


def load(config=None):
    manifest = verify()
    official()  # Register the audited attachment's code directory.
    from evaluation_validation import read_evaluation_config
    module = importlib.import_module('multicore_cut_evaluate_problem_2')
    config = Path(config or PROCESSED / 'data/config.txt')
    settings = read_evaluation_config(str(config))
    delay = module.read_scene_b_config(str(config))['cross_core_copy_delay_cycles']
    return settings, delay, {'input_manifest_sha256': sha((PROCESSED/'manifest.json').read_bytes()),
                           'source_zip_sha256': manifest['source_sha256'],
                           'official_sha256': {p: h for p, h in manifest['files'].items()
                                               if p.startswith('code/')},
                           'config_sha256': sha(config.read_bytes())}


def evaluate(raw, plan, settings, delay):
    module = importlib.import_module('multicore_cut_evaluate_problem_2')
    result = module.evaluate_scene_b(raw, plan, settings['bandwidth'], settings['capacity'], delay)
    check(result, settings, delay)
    return result


def check(result, settings, delay):
    if result['scene'] != 'B' or result['cross_core_copy_delay_cycles'] != delay:
        raise AssertionError('Wrong evaluation scene or synchronization parameter')
    traffic = result['data_movement_bytes']
    assert traffic['scheduled_copy_bytes'] - traffic['original_graph_copy_bytes'] == traffic['added_copy_bytes']
    assert traffic['partition_added_copy_bytes'] + traffic['spill_added_copy_bytes'] == traffic['added_copy_bytes']
    for peak in result['memory_peak_by_core'].values():
        for tier, cap in settings['capacity'].items():
            assert 0 <= peak[tier] <= cap, (tier, peak, cap)
    for transfer in result['cross_core_transfers']:
        assert transfer['copy_in_start'] >= transfer['copy_in_release']


def fixed_reference(raw, settings):
    """The supplied whole-graph single-core baseline, not an optimized B schedule."""
    from singlecore_evaluate import evaluate_singlecore
    return evaluate_singlecore(raw, settings['bandwidth'], settings['capacity'])


def key(plan):
    return sha(json.dumps(plan, sort_keys=True, separators=(',', ':')).encode())
