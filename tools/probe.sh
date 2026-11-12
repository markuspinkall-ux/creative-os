#!/bin/bash
set +e
curl -s "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=8" | python3 -c "
import sys,json
for d in json.load(sys.stdin):
    print('##', d['tag_name'], d['published_at'], d.get('prerelease'))
    for a in d['assets']:
        n=a['name']
        if any(k in n for k in ('ubuntu','linux')): print('  ', n, a['size'], a.get('digest'))
"
exit 0
