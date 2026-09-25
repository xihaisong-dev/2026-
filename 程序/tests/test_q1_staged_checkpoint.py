import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_q1 import fixture
from q1_staged_portfolio import save,read_selected,replay

class CheckpointTests(unittest.TestCase):
    def test_mismatch_cannot_replace_verified_fallback(self):
        with tempfile.TemporaryDirectory() as name:
            out=Path(name);p={'node_to_subgraph':{},'core_schedules':[[],[]]}
            old={'makespan':10,'data_movement_bytes':{'added_copy_bytes':0}}
            trial={'makespan':9,'data_movement_bytes':{'added_copy_bytes':0}}
            save(out,'verified',p,old);save(out,'candidate',p,trial)
            with patch('q1_staged_portfolio.context',return_value=({}, {}, {})),patch('q1_staged_portfolio.original',return_value=old):
                with self.assertRaises(RuntimeError):replay(Path('unused'),2,out,0)
            self.assertEqual(read_selected(out,'verified')[1],old)

    def test_verified_result_promoted_only_after_complete_replay(self):
        with tempfile.TemporaryDirectory() as name:
            out=Path(name);p={'node_to_subgraph':{},'core_schedules':[[],[]]}
            old={'makespan':10,'data_movement_bytes':{'added_copy_bytes':0}}
            trial={'makespan':9,'data_movement_bytes':{'added_copy_bytes':2}}
            save(out,'verified',p,old);save(out,'candidate',p,trial)
            with patch('q1_staged_portfolio.context',return_value=({}, {}, {})),patch('q1_staged_portfolio.original',return_value=trial):
                replay(Path('unused'),2,out,0)
            self.assertEqual(read_selected(out,'verified')[1],trial)

if __name__=='__main__':unittest.main()
