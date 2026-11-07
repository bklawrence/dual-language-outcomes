"""A concurrent main update must not lose an accepted journal or other work."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
JOURNAL = Path('data/registry/hand_coded_reviews')


class FieldnotesPublicationTests(unittest.TestCase):
    def run_race(self, conflict=False):
        with tempfile.TemporaryDirectory(prefix='fieldnotes-publication-') as directory:
            base = Path(directory)
            remote, seed, worker = [base / name for name in ['remote.git', 'seed', 'worker']]
            binpath, runtime = base / 'bin', base / 'runtime'
            binpath.mkdir(); runtime.mkdir()

            def git(*args, cwd=None):
                result = subprocess.run(['git', *args], cwd=cwd, text=True, capture_output=True, check=True)
                return result.stdout.strip()

            git('init', '--bare', str(remote))
            git('init', '--initial-branch=main', str(seed))
            git('config', 'user.name', 'Test', cwd=seed)
            git('config', 'user.email', 'test@example.invalid', cwd=seed)
            (seed / JOURNAL).mkdir(parents=True)
            (seed / JOURNAL / 'accepted.json').write_text('accepted\n')
            (seed / 'code.txt').write_text('initial-main')
            git('add', '.', cwd=seed); git('commit', '-m', 'Initial', cwd=seed)
            git('remote', 'add', 'origin', str(remote), cwd=seed)
            git('push', '-u', 'origin', 'main', cwd=seed)
            git('symbolic-ref', 'HEAD', 'refs/heads/main', cwd=remote)
            git('clone', str(remote), str(worker))
            (worker / JOURNAL / 'new.json').write_text('new-review\n')
            (worker / 'data/curated').mkdir(); (worker / 'data/reports').mkdir()
            (worker / 'data/curated/retry.json').write_text('{}')
            (seed / 'code.txt').write_text('new-main')
            if conflict:
                (seed / JOURNAL / 'accepted.json').write_text('different immutable content\n')
            git('commit', '-am', 'Concurrent main update', cwd=seed)
            git('push', 'origin', 'main', cwd=seed)
            concurrent_head = git('rev-parse', 'HEAD', cwd=seed)

            # Real Git repositories exercise rejection, fetch and ancestry.
            # Small tool substitutes make the rebuild record its actual inputs.
            scripts = {
                'python': '#!/bin/sh\nif [ "$1" = - ]; then exec "'+sys.executable+'" "$@"; fi\n',
                'npm': '#!/bin/sh\nexit 0\n',
                'dl-outcomes': '#!'+sys.executable+'\n'+'''import json, sys
from pathlib import Path
if sys.argv[1] == 'build':
    Path('data/curated').mkdir(exist_ok=True)
    Path('data/reports').mkdir(exist_ok=True)
    Path('data/curated/retry.json').write_text(json.dumps({
        'code': Path('code.txt').read_text(),
        'journals': sorted(p.name for p in Path('data/registry/hand_coded_reviews').glob('*.json'))}))
''',
            }
            for name, body in scripts.items():
                path = binpath / name; path.write_text(body); path.chmod(0o755)
            workflow = (ROOT / '.github/workflows/fieldnotes.yml').read_text()
            block = workflow.split('      - name: Save the coding journal and derived dataset together\n', 1)[1]
            block = block.split('        run: |\n', 1)[1].split('      - uses:', 1)[0]
            script = base / 'publish.sh'
            script.write_text(''.join(line[10:]+'\n' for line in block.splitlines()))
            env = dict(os.environ, PATH=str(binpath)+os.pathsep+os.environ['PATH'],
                       RUNNER_TEMP=str(runtime), FIELDNOTES_BROWSER_CHECK='true')
            result = subprocess.run(['bash', '-e', str(script)], cwd=worker, env=env, text=True, capture_output=True)
            if conflict:
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Conflicting immutable review journal', result.stderr)
                self.assertEqual(git('rev-parse', 'main', cwd=remote), concurrent_head)
                self.assertEqual((runtime / 'fieldnotes-journal/new.json').read_text(), 'new-review\n')
            else:
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                git('merge-base', '--is-ancestor', concurrent_head, 'HEAD', cwd=worker)
                self.assertEqual(json.loads((worker / 'data/curated/retry.json').read_text()),
                                 {'code': 'new-main', 'journals': ['accepted.json', 'new.json']})
                self.assertEqual((worker / JOURNAL / 'new.json').read_text(), 'new-review\n')
                self.assertEqual(git('rev-parse', 'HEAD', cwd=worker), git('rev-parse', 'main', cwd=remote))

    def test_retry_preserves_accepted_reviews_and_concurrent_main_update(self):
        self.run_race()

    def test_conflicting_immutable_journal_stops_without_overwriting_remote(self):
        self.run_race(conflict=True)
