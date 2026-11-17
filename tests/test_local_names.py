import unittest
from tools.local_names import namespace_new_locals


class LocalNamesTests(unittest.TestCase):
    def test_indented_locals_parameters_and_literals(self):
        source = '''globals
sound p
integer i
endglobals
function MJ_Test takes integer i returns nothing
    local player p=Player(i)
    // p and i must stay in this comment
    call DisplayTextToPlayer(p,0,0,"p i")
    call CreateUnit(p,'p001',i,0,0)
endfunction
function original takes nothing returns nothing
set p=null
endfunction
'''
        result = namespace_new_locals(source.encode()).decode()
        self.assertIn('takes integer mjlocal_i', result)
        self.assertIn('local player mjlocal_p=Player(mjlocal_i)', result)
        self.assertIn('DisplayTextToPlayer(mjlocal_p,0,0,"p i")', result)
        self.assertIn("CreateUnit(mjlocal_p,'p001',mjlocal_i,0,0)", result)
        self.assertIn('// p and i must stay in this comment', result)
        self.assertTrue(result.endswith('function original takes nothing returns nothing\nset p=null\nendfunction\n'))
        self.assertEqual(namespace_new_locals(result.encode()), result.encode())
