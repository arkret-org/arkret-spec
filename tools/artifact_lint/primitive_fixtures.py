"""Close named primitive inputs, byte encodings, digests and signatures."""
from .core import ARTIFACTS, Lint, load_json
from ..regenerate_named_primitive_fixtures import NAMES, build


def check_named_primitive_fixtures(lint: Lint) -> None:
    for name in NAMES:
        path = ARTIFACTS / 'fixtures' / name
        source = load_json(lint, path)
        if not isinstance(source, dict):
            continue
        if build(name, source) != source:
            lint.fail(path, 'named primitive inputs/bytes/digests/signatures drift; regenerate from source inputs')
