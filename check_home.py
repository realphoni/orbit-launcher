"""Exercise queue, hiding, preferences and backups through the real bridge."""
import json
from pathlib import Path
import tempfile
from PySide6 import QtWidgets, QtWebEngineWidgets
from PySide6.QtCore import QTimer
import launcher

temp=tempfile.TemporaryDirectory(dir=launcher.BASE)
launcher.DATA=Path(temp.name)
backup=launcher.DATA/'backup.json'
QtWidgets.QFileDialog.getSaveFileName=lambda *a,**kw:(str(backup),'')
QtWidgets.QFileDialog.getOpenFileName=lambda *a,**kw:(str(backup),'')
view=None
results={}
OriginalView=QtWebEngineWidgets.QWebEngineView
class View(OriginalView):
    def __init__(self,*a,**kw):
        global view
        super().__init__(*a,**kw)
        view=self
QtWebEngineWidgets.QWebEngineView=View
OriginalApp=QtWidgets.QApplication
class App(OriginalApp):
    def exec(self):
        QTimer.singleShot(8000,begin)
        QTimer.singleShot(25000,lambda:self.exit(2))
        return super().exec()
QtWidgets.QApplication=App
def js(code,callback=None):view.page().runJavaScript(code,callback or (lambda v:None))
def begin():
    js("window.qaIds=data.games.slice(0,2).map(g=>g.id);window.qaHome=tab==='home'&&document.querySelectorAll('.home-card').length>0;api.libraryAction(qaIds[0],'queue');api.libraryAction(qaIds[1],'queue');api.coverSize('large')")
    QTimer.singleShot(800,reorder)
def reorder():
    js("api.libraryAction(qaIds[1],'first');api.libraryAction(qaIds[0],'hide')")
    QTimer.singleShot(800,verify_hidden)
def verify_hidden():
    js("""JSON.stringify((()=>{goTab('all');const excluded=!filtered.some(g=>g.id===qaIds[0]);goTab('hidden');const hidden=filtered.some(g=>g.id===qaIds[0]);return {home:qaHome,excluded,hidden,queue:data.settings.queue[0]===qaIds[1],cover:document.documentElement.dataset.covers==='large'}})())""",lambda value:results.update(json.loads(value)))
    js("api.exportBackup()")
    QTimer.singleShot(800,change)
def change():
    results['export']=backup.exists()
    js("api.libraryAction(qaIds[0],'hide');api.libraryAction(qaIds[0],'queue');api.coverSize('small')")
    QTimer.singleShot(800,restore)
def restore():
    js("api.importBackup()")
    QTimer.singleShot(800,verify_restore)
def verify_restore():
    js("JSON.stringify({restored:data.settings.hidden.includes(qaIds[0])&&data.settings.queue.includes(qaIds[0])&&data.settings.coverSize==='large'})",lambda value:results.update(json.loads(value)))
    js("goTab('home')")
    QTimer.singleShot(800,finish)
def finish():
    results['safetyBackup']=(launcher.DATA/'settings-before-restore.json').exists()
    results['persisted']=launcher.load_settings().get('coverSize')=='large'
    view.grab().save(str(launcher.BASE/'home-preview.png'))
    print(json.dumps(results),flush=True)
    QtWidgets.QApplication.instance().exit(0 if results and all(results.values()) else 1)
try:launcher.main()
finally:temp.cleanup()
