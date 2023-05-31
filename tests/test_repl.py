from datadm.repl import REPL


def test_exec():
    repl = REPL()
    out = repl.exec("print('hi')")
    assert 'hi' in out['stdout']
