#!/bin/bash
set +e
dnf install -y -q python3 >/dev/null 2>&1
curl -sL https://huggingface.co/microsoft/TRELLIS.2-4B/resolve/main/pipeline.json; echo
for r in microsoft/TRELLIS.2-4B microsoft/TRELLIS-image-large facebook/dinov3-vitl16-pretrain-lvd1689m briaai/RMBG-2.0 ZhengPeng7/BiRefNet; do
  echo "== $r"; curl -s "https://huggingface.co/api/models/$r?blobs=true" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print('gated',d.get('gated'),'license',[t for t in d.get('tags',[]) if t.startswith('license')], 'error', d.get('error'))
tot=0
for s in d.get('siblings',[]):
    tot+=s.get('size') or 0
    if (s.get('size') or 0) > 5e7: print('  ',s['rfilename'], round((s.get('size') or 0)/1e9,2),'GB')
print('  gesamt', round(tot/1e9,2),'GB')
" 2>&1 | head -30
done
exit 0
