"""Explicit repository layouts and source-only candidate reconstruction."""
import difflib
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepositoryLayout:
    vendor: str
    source: str
    imports: str


LAYOUTS = {
    'https://github.com/psf/requests': RepositoryLayout('requests', 'requests', '.'),
    'https://github.com/pallets/click': RepositoryLayout('click', 'src/click', 'src'),
}


def repository_layout(repository):
    try:
        return LAYOUTS[repository]
    except (KeyError, TypeError):
        raise ValueError('Repository is not registered') from None


def reconstruct_candidate(base: Path, exported: Path, candidate: Path, layout: RepositoryLayout) -> str:
    """Use the clean base, overlay only existing package Python files, return diff."""
    if layout not in LAYOUTS.values():
        raise ValueError('Unregistered source layout')
    if exported.is_symlink():
        raise ValueError('Linked export root rejected')
    originals = sorted((base / layout.source).rglob('*.py'))
    if not originals:
        raise ValueError('No allowed source files')
    checked = []
    for original in originals:
        relative = original.relative_to(base)
        source = exported
        for part in relative.parts:
            source = source / part
            if source.is_symlink():
                raise ValueError('Linked exported source rejected')
        if not source.is_file():
            raise ValueError('Missing allowed source file')
        checked.append((original, source, relative))
    shutil.copytree(base, candidate)
    patches = []
    for original, source, relative in checked:
        shutil.copyfile(source, candidate / relative)
        patches.extend(difflib.unified_diff(original.read_text(encoding='utf-8').splitlines(True),
            source.read_text(encoding='utf-8').splitlines(True),
            fromfile='a/' + relative.as_posix(), tofile='b/' + relative.as_posix()))
    return ''.join(patches)
