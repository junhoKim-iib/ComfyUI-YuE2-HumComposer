import re

NAMES = ('C','C#','D','Eb','E','F','F#','G','Ab','A','Bb','B')
NATURAL = {'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}
SCALES = {
    'major': (0,2,4,5,7,9,11), 'minor': (0,2,3,5,7,8,10),
    'dorian': (0,2,3,5,7,9,10), 'phrygian': (0,1,3,5,7,8,10),
    'lydian': (0,2,4,6,7,9,11), 'mixolydian': (0,2,4,5,7,9,10),
    'locrian': (0,1,3,5,6,8,10),
}


def normalize_mode(mode: str) -> str:
    value = mode.strip().lower()
    value = {'ionian':'major','aeolian':'minor'}.get(value, value)
    if value not in SCALES:
        raise ValueError(f'Unsupported mode {mode!r}')
    return value


def pitch_class(name: str) -> int:
    match = re.fullmatch(r'([A-Ga-g])([#b]{0,2})', name.strip())
    if not match:
        raise ValueError(f'Invalid pitch name {name!r}')
    return (NATURAL[match[1].upper()] + match[2].count('#') - match[2].count('b')) % 12


def degree_name(tonic: str, mode: str, degree: int) -> str:
    letter = 'CDEFGAB'[('CDEFGAB'.index(tonic[0].upper()) + degree) % 7]
    pc = (pitch_class(tonic) + SCALES[normalize_mode(mode)][degree]) % 12
    shift = (pc - NATURAL[letter] + 6) % 12 - 6
    if abs(shift) > 2:
        raise ValueError('Chord spelling would require more than a double accidental')
    return letter + ('#' * shift if shift > 0 else 'b' * -shift)
