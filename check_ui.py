"""Render the real library for local visual verification without launching games."""
import json
from pathlib import Path
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage

base = Path(__file__).parent
app = QApplication([])
view = QWebEngineView()
class Page(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        print(f'JS {line}: {message}', flush=True)
view.setPage(Page(view))
view.resize(1600, 1000)
data = (base / 'data/library.json').read_text()
def loaded(ok):
    if not ok: raise RuntimeError('Page did not load')
    view.page().runJavaScript('accept(' + json.dumps(data) + ')')
    QTimer.singleShot(1800, check)
def check():
    script = """(()=>{const total=document.querySelectorAll('.card').length; $('search').value='Portal';render(); const search=filtered.every(g=>g.name.toLowerCase().includes('portal'))&&filtered.length>0;$('search').value='';render();let id=selected.id;data.settings.favorites=[id];tab='favorites';render();const favorites=filtered.length===1&&filtered[0].id===id;tab='all';data.settings.favorites=[];render();details();const dialog=$('dialog').open;$('dialog').close();openSettings(); const settingsScan=!!$('scan-games'); const themeCount=document.querySelectorAll('.theme-choice').length; let savedTheme=''; let scanCalls=0; api={theme:n=>savedTheme=n,refresh:()=>scanCalls++}; document.querySelector('[data-theme=violet].theme-choice').click(); const theme=savedTheme==='violet'&&document.documentElement.dataset.theme==='violet'; $('scan-games').click(); $('scan-games').click(); const scanBusy=scanning&&$('scan-games').disabled&&scanCalls===1; finishScan(data); const scanDone=!scanning&&!$('scan-games').disabled&&$('scan-result').textContent.includes('Scan complete'); return {settingsScan,themeCount,theme,scanBusy,scanDone,total,search,favorites,dialog,drives:document.querySelectorAll('.drive').length,title:$('hero-title').textContent}})()"""
    view.page().runJavaScript('JSON.stringify(' + script + ')', result)
def result(value):
    value = json.loads(value) if value else None
    print(json.dumps(value), flush=True)
    view.grab().save(str(base / 'preview.png'))
    app.exit(0 if value and value['total'] > 0 and value['search'] and value['favorites'] and value['dialog'] and value['settingsScan'] and value['themeCount'] == 4 and value['theme'] and value['scanBusy'] and value['scanDone'] else 1)
view.loadFinished.connect(loaded)
view.load(QUrl.fromLocalFile(str(base / 'index.html')))
view.show()
QTimer.singleShot(20000, lambda: app.exit(2))
raise SystemExit(app.exec())
