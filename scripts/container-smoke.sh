#!/usr/bin/env bash
set -euo pipefail
# Isolated network and throwaway containers: no host port or user data is mounted.
image=${1:-localhost/ha-private-git-manager:0.2.1}
suffix="$$-$(date +%s)"
network="pgm-test-$suffix"
container="pgm-test-$suffix"
cleanup() {
  podman rm -f "$container" >/dev/null 2>&1 || true
  podman network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT
podman network create --internal --subnet 172.30.32.0/24 "$network" >/dev/null
podman run -d --name "$container" --network "$network" --ip 172.30.32.10 "$image" >/dev/null
podman run --rm -i --network "$network" --ip 172.30.32.2 --entrypoint python "$image" - <<'PY'
import json, time, urllib.request
base='http://172.30.32.10:8099/'
for attempt in range(100):
    try:
        if urllib.request.urlopen(base+'health',timeout=2).status == 200:
            break
    except OSError:
        time.sleep(.1)
else:
    raise RuntimeError('Container did not become ready')
def request(path, method='GET', payload=None):
    data=json.dumps(payload).encode() if payload is not None else None
    req=urllib.request.Request(base+path,data=data,method=method,headers={'X-PGM-Request':'1','Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=5) as response:
        return response.read()
assert b'static/app.js' in request('')
assert json.loads(request('api/state'))['version']=='0.2.1'
for lang in ['es','en']:
    assert json.loads(request('static/locales/'+lang+'.json'))['install']
key=json.loads(request('api/keys','POST',{'name':'Isolated container smoke test'}))
assert key['public'].startswith('ssh-ed25519 ')
repo=json.loads(request('api/repos','POST',{'name':'Isolated HTTPS test','url':'https://example.org/owner/repo.git','ref':'main','token':'smoke-only-token'}))
assert b'smoke-only-token' not in request('api/state')
assert b'SSH key created.' in request('api/logs?language=en&download=true')
request('api/repos/'+repo['id'],'DELETE')
request('api/keys/'+key['id'],'DELETE')
print('PASS: real Ingress source IP, assets, languages, private keys, token redaction and logs')
PY
podman run --rm -i --network "$network" --ip 172.30.32.4 --entrypoint python "$image" - <<'PY'
import urllib.request, urllib.error
request=urllib.request.Request('http://172.30.32.10:8099/api/state',headers={'X-Forwarded-For':'172.30.32.2'})
try:
    urllib.request.urlopen(request,timeout=5)
except urllib.error.HTTPError as error:
    assert error.code==403
else:
    raise AssertionError('Non-Ingress request was accepted')
print('PASS: non-Ingress traffic denied, spoofed forwarding header ignored')
PY
podman exec "$container" python -c "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8099/health').status==200; print('PASS: container health check')"
