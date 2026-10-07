from semantic_helpers import source,policy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from semantic_memory.store import SemanticStore
from input_store import private_write,recover_deletion

class DeletionIntegrationTests(unittest.TestCase):
    def test_capture_manifest_cleans_graph_idempotently_before_finishing(self):
        with tempfile.TemporaryDirectory() as temp:
            data=Path(temp); root=data/'memory';root.mkdir()
            with_store=SemanticStore(root/'semantic.sqlite3')
            with_store.ingest(source(),policy());with_store.close()
            manifest=root/'.deletion.json'
            private_write(manifest,{'root':str(root),'data':str(data),'items':{},'session':'session','files':[],'retained_latest':None})
            recover_deletion(root)
            db=SemanticStore(root/'semantic.sqlite3')
            self.assertEqual(db.count('sources'),0);db.close()
            self.assertFalse(manifest.exists())
