from icloud_photos.fib import fib

def test_fib():
    assert fib(1) == 1
    assert fib(2) == 1
    assert fib(3) == 2
    assert fib(4) == 3
    assert fib(5) == 5


def test_fib_bad_input():
    assert fib(0) == -1
    assert fib(-34) == -1
