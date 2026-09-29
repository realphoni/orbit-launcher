"""Exercise the real bridge using isolated settings; never launches a game."""
import json
from pathlib import Path
import tempfile
from PySide6 import QtWidgets, QtWebEngineWidgets
from PySide6.QtCore import QTimer
import launcher

test_dir=tempfile.TemporaryDirectory(dir=launcher.BASE)
launcher.DATA=Path(test_dir.name)
launcher.fetch_reviews=lambda appid: dict(percent=88,label='Very Positive',total=100,positive=88,negative=12,fetched=1780000000)
view=None
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
        QTimer.singleShot(8000,edit)
        QTimer.singleShot(25000,lambda:self.exit(2))
        return super().exec()
QtWidgets.QApplication=App
def edit():
    view.page().runJavaScript("""(()=>{const g=data.games.find(g=>g.source==='Steam');selectGame(g);details();document.querySelector('[data-rating="4"]').click();$('game-progress').value='Completed';$('game-collections').value='Weekend, Co-op';$('game-notes').value='Saved through the actual desktop bridge';$('save-profile').click();$('load-reviews').click()})()""")
    QTimer.singleShot(2200,verify)
def verify():
    script="""(()=>{const p=profile(selected);const saved=p.rating===4&&p.status==='Completed'&&p.notes.includes('actual desktop bridge');const reviews=$('review-summary').textContent.includes('88%');$('dialog').close();$('collection-filter').value='Weekend';$('progress-filter').value='Completed';render();const filters=filtered.length===1;const id=selected.id;$('sort').value='rating';render();const sorted=filtered[0]?.id===id;$('surprise').click();return JSON.stringify({saved,reviews,filters,sorted,details:$('dialog').open,cards:data.games.length})})()"""
    view.page().runJavaScript(script,report)
def report(raw):
    result=json.loads(raw or '{}')
    persisted=launcher.load_settings().get('profiles',{})
    result['persisted']=any(p['rating']==4 for p in persisted.values())
    print(json.dumps(result),flush=True)
    def finish():
        view.grab().save(str(launcher.BASE/'features-preview.png'))
        QtWidgets.QApplication.instance().exit(0 if all(result.get(k) for k in ['saved','reviews','filters','sorted','details','persisted']) else 1)
    QTimer.singleShot(700,finish)
try: launcher.main()
finally: test_dir.cleanup()
