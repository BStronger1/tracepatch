"""Post-hoc Click context-prefix probes; never alter frozen acceptance grades."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runner', ROOT / 'scripts/run-repo.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
PROBE = '''import unittest
from click import Choice, Command, Option
from click.shell_completion import ShellComplete

def words(command, context_args):
    result = ShellComplete(command, context_args, "demo", "_DEMO_COMPLETE").get_completions(["-c"], "+")
    return [item.value for item in result]

class ContextPrefixes(unittest.TestCase):
    def test_dynamic_get_params_option(self):
        class DynamicCommand(Command):
            def get_params(self, ctx):
                return super().get_params(ctx) + [Option(["+dynamic"], is_flag=True)]
        command = DynamicCommand("demo", params=[Option(["-c"], type=Choice(["+red"]))])
        self.assertEqual(words(command, {}), ["+dynamic"])

    def test_help_option_from_context_arguments(self):
        command = Command("demo", params=[Option(["-c"], type=Choice(["+red"]))])
        self.assertEqual(words(command, {"help_option_names": ["+assist"]}), ["+assist"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, action='append', required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Do not overwrite evidence')
    args.run_dir.mkdir(parents=True, exist_ok=False)
    probe = args.run_dir / 'verify.py'
    probe.write_text(PROBE, encoding='utf-8')
    config = json.loads((ROOT / 'tasks/repos/click-2040/task.json').read_text())
    records = []
    for source in [args.reference, *args.candidate]:
        files = sorted((source / 'src/click').rglob('*.py'))
        assert files, 'Missing Click sources'
        hashes = {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        result = runner.verify(config['image'], source.resolve(), args.run_dir.resolve(), import_directory='src')
        records.append({'source': source.as_posix(), 'source_hashes': hashes, 'verification': result})
        if len(records) == 1:
            assert result['returncode'] == 0 and 'Ran 2 tests' in result['output'], 'Reference must pass post-hoc probes'
    report = {'scope': 'Post-hoc checks prompted by patch inspection; no change to frozen grades, no model calls',
              'model_api_calls': 0, 'image': config['image'], 'probe': PROBE,
              'probe_sha256': hashlib.sha256(PROBE.encode()).hexdigest(), 'records': records}
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps({'posthoc_returncodes': [r['verification']['returncode'] for r in records], 'model_api_calls': 0}))


if __name__ == '__main__':
    main()
