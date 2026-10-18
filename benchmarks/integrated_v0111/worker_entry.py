"""Launch unchanged CAAIF worker with benchmark instrumentation activated."""
import runpy
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from benchmarks.integrated_v0111.operation_meter import install
install()
role,port = sys.argv[1:]
sys.argv=[str(ROOT/'examples/http_agent_worker.py'), role, port]
runpy.run_path(str(ROOT/'examples/http_agent_worker.py'),run_name='__main__')
