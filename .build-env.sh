#!/usr/bin/env bash
# Sandbox one-click rebuild script: restores the full environment after the sandbox is reset and rebuilds the dm driver.
# After the platform reset, everything except /workspace is lost (clojure/metabase source/m2 cache/mirror service),
# and /workspace/target is excluded by .gitignore, so it is also lost. This script rebuilds all of it in one go,
# with the output jar placed in /workspace/dist/ (survives the reset).
# Usage: bash /workspace/.build-env.sh 2>&1 | tail -30
set -euo pipefail

DRIVER_PATH=/workspace
MB=/data/metabase
DIST=$DRIVER_PATH/dist
OUT_JAR=$DIST/dm.metabase-driver.jar
MB_TAG=v0.65.2.2

mkdir -p "$DIST"

# 1. Clojure CLI
if ! command -v clojure >/dev/null; then
  echo "[1/5] installing clojure CLI..."
  cd /tmp
  curl -sfO https://download.clojure.org/install/linux-install-1.11.1.1403.sh
  chmod +x linux-install-1.11.1.1403.sh
  ./linux-install-1.11.1.1403.sh >/tmp/clojure-install.log 2>&1
else
  echo "[1/5] clojure OK"
fi

# 2. metabase source
if [ ! -f "$MB/deps.edn" ]; then
  echo "[2/5] cloning metabase $MB_TAG..."
  rm -rf "$MB"
  git clone --depth 1 --branch "$MB_TAG" https://github.com/metabase/metabase.git "$MB"
else
  echo "[2/5] metabase OK"
fi

# 3. local maven mirror
if ! ss -ltn | grep -q ":8897"; then
  echo "[3/5] starting maven mirror :8897..."
  cat > /tmp/maven-mirror.py << 'PYEOF'
#!/usr/bin/env python3
import os, sys, threading, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
UPSTREAMS = sys.argv[2:]; CACHE = "/tmp/m2-cache"
PROXY = "http://127.0.0.1:18080"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({"http": PROXY, "https": PROXY}))
os.makedirs(CACHE, exist_ok=True); LOCK = threading.Lock()
def fetch(upstream, path):
    with OPENER.open(urllib.request.Request(upstream.rstrip("/") + path), timeout=60) as r:
        return r.read()
class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def do_HEAD(self): self._h()
    def do_GET(self): self._h()
    def _h(self):
        path = self.path.split("?")[0]
        fp = os.path.join(CACHE, path.lstrip("/"))
        with LOCK:
            if os.path.exists(fp):
                return self._serve(fp)
            for up in UPSTREAMS:
                try: data = fetch(up, path)
                except Exception: continue
                os.makedirs(os.path.dirname(fp), exist_ok=True)
                open(fp + ".tmp", "wb").write(data); os.replace(fp + ".tmp", fp)
                return self._serve(fp)
        self.send_error(404)
    def _serve(self, fp):
        data = open(fp, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command == "GET": self.wfile.write(data)
    def log_message(self, *a): pass
ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
PYEOF
  nohup python3 /tmp/maven-mirror.py 8897 \
    https://maven.aliyun.com/repository/public \
    https://repo.clojars.org \
    https://repo1.maven.org/maven2 \
    https://build.shibboleth.net/maven/releases \
    >/tmp/maven-mirror.log 2>&1 &
  sleep 1
else
  echo "[3/5] mirror OK"
fi

# 4. settings.xml + shib preseeding (shib POM declares internal repo, mirror unreliable, curl fallback works)
echo "[4/5] settings.xml + shib preseed..."
mkdir -p /root/.m2
cat > /root/.m2/settings.xml << 'XMLEOF'
<?xml version="1.0" encoding="UTF-8"?>
<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0">
  <mirrors>
    <mirror><id>local-mirror</id><mirrorOf>*</mirrorOf><url>http://127.0.0.1:8897</url></mirror>
  </mirrors>
</settings>
XMLEOF
R=/root/.m2/repository; S=https://build.shibboleth.net/maven/releases
for c in \
  net/shibboleth/parent/11.3.1/parent-11.3.1.pom \
  net/shibboleth/utilities/java-support/8.3.1/java-support-8.3.1 \
  net/shibboleth/ext/spring-extensions/6.2.0/spring-extensions-6.2.0 \
  org/opensaml/opensaml-core/4.2.0/opensaml-core-4.2.0 \
  org/opensaml/opensaml-profile-api/4.2.0/opensaml-profile-api-4.2.0 \
  org/opensaml/opensaml-profile-impl/4.2.0/opensaml-profile-impl-4.2.0 \
  org/opensaml/opensaml-messaging-api/4.2.0/opensaml-messaging-api-4.2.0 \
  org/opensaml/opensaml-messaging-impl/4.2.0/opensaml-messaging-impl-4.2.0 \
  org/opensaml/opensaml-security-api/4.2.0/opensaml-security-api-4.2.0 \
  org/opensaml/opensaml-security-impl/4.2.0/opensaml-security-impl-4.2.0 \
  org/opensaml/opensaml-saml-api/4.2.0/opensaml-saml-api-4.2.0 \
  org/opensaml/opensaml-saml-impl/4.2.0/opensaml-saml-impl-4.2.0 \
  org/opensaml/opensaml-soap-api/4.2.0/opensaml-soap-api-4.2.0 \
  org/opensaml/opensaml-storage-api/4.2.0/opensaml-storage-api-4.2.0 \
  org/opensaml/opensaml-xmlsec-api/4.2.0/opensaml-xmlsec-api-4.2.0 \
  org/opensaml/opensaml-xmlsec-impl/4.2.0/opensaml-xmlsec-impl-4.2.0 ; do
  for ext in pom jar; do
    f="$R/$c.$ext"; [[ "$c" == *.pom ]] && break
    [ -f "$f" ] && continue
    mkdir -p "$(dirname "$f")"
    curl -sf --max-time 60 -o "$f" "$S/$c.$ext" || true
  done
done
for p in io/dropwizard/metrics/metrics-bom/4.2.9/metrics-bom-4.2.9.pom \
         org/springframework/spring-framework-bom/5.3.19/spring-framework-bom-5.3.19.pom ; do
  f="$R/$p"; [ -f "$f" ] && continue
  mkdir -p "$(dirname "$f")"
  curl -sf --max-time 60 -o "$f" "https://maven.aliyun.com/repository/public/$p" || true
done

# 5. Build (full dependency download on first run, ~15-20 minutes; ~2 minutes when cache is warm)
echo "[5/5] building dm driver..."
cd "$MB"
clojure -Sdeps "{:aliases {:dm {:extra-deps {com.metabase/dm-driver {:local/root \"$DRIVER_PATH\"}}}}}" \
  -X:build:dm build-drivers.build-driver/build-driver! \
  "{:driver :dm, :project-dir \"$DRIVER_PATH\", :target-dir \"$DRIVER_PATH/target\"}" \
  2>&1 | tee /tmp/dm-build.log | tail -5

cp "$DRIVER_PATH/target/dm.metabase-driver.jar" "$OUT_JAR"
echo "BUILD_OK $OUT_JAR ($(du -h "$OUT_JAR" | cut -f1))"
