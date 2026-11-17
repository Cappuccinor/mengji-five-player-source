import math
from pathlib import Path
import unittest
from tests.progress_harness import progress_environment

ROOT=Path(__file__).resolve().parents[1]

class ProgressTransferTests(unittest.TestCase):
    def environment(self):
        transfer=ROOT/'src/progress_transfer.j';self.assertTrue(transfer.exists(),'synchronized progress transfer missing')
        return progress_environment('\n'.join((ROOT/path).read_text(encoding='utf8') for path in ['src/progress_schema.j','src/progress.j','src/progress_transfer.j']))

    def test_chunk_reorder_duplicates_and_complete_apply_preserve_player_boundary(self):
        e=self.environment();e['MJ_SetInt'](0,'SCORE',456);code=e['MJ_ExportProgress'](0)
        parts=[code[i:i+96] for i in range(0,len(code),96)]
        for i in reversed(range(len(parts))):self.assertTrue(e['MJ_ReceiveProgressChunk'](5,i,len(parts),parts[i]))
        self.assertTrue(e['MJ_ReceiveProgressChunk'](5,0,len(parts),parts[0]))
        self.assertTrue(e['MJ_IsProgressImportPending'](5));self.assertEqual(e['MJ_GetInt'](5,'SCORE'),0)
        self.assertTrue(e['MJ_ApplyProgressTransfer'](5));self.assertEqual(e['MJ_GetInt'](5,'SCORE'),456)
        self.assertFalse(e['MJ_IsProgressImportPending'](5));self.assertEqual(e['MJ_GetInt'](1,'SCORE'),0)

    def test_incomplete_conflicting_and_invalid_packets_do_not_apply_or_erase_progress(self):
        e=self.environment();e['MJ_SetInt'](0,'SCORE',99);code=e['MJ_ExportProgress'](0)
        parts=[code[i:i+96] for i in range(0,len(code),96)]
        self.assertTrue(e['MJ_ReceiveProgressChunk'](0,0,len(parts),parts[0]))
        self.assertFalse(e['MJ_ApplyProgressTransfer'](0));self.assertEqual(e['MJ_GetInt'](0,'SCORE'),99)
        self.assertFalse(e['MJ_ReceiveProgressChunk'](0,0,len(parts),'X'*96))
        self.assertFalse(e['MJ_ReceiveProgressChunk'](0,-1,len(parts),'X'))
        self.assertFalse(e['MJ_ReceiveProgressChunk'](0,0,44,'X'*96))
        self.assertFalse(e['MJ_ReceiveProgressChunk'](4,0,1,'X'))
        e['MJ_CancelProgressTransfer'](0);self.assertFalse(e['MJ_AnyProgressImportPending']())
        self.assertEqual(e['MJ_GetInt'](0,'SCORE'),99)

    def test_lock_rejects_packets_and_pending_imports_but_leaving_can_cancel(self):
        e=self.environment();code=e['MJ_ExportProgress'](0);parts=[code[i:i+96] for i in range(0,len(code),96)]
        self.assertTrue(e['MJ_ReceiveProgressChunk'](5,0,len(parts),parts[0]));self.assertTrue(e['MJ_AnyProgressImportPending']())
        e['MJ_LockProgress']();self.assertFalse(e['MJ_ReceiveProgressChunk'](5,0,len(parts),parts[0]))
        self.assertFalse(e['MJ_ApplyProgressTransfer'](5));e['MJ_CancelProgressTransfer'](5)
        self.assertFalse(e['MJ_AnyProgressImportPending']())

    def test_actual_chat_commands_export_and_restore_a_fresh_game(self):
        chat=ROOT/'src/progress_chat.j';self.assertTrue(chat.exists(),'progress chat flow missing')
        from tools.progress_schema import progress_module
        code=progress_module()+'\n'+(ROOT/'src/selection_state.j').read_text(encoding='utf8')+'\n'+chat.read_text(encoding='utf8')
        def new_game(player):
            e=progress_environment(code);messages=[];message=['']
            e.update(MJ_AllHeroMode=False,MJ_RefreshSelectionUI=lambda:None,GetTriggerPlayer=lambda:player,
                GetEventPlayerChatString=lambda:message[0],DisplayTimedTextToPlayer=lambda p,x,y,t,text:messages.append(text))
            return e,messages,message
        e,messages,message=new_game(0);e['MJ_SetInt'](0,'SCORE',200)
        message[0]='-mjsave';e['MJ_OnProgressChat']()
        packets=[m for m in messages if m.startswith('-mjload ')];self.assertGreater(len(packets),0)
        self.assertTrue(all(len(packet)<127 for packet in packets))
        e2,m2,msg2=new_game(5)
        for packet in packets:msg2[0]=packet;e2['MJ_OnProgressChat']()
        self.assertTrue(e2['MJ_IsProgressImportPending'](5));self.assertEqual(e2['MJ_GetInt'](5,'SCORE'),0)
        msg2[0]='-mjapply';e2['MJ_OnProgressChat']()
        self.assertEqual(e2['MJ_GetInt'](5,'SCORE'),200);self.assertFalse(e2['MJ_IsProgressImportPending'](5))

    def test_import_packet_cancels_ready_and_pending_player_cannot_start_game(self):
        chat=ROOT/'src/progress_chat.j';self.assertTrue(chat.exists(),'progress chat flow missing')
        from tools.progress_schema import progress_module
        code=progress_module()+'\n'+(ROOT/'src/selection_state.j').read_text(encoding='utf8')+'\n'+chat.read_text(encoding='utf8')
        e=progress_environment(code);e.update(MJ_AllHeroMode=True,GetTriggerPlayer=lambda:5,
            MJ_RefreshSelectionUI=lambda:None,DisplayTimedTextToPlayer=lambda *a:None)
        e['MJ_SelectState']=1;e['MJ_Present'][4]=True;e['MJ_Ready'][4]=True;e['MJ_Chosen'][4]=123
        data=e['MJ_ExportProgress'](5);first=data[:96];total=math.ceil(len(data)/96)
        e['GetEventPlayerChatString']=lambda:'-mjload 1/'+str(total)+' '+first
        e['MJ_OnProgressChat']();self.assertFalse(e['MJ_Ready'][4]);self.assertEqual(e['MJ_SelectState'],1)

    def test_import_refreshes_only_unconfirmed_host_difficulty_menu(self):
        from tools.progress_schema import progress_module
        e=progress_environment(progress_module()+(ROOT/'src/progress_chat.j').read_text(encoding='utf8'))
        buttons=[];shown=[];enabled=[True];selected=[0];load=e['LoadInteger']
        e.update(GM=1,Fq=2,Fa=3,GI={},DI='game',Player=lambda p:p,IsTriggerEnabled=lambda t:enabled[0],
            LoadInteger=lambda t,p,k:selected[0] if t=='game' else load(t,p,k),CountPlayersInForceBJ=lambda f:5,
            DialogClear=lambda d:buttons.clear(),DialogSetMessage=lambda *a:None,
            DialogAddButtonBJ=lambda d,t:buttons.append(t),GetLastCreatedButtonBJ=lambda:len(buttons),
            EnableTrigger=lambda t:None,DialogDisplayBJ=lambda show,d,p:shown.append((show,d,p)))
        e['MJ_SetInt'](0,'GG',10)
        e['MJ_RefreshProgressDifficulty'](0)
        self.assertEqual(len(buttons),10);self.assertEqual(shown,[(True,2,0)])
        self.assertTrue(e['MJ_ProgressDifficultyGrace'])
        enabled[0]=False;e['MJ_RefreshProgressDifficulty'](0);self.assertEqual(len(shown),1)
        enabled[0]=True;selected[0]=1;e['MJ_RefreshProgressDifficulty'](0);self.assertEqual(len(shown),1)
        selected[0]=0;e['MJ_RefreshProgressDifficulty'](5);self.assertEqual(len(shown),1)
