from .ui import HTML as BASE_HTML

TOGGLE='''<a href="/" aria-label="Open business dashboard" style="position:fixed;top:16px;right:16px;z-index:9999;text-decoration:none;border:1px solid #315779;background:rgba(10,23,40,.96);color:#eef6ff;padding:11px 15px;border-radius:12px;font:800 14px system-ui,-apple-system,sans-serif;box-shadow:0 10px 28px rgba(0,0,0,.28);backdrop-filter:blur(10px)">← Dashboard</a>'''

# Keep the existing Jarvis voice UI untouched and add a permanent one-click
# return to the Panther Peptides operating dashboard.
HTML=BASE_HTML.replace('<body>','<body>'+TOGGLE,1)
