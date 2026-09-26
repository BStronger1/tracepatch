import tempfile
import unittest
from pathlib import Path
from tracepatch.repositories import repository_layout, reconstruct_candidate, RepositoryLayout


class RepositoryTests(unittest.TestCase):
    def test_registered_layouts_and_unknown_repository(self):
        self.assertEqual(repository_layout('https://github.com/psf/requests').source, 'requests')
        self.assertEqual(repository_layout('https://github.com/pallets/click').source, 'src/click')
        for value in ('../../private', 'https://example.invalid/repo', None):
            with self.assertRaises(ValueError):
                repository_layout(value)

    def test_only_existing_python_sources_are_exported_for_both_layouts(self):
        for repo in ('https://github.com/psf/requests', 'https://github.com/pallets/click'):
            with self.subTest(repo=repo), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                base, exported, candidate = (root/n for n in ('base','exported','candidate'))
                layout = repository_layout(repo)
                for folder in (base, exported):
                    (folder/layout.source).mkdir(parents=True)
                    (folder/layout.source/'core.py').write_text('old\n' if folder==base else 'new\n')
                    (folder/'tests.py').write_text('original test' if folder==base else 'tampered test')
                (base/layout.source/'data.txt').write_text('original data')
                (exported/layout.source/'data.txt').write_text('tampered data')
                (exported/layout.source/'extra.py').write_text('unapproved new file')
                patch = reconstruct_candidate(base,exported,candidate,layout)
                self.assertEqual((candidate/layout.source/'core.py').read_text(),'new\n')
                self.assertEqual((candidate/'tests.py').read_text(),'original test')
                self.assertEqual((candidate/layout.source/'data.txt').read_text(),'original data')
                self.assertFalse((candidate/layout.source/'extra.py').exists())
                self.assertIn('a/'+layout.source+'/core.py',patch)

    def test_missing_files_and_unregistered_paths_fail_before_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            base,exported,candidate=(root/n for n in ('base','exported','candidate'))
            (base/'requests').mkdir(parents=True)
            (base/'requests/core.py').write_text('original')
            exported.mkdir()
            with self.assertRaisesRegex(ValueError,'Missing'):
                reconstruct_candidate(base,exported,candidate,repository_layout('https://github.com/psf/requests'))
            self.assertFalse(candidate.exists())
            with self.assertRaisesRegex(ValueError,'Unregistered'):
                reconstruct_candidate(base,exported,candidate,RepositoryLayout('x','../outside','.'))

    def test_linked_exports_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            base,exported,candidate=(root/n for n in ('base','exported','candidate'))
            (base/'requests').mkdir(parents=True)
            (exported/'requests').mkdir(parents=True)
            (base/'requests/core.py').write_text('original')
            outside=root/'outside.py'
            outside.write_text('must not copy')
            try:
                (exported/'requests/core.py').symlink_to(outside)
            except OSError:
                self.skipTest('Symbolic link creation is unavailable on this host')
            with self.assertRaisesRegex(ValueError,'Linked'):
                reconstruct_candidate(base,exported,candidate,repository_layout('https://github.com/psf/requests'))
            self.assertFalse(candidate.exists())
