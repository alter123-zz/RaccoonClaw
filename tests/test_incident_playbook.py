import pathlib
import sys

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from incident_playbook import build_incident_summary, classify_incident


def test_delivery_failed_maps_to_high_severity():
    payload = classify_incident(
        {
            'status': 'critical',
            'lastDeliveryStatus': 'failed',
            'lastRunStatus': 'success',
            'consecutiveErrors': 0,
            'intervalMs': 900000,
            'channel': 'imessage',
            'target': 'anthappy@126.com',
        },
        now_ms=1_000_000,
    )
    assert payload is not None
    assert payload['severity'] == 'sev1'
    assert payload['ownerDept'] == '交付运营部'


def test_incident_summary_picks_highest_priority_job():
    jobs = [
        {
            'id': 'a',
            'name': '任务A',
            'incident': {
                'severity': 'sev3',
                'severityLabel': 'SEV-3',
                'tone': 'warn',
                'label': '计划超时',
                'summary': 'A',
                'ownerDept': '总裁办',
                'steps': ['x'],
                'nextUpdateBy': '2026-03-13T00:00:00Z',
            },
        },
        {
            'id': 'b',
            'name': '任务B',
            'incident': {
                'severity': 'sev1',
                'severityLabel': 'SEV-1',
                'tone': 'err',
                'label': '投递链路失败',
                'summary': 'B',
                'ownerDept': '交付运营部',
                'steps': ['y'],
                'nextUpdateBy': '2026-03-13T00:00:00Z',
            },
        },
    ]
    payload = build_incident_summary(jobs, now_ms=1_000_000)
    assert payload is not None
    assert payload['severity'] == 'sev1'
    assert payload['title'] == '投递链路失败'
