DATA = set()  # type: ignore

RAWD = '____'  # Collect rest of chunk as raw data

SCHEMA = {
    'ANIM': {'AHDR', 'FRME'},
    'AHDR': DATA,
    'FRME': {'FTCH', 'IACT', 'XPAL', 'TEXT', 'STOR', 'FOBJ', 'NPAL'},
    'FTCH': DATA,
    'IACT': DATA,
    'XPAL': DATA,
    'TEXT': DATA,
    'STOR': DATA,
    'FOBJ': DATA,
    'NPAL': DATA
}
