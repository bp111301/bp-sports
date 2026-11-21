"""Exercise the dispatch decision with a fake GitHub CLI; no workflow runs start."""
from pathlib import Path
import subprocess

import pytest

WORKFLOW=Path('.github/workflows/final_grading_watchdog.yml').read_text()
FUNCTION=WORKFLOW.split('          dispatch_if_due() {',1)[1].split('          for ((check=',1)[0]
FUNCTION='dispatch_if_due() {'+FUNCTION

def dispatch_result(status,age,workflow='game_status.yml',max_age=900):
    import os
    script=FAKE_GH+FUNCTION+f'\ndispatch_if_due {workflow} {max_age}\n'
    return subprocess.run(['bash','-c',script],env={**os.environ,'FAKE_STATUS':status,'FAKE_AGE':str(age),'GITHUB_REPOSITORY':'owner/repo'},capture_output=True,text=True,check=True)


FAKE_GH='''
  gh() {
    if [[ "$2" == --method ]]; then echo "DISPATCHED:$4"; return; fi
    if [[ "$FAKE_STATUS" == api_error ]]; then return 1; fi
    if [[ "$FAKE_STATUS" == missing ]]; then echo missing; return; fi
    printf '%s\\t%s\\n' "$FAKE_STATUS" "$(date -u -d "@$(( $(date -u +%s) - FAKE_AGE ))" +%FT%TZ)"
  }
'''


@pytest.mark.parametrize('status,age,dispatch',[
    ('completed',1200,True),('completed',600,False),('in_progress',1200,False),
    ('queued',1200,False),('missing',0,True),('api_error',1200,False),
])
def test_score_watchdog_restarts_overdue_runs_without_duplicate_dispatches(status,age,dispatch):
    result=dispatch_result(status,age)
    assert ('DISPATCHED' in result.stdout)==dispatch


@pytest.mark.parametrize('workflow,max_age',[('nhl_research_ledger.yml',43200),('cbb_prospective.yml',21600)])
@pytest.mark.parametrize('state,fresh,expected',[('completed',True,False),('completed',False,True),('in_progress',False,False),('queued',False,False)])
def test_producer_refreshes_are_overdue_only_and_do_not_cancel_active_work(workflow,max_age,state,fresh,expected):
    result=dispatch_result(state,3600 if fresh else max_age+3600,workflow,max_age)
    assert ('DISPATCHED' in result.stdout)==expected
    if expected:assert 'repos/owner/repo/actions/workflows/'+workflow+'/dispatches' in result.stdout
