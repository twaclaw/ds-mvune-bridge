from src import dstiny


def test_calculate_answer():
    Tel = dstiny.dSTel('g', 1, [0x07, 3, 0x00])
    res = 'g107030031\r\n'
    assert res == Tel.get()

