import tempfile,unittest,sys
from unittest.mock import patch
import config,tracker

class RelaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        context=config.use_paths(self.tmp.name);context.__enter__();self.addCleanup(context.__exit__,None,None,None)
        self.tracker=tracker.Tracker(show_widget=False,trail=False)

    def test_restart_spawns_fresh_native_process_with_existing_arguments(self):
        self.tracker.after_exit='restart'
        with patch.object(sys,'argv',['/test/launch.py','start','--no-setup']),patch('tracker.subprocess.Popen') as spawn,patch('tracker.os.execv') as replace:
            self.tracker.hand_over()
        spawn.assert_called_once_with([sys.executable,'/test/launch.py','start','--no-setup'])
        replace.assert_not_called()

    def test_setup_handoff_preserves_launcher_and_dispatches_setup(self):
        self.tracker.after_exit='setup'
        with patch.object(sys,'argv',['/test/launch.py']),patch('tracker.subprocess.Popen') as spawn,patch('tracker.os.execv'):
            self.tracker.hand_over()
        spawn.assert_called_once_with([sys.executable,'/test/launch.py','setup','--again'])

    def test_open_control_reaches_main_window_without_status_item(self):
        with patch.object(self.tracker,'open_window') as show:self.tracker.apply_control({'action':'open'})
        show.assert_called_once()

    def test_permission_restart_uses_fresh_app_and_terminates_old_one(self):
        import permissions
        system=permissions.MacSystem()
        with patch.object(sys,'argv',['/test/launch.py','setup']),patch('permissions.subprocess.Popen') as spawn,patch('permissions.os.execv') as replace,patch('AppKit.NSApplication') as app:
            system.relaunch()
        spawn.assert_called_once_with([sys.executable,'/test/launch.py','setup'])
        replace.assert_not_called()
        app.sharedApplication.return_value.terminate_.assert_called_once_with(None)
