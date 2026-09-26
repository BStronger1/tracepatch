"""Re-evaluate a saved candidate with a versioned verifier; never rewrite its run."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, required=True)
    parser.add_argument('--task', required=True, choices=sorted(p.parent.name for p in (ROOT/'tasks/repos').glob('*/task.json')))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    batch = args.batch.resolve()
    if not batch.is_relative_to((ROOT/'runs').resolve()):
        parser.error('Batch must be inside this project runs directory')
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(batch):
        parser.error('Choose a new output file outside the original batch')
    manifest = json.loads((batch/'manifest.json').read_text())
    if len(manifest['tasks']) != 1:
        parser.error('Expected a single-task real-repository batch')
    original_task = next(iter(manifest['tasks']))
    if Path(original_task).name != original_task or '/' in original_task or '\\' in original_task:
        parser.error('Invalid task identifier')
    task = ROOT/'tasks/repos'/args.task
    target = json.loads((task/'task.json').read_text())
    for field in ('repository', 'base_commit', 'image'):
        if manifest['provenance'].get(field) != target.get(field):
            parser.error('Incompatible evaluation provenance: ' + field)
    run = batch/(batch.name+'--'+original_task)
    candidate = run/'candidate'
    if not candidate.is_dir() or candidate.is_symlink():
        parser.error('Saved candidate directory is missing or linked')
    source_hashes = {}
    for path in sorted(candidate.rglob('*')):
        if path.is_symlink():
            parser.error('Linked candidate entries are not supported')
        if path.is_file():
            source_hashes[path.relative_to(candidate).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    candidate_hash = hashlib.sha256(json.dumps(source_hashes,sort_keys=True).encode()).hexdigest()
    original = json.loads((run/'result.json').read_text())
    spec = importlib.util.spec_from_file_location('repo_runner',ROOT/'scripts/run-repo.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    layout = runner.repository_layout(target['repository'])
    result = runner.verify(target['image'],candidate,task,import_directory=layout.imports)
    report = {'scope':'Retrospective independent verification; original results unchanged; no API calls',
              'batch':batch.name,'original_task':original_task,'evaluation_task':args.task,
              'evaluation_version':target.get('evaluation_version',1),
              'original_completion':original.get('completion'),
              'reevaluated_completion':runner.completion_status(original.get('agent_exit'),result),
              'verification':result,
              'evidence_sha256':{'original_result':hashlib.sha256((run/'result.json').read_bytes()).hexdigest(),
                                 'candidate_tree':candidate_hash,
                                 'patch':hashlib.sha256((run/'patch.diff').read_bytes()).hexdigest(),
                                 'task':hashlib.sha256((task/'task.json').read_bytes()).hexdigest(),
                                 'verifier':hashlib.sha256((task/'verify.py').read_bytes()).hexdigest()}}
    with output.open('x',encoding='utf-8') as handle:
        json.dump(report,handle,indent=2)
    print(json.dumps({'batch':batch.name,'evaluation_task':args.task,
                      'completion':report['reevaluated_completion']},indent=2))


if __name__ == '__main__':
    main()
