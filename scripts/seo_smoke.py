"""Read-only live crawl, durable report and fresh-process readback. Never starts Jarvis workers."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
parser = argparse.ArgumentParser()
parser.add_argument('--site', choices=['panther', 'shopify', 'public_control'], required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if not os.getenv('DATABASE_PATH'):
    parser.error('Set DATABASE_PATH to an isolated smoke-test database, never production')
from app223 import seo
if args.site == 'public_control':
    # A known public technical-documentation control, only in this standalone process.
    # Production tool/API still accepts Panther and Shopify only.
    seo.SITES['public_control'] = 'https://developers.google.com'
result = seo.run_audit(args.site, max_pages=2)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, indent=2)+'\n')
code = "from app223 import seo; "
if args.site == 'public_control': code += "seo.SITES['public_control']='https://developers.google.com'; "
code += f"import json; print(json.dumps(seo.latest_report({args.site!r},{result['report_id']})))"
saved=json.loads(subprocess.check_output([sys.executable,'-c',code], text=True, env=os.environ))
assert saved['report'] == result['report'], 'Fresh-process persisted report differs'
print(json.dumps({'site':args.site, 'state':result['report']['state'], 'pages':len(result['report']['pages']), 'report_id':result['report_id'], 'fresh_process_readback':True, 'output':str(args.output)}))
