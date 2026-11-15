"""Exercise the dispatch decision with a fake GitHub CLI; no workflow runs start."""
from pathlib import Path
import subprocess

import pytest

WORKFLOW=Path('.github/workflows/final_grading_watchdog.yml').read_text()
FUNCTION=WORKFLOW.split('          dispatch_if_due() {',1)[1].split('          for ((check=',1)[0]
FUNCTION='dispatch_if_due() {'+FUNCTION

@pytest.mark.parametrize('status,age,dispatch',[
    ('completed',1200,True),('completed',600,False),('in_progress',1200,False),
    ('queued',1200,False),('missing',0,True),('api_error',1200,False),
])
def test_score_watchdog_restarts_overdue_runs_without_duplicate_dispatches(status,age,dispatch):
    script='''
      gh() {
        if [[ "$2" == --method ]]; then echo DISPATCHED; return; fi
        if [[ "$FAKE_STATUS" == api_error ]]; then return 1; fi
        if [[ "$FAKE_STATUS" == missing ]]; then echo missing; return; fi
        printf '%s\\t%s\\n' "$FAKE_STATUS" "$(date -u -d "@$(( $(date -u +%s) - FAKE_AGE ))" +%FT%TZ)"
      }
    '''+FUNCTION+'\ndispatch_if_due game_status.yml 900\n'
    import os
    result=subprocess.run(['bash','-c',script],env={**os.environ,'FAKE_STATUS':status,'FAKE_AGE':str(age),'GITHUB_REPOSITORY':'owner/repo'},capture_output=True,text=True,check=True)
    assert ('DISPATCHED' in result.stdout)==dispatch
