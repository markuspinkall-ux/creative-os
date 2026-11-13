#!/bin/bash
# Suche: leichtes 2x-Upscaling-Modell (Webcam) mit freier Lizenz
set +e
dnf install -y -q curl jq python3 >/dev/null 2>&1
for p in 1 2 3; do
  curl -fsSL "https://api.github.com/repos/Phhofm/models/releases?per_page=100&page=$p" \
   | jq -r '.[]|select(.tag_name|test("^2x";"i"))|.tag_name+" | "+([.assets[]|.name+" ("+(.size|tostring)+") "+.browser_download_url]|join(" ; "))'
done | grep -i -E "span|compact|esrgan" | head -60
echo "---- HF"
curl -fsSL "https://huggingface.co/api/models?search=NomosUni&limit=50" | jq -r '.[].id'
curl -fsSL "https://huggingface.co/api/models?search=span_multijpg&limit=50" | jq -r '.[].id'
echo "---- xinntao"
curl -fsSL "https://api.github.com/repos/xinntao/Real-ESRGAN/releases?per_page=30" | jq -r '.[]|.tag_name+" | "+([.assets[]|.name]|join(", "))'
exit 0
