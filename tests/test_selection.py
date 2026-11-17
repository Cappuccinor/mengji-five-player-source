from pathlib import Path
import unittest
from tests.jass_subset import execute

ROOT=Path(__file__).resolve().parents[1]


class SelectionTests(unittest.TestCase):
    def setUp(self):
        path=ROOT/'src/selection_state.j'
        self.assertTrue(path.exists(),'Selection implementation is missing')
        self.e=execute(path.read_text(encoding='utf8'))
        self.call('MJ_ResetSelection')
        # Three legitimate fixture hero ids; catalog generation has separate tests.
        self.e['MJ_HeroCount']=3
        for i,hero in enumerate([100,200,300]):
            self.e['MJ_HeroIds'][i]=hero

    def call(self,name,*args):
        return self.e[name](*args)

    def begin(self,count):
        for i in range(count):
            self.call('MJ_JoinSelection',i)
        self.call('MJ_BeginSelection')

    def test_all_five_required_and_start_once(self):
        self.e['MJ_HeroCount']=5
        self.e['MJ_HeroIds'][3]=400
        self.e['MJ_HeroIds'][4]=500
        self.begin(5)
        for i in range(4):
            self.assertTrue(self.call('MJ_ConfirmHero',i,(i+1)*100))
        self.assertEqual(self.e['MJ_SelectState'],1)
        self.assertTrue(self.call('MJ_ConfirmHero',4,500))
        self.assertEqual(self.e['MJ_SelectState'],2)
        self.assertEqual(self.e['MJ_StartRequests'],1)
        self.assertFalse(self.call('MJ_ConfirmHero',4,500))
        self.call('MJ_TryStart')
        self.assertEqual(self.e['MJ_StartRequests'],1)

    def test_same_hero_conflict_cancel_releases(self):
        self.begin(3)
        self.assertTrue(self.call('MJ_ConfirmHero',0,100))
        self.assertFalse(self.call('MJ_ConfirmHero',1,100))
        self.assertFalse(self.e['MJ_Ready'][1])
        self.assertTrue(self.call('MJ_CancelReady',0))
        self.assertTrue(self.call('MJ_ConfirmHero',1,100))

    def test_missing_player_leaves_and_remaining_ready_start(self):
        self.begin(2)
        self.call('MJ_ConfirmHero',0,100)
        self.call('MJ_LeaveSelection',1)
        self.assertEqual(self.e['MJ_SelectState'],2)
        self.assertEqual(self.e['MJ_StartRequests'],1)

    def test_no_players_never_start(self):
        self.begin(0)
        self.call('MJ_TryStart')
        self.assertEqual(self.e['MJ_StartRequests'],0)

    def test_invalid_sender_or_hero_cannot_ready(self):
        self.begin(2)
        for sender,hero in [(-1,100),(5,100),(2,100),(0,999),(0,0)]:
            self.assertFalse(self.call('MJ_ConfirmHero',sender,hero))
        self.assertEqual(self.e['MJ_StartRequests'],0)

    def test_late_cancel_after_start_is_rejected(self):
        self.begin(1)
        self.call('MJ_ConfirmHero',0,100)
        self.assertFalse(self.call('MJ_CancelReady',0))
        self.assertEqual(self.e['MJ_Chosen'][0],100)

    def test_waiting_does_not_assign_or_start(self):
        self.begin(3)
        for _ in range(900):
            self.call('MJ_TryStart')
        self.assertEqual(self.e['MJ_StartRequests'],0)
        self.assertEqual([self.e['MJ_Chosen'][i] for i in range(3)],[0,0,0])

    def test_leaver_releases_lock_while_selection_still_pending(self):
        self.begin(3)
        self.call('MJ_ConfirmHero',0,100)
        self.call('MJ_LeaveSelection',0)
        self.assertTrue(self.call('MJ_ConfirmHero',1,100))
        self.assertEqual(self.e['MJ_SelectState'],1)

    def test_leave_after_start_does_not_erase_locked_initialization_choice(self):
        self.begin(1)
        self.call('MJ_ConfirmHero',0,100)
        self.call('MJ_LeaveSelection',0)
        self.assertEqual(self.e['MJ_Chosen'][0],100)
        self.assertEqual(self.e['MJ_StartRequests'],1)
