from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


def test_daily_wrapper_collects_three_orgs_for_previous_seoul_day(tmp_path: Path) -> None:
    wrapper = tmp_path / 'run-daily.sh'
    wrapper.write_text(Path('run-daily.sh').read_text())
    executable = tmp_path / '.venv/bin/commitpoem'
    executable.parent.mkdir(parents=True)
    executable.write_text('#!/bin/bash\nprintf "%s\\n" "$@"\n')
    executable.chmod(0o755)
    now = datetime.now(ZoneInfo('Asia/Seoul'))
    run = subprocess.run(['bash', str(wrapper)], env={**os.environ, 'TZ': 'UTC',
                         'COMMITPOEM_LOCAL_ROOTS': str(tmp_path)}, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    args = run.stdout.splitlines()
    assert args[args.index('--local-root') + 1] == str(tmp_path)
    assert '--update-main' in args
    assert [args[i + 1] for i, value in enumerate(args) if value == '--org'] == [
        'qo-kr', 'genideas-secure-labs', 'k-gen-food',
    ]
    since = datetime.fromisoformat(args[args.index('--since') + 1])
    until = datetime.fromisoformat(args[args.index('--until') + 1])
    assert since.utcoffset() == timedelta(hours=9)
    assert since.date() == now.date() - timedelta(days=1)
    assert since.hour == 0 and until.hour == 23 and until.minute == 59 and until.second == 59
    assert until - since == timedelta(days=1, seconds=-1)
