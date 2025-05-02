

from nutcracker.sputm.script.opcodes import SubOpsV6, SubOpsV8
from nutcracker.sputm.script.opcodes_he import SubOpsHE100


def test_lookup() -> None:
    assert SubOpsV6.lookup(65) == 'SO_AT', SubOpsV6.lookup(65)
    assert SubOpsV8.lookup(65)  == 'SO_HEAP_LOAD_SOUND', SubOpsV8.lookup(65)
    assert SubOpsV6.lookup(255) == 'SO_END', SubOpsV6.lookup(255)
    assert SubOpsV8.lookup(201)  == 'SO_END', SubOpsV8.lookup(201)
    assert SubOpsHE100.Wait.lookup(5) == 'SO_ARRAY', SubOpsHE100.Array.lookup(5)
    assert SubOpsHE100.Wait.lookup(128) == 'SO_WAIT_FOR_ACTOR', SubOpsHE100.Wait.lookup(128)
    assert SubOpsHE100.Sound.lookup(5) == 'SO_ARRAY', SubOpsHE100.Sound.lookup(5)
    assert SubOpsHE100.Sound.lookup(128) == 'SO_SOUND_ADD', SubOpsHE100.Sound.lookup(128)
