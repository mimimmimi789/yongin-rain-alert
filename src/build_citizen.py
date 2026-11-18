# citizen_script.js + citizen_theme.css -> citizen3d_template.html, data3d.json 주입 -> citizen3d.html (artifact) / site/index.html (GitHub Pages)
import re
t=open('citizen3d_template.html',encoding='utf-8').read()
js=open('citizen_script.js',encoding='utf-8').read()
css=open('citizen_theme.css',encoding='utf-8').read()
i=t.rfind('<script>');j=t.rfind('</script>')
t=t[:i+8]+js+t[j:]
A,B='/*THEME-START*/','/*THEME-END*/'
if A in t: t=re.sub(re.escape(A)+'.*?'+re.escape(B),lambda m:A+css+B,t,flags=re.S)
else:
    k=t.find('</style>'); t=t[:k]+A+css+B+'\n'+t[k:]
open('citizen3d_template.html','w',encoding='utf-8').write(t)
page=t.replace('__DATA__',open('data3d.json',encoding='utf-8').read(),1)
open('citizen3d.html','w',encoding='utf-8').write(page)
b=page.find('<div class="app">')
site=('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
      '<meta name="description" content="용인시 38개 읍면동 호우 위험 단계와 빗물 흐름을 기상청 예보로 보여주는 지도">\n'
      '<style>html,body{margin:0}</style>\n'+page[:b]+'\n</head>\n<body>\n'+page[b:]+'\n</body>\n</html>\n')
open('site_index.html','w',encoding='utf-8').write(site)
print('ok')
