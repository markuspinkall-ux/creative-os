#!/bin/bash
# Probe: lokale KI für das KI-Widget (Fedora-Pakete, Modelle auf Hugging Face, llama.cpp-Releases)
set +e
for p in llama-cpp ollama; do echo "== dnf info $p"; dnf info -q "$p" 2>&1 | head -20; done
dnf install -y -q llama-cpp >/dev/null 2>&1 && { rpm -ql llama-cpp | grep bin/; ldd /usr/bin/llama-server | grep -i -E "vulkan|cuda|hip|blas"; rpm -q --requires llama-cpp | head -30; }
dnf repoquery -q 'llama-cpp*' 2>&1 | head
echo "== HF Gemma 4"
curl -s "https://huggingface.co/api/models?author=google&search=gemma-4&limit=50" | python3 -c "import sys,json; [print(m['id']) for m in json.load(sys.stdin)]"
curl -s "https://huggingface.co/api/models?author=ggml-org&search=gemma-4&limit=50" | python3 -c "import sys,json; [print(m['id']) for m in json.load(sys.stdin)]"
for r in google/gemma-4-12B-it-qat-q4_0-gguf google/gemma-4-12b-it-qat-q4_0-gguf ggml-org/gemma-4-E4B-it-GGUF ggml-org/gemma-4-E2B-it-GGUF ggml-org/gemma-4-12B-it-GGUF unsloth/gemma-4-12B-it-GGUF; do
  echo "== $r"; curl -s "https://huggingface.co/api/models/$r?blobs=true" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('gated',d.get('gated'),'license',[t for t in d.get('tags',[]) if t.startswith('license')])
for s in d.get('siblings',[]):
    if s['rfilename'].endswith('.gguf'): print(s['rfilename'], s.get('size'), (s.get('lfs') or {}).get('sha256'))
" 2>&1 | head -30
done
echo "== llama.cpp latest"
curl -s https://api.github.com/repos/ggml-org/llama.cpp/releases/latest | python3 -c "
import sys,json; d=json.load(sys.stdin); print(d['tag_name'])
[print(a['name'], a['size'], a.get('digest')) for a in d['assets'] if 'ubuntu' in a['name'] or 'linux' in a['name']]"
exit 0
